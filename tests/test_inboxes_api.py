from __future__ import annotations

import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app.db.models import Client, ClientUser
import app.integrations.gmail as gmail_integration
from app.inboxes.models import Inbox
from app.inboxes import service as inbox_service
from app.security.passwords import hash_password
from app.utils.crypto import decrypt_secret


def _auth_headers(client, test_db, tenant: Client) -> dict[str, str]:
    password = "InboxPass123!"
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=tenant.id,
        email=f"owner-{tenant.id.hex[:8]}@example.com",
        password_hash=hash_password(password),
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(user)
    test_db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_inboxes_list_is_scoped_to_current_tenant(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    other_tenant = Client(
        id=uuid.uuid4(),
        name="Other Company",
        api_key="other-api-key",
        plan_id="starter",
        plan="starter",
        monthly_ticket_limit=100,
    )
    test_db.add(other_tenant)
    test_db.flush()

    owned_inbox = Inbox(
        tenant_id=test_client_record.id,
        email_address="support@test-company.com",
        provider_type="gmail",
        is_active=True,
    )
    foreign_inbox = Inbox(
        tenant_id=other_tenant.id,
        email_address="support@other-company.com",
        provider_type="imap",
        is_active=True,
    )
    test_db.add_all([owned_inbox, foreign_inbox])
    test_db.commit()

    response = client.get("/inboxes", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "support@test-company.com"
    assert body[0]["provider"] == "gmail"
    assert "access_token" not in body[0]
    assert "refresh_token" not in body[0]
    assert "imap_password" not in body[0]


def test_connect_imap_validates_and_encrypts_password(monkeypatch, test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    called = {}

    def fake_test_imap_connection(*, imap_host: str, imap_port: int, username: str, password: str) -> None:
        called["args"] = {
            "imap_host": imap_host,
            "imap_port": imap_port,
            "username": username,
            "password": password,
        }

    monkeypatch.setattr(inbox_service, "test_imap_connection", fake_test_imap_connection)

    response = client.post(
        "/inboxes/connect-imap",
        headers=headers,
        json={
            "email": "support@example.com",
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "username": "support-user",
            "password": "super-secret",
        },
    )

    assert response.status_code == 200
    assert called["args"]["imap_host"] == "imap.example.com"
    assert called["args"]["imap_port"] == 993
    assert response.json()["provider"] == "imap"
    assert response.json()["status"] == "active"

    saved_inbox = (
        test_db.query(Inbox)
        .filter(Inbox.tenant_id == test_client_record.id, Inbox.email_address == "support@example.com")
        .first()
    )
    assert saved_inbox is not None
    assert saved_inbox.provider_type == "imap"
    assert saved_inbox.imap_password != "super-secret"
    assert decrypt_secret(saved_inbox.imap_password) == "super-secret"


def test_connect_imap_returns_error_when_validation_fails(monkeypatch, test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    def fake_test_imap_connection(**_kwargs) -> None:
        raise inbox_service.HTTPException(status_code=400, detail="Unable to connect to the IMAP server")

    monkeypatch.setattr(inbox_service, "test_imap_connection", fake_test_imap_connection)

    response = client.post(
        "/inboxes/connect-imap",
        headers=headers,
        json={
            "email": "support@example.com",
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "username": "support-user",
            "password": "bad-password",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unable to connect to the IMAP server"


def test_gmail_oauth_flow_stores_inbox_and_redirects(monkeypatch, test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    monkeypatch.setattr(inbox_service.settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(inbox_service.settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(inbox_service.settings, "google_oauth_redirect_uri", "http://testserver/auth/gmail/callback")
    monkeypatch.setattr(inbox_service, "exchange_google_code", lambda _code: {
        "access_token": "gmail-access-token",
        "refresh_token": "gmail-refresh-token",
        "expires_in": 3600,
    })
    monkeypatch.setattr(inbox_service, "fetch_google_user_email", lambda _token: "owner@example.com")

    connect_url_response = client.get("/inboxes/gmail/connect-url", headers=headers)
    assert connect_url_response.status_code == 200

    oauth_redirect = client.get(connect_url_response.json()["connect_url"], follow_redirects=False)
    assert oauth_redirect.status_code == 307
    google_url = oauth_redirect.headers["location"]
    parsed_google_url = urlparse(google_url)
    state = parse_qs(parsed_google_url.query)["state"][0]

    callback_response = client.get(
        f"/auth/gmail/callback?code=test-oauth-code&state={state}",
        follow_redirects=False,
    )

    assert callback_response.status_code == 307
    assert callback_response.headers["location"] == "/settings?gmail_connected=true"

    saved_inbox = (
        test_db.query(Inbox)
        .filter(Inbox.tenant_id == test_client_record.id, Inbox.email_address == "owner@example.com")
        .first()
    )
    assert saved_inbox is not None
    assert saved_inbox.provider_type == "gmail"
    assert decrypt_secret(saved_inbox.access_token) == "gmail-access-token"
    assert decrypt_secret(saved_inbox.refresh_token) == "gmail-refresh-token"


def test_inboxes_gmail_connect_derives_redirect_uri_from_app_base_url(monkeypatch, test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    monkeypatch.setattr(inbox_service.settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(inbox_service.settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(inbox_service.settings, "google_oauth_redirect_uri", "")
    monkeypatch.setattr(inbox_service.settings, "google_redirect_uri", "")
    monkeypatch.setattr(inbox_service.settings, "google_inboxes_oauth_redirect_uri", "")
    monkeypatch.setattr(inbox_service.settings, "app_base_url", "http://testserver")

    connect_url_response = client.get("/inboxes/gmail/connect-url", headers=headers)
    assert connect_url_response.status_code == 200

    oauth_redirect = client.get(connect_url_response.json()["connect_url"], follow_redirects=False)
    assert oauth_redirect.status_code == 307
    google_url = urlparse(oauth_redirect.headers["location"])
    query = parse_qs(google_url.query)

    assert query["redirect_uri"] == ["http://testserver/auth/gmail/callback"]


def test_integrations_gmail_connect_derives_redirect_uri_from_app_base_url(monkeypatch, test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    monkeypatch.setattr(gmail_integration.settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(gmail_integration.settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(gmail_integration.settings, "google_oauth_redirect_uri", "")
    monkeypatch.setattr(gmail_integration.settings, "google_redirect_uri", "")
    monkeypatch.setattr(gmail_integration.settings, "google_integrations_oauth_redirect_uri", "")
    monkeypatch.setattr(gmail_integration.settings, "app_base_url", "http://testserver")
    monkeypatch.setattr(gmail_integration.settings, "gmail_pubsub_topic", "projects/test/topics/gmail")

    response = client.get("/integrations/gmail/connect", headers=headers)

    assert response.status_code == 200
    google_url = urlparse(response.json()["auth_url"])
    query = parse_qs(google_url.query)

    assert query["redirect_uri"] == ["http://testserver/integrations/gmail/callback"]


def test_integrations_gmail_connect_reports_missing_pubsub_topic(monkeypatch, test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)

    monkeypatch.setattr(gmail_integration.settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(gmail_integration.settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(gmail_integration.settings, "google_oauth_redirect_uri", "")
    monkeypatch.setattr(gmail_integration.settings, "google_redirect_uri", "")
    monkeypatch.setattr(gmail_integration.settings, "google_integrations_oauth_redirect_uri", "")
    monkeypatch.setattr(gmail_integration.settings, "app_base_url", "http://testserver")
    monkeypatch.setattr(gmail_integration.settings, "gmail_pubsub_topic", "")

    response = client.get("/integrations/gmail/connect", headers=headers)

    assert response.status_code == 500
    assert "GMAIL_PUBSUB_TOPIC" in response.json()["detail"]

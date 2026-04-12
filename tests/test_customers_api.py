import uuid
from datetime import datetime, timezone

from app.db.models import Complaint, Customer
from app.services.customer_profile import CustomerProfileService


def test_customer_list_and_360_endpoint(test_db, client, test_client_record):
    test_client_record.plan_id = "pro"
    test_client_record.plan = "pro"
    test_db.commit()

    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Customer 360 ticket",
        source="api",
        customer_email="owner@example.com",
        category="support",
        sentiment=-0.1,
        priority=2,
        ticket_id="TKT-360",
        thread_id="TH-360",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(complaint)
    test_db.commit()

    customer = CustomerProfileService(test_db).sync_customer_for_complaint(complaint, commit=True)

    list_response = client.get(
        "/api/v1/customers",
        headers={"x-api-key": test_client_record.api_key},
    )
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["id"] == str(customer.id)

    detail_response = client.get(
        f"/api/v1/customers/{customer.id}",
        headers={"x-api-key": test_client_record.api_key},
    )
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["profile"]["primary_email"] == "owner@example.com"
    assert len(detail_body["recent_tickets"]) == 1
    assert len(detail_body["interaction_timeline"]) == 1

    snapshot_response = client.get(
        f"/api/v1/customers/{customer.id}/360",
        headers={"x-api-key": test_client_record.api_key},
    )
    assert snapshot_response.status_code == 200
    snapshot_body = snapshot_response.json()
    assert snapshot_body["identity"]["primary_email"] == "owner@example.com"
    assert snapshot_body["metrics"]["total_tickets"] == 1
    assert snapshot_body["churn_risk"] in {"low", "medium", "high"}


def test_customer_duplicates_and_merge_endpoint(test_db, client, test_client_record):
    test_client_record.plan_id = "pro"
    test_client_record.plan = "pro"
    test_db.commit()

    first = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="john@acme.com",
        emails=["john@acme.com"],
        full_name="John Smith",
    )
    second = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="jon@acme.com",
        emails=["jon@acme.com"],
        full_name="Jon Smith",
    )
    test_db.add_all([first, second])
    test_db.commit()

    duplicates_response = client.get(
        f"/api/v1/customers/{second.id}/duplicates",
        headers={"x-api-key": test_client_record.api_key},
    )
    assert duplicates_response.status_code == 200
    duplicates_body = duplicates_response.json()
    assert duplicates_body["potential_duplicates"]
    assert duplicates_body["potential_duplicates"][0]["customer"]["id"] == str(first.id)

    merge_response = client.post(
        "/api/v1/customers/merge",
        json={
            "master_customer_id": str(first.id),
            "duplicate_customer_id": str(second.id),
        },
        headers={"x-api-key": test_client_record.api_key},
    )
    assert merge_response.status_code == 200
    merge_body = merge_response.json()
    assert merge_body["success"] is True
    assert merge_body["master_customer"]["id"] == str(first.id)


def test_customer_notes_and_relationships_endpoints(test_db, client, test_client_record):
    test_client_record.plan_id = "pro"
    test_client_record.plan = "pro"
    test_db.commit()

    parent = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="parent@example.com",
        emails=["parent@example.com"],
        full_name="Parent",
    )
    child = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="child@example.com",
        emails=["child@example.com"],
        full_name="Child",
    )
    test_db.add_all([parent, child])
    test_db.commit()

    note_response = client.post(
        f"/api/v1/customers/{parent.id}/notes",
        json={"content": "VIP customer", "note_type": "vip", "pinned": True},
        headers={"x-api-key": test_client_record.api_key},
    )
    assert note_response.status_code == 200
    assert note_response.json()["note"]["pinned"] is True

    relationship_response = client.post(
        f"/api/v1/customers/{parent.id}/relationships",
        json={
            "child_customer_id": str(child.id),
            "relationship_type": "employee",
            "role_title": "Finance Lead",
            "is_primary_contact": True,
        },
        headers={"x-api-key": test_client_record.api_key},
    )
    assert relationship_response.status_code == 200
    relationship_body = relationship_response.json()
    assert relationship_body["relationship"]["child_customer_id"] == str(child.id)

    list_relationships = client.get(
        f"/api/v1/customers/{parent.id}/relationships",
        headers={"x-api-key": test_client_record.api_key},
    )
    assert list_relationships.status_code == 200
    assert len(list_relationships.json()["items"]) == 1


def test_customer_update_endpoint_supports_tags_and_notes(test_db, client, test_client_record):
    test_client_record.plan_id = "pro"
    test_client_record.plan = "pro"
    test_db.commit()

    customer = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="vip@example.com",
        emails=["vip@example.com"],
        full_name="VIP Customer",
    )
    test_db.add(customer)
    test_db.commit()

    response = client.patch(
        f"/api/v1/customers/{customer.id}",
        json={"tags": ["VIP", "risky"], "notes": "Retention watch", "name": "VIP Customer"},
        headers={"x-api-key": test_client_record.api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["customer"]["tags"] == ["VIP", "risky"]
    assert body["customer"]["notes"] == "Retention watch"
    assert body["customer"]["name"] == "VIP Customer"

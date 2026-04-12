import uuid
from datetime import datetime, timezone

from app.db.models import ClientUser, Complaint, Team, TeamMember
from app.security.passwords import hash_password


def _auth_headers(client, test_db, tenant) -> dict[str, str]:
    password = "TeamsPass123!"
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=tenant.id,
        email=f"teams-{tenant.id.hex[:8]}@example.com",
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_teams_crud_and_member_management_endpoints(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        email="agent@example.com",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(user)
    test_db.commit()

    create_response = client.post(
        "/api/v1/teams",
        headers=headers,
        json={"name": "Support"},
    )
    assert create_response.status_code == 201
    team_id = create_response.json()["team"]["id"]

    list_response = client.get("/api/v1/teams", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["name"] == "Support"

    add_member_response = client.post(
        f"/api/v1/teams/{team_id}/members",
        headers=headers,
        json={"user_id": str(user.id), "role": "agent", "capacity": 7},
    )
    assert add_member_response.status_code == 201
    member_id = add_member_response.json()["member"]["id"]
    assert add_member_response.json()["member"]["capacity"] == 7

    members_response = client.get(f"/api/v1/teams/{team_id}/members", headers=headers)
    assert members_response.status_code == 200
    assert len(members_response.json()["items"]) == 1
    assert members_response.json()["items"][0]["email"] == "agent@example.com"

    update_member_response = client.patch(
        f"/api/v1/team-members/{member_id}",
        headers=headers,
        json={"role": "manager", "capacity": 9, "is_active": False},
    )
    assert update_member_response.status_code == 200
    member_payload = update_member_response.json()["member"]
    assert member_payload["role"] == "manager"
    assert member_payload["capacity"] == 9
    assert member_payload["is_active"] is False


def test_assignment_dashboard_endpoint_returns_teams_and_active_tickets(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        email="dashboard-agent@example.com",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
    )
    team = Team(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        name="Support",
    )
    member = TeamMember(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=user.id,
        role="agent",
        capacity=5,
        active_tasks=2,
        is_active=True,
    )
    ticket = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Need help with a chargeback",
        category="billing",
        sentiment=-0.2,
        priority=3,
        ticket_id="TKT-DASH-1",
        ticket_number="TKT-DASH-1",
        thread_id="TH-DASH-1",
        created_at=datetime.now(timezone.utc),
        state="assigned",
        status="IN_PROGRESS",
        resolution_status="open",
        team_id=team.id,
        assigned_team=team.name,
        assigned_user_id=user.id,
        assigned_to=user.email,
    )
    resolved_ticket = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Already solved",
        category="support",
        sentiment=0.0,
        priority=1,
        ticket_id="TKT-DASH-2",
        ticket_number="TKT-DASH-2",
        thread_id="TH-DASH-2",
        created_at=datetime.now(timezone.utc),
        state="resolved",
        status="RESOLVED",
        resolution_status="resolved",
    )
    test_db.add_all([user, team, member, ticket, resolved_ticket])
    test_db.commit()

    response = client.get("/api/v1/dashboard/assignments", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["teams"]) == 1
    assert payload["teams"][0]["name"] == "Support"
    assert payload["teams"][0]["members"][0]["active_tasks"] == 2
    assert len(payload["tickets"]) == 1
    assert payload["tickets"][0]["subject"] == "Need help with a chargeback"
    assert payload["tickets"][0]["priority"] == "high"
    assert payload["tickets"][0]["team_id"] == str(team.id)


def test_manual_ticket_reassign_updates_workload_counts(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    source_user = ClientUser(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        email="source-agent@example.com",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
    )
    target_user = ClientUser(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        email="target-agent@example.com",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
    )
    team = Team(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        name="Operations",
    )
    source_member = TeamMember(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=source_user.id,
        role="agent",
        capacity=5,
        active_tasks=2,
        is_active=True,
    )
    target_member = TeamMember(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=target_user.id,
        role="agent",
        capacity=5,
        active_tasks=1,
        is_active=True,
    )
    ticket = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Reassign this ticket",
        category="support",
        sentiment=0.0,
        priority=2,
        ticket_id="TKT-REALLOCATE",
        ticket_number="TKT-REALLOCATE",
        thread_id="TH-REALLOCATE",
        created_at=datetime.now(timezone.utc),
        state="assigned",
        status="IN_PROGRESS",
        resolution_status="open",
        team_id=team.id,
        assigned_team=team.name,
        assigned_user_id=source_user.id,
        assigned_to=source_user.email,
    )
    test_db.add_all([source_user, target_user, team, source_member, target_member, ticket])
    test_db.commit()

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}/assign",
        headers=headers,
        json={"user_id": str(target_user.id)},
    )

    assert response.status_code == 200
    test_db.refresh(ticket)
    test_db.refresh(source_member)
    test_db.refresh(target_member)
    assert ticket.assigned_user_id == target_user.id
    assert ticket.assigned_to == "target-agent@example.com"
    assert source_member.active_tasks == 1
    assert target_member.active_tasks == 2

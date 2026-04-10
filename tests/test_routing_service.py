import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import ClientUser, Complaint, RoutingRule, Team, TeamMember, TicketAssignment
from app.services.routing_service import RoutingService
from app.services.ticket_state_machine import TicketStateMachine


def _create_user(test_db, client_id, email: str) -> ClientUser:
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=client_id,
        email=email,
        password_hash="hash",
    )
    test_db.add(user)
    return user


def _create_team(test_db, client_id, name: str) -> Team:
    team = Team(
        id=uuid.uuid4(),
        client_id=client_id,
        name=name,
    )
    test_db.add(team)
    return team


def _create_member(
    test_db,
    *,
    client_id,
    team_id,
    user_id,
    role: str = "agent",
    capacity: int = 10,
    active_tasks: int = 0,
    updated_at: datetime | None = None,
) -> TeamMember:
    member = TeamMember(
        id=uuid.uuid4(),
        client_id=client_id,
        team_id=team_id,
        user_id=user_id,
        role=role,
        capacity=capacity,
        active_tasks=active_tasks,
        is_active=True,
        updated_at=updated_at or datetime.now(timezone.utc),
    )
    test_db.add(member)
    return member


def _create_complaint(test_db, client_id, category: str, priority: int = 2) -> Complaint:
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=client_id,
        summary=f"{category} ticket",
        category=category,
        sentiment=0.0,
        priority=priority,
        ticket_id=f"TKT-{str(uuid.uuid4())[:8]}",
        thread_id=f"TH-{str(uuid.uuid4())[:8]}",
        state="new",
        status="AUTO_REPLY",
        resolution_status="open",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(complaint)
    test_db.flush()
    return complaint


def test_route_ticket_uses_routing_rule_and_least_loaded_agent(test_db, test_client_record):
    user_one = _create_user(test_db, test_client_record.id, "agent-one@example.com")
    user_two = _create_user(test_db, test_client_record.id, "agent-two@example.com")
    team = _create_team(test_db, test_client_record.id, "refund")
    older_time = datetime.now(timezone.utc) - timedelta(hours=2)
    newer_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    member_one = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=user_one.id,
        active_tasks=3,
        updated_at=newer_time,
    )
    member_two = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=user_two.id,
        active_tasks=1,
        updated_at=older_time,
    )
    test_db.add(
        RoutingRule(
            id=uuid.uuid4(),
            client_id=test_client_record.id,
            category="refund",
            team_id=team.id,
        )
    )
    complaint = _create_complaint(test_db, test_client_record.id, "refund")
    test_db.commit()

    result = RoutingService(test_db).route_ticket(
        complaint,
        {"category": "refund", "priority": 2, "intent": "complaint"},
        commit=False,
    )
    test_db.commit()
    test_db.refresh(member_one)
    test_db.refresh(member_two)

    assert result.team_id == team.id
    assert result.assigned_user_id == user_two.id
    assert complaint.team_id == team.id
    assert complaint.assigned_team == "refund"
    assert complaint.assigned_user_id == user_two.id
    assert complaint.assigned_to == "agent-two@example.com"
    assert member_one.active_tasks == 3
    assert member_two.active_tasks == 2
    assert (
        test_db.query(TicketAssignment)
        .filter(
            TicketAssignment.complaint_id == complaint.id,
            TicketAssignment.unassigned_at.is_(None),
            TicketAssignment.assigned_to == "agent-two@example.com",
        )
        .count()
        == 1
    )


def test_select_assignee_breaks_ties_by_oldest_updated_at(test_db, test_client_record):
    first_user = _create_user(test_db, test_client_record.id, "older@example.com")
    second_user = _create_user(test_db, test_client_record.id, "newer@example.com")
    team = _create_team(test_db, test_client_record.id, "sales")
    older_time = datetime.now(timezone.utc) - timedelta(hours=3)
    newer_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    older_member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=first_user.id,
        active_tasks=1,
        updated_at=older_time,
    )
    newer_member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=second_user.id,
        active_tasks=1,
        updated_at=newer_time,
    )
    test_db.commit()

    selected = RoutingService(test_db).select_assignee(team.id, priority=2)

    assert selected is not None
    assert selected.id == older_member.id
    assert selected.id != newer_member.id


def test_route_ticket_falls_back_to_support_team_without_rule(test_db, test_client_record):
    support_user = _create_user(test_db, test_client_record.id, "support@example.com")
    support_team = _create_team(test_db, test_client_record.id, "support")
    support_member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=support_team.id,
        user_id=support_user.id,
        active_tasks=0,
    )
    complaint = _create_complaint(test_db, test_client_record.id, "complaint")
    test_db.commit()

    result = RoutingService(test_db).route_ticket(
        complaint,
        {"category": "complaint", "priority": 2, "intent": "complaint"},
        commit=False,
    )
    test_db.commit()
    test_db.refresh(support_member)

    assert result.team_id == support_team.id
    assert complaint.team_id == support_team.id
    assert complaint.assigned_team == "support"
    assert complaint.assigned_user_id == support_user.id
    assert support_member.active_tasks == 1


def test_route_ticket_falls_back_to_manager_when_agents_are_full(test_db, test_client_record):
    agent_user = _create_user(test_db, test_client_record.id, "agent@example.com")
    manager_user = _create_user(test_db, test_client_record.id, "manager@example.com")
    team = _create_team(test_db, test_client_record.id, "support")
    _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=agent_user.id,
        role="agent",
        capacity=1,
        active_tasks=1,
    )
    manager_member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=manager_user.id,
        role="manager",
        capacity=1,
        active_tasks=1,
    )
    complaint = _create_complaint(test_db, test_client_record.id, "support")
    test_db.commit()

    result = RoutingService(test_db).route_ticket(
        complaint,
        {"category": "support", "priority": 2, "intent": "complaint"},
        commit=False,
    )
    test_db.commit()
    test_db.refresh(manager_member)

    assert result.assigned_user_id == manager_user.id
    assert complaint.assigned_user_id == manager_user.id
    assert complaint.assigned_to == "manager@example.com"
    assert manager_member.active_tasks == 2


def test_high_priority_ticket_prefers_manager_before_agents(test_db, test_client_record):
    manager_user = _create_user(test_db, test_client_record.id, "priority-manager@example.com")
    agent_user = _create_user(test_db, test_client_record.id, "priority-agent@example.com")
    team = _create_team(test_db, test_client_record.id, "billing")
    manager_member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=manager_user.id,
        role="manager",
        capacity=5,
        active_tasks=1,
    )
    _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=agent_user.id,
        role="agent",
        capacity=20,
        active_tasks=0,
    )
    test_db.add(
        RoutingRule(
            id=uuid.uuid4(),
            client_id=test_client_record.id,
            category="billing",
            team_id=team.id,
        )
    )
    complaint = _create_complaint(test_db, test_client_record.id, "billing", priority=4)
    test_db.commit()

    result = RoutingService(test_db).route_ticket(
        complaint,
        {"category": "billing", "priority": "high", "intent": "complaint"},
        commit=False,
    )
    test_db.commit()
    test_db.refresh(manager_member)

    assert result.assigned_user_id == manager_user.id
    assert complaint.assigned_user_id == manager_user.id
    assert complaint.assigned_to == "priority-manager@example.com"
    assert manager_member.active_tasks == 2


def test_high_priority_ticket_uses_highest_capacity_agent_without_manager(test_db, test_client_record):
    low_capacity_user = _create_user(test_db, test_client_record.id, "small-capacity@example.com")
    high_capacity_user = _create_user(test_db, test_client_record.id, "large-capacity@example.com")
    team = _create_team(test_db, test_client_record.id, "complaint")
    _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=low_capacity_user.id,
        role="agent",
        capacity=5,
        active_tasks=0,
    )
    high_capacity_member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=high_capacity_user.id,
        role="agent",
        capacity=25,
        active_tasks=2,
    )
    complaint = _create_complaint(test_db, test_client_record.id, "complaint", priority=4)
    test_db.commit()

    result = RoutingService(test_db).route_ticket(
        complaint,
        {"category": "complaint", "priority": "high", "intent": "complaint"},
        commit=False,
    )
    test_db.commit()
    test_db.refresh(high_capacity_member)

    assert result.assigned_user_id == high_capacity_user.id
    assert complaint.assigned_user_id == high_capacity_user.id
    assert complaint.assigned_to == "large-capacity@example.com"
    assert high_capacity_member.active_tasks == 3


def test_workload_released_on_resolve_and_restored_on_reopen(test_db, test_client_record):
    user = _create_user(test_db, test_client_record.id, "closer@example.com")
    team = _create_team(test_db, test_client_record.id, "support")
    member = _create_member(
        test_db,
        client_id=test_client_record.id,
        team_id=team.id,
        user_id=user.id,
        active_tasks=1,
    )
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Workload release test",
        category="support",
        sentiment=0.0,
        priority=2,
        ticket_id="TKT-WORKLOAD",
        ticket_number="TKT-WORKLOAD",
        thread_id="TH-WORKLOAD",
        created_at=datetime.now(timezone.utc),
        state="in_progress",
        status="IN_PROGRESS",
        resolution_status="open",
        team_id=team.id,
        assigned_team=team.name,
        assigned_user_id=user.id,
        assigned_to=user.email,
    )
    test_db.add(complaint)
    test_db.commit()

    state_machine = TicketStateMachine(test_db)
    success, error = state_machine.transition(
        complaint,
        "resolved",
        "tester@example.com",
        reason="unit test resolve",
        commit=False,
    )
    assert success is True
    assert error is None
    test_db.commit()
    test_db.refresh(member)
    assert member.active_tasks == 0

    success, error = state_machine.transition(
        complaint,
        "reopened",
        "tester@example.com",
        reason="unit test reopen",
        commit=False,
    )
    assert success is True
    assert error is None
    test_db.commit()
    test_db.refresh(member)
    assert member.active_tasks == 1

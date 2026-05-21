import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import AutomationRule, Complaint, Customer, EventLog, UnifiedMessage, WorkflowExecution
from app.services.action_executor import execute_action
from app.services.customer_profile import CustomerProfileService
from app.services.event_logger import log_event


def test_customer_360_includes_event_timeline_with_tenant_isolation(test_db, test_client_record):
    other_client_id = uuid.uuid4()
    customer = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="evented@example.com",
        emails=["evented@example.com"],
        full_name="Evented Customer",
    )
    test_db.add(customer)
    test_db.commit()

    visible = log_event(
        test_db,
        test_client_record.id,
        "sentiment_drop_detected",
        {"summary": "Sentiment dropped after billing reply"},
        customer_id=customer.id,
        source="intelligence",
        actor_type="system",
        sentiment_score=-0.8,
    )
    log_event(
        test_db,
        other_client_id,
        "sentiment_drop_detected",
        {"summary": "Other tenant event"},
        customer_id=customer.id,
        source="intelligence",
        actor_type="system",
    )
    test_db.commit()

    data = CustomerProfileService(test_db).get_customer_360(str(customer.id))
    timeline_ids = [item["id"] for item in data["timeline"]]

    assert f"event:{visible.id}" in timeline_ids
    assert all(item["data"].get("client_id") != str(other_client_id) for item in data["timeline"] if item["type"] == "event")


def test_weighted_churn_uses_events_sentiment_escalations_and_inactivity(test_db, test_client_record):
    old_seen = datetime.now(timezone.utc) - timedelta(days=35)
    customer = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="risk@example.com",
        emails=["risk@example.com"],
        full_name="Risk Customer",
        last_contacted_at=old_seen,
        last_interaction_at=old_seen,
        avg_satisfaction_score=2.0,
    )
    test_db.add(customer)
    for index in range(3):
        test_db.add(
            Complaint(
                id=uuid.uuid4(),
                client_id=test_client_record.id,
                customer_id=customer.id,
                summary=f"Unresolved complaint {index}",
                category="billing",
                sentiment=-0.7,
                priority=4,
                ticket_id=f"TKT-RISK-{index}",
                thread_id=f"TH-RISK-{index}",
                resolution_status="open",
                escalation_level=1,
                created_at=datetime.now(timezone.utc) - timedelta(days=index),
            )
        )
        test_db.add(
            UnifiedMessage(
                id=uuid.uuid4(),
                client_id=test_client_record.id,
                customer_id=customer.id,
                channel="email",
                external_message_id=f"msg-risk-{index}",
                sender_id="risk@example.com",
                message_text="This keeps getting worse",
                timestamp=datetime.now(timezone.utc) - timedelta(days=index),
                direction="inbound",
                status="processed",
                raw_payload={"sentiment": -0.8 + (index * 0.05)},
            )
        )
    test_db.commit()
    log_event(
        test_db,
        test_client_record.id,
        "payment_failed",
        {"summary": "Payment failed"},
        customer_id=customer.id,
        source="billing",
        actor_type="system",
    )
    test_db.commit()

    risk = CustomerProfileService(test_db).compute_churn_risk(customer)

    assert risk["level"] == "high"
    assert risk["score"] >= 75
    assert "Refund/payment risk event detected" in risk["explanation"]


def test_workflow_execution_records_success(test_db, test_client_record):
    customer = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="workflow@example.com",
        emails=["workflow@example.com"],
    )
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        customer_id=customer.id,
        summary="Needs priority",
        category="billing",
        sentiment=-0.4,
        priority=2,
        ticket_id="TKT-WORKFLOW",
        thread_id="TH-WORKFLOW",
    )
    rule = AutomationRule(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        trigger_type="sentiment",
        trigger_value="-0.2",
        action_type="mark_high_priority",
        enabled=True,
    )
    test_db.add_all([customer, complaint, rule])
    test_db.commit()

    execution = execute_action(rule, complaint, test_client_record, db=test_db, trigger_event_type="message_processed")
    test_db.commit()

    saved = test_db.query(WorkflowExecution).filter(WorkflowExecution.id == execution.id).one()
    event = test_db.query(EventLog).filter(EventLog.event_type == "workflow_action_succeeded").one()
    assert complaint.priority == 5
    assert saved.execution_status == "succeeded"
    assert saved.customer_id == customer.id
    assert event.complaint_id == complaint.id

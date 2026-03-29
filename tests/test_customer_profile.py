import uuid
from datetime import datetime, timezone

from app.db.models import Complaint, Customer, CustomerInteraction, CustomerNote, CustomerRelationship
from app.services.customer_deduplication import CustomerDeduplicator
from app.services.customer_profile import CustomerProfileService


def test_get_or_create_customer_dedupes_exact_email(test_db, test_client_record):
    service = CustomerProfileService(test_db)

    first = service.get_or_create_customer(
        client_id=test_client_record.id,
        email="Customer@Example.com",
        commit=True,
    )
    second = service.get_or_create_customer(
        client_id=test_client_record.id,
        email="customer@example.com",
        commit=True,
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert second.primary_email == "customer@example.com"
    assert second.emails == ["customer@example.com"]


def test_find_duplicates_with_fuzzy_name_and_domain(test_db, test_client_record):
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

    duplicates = CustomerDeduplicator(test_db).find_duplicates(second)

    assert duplicates
    duplicate, confidence = duplicates[0]
    assert duplicate.id == first.id
    assert confidence >= 0.85


def test_merge_customers_reassigns_related_records(test_db, test_client_record):
    master = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="master@example.com",
        emails=["master@example.com"],
        full_name="Master Customer",
    )
    duplicate = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="dup@example.com",
        emails=["dup@example.com"],
        full_name="Duplicate Customer",
    )
    parent = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="parent@example.com",
        emails=["parent@example.com"],
        full_name="Parent Customer",
    )
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        customer_id=duplicate.id,
        summary="Merge me",
        category="billing",
        sentiment=-0.5,
        priority=3,
        ticket_id="TKT-MERGE",
        thread_id="TH-MERGE",
        created_at=datetime.now(timezone.utc),
    )
    interaction = CustomerInteraction(
        id=uuid.uuid4(),
        customer_id=duplicate.id,
        client_id=test_client_record.id,
        interaction_type="ticket",
        interaction_channel="api",
        complaint_id=complaint.id,
        summary="Merged interaction",
    )
    note = CustomerNote(
        id=uuid.uuid4(),
        customer_id=duplicate.id,
        author_email="agent@example.com",
        content="Important note",
    )
    relationship = CustomerRelationship(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        parent_customer_id=parent.id,
        child_customer_id=duplicate.id,
        relationship_type="employee",
    )
    test_db.add_all([master, duplicate, parent, complaint, interaction, note, relationship])
    test_db.commit()

    merged = CustomerDeduplicator(test_db).merge_customers(
        master_id=str(master.id),
        duplicate_id=str(duplicate.id),
        merged_by="agent@example.com",
        commit=True,
    )

    test_db.refresh(complaint)
    test_db.refresh(interaction)
    test_db.refresh(note)
    test_db.refresh(relationship)
    test_db.refresh(duplicate)

    assert merged.id == master.id
    assert complaint.customer_id == master.id
    assert interaction.customer_id == master.id
    assert note.customer_id == master.id
    assert relationship.child_customer_id == master.id
    assert duplicate.is_master is False
    assert duplicate.merged_into == master.id


def test_sync_customer_for_complaint_creates_profile_and_interaction(test_db, test_client_record):
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Need help with checkout",
        source="email",
        customer_email="buyer@example.com",
        customer_phone="+1 (555) 123-4567",
        category="billing",
        sentiment=-0.2,
        priority=2,
        ticket_id="TKT-CUST",
        thread_id="TH-CUST",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(complaint)
    test_db.commit()

    customer = CustomerProfileService(test_db).sync_customer_for_complaint(
        complaint,
        interaction_type="ticket",
        interaction_channel="email",
        commit=True,
    )

    test_db.refresh(complaint)
    assert customer is not None
    assert complaint.customer_id == customer.id
    assert customer.total_tickets == 1
    assert customer.total_interactions == 1

    interactions = (
        test_db.query(CustomerInteraction)
        .filter(CustomerInteraction.customer_id == customer.id, CustomerInteraction.complaint_id == complaint.id)
        .all()
    )
    assert len(interactions) == 1

import pytest
from app.db.models import Complaint, Customer, JobQueue


def test_complaint_submission_success(client, test_client_record):
    """Test successful complaint submission"""
    response = client.post(
        "/webhook/complaint",
        headers={"x-api-key": test_client_record.api_key},
        json={
            "message": "I want a refund for duplicate charge",
            "source": "api",
            "customer_email": "test@example.com"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "ticket_id" in data


def test_complaint_invalid_api_key(client):
    """Test complaint with invalid API key"""
    response = client.post(
        "/webhook/complaint",
        headers={"x-api-key": "invalid_key"},
        json={"message": "Test complaint"}
    )
    
    assert response.status_code == 401


def test_complaint_missing_api_key(client):
    """Test complaint without API key"""
    response = client.post(
        "/webhook/complaint",
        json={"message": "Test complaint"}
    )
    
    assert response.status_code == 401


def test_complaint_empty_message(client, test_client_record):
    """Test complaint with empty message"""
    response = client.post(
        "/webhook/complaint",
        headers={"x-api-key": test_client_record.api_key},
        json={"message": ""}
    )
    
    assert response.status_code == 400


def test_complaint_creates_job(client, test_client_record, test_db):
    """Test that complaint creates background job"""
    response = client.post(
        "/webhook/complaint",
        headers={"x-api-key": test_client_record.api_key},
        json={
            "message": "Need help with billing",
            "source": "api"
        }
    )
    
    assert response.status_code == 200
    
    # Check job was created
    job = test_db.query(JobQueue).filter(
        JobQueue.job_type == "process_complaint_ai"
    ).first()
    
    assert job is not None
    assert job.status == "queued"


def test_complaint_links_customer_profile(client, test_client_record, test_db):
    response = client.post(
        "/webhook/complaint",
        headers={"x-api-key": test_client_record.api_key},
        json={
            "message": "My invoice was charged twice",
            "source": "api",
            "customer_email": "linked@example.com",
            "customer_phone": "+1 (555) 111-2222",
        },
    )

    assert response.status_code == 200

    complaint = test_db.query(Complaint).order_by(Complaint.created_at.desc()).first()
    assert complaint is not None
    assert complaint.customer_id is not None

    customer = test_db.query(Customer).filter(Customer.id == complaint.customer_id).first()
    assert customer is not None
    assert customer.primary_email == "linked@example.com"
    assert customer.total_tickets == 1


def test_usage_limit_enforcement(client, test_client_record, test_db):
    """Test that usage limits are enforced"""
    test_client_record.monthly_ticket_limit = 50
    test_db.commit()
    test_db.refresh(test_client_record)

    # Submit 50 complaints (the limit)
    for i in range(50):
        response = client.post(
            "/webhook/complaint",
            headers={"x-api-key": test_client_record.api_key},
            json={"message": f"Complaint {i}"}
        )
        assert response.status_code == 200
    
    # 51st should fail
    response = client.post(
        "/webhook/complaint",
        headers={"x-api-key": test_client_record.api_key},
        json={"message": "Should fail"}
    )
    
    assert response.status_code == 402
    assert "limit exceeded" in response.json()["detail"]["message"].lower()

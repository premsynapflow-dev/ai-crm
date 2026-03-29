import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid

os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("DISABLE_SCHEMA_GUARD", "1")

from app.main import app
from app.db.models import Base
from app.db.session import get_db
from app.utils.security import generate_api_key
from datetime import datetime, timedelta, timezone
import uuid

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with DB override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    import app.billing.usage as billing_usage
    import app.middleware.audit as audit_middleware
    import app.middleware.feature_gate as feature_gate_middleware
    import app.middleware.rls_context as rls_context_middleware

    original_usage_session_local = billing_usage.SessionLocal
    original_audit_session_local = audit_middleware.SessionLocal
    original_feature_gate_session_local = feature_gate_middleware.SessionLocal
    original_rls_session_local = rls_context_middleware.SessionLocal
    original_feature_gate_resolve_client = feature_gate_middleware.FeatureGateMiddleware._resolve_client

    def safe_resolve_client(self, request):
        client_id = feature_gate_middleware.resolve_client_id_from_request(request)
        if not client_id:
            return None
        db = feature_gate_middleware.SessionLocal()
        try:
            try:
                parsed_client_id = uuid.UUID(str(client_id))
            except (TypeError, ValueError):
                parsed_client_id = client_id
            return db.query(feature_gate_middleware.Client).filter(feature_gate_middleware.Client.id == parsed_client_id).first()
        finally:
            db.close()

    billing_usage.SessionLocal = TestingSessionLocal
    audit_middleware.SessionLocal = TestingSessionLocal
    feature_gate_middleware.SessionLocal = TestingSessionLocal
    rls_context_middleware.SessionLocal = TestingSessionLocal
    feature_gate_middleware.FeatureGateMiddleware._resolve_client = safe_resolve_client
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    billing_usage.SessionLocal = original_usage_session_local
    audit_middleware.SessionLocal = original_audit_session_local
    feature_gate_middleware.SessionLocal = original_feature_gate_session_local
    rls_context_middleware.SessionLocal = original_rls_session_local
    feature_gate_middleware.FeatureGateMiddleware._resolve_client = original_feature_gate_resolve_client


@pytest.fixture
def test_client_record(test_db):
    """Create a test client record"""
    from app.db.models import Client

    client = Client(
        id=uuid.uuid4(),
        name="Test Company",
        api_key=generate_api_key(),
        plan_id="starter",
        monthly_ticket_limit=500,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    test_db.add(client)
    test_db.commit()
    test_db.refresh(client)
    return client

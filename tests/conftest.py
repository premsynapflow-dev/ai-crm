import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.models import Base
from app.db.session import get_db
from app.utils.security import generate_api_key
from datetime import datetime, timedelta, timezone
import uuid

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


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

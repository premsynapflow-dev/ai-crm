import os
import unittest
import uuid
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass123")

from app.api.public import router as public_router
from app.client_portal import router as portal_router


class _FakeQuery:
    def __init__(self, result=None):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class _FakeDB:
    def __init__(self, query_results=None):
        self.added = []
        self.query_results = list(query_results or [])
        self.deleted = []

    def query(self, *args, **kwargs):
        result = self.query_results.pop(0) if self.query_results else None
        return _FakeQuery(result)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self):
        return None

    def rollback(self):
        return None

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        return obj

    def delete(self, obj):
        self.deleted.append(obj)

    def close(self):
        return None


class PublicSignupTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(public_router)
        self.client = TestClient(app)

    def _trial_plan(self, client):
        client.plan_id = "free"
        client.plan = "free"
        client.monthly_ticket_limit = 50
        return client

    def test_signup_accepts_json(self):
        fake_db = _FakeDB()
        with patch("app.api.public.SessionLocal", return_value=fake_db), patch(
            "app.api.public.hash_password", return_value="hashed"
        ), patch("app.api.public.apply_signup_plan", side_effect=self._trial_plan), patch(
            "app.api.public.enqueue_welcome_sequence"
        ):
            response = self.client.post(
                "/api/signup",
                json={
                    "company_name": "Acme",
                    "email": "founder@example.com",
                    "password": "strongpass123",
                    "phone_number": "+919876543210",
                    "business_sector": "nbfc_hfc",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "created")
        self.assertEqual(len(fake_db.added), 2)

    def test_signup_accepts_form_data(self):
        fake_db = _FakeDB()
        with patch("app.api.public.SessionLocal", return_value=fake_db), patch(
            "app.api.public.hash_password", return_value="hashed"
        ), patch("app.api.public.apply_signup_plan", side_effect=self._trial_plan), patch(
            "app.api.public.enqueue_welcome_sequence"
        ):
            response = self.client.post(
                "/api/signup",
                data={
                    "company_name": "Acme",
                    "email": "founder@example.com",
                    "password": "strongpass123",
                    "phone_number": "+919876543210",
                    "business_sector": "nbfc_hfc",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "created")
        self.assertEqual(len(fake_db.added), 2)


class PortalLoginTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="0123456789abcdef0123456789abcdef")
        app.include_router(portal_router)
        self.client = TestClient(app)

    def test_portal_login_invalid_password_returns_401(self):
        fake_user = type("User", (), {"id": uuid.uuid4(), "email": "user@example.com", "password_hash": "bad-hash"})()
        fake_db = _FakeDB(query_results=[fake_user])
        with patch("app.client_portal.verify_password", side_effect=ValueError("hash error")):
            app = self.client.app
            app.dependency_overrides = {}
            from app.db.session import get_db

            def override_get_db():
                yield fake_db

            app.dependency_overrides[get_db] = override_get_db
            response = self.client.post(
                "/portal/login",
                data={"email": "user@example.com", "password": "wrongpass"},
            )
            app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password", response.text)


if __name__ == "__main__":
    unittest.main()

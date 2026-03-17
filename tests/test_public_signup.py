import os
import unittest
import uuid
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass123")

from app.api.public import router as public_router


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []

    def query(self, *args, **kwargs):
        return _FakeQuery()

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

    def close(self):
        return None


class PublicSignupTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(public_router)
        self.client = TestClient(app)

    def _trial_plan(self, client):
        client.plan_id = "trial"
        client.plan = "trial"
        client.monthly_ticket_limit = 50
        return client

    def test_signup_accepts_json(self):
        fake_db = _FakeDB()
        with patch("app.api.public.SessionLocal", return_value=fake_db), patch(
            "app.api.public.hash_password", return_value="hashed"
        ), patch("app.api.public.apply_trial_plan", side_effect=self._trial_plan), patch(
            "app.api.public.enqueue_welcome_sequence"
        ):
            response = self.client.post(
                "/api/signup",
                json={
                    "company_name": "Acme",
                    "email": "founder@example.com",
                    "password": "strongpass123",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "created")

    def test_signup_accepts_form_data(self):
        fake_db = _FakeDB()
        with patch("app.api.public.SessionLocal", return_value=fake_db), patch(
            "app.api.public.hash_password", return_value="hashed"
        ), patch("app.api.public.apply_trial_plan", side_effect=self._trial_plan), patch(
            "app.api.public.enqueue_welcome_sequence"
        ):
            response = self.client.post(
                "/api/signup",
                data={
                    "company_name": "Acme",
                    "email": "founder@example.com",
                    "password": "strongpass123",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "created")


if __name__ == "__main__":
    unittest.main()

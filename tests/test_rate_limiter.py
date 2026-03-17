import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limiter import DatabaseRateLimitMiddleware


class _FakeQuery:
    def __init__(self, count_value):
        self.count_value = count_value

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return self.count_value


class _FakeSession:
    def __init__(self, count_value):
        self.count_value = count_value

    def query(self, *args, **kwargs):
        return _FakeQuery(self.count_value)

    def close(self):
        return None


class RateLimiterTests(unittest.TestCase):
    def _build_app(self, count_value):
        app = FastAPI()
        app.add_middleware(DatabaseRateLimitMiddleware)

        @app.get("/webhook/complaint")
        def complaint_probe():
            return {"ok": True}

        session_factory = lambda: _FakeSession(count_value)
        return app, session_factory

    def test_allows_requests_under_limit(self):
        app, session_factory = self._build_app(0)
        with patch("app.middleware.rate_limiter.SessionLocal", session_factory):
            client = TestClient(app)
            response = client.get("/webhook/complaint")
        self.assertEqual(response.status_code, 200)

    def test_blocks_requests_over_limit(self):
        app, session_factory = self._build_app(100)
        with patch("app.middleware.rate_limiter.SessionLocal", session_factory):
            client = TestClient(app)
            response = client.get("/webhook/complaint")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Rate limit exceeded. Please try again later.")


if __name__ == "__main__":
    unittest.main()

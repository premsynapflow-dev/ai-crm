import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limiter import DatabaseRateLimitMiddleware


class RateLimiterTests(unittest.TestCase):
    def _build_app(self):
        app = FastAPI()
        app.add_middleware(DatabaseRateLimitMiddleware)

        @app.get("/webhook/complaint")
        def complaint_probe():
            return {"ok": True}

        return app

    def test_allows_requests_under_limit(self):
        app = self._build_app()
        with patch("app.middleware.rate_limiter.rate_limiter.is_allowed", return_value=True) as is_allowed:
            client = TestClient(app)
            response = client.get("/webhook/complaint")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(is_allowed.called)

    def test_blocks_requests_over_limit(self):
        app = self._build_app()
        with patch("app.middleware.rate_limiter.rate_limiter.is_allowed", return_value=False) as is_allowed:
            client = TestClient(app)
            response = client.get("/webhook/complaint")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Rate limit exceeded. Please try again later.")
        self.assertTrue(is_allowed.called)


if __name__ == "__main__":
    unittest.main()

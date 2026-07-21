"""Offline smoke tests for the application shell and security defaults."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest


_temp_dir = tempfile.TemporaryDirectory(prefix="agent-invest-tests-")
_database_path = Path(_temp_dir.name, "smoke.db").as_posix()

# Set these before importing application modules. Environment variables override
# any developer .env file that may exist on the machine running the tests.
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_database_path}",
        "RAG_ENABLED": "false",
        "ADMIN_PASSWORD": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_WEBHOOK_SECRET_TOKEN": "",
        "TELEGRAM_ADMIN_TOKEN": "",
        "TELEGRAM_DAILY_REPORT_ENABLED": "false",
        "TELEGRAM_COMMUNITY_REPORT_ENABLED": "false",
        "TELEGRAM_PAID_REPORT_ENABLED": "false",
        "TELEGRAM_ALERTS_ENABLED": "false",
        "CALENDAR_ALERT_ENABLED": "false",
        "AUTO_ANALYZE_ENABLED": "false",
        "FRONTEND_URL": "http://localhost:3000",
        "CORS_ALLOW_ORIGINS": "",
        "CORS_ALLOW_ORIGIN_REGEX": "",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from database import engine  # noqa: E402
from main import app  # noqa: E402


class ApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        engine.dispose()
        _temp_dir.cleanup()

    def test_root_and_health(self) -> None:
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["app"], "Agent Invest API")

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "healthy"})

    def test_empty_database_reads(self) -> None:
        self.assertEqual(self.client.get("/predictions").status_code, 200)
        self.assertEqual(self.client.get("/accuracy").status_code, 200)
        self.assertEqual(self.client.get("/telegram/status").status_code, 200)

    def test_admin_fails_closed_without_password(self) -> None:
        response = self.client.post("/admin/login", json={"password": ""})
        self.assertEqual(response.status_code, 503)

    def test_telegram_webhook_fails_closed_without_secret(self) -> None:
        response = self.client.post("/telegram/webhook", json={})
        self.assertEqual(response.status_code, 503)

    def test_cors_allows_local_frontend_only(self) -> None:
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
        allowed = self.client.options("/health", headers=headers)
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), headers["Origin"])

        blocked = self.client.options(
            "/health",
            headers={**headers, "Origin": "https://untrusted.example"},
        )
        self.assertIsNone(blocked.headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()

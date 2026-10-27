import base64

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app
from app.security.dashboard import valid_dashboard_authorization


def test_dashboard_authorization_accepts_only_configured_reviewer_password():
    header = "Basic " + base64.b64encode(b"reviewer:local-test-password").decode()

    assert valid_dashboard_authorization(header, "local-test-password")
    assert not valid_dashboard_authorization(header, "different-password")
    assert not valid_dashboard_authorization("Bearer local-test-password", "local-test-password")
    assert not valid_dashboard_authorization("Basic not-base64", "local-test-password")


def test_dashboard_auth_is_disabled_only_when_no_password_is_configured():
    assert not valid_dashboard_authorization(None, "local-test-password")


def test_render_postgres_urls_are_normalized_for_async_sqlalchemy():
    common = {
        "REDIS_URL": "redis://localhost:6379/0",
        "GEMINI_API_KEY": "test-only",
        "CLOUDMAILIN_SECRET": "test-only",
    }
    settings = Settings(DATABASE_URL="postgresql://user:pass@db.internal/demo", **common)
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@db.internal/demo"


def test_production_rejects_default_role_and_unsigned_webhook():
    common = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/demo",
        "REDIS_URL": "redis://localhost:6379/0",
        "GEMINI_API_KEY": "test-only",
        "CLOUDMAILIN_SECRET": "test-only",
        "APP_ENV": "production",
    }
    with pytest.raises(ValidationError):
        Settings(**common)
    with pytest.raises(ValidationError):
        Settings(
            **common,
            APP_ROLE="web",
            DASHBOARD_PASSWORD="a-long-demo-password",
            ALLOW_UNSIGNED_WEBHOOK=True,
        )


def test_production_api_requires_reviewer_password(monkeypatch):
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/demo",
        REDIS_URL="redis://localhost:6379/0",
        GEMINI_API_KEY="test-only",
        CLOUDMAILIN_SECRET="test-only",
        APP_ENV="production",
        APP_ROLE="web",
        DASHBOARD_PASSWORD="local-test-password-long",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    with TestClient(app) as client:
        for path in (
            "/api/auth/check",
            "/api/review/queue",
            "/api/runs",
            "/api/metrics/summary",
        ):
            denied = client.get(path)
            assert denied.status_code == 401

        valid = "Basic " + base64.b64encode(b"reviewer:local-test-password-long").decode()
        allowed = client.get("/api/auth/check", headers={"Authorization": valid})
        assert allowed.status_code == 200
        assert allowed.json() == {"authenticated": True, "required": True}


def test_health_is_public_and_returns_unhealthy_status_when_dependencies_fail(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise OSError("database unavailable")

    class BrokenRedis:
        async def ping(self):
            return False

    monkeypatch.setattr("app.db.session.get_engine", lambda: BrokenEngine())
    monkeypatch.setattr("app.redis_client.get_redis", lambda: BrokenRedis())

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["worker"] is True

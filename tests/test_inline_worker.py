import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app


def test_inline_worker_runs_inside_application_lifespan(monkeypatch):
    from app.workers import inline

    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/demo",
        REDIS_URL="redis://localhost:6379/0",
        GEMINI_API_KEY="test-only",
        CLOUDMAILIN_SECRET="test-only",
        APP_ENV="production",
        APP_ROLE="web",
        DASHBOARD_PASSWORD="local-test-password-long",
        RUN_INLINE_WORKER=True,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    startup = AsyncMock()
    monkeypatch.setattr(inline, "get_worker_kwargs", lambda: {"on_startup": startup})

    workers = []

    class FakeWorker:
        def __init__(self, **kwargs):
            self.on_startup = kwargs["on_startup"]
            self.handle_signals = kwargs["handle_signals"]
            self.closed = False
            workers.append(self)

        async def async_run(self):
            await self.on_startup({})
            await asyncio.Event().wait()

        async def close(self):
            self.closed = True

    monkeypatch.setattr(inline, "Worker", FakeWorker)

    with TestClient(app) as client:
        assert client.get("/").status_code == 200

    startup.assert_awaited_once()
    assert len(workers) == 1
    assert workers[0].handle_signals is False
    assert workers[0].closed is True


def test_inline_worker_requires_gemini_key_in_production():
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/demo",
            REDIS_URL="redis://localhost:6379/0",
            GEMINI_API_KEY="",
            CLOUDMAILIN_SECRET="test-only",
            APP_ENV="production",
            APP_ROLE="web",
            DASHBOARD_PASSWORD="local-test-password-long",
            RUN_INLINE_WORKER=True,
        )

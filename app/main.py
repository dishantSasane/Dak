"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_cases,
    routes_manual,
    routes_metrics,
    routes_review,
    routes_runs,
    webhook,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Inbox Triage", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(routes_manual.router)
app.include_router(routes_cases.router)
app.include_router(routes_runs.router)
app.include_router(routes_review.router)
app.include_router(routes_metrics.router)


@app.get("/health")
async def health() -> dict:
    """No auth; used by the keep-warm ping (§1.5)."""
    db_ok = redis_ok = False
    try:
        from sqlalchemy import text

        from app.db.session import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001 - health must never raise
        pass
    try:
        from app.redis_client import get_redis

        redis_ok = bool(await get_redis().ping())
    except Exception:  # noqa: BLE001
        pass
    return {"status": "ok" if (db_ok and redis_ok) else "degraded", "db": db_ok, "redis": redis_ok}

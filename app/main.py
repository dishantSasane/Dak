"""FastAPI application entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_cases,
    routes_demo,
    routes_manual,
    routes_metrics,
    routes_review,
    routes_runs,
    webhook,
)
from app.config import get_settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Dak", version="1.0")


@app.middleware("http")
async def protect_dashboard(request: Request, call_next):
    """Protect dashboard APIs while preserving token-scoped public case links."""
    settings = get_settings()
    path = request.url.path
    token_public_case = path.startswith("/t/") or path.startswith("/api/cases/")
    protected = (path.startswith("/api/") and not token_public_case) or path in {
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    if protected and request.method != "OPTIONS" and settings.DASHBOARD_PASSWORD:
        from app.security.dashboard import valid_dashboard_authorization

        if not valid_dashboard_authorization(
            request.headers.get("Authorization"), settings.DASHBOARD_PASSWORD
        ):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Reviewer sign-in required"},
                headers={"WWW-Authenticate": 'Basic realm="Dak reviewer"'},
            )
            return response
    return await call_next(request)

app.include_router(webhook.router)
app.include_router(routes_demo.router)
app.include_router(routes_manual.router)
app.include_router(routes_cases.router)
app.include_router(routes_runs.router)
app.include_router(routes_review.router)
app.include_router(routes_metrics.router)


@app.get("/api/auth/check", tags=["auth"])
async def auth_check() -> dict:
    """A lightweight request the UI uses to validate the reviewer password."""
    return {"authenticated": True, "required": bool(get_settings().DASHBOARD_PASSWORD)}


@app.get("/health", response_model=None)
async def health() -> dict | JSONResponse:
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
    result = {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }
    return result if db_ok and redis_ok else JSONResponse(status_code=503, content=result)


_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend_app(frontend_path: str):
        """Serve the Vite app and its client-side routes from the API origin."""
        from fastapi.responses import FileResponse

        if frontend_path.startswith(("api/", "webhook/")) or frontend_path in {
            "health",
            "docs",
            "redoc",
            "openapi.json",
        }:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return FileResponse(_FRONTEND_DIST / "index.html")

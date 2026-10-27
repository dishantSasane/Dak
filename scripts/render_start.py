"""Render entrypoint for the API and its optional in-process ARQ worker."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from time import monotonic

from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("render_start")


async def wait_for_bootstrap(timeout_seconds: int = 1200) -> None:
    """Wait for the worker's migration and synthetic reference-data bootstrap."""
    manifest = json.loads((ROOT / "data/corpus/manifest.json").read_text())
    version = get_settings().CORPUS_VERSION
    expected = sum(item["clause_count"] for item in manifest["documents"])
    deadline = monotonic() + timeout_seconds
    last_error = "database bootstrap not complete"
    last_log = 0.0
    logging.basicConfig(level=logging.INFO)
    while monotonic() < deadline:
        try:
            async with get_engine().connect() as connection:
                count = await connection.scalar(
                    text("SELECT count(*) FROM policy_chunks WHERE corpus_version = :version"),
                    {"version": version},
                )
                if count and count == expected:
                    logger.info("database bootstrap ready with %s corpus clauses", count)
                    return
                last_error = f"policy corpus has {count or 0}/{expected} clauses"
        except Exception as exc:  # noqa: BLE001 - database may not be migrated yet
            last_error = f"database bootstrap check failed ({type(exc).__name__})"
        if monotonic() - last_log >= 30:
            logger.info("waiting for the Render worker: %s", last_error)
            last_log = monotonic()
        await asyncio.sleep(5)
    raise TimeoutError(
        f"Render worker did not finish database setup within 20 minutes: {last_error}"
    )


def run_worker_setup() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "scripts.bootstrap_render"], check=True)


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("APP_ROLE", "web")
    if role == "worker":
        run_worker_setup()
        os.execvp("arq", ["arq", "app.workers.process.WorkerSettings"])
    if role != "web":
        raise SystemExit("Expected Render role 'web' or 'worker'")
    if get_settings().RUN_INLINE_WORKER:
        run_worker_setup()
    asyncio.run(wait_for_bootstrap())
    port = os.environ.get("PORT", "10000")
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
    )


if __name__ == "__main__":
    main()

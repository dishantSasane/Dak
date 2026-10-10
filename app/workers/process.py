"""ARQ worker — T1.5 skeleton.

process_email(email_id) currently creates a `runs` row and marks it `failed`
with reason `not_implemented`. T5.3 replaces the stub with a real graph
invocation.
"""

from __future__ import annotations

import logging
import uuid

from arq.connections import RedisSettings

from app.config import get_settings
from app.db.models import Email, Run
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)


async def process_email(ctx: dict, email_id: int) -> int:
    """Create a run row for an ingested email (stub until T5.3)."""
    async with get_sessionmaker()() as session:
        email = await session.get(Email, email_id)
        if email is None:
            logger.error("process_email: email %s not found", email_id)
            return -1
        run = Run(
            email_id=email.id,
            case_id=email.case_id,
            thread_id=str(uuid.uuid4()),
            status="failed",
            escalation_reason="not_implemented",
        )
        session.add(run)
        await session.commit()
        logger.info("process_email: created stub run %s for email %s", run.id, email_id)
        return int(run.id)


async def startup(ctx: dict) -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("worker started")


async def shutdown(ctx: dict) -> None:
    logger.info("worker stopped")


class WorkerSettings:
    functions = [process_email]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = get_settings().WORKER_CONCURRENCY
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)

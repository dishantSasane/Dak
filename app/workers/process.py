"""Durable ARQ entry point, checkpoint resume and periodic lost-dispatch recovery."""

from __future__ import annotations

import logging
import uuid

from arq import Retry, cron
from arq.connections import RedisSettings
from sqlalchemy import exists, select, text

from app.config import get_settings
from app.db.models import Email, Run
from app.db.session import get_sessionmaker
from app.graph.build import process_run, setup_checkpoint_schema
from app.llm.gemini import ModelRateLimited
from app.tools.base import write_event

logger = logging.getLogger(__name__)
TERMINAL = ("pending_review", "approved", "rejected", "escalated", "failed")


async def process_email(ctx: dict, email_id: int) -> int:
    factory = get_sessionmaker()
    # A transaction-scoped advisory lock survives all graph-node commits because
    # it has its own held connection. A competing worker retries instead of
    # invoking the same thread concurrently.
    async with factory() as lock:
        acquired = await lock.scalar(
            text("SELECT pg_try_advisory_xact_lock(44202, :email)"), {"email": email_id}
        )
        if not acquired:
            raise Retry(defer=2)
        async with factory() as session:
            email = await session.get(Email, email_id)
            if email is None or email.raw_payload.get("unparseable"):
                return -1
            await session.execute(select(Email.id).where(Email.id == email_id).with_for_update())
            run = await session.scalar(select(Run).where(Run.email_id == email_id).limit(1))
            if (
                run is not None
                and run.status in TERMINAL
                and run.escalation_reason != "not_implemented"
            ):
                return int(run.id)
            if run is None:
                run = Run(
                    email_id=email.id,
                    case_id=email.case_id,
                    thread_id=str(uuid.uuid4()),
                    status="running",
                )
                session.add(run)
            else:
                run.status = "running"
                run.escalation_reason = None
            await session.commit()
            run_id = int(run.id)
        try:
            await process_run(
                run_id,
                factory,
                client=ctx.get("model_client"),
                checkpointer=ctx.get("checkpointer"),
                initialize_checkpointer=not ctx.get("checkpointer_schema_ready", False),
            )
        except ModelRateLimited:
            logger.info("Model quota backoff for run %s", run_id)
            raise Retry(defer=60) from None
        except Exception:
            logger.exception("Worker failed for run %s", run_id)
            async with factory() as session:
                failed = await session.get(Run, run_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.escalation_reason = "tool_failure"
                    await session.commit()
                    await write_event(
                        session,
                        run_id,
                        "worker",
                        "error",
                        {"reason": "worker_failure", "resumable": True},
                    )
            raise
        return run_id


async def reconcile_pending(ctx: dict) -> int:
    """Recover committed emails whose dispatch was lost before a queue write."""
    async with get_sessionmaker()() as session:
        completed = exists(select(Run.id).where(Run.email_id == Email.id, Run.status.in_(TERMINAL)))
        ids = (
            await session.scalars(
                select(Email.id)
                .where(
                    Email.direction == "inbound",
                    Email.raw_payload["unparseable"].as_boolean().is_not(True),
                    ~completed,
                )
                .order_by(Email.received_at)
                .limit(100)
            )
        ).all()
    for email_id in ids:
        await ctx["redis"].enqueue_job("process_email", email_id, _job_id=f"email:{email_id}")
    return len(ids)


async def startup(ctx: dict) -> None:
    logging.basicConfig(level=logging.INFO)
    await setup_checkpoint_schema()
    ctx["checkpointer_schema_ready"] = True
    await reconcile_pending(ctx)
    logger.info("worker ready; checkpoints initialized and pending emails reconciled")


async def shutdown(ctx: dict) -> None:
    logger.info("worker stopped")


class WorkerSettings:
    functions = [process_email]
    cron_jobs = [cron(reconcile_pending, second=0)]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = get_settings().WORKER_CONCURRENCY
    job_timeout = 600
    max_tries = 3
    keep_result = 0
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)

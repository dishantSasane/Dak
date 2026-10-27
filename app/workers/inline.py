"""Run ARQ within the API process for small, single-service deployments."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from arq.worker import Worker, get_kwargs

from app.workers.process import WorkerSettings


def get_worker_kwargs() -> dict:
    """Build ARQ options from the normal worker settings."""
    return get_kwargs(dict(WorkerSettings.__dict__))


@asynccontextmanager
async def inline_worker() -> AsyncIterator[asyncio.Task]:
    """Start one ARQ worker and close it cleanly with the web application."""
    kwargs = get_worker_kwargs()
    original_startup = kwargs.get("on_startup")
    ready = asyncio.Event()

    async def on_startup(ctx: dict) -> None:
        if original_startup is not None:
            await original_startup(ctx)
        ready.set()

    kwargs["on_startup"] = on_startup
    kwargs["handle_signals"] = False
    worker = Worker(**kwargs)
    task = asyncio.create_task(worker.async_run(), name="dak-inline-arq-worker")
    ready_task = asyncio.create_task(ready.wait())
    try:
        done, _ = await asyncio.wait(
            (ready_task, task), timeout=60, return_when=asyncio.FIRST_COMPLETED
        )
        if ready_task not in done:
            if task.done():
                await task
            raise TimeoutError("ARQ worker did not finish startup within 60 seconds")
        yield task
    finally:
        ready_task.cancel()
        with suppress(asyncio.CancelledError):
            await ready_task
        try:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        finally:
            await worker.close()

"""Typed tool boundary, run-scoped caching and durable trace events."""

from collections.abc import Awaitable, Callable
from hashlib import sha256
from time import monotonic
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunEvent
from app.redis_client import cache_get_json, cache_set_json


class ToolResult[T](BaseModel):
    ok: bool
    value: T | None = None
    error: str | None = None
    cache_hit: bool = False


async def write_event(
    session: AsyncSession,
    run_id: int,
    node: str,
    event_type: str,
    payload: dict,
    duration_ms: int | None = None,
) -> None:
    # Serialize sequence allocation, including concurrent calls within a run.
    await session.execute(select(Run.id).where(Run.id == run_id).with_for_update())
    last = await session.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id))
    session.add(
        RunEvent(
            run_id=run_id,
            seq=(last or 0) + 1,
            node=node,
            event_type=event_type,
            payload=payload,
            duration_ms=duration_ms,
        )
    )
    await session.commit()


class ToolContext:
    def __init__(self, session: AsyncSession, run_id: int, state: dict[str, Any]) -> None:
        self.session = session
        self.run_id = run_id
        self.state = state

    async def call[T: BaseModel](
        self,
        name: str,
        args: dict,
        operation: Callable[[], Awaitable[T]],
        schema: type[T],
        *,
        customer: bool = False,
        ttl: int = 300,
    ) -> ToolResult[T]:
        if customer:
            self.state["used_customer_tools"] = True
        await write_event(
            self.session, self.run_id, "tools", "tool_call", {"tool": name, "args": args}
        )
        started = monotonic()
        key = f"tool:{self.run_id}:{name}:{sha256(str(sorted(args.items())).encode()).hexdigest()}"
        try:
            cached = await cache_get_json(key) if ttl else None
            value = schema.model_validate(cached) if cached is not None else await operation()
            if ttl and cached is None:
                await cache_set_json(key, value.model_dump(mode="json"), ttl)
            result = ToolResult[T](ok=True, value=value, cache_hit=cached is not None)
        except Exception as exc:
            # Provider quota/budget errors retain their typed graph/worker semantics.
            from app.llm.gemini import ModelError
            if isinstance(exc, ModelError):
                raise
            # Tool contract: errors become explicit results and escalation state.
            await self.session.rollback()
            self.state["tool_error"] = f"{name}: {type(exc).__name__}"
            result = ToolResult[T](ok=False, error=self.state["tool_error"])
        await write_event(
            self.session,
            self.run_id,
            "tools",
            "tool_result",
            {"tool": name, **result.model_dump(mode="json")},
            int((monotonic() - started) * 1000),
        )
        return result

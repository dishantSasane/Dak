"""Schema-constrained Gemini boundary with counted retries and an eight-call cap."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Run
from app.llm.rate_limit import RateLimiter
from app.tools.base import write_event

MAX_MODEL_CALLS = 8


class ModelError(RuntimeError):
    pass


class ModelOutputInvalid(ModelError):
    pass


class ModelBudgetExceeded(ModelError):
    pass


class ModelUnavailable(ModelError):
    pass


class ModelRateLimited(ModelError):
    pass


class ModelClient(Protocol):
    async def generate[T: BaseModel](
        self,
        *,
        session: AsyncSession,
        run_id: int,
        node: str,
        schema: type[T],
        system: str,
        prompt: str,
        light: bool = False,
        eval_run: bool = False,
    ) -> T: ...


class GeminiAdapter:
    def __init__(
        self,
        *,
        transport: Callable[..., Awaitable[Any]] | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.transport = transport
        self.limiter = limiter or RateLimiter()

    async def _send(self, model: str, system: str, prompt: str, schema: type[BaseModel]) -> Any:
        from google import genai
        from google.genai import types

        async with genai.Client(
            api_key=get_settings().GEMINI_API_KEY, http_options=types.HttpOptions(timeout=45_000)
        ).aio as client:
            return await client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

    async def generate[T: BaseModel](
        self,
        *,
        session: AsyncSession,
        run_id: int,
        node: str,
        schema: type[T],
        system: str,
        prompt: str,
        light: bool = False,
        eval_run: bool = False,
    ) -> T:
        from google.genai.errors import APIError

        settings = get_settings()
        if self.transport is None and settings.GEMINI_API_KEY in ("test-only", "replace-me"):
            raise ModelUnavailable("Configure GEMINI_API_KEY locally to enable live generation")
        model = settings.GEMINI_MODEL_TRIAGE if light else settings.GEMINI_MODEL_DRAFT
        for attempt in range(3):
            await self.limiter.acquire(eval_run=eval_run)
            run = await session.scalar(
                select(Run)
                .where(Run.id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if run is None:
                raise ModelUnavailable("Run no longer exists")
            if run.model_calls >= MAX_MODEL_CALLS:
                await session.rollback()
                raise ModelBudgetExceeded("Eight-call budget exhausted, including retries")
            run.model_calls += 1
            await session.commit()
            started = monotonic()
            payload: dict[str, Any] = {
                "model": model,
                "attempt": attempt + 1,
                "schema": schema.__name__,
                "provider": "recorded_fixture" if self.transport is not None else "gemini",
                "cache_hit": False,
            }
            try:
                response = await (self.transport or self._send)(model, system, prompt, schema)
                usage = getattr(response, "usage_metadata", None)
                prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
                completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
                await session.execute(
                    update(Run)
                    .where(Run.id == run_id)
                    .values(
                        total_prompt_tokens=Run.total_prompt_tokens + prompt_tokens,
                        total_completion_tokens=Run.total_completion_tokens + completion_tokens,
                    )
                )
                await session.commit()
                payload.update(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
                parsed = getattr(response, "parsed", None)
                result = (
                    schema.model_validate(parsed)
                    if parsed is not None
                    else (schema.model_validate_json(response.text or ""))
                )
            except ValidationError as exc:
                payload["error"] = "model_output_invalid"
                await write_event(
                    session,
                    run_id,
                    node,
                    "model_call",
                    payload,
                    int((monotonic() - started) * 1000),
                )
                if attempt == 2:
                    raise ModelOutputInvalid(
                        "Malformed structured output after three attempts"
                    ) from exc
                await asyncio.sleep(2**attempt)
                continue
            except APIError as exc:
                payload["error"] = f"provider_http_{exc.code}"
                await write_event(
                    session,
                    run_id,
                    node,
                    "model_call",
                    payload,
                    int((monotonic() - started) * 1000),
                )
                if exc.code == 429:
                    raise ModelRateLimited("Provider quota requires worker backoff") from exc
                raise ModelUnavailable(f"Gemini provider returned HTTP {exc.code}") from exc
            except (OSError, TimeoutError) as exc:
                payload["error"] = type(exc).__name__
                await write_event(
                    session,
                    run_id,
                    node,
                    "model_call",
                    payload,
                    int((monotonic() - started) * 1000),
                )
                raise ModelUnavailable("Gemini transport unavailable") from exc
            await write_event(
                session, run_id, node, "model_call", payload, int((monotonic() - started) * 1000)
            )
            return result
        raise ModelOutputInvalid("No validated response")

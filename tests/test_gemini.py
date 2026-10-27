from types import SimpleNamespace
from uuid import uuid4

import pytest
from google.genai.errors import APIError
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Case, Email, Run, RunEvent
from app.llm.gemini import GeminiAdapter, ModelBudgetExceeded, ModelOutputInvalid, ModelRateLimited
from app.llm.rate_limit import RateLimiter


class Result(BaseModel):
    value: str


class NoWait(RateLimiter):
    async def acquire(self, *, eval_run: bool = False) -> None:
        return None


@pytest.fixture
async def generation_run(database):
    session, _ = database
    case = Case(token="INS-7K3M-2XQ9", contact_email="fixture@example.test")
    session.add(case)
    await session.flush()
    email = Email(
        case_id=case.id,
        message_id=str(uuid4()),
        direction="inbound",
        sender=case.contact_email,
        recipient="demo@example.test",
    )
    session.add(email)
    await session.flush()
    run = Run(email_id=email.id, case_id=case.id, thread_id=str(uuid4()), status="running")
    session.add(run)
    await session.commit()
    return session, run


def response(parsed=None, text=None):
    return SimpleNamespace(
        parsed=parsed,
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=3, candidates_token_count=2),
    )


async def invoke(adapter, session, run):
    return await adapter.generate(
        session=session,
        run_id=run.id,
        node="triage",
        schema=Result,
        system="instructions",
        prompt="untrusted email",
        light=True,
    )


async def test_schema_validated_accounted_and_traced(generation_run):
    session, run = generation_run

    async def send(*args):
        return response({"value": "ok"})

    result = await invoke(GeminiAdapter(transport=send, limiter=NoWait()), session, run)
    assert result.value == "ok"
    await session.refresh(run)
    assert (run.model_calls, run.total_prompt_tokens, run.total_completion_tokens) == (1, 3, 2)
    event = await session.scalar(select(RunEvent).where(RunEvent.run_id == run.id))
    assert event.event_type == "model_call"
    assert event.payload["schema"] == "Result"


async def test_malformed_output_retries_twice_then_typed_failure(generation_run):
    session, run = generation_run

    async def send(*args):
        return response(text="not json")

    with pytest.raises(ModelOutputInvalid):
        await invoke(GeminiAdapter(transport=send, limiter=NoWait()), session, run)
    await session.refresh(run)
    assert run.model_calls == 3
    assert run.total_prompt_tokens == 9
    events = (await session.scalars(select(RunEvent).where(RunEvent.run_id == run.id))).all()
    assert len(events) == 3
    assert all(event.payload["error"] == "model_output_invalid" for event in events)


async def test_budget_counts_failed_attempts_and_prevents_ninth_call(generation_run):
    session, run = generation_run
    run.model_calls = 7
    await session.commit()
    calls = []

    async def send(*args):
        calls.append(1)
        return response(text="bad")

    with pytest.raises(ModelBudgetExceeded):
        await invoke(GeminiAdapter(transport=send, limiter=NoWait()), session, run)
    await session.refresh(run)
    assert run.model_calls == 8 and len(calls) == 1


async def test_429_is_observable_and_requires_worker_backoff(generation_run):
    session, run = generation_run

    async def send(*args):
        raise APIError(429, {"error": {"code": 429, "message": "fixture quota"}})

    with pytest.raises(ModelRateLimited):
        await invoke(GeminiAdapter(transport=send, limiter=NoWait()), session, run)
    event = await session.scalar(select(RunEvent).where(RunEvent.run_id == run.id))
    assert event.payload["error"] == "provider_http_429"


async def test_redis_limiter_reserves_global_and_lower_priority_eval_slots(monkeypatch):
    from app.config import get_settings
    from app.redis_client import get_redis

    redis = get_redis()
    await redis.delete("gemini:next-call", "gemini:eval-next")
    monkeypatch.setattr(get_settings(), "RPM_LIMIT", 1000)
    limiter = RateLimiter()
    await limiter.acquire()
    first_global = float(await redis.get("gemini:next-call"))
    await limiter.acquire(eval_run=True)
    next_global = float(await redis.get("gemini:next-call"))
    eval_ready = float(await redis.get("gemini:eval-next"))
    assert next_global >= first_global + 59
    assert eval_ready >= next_global + 59
    await redis.delete("gemini:next-call", "gemini:eval-next")

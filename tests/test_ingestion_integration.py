"""Requires migrated PostgreSQL and Redis; see README for isolated service setup."""

import hashlib
import hmac
import os
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from app.api import webhook
from app.db.models import Case, Email, Run
from app.db.session import get_session
from app.main import app
from app.services.cases import resolve_case
from app.workers.process import process_email


@pytest.fixture
async def client(database, monkeypatch):
    session, _ = database

    async def dependency():
        yield session

    app.dependency_overrides[get_session] = dependency
    monkeypatch.setattr(webhook, "enqueue_email_processing", AsyncMock())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def post(client, payload):
    import json

    body = json.dumps(payload).encode()
    signature = hmac.new(
        os.environ["CLOUDMAILIN_SECRET"].encode(), body, hashlib.sha256
    ).hexdigest()
    return await client.post("/webhook/email", content=body, headers={"X-CM-Signature": signature})


async def test_webhook_deduplicates_and_public_case_is_safe(client, database):
    session, _ = database
    payload = {
        "sender": "demo@example.com",
        "subject": "<script>alert(1)</script>",
        "plain": "x" * 300,
        "headers": {"Message-ID": "<dedupe@example.com>"},
    }
    first = await post(client, payload)
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    second = await post(client, payload)
    assert second.json() == {"status": "duplicate"}
    assert await session.scalar(select(func.count()).select_from(Email)) == 1
    assert await session.scalar(select(func.count()).select_from(Case)) == 1
    token = first.json()["token"]
    public = await client.get(f"/api/cases/{token}")
    assert len(public.json()["emails"][0]["preview"]) == 200
    page = await client.get(f"/t/{token}")
    assert "<script>" not in page.text
    assert "&lt;script&gt;" in page.text
    assert (await client.get("/api/cases/unknown")).status_code == 404


async def test_invalid_signature_never_persists(client, database):
    response = await client.post("/webhook/email", json={"sender": "x"})
    assert response.status_code == 401
    assert await database[0].scalar(select(func.count()).select_from(Email)) == 0


async def test_unparseable_payload_stored_once(client, database):
    for _ in range(2):
        response = await post(client, {"headers": []})
        assert response.status_code == 200
    emails = (await database[0].scalars(select(Email))).all()
    assert len(emails) == 1
    assert emails[0].raw_payload["unparseable"] is True


async def test_queue_outage_recovers_on_provider_retry(client, database, monkeypatch):
    payload = {"sender": "demo@example.com", "headers": {"message_id": "<retry@example.com>"}}
    monkeypatch.setattr(
        webhook, "enqueue_email_processing", AsyncMock(side_effect=OSError("offline"))
    )
    assert (await post(client, payload)).status_code == 503
    monkeypatch.setattr(webhook, "enqueue_email_processing", AsyncMock())
    assert (await post(client, payload)).json()["status"] == "duplicate"
    assert await database[0].scalar(select(func.count()).select_from(Email)) == 1


async def test_four_resolution_paths(database):
    session, _ = database
    case, created = await resolve_case(session, subject="ASP-2024-4471", sender="demo@example.com")
    assert created
    session.add(
        Email(
            case_id=case.id,
            message_id="<parent@example.com>",
            direction="inbound",
            sender="demo@example.com",
            recipient="inbox@example.com",
        )
    )
    await session.commit()
    for arguments in [
        {"subject": f"Re: [{case.token}]", "in_reply_to": "<mangled>"},
        {"subject": "reply", "in_reply_to": "<parent@example.com>"},
        {"subject": "reply", "references": "<old> <parent@example.com>"},
        {"subject": "ASP-2024-4471"},
    ]:
        resolved, created = await resolve_case(session, sender="demo@example.com", **arguments)
        assert resolved.id == case.id and not created
    other, created = await resolve_case(session, subject="new", sender="other@example.com")
    assert created and other.id != case.id


async def test_worker_retries_create_one_run(client, database, monkeypatch):
    _, factory = database
    from app.workers import process

    monkeypatch.setattr(process, "get_sessionmaker", lambda: factory)
    await post(client, {"sender": "demo@example.com"})
    email_id = await database[0].scalar(select(Email.id))
    first = await process_email({}, email_id)
    second = await process_email({}, email_id)
    assert first == second
    async with factory() as session:
        runs = (await session.scalars(select(Run))).all()
        assert len(runs) == 1
        assert runs[0].status == "escalated"
        assert runs[0].escalation_reason == "model_output_invalid"


async def test_tool_events_cache_and_customer_guard(client, database):
    from app.db.models import RunEvent
    from app.models.schemas import PolicyLookupResult
    from app.tools.base import ToolContext
    from app.tools.policy import lookup_policy

    session, _ = database
    await post(client, {"sender": "demo@example.com"})
    email = await session.scalar(select(Email))
    run = Run(email_id=email.id, case_id=email.case_id, thread_id="tool-test", status="running")
    session.add(run)
    await session.commit()
    state = {}
    context = ToolContext(session, run.id, state)

    async def operation():
        return await lookup_policy(session, "ASP-0000-0000")

    first = await context.call(
        "lookup_policy", {"policy_number": "ASP-0000-0000"}, operation, PolicyLookupResult
    )
    second = await context.call(
        "lookup_policy", {"policy_number": "ASP-0000-0000"}, operation, PolicyLookupResult
    )
    assert first.ok and first.value.found is False
    assert not first.cache_hit and second.cache_hit
    assert not state.get("used_customer_tools")
    await context.call(
        "get_policy_details",
        {"policy_number": "ASP-0000-0000"},
        operation,
        PolicyLookupResult,
        customer=True,
    )
    assert state["used_customer_tools"] is True
    events = (
        await session.scalars(
            select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)
        )
    ).all()
    assert [event.seq for event in events] == list(range(1, 7))
    assert events[3].payload["cache_hit"] is True


async def test_real_queue_processes_email(client, database, monkeypatch):
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.worker import Worker

    from app.config import get_settings
    from app.redis_client import enqueue_email_processing
    from app.workers import process

    session, factory = database
    monkeypatch.setattr(process, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(webhook, "enqueue_email_processing", enqueue_email_processing)
    response = await post(client, {"sender": "queued@example.test", "subject": "Real local queue"})
    assert response.status_code == 200
    pool = await create_pool(RedisSettings.from_dsn(get_settings().REDIS_URL))
    worker = Worker([process_email], redis_pool=pool, burst=True, handle_signals=False)
    try:
        await worker.async_run()
    finally:
        await worker.close()
    async with factory() as verification:
        run = await verification.scalar(
            select(Run).join(Email).where(Email.sender == "queued@example.test")
        )
        assert run is not None and run.escalation_reason == "model_output_invalid"


async def test_seed_loader_and_policy_tools(database, monkeypatch):
    import json
    from pathlib import Path

    from app.db import session as sessions
    from app.db.models import Policy
    from app.tools.base import ToolContext
    from app.tools.policy import PolicyTools
    from scripts.seed import load

    session, factory = database
    monkeypatch.setattr(sessions, "get_sessionmaker", lambda: factory)
    await session.execute(text("TRUNCATE policies CASCADE"))
    await session.commit()
    root = Path("data/seeds")
    rows = [
        json.loads((root / f"{name}.json").read_text())
        for name in ["policies", "claims", "grievances"]
    ]
    await load(*rows)
    case = Case(token="INS-7K3M-2XQ9", contact_email="demo@example.test")
    session.add(case)
    await session.flush()
    email = Email(
        case_id=case.id,
        message_id="tools-seed",
        direction="inbound",
        sender="demo",
        recipient="demo",
    )
    session.add(email)
    await session.flush()
    run = Run(email_id=email.id, case_id=case.id, thread_id="seed-tools")
    session.add(run)
    await session.commit()
    state = {}
    tools = PolicyTools(ToolContext(session, run.id, state))
    for status in ["active", "lapsed", "cancelled"]:
        policy = await session.scalar(select(Policy).where(Policy.status == status).limit(1))
        result = await tools.lookup_policy(policy.policy_number)
        assert result.ok and result.value.found
        assert result.value.active == (status == "active")
        assert not state.get("used_customer_tools")
    await tools.get_policy_details(rows[0][0]["policy_number"])
    assert state["used_customer_tools"]
    state.clear()
    await tools.get_case_history(rows[0][0]["policy_number"])
    assert state["used_customer_tools"]


async def test_manual_submission_existing_run_is_processed(client, database, monkeypatch):
    from app.api import routes_manual
    from app.workers import process

    session, factory = database
    monkeypatch.setattr(routes_manual, "enqueue_email_processing", AsyncMock())
    monkeypatch.setattr(process, "get_sessionmaker", lambda: factory)
    response = await client.post(
        "/api/manual-email",
        json={
            "sender": "manual@example.test",
            "subject": "Coverage",
            "body": "How does co-pay work?",
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    email_id = await session.scalar(select(Run.email_id).where(Run.id == run_id))
    assert await process_email({}, email_id) == run_id
    async with factory() as verification:
        runs = (await verification.scalars(select(Run))).all()
        assert len(runs) == 1
        assert runs[0].status == "escalated"


async def test_cloudmailin_bearer_authorization(client):
    response = await client.post(
        "/webhook/email",
        json={
            "envelope": {"from": "demo@example.test", "to": "inbox@example.test"},
            "headers": {"message_id": "<cloudmailin@example.test>", "subject": "Question"},
            "plain": "What is co-pay?",
        },
        headers={"Authorization": f"Bearer {os.environ['CLOUDMAILIN_SECRET']}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

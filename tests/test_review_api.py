"""Database-backed review safety and citation provenance checks."""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes_review import review_action, review_detail, review_queue
from app.db.models import Case, Draft, Email, Review, Run, RunEvent
from app.models.schemas import ReviewActionRequest


async def make_run(session, status="pending_review"):
    case = Case(token="INS-APIT-0001", contact_email="demo@example.test")
    session.add(case)
    await session.flush()
    email = Email(
        case_id=case.id,
        message_id="api-review-test",
        direction="inbound",
        sender=case.contact_email,
        recipient="demo@example.test",
        subject="Synthetic coverage",
        body_plain="Synthetic email body",
    )
    session.add(email)
    await session.flush()
    run = Run(email_id=email.id, case_id=case.id, thread_id="api-test", status=status)
    session.add(run)
    await session.commit()
    return run


async def test_latest_attempt_and_snapshot_citations(database):
    session, _ = database
    run = await make_run(session)
    session.add_all(
        [
            Draft(
                run_id=run.id,
                attempt=1,
                sentences=[],
                rendered_text="blocked",
                validation_passed=False,
            ),
            Draft(
                run_id=run.id,
                attempt=2,
                sentences=[{"kind": "factual", "text": "Covered", "cite": "ASP-C01"}],
                rendered_text="Covered",
                validation_passed=True,
            ),
            RunEvent(
                run_id=run.id,
                seq=1,
                node="query_agent",
                event_type="node_end",
                payload={
                    "retrieved_chunks": [
                        {
                            "clause_id": "ASP-C01",
                            "clause_title": "Actual snapshot",
                            "content": "Retrieved content",
                            "score": 0.9,
                        }
                    ],
                    "internal_note": "Reviewer note",
                },
            ),
        ]
    )
    await session.commit()
    queue = await review_queue(
        status="pending_review", category=None, limit=50, offset=0, session=session
    )
    assert queue["items"][0]["validation_passed"] is True
    detail = await review_detail(run.id, session)
    assert len(detail["drafts"]) == 2
    assert detail["citations"][0]["content"] == "Retrieved content"
    assert detail["internal_note"] == "Reviewer note"


async def test_review_rejects_unvalidated_and_empty_edits(database):
    session, _ = database
    run = await make_run(session)
    for body, status in [
        (ReviewActionRequest(action="approved"), 409),
        (ReviewActionRequest(action="edited", edited_text=" "), 422),
    ]:
        with pytest.raises(HTTPException) as error:
            await review_action(run.id, body, session)
        assert error.value.status_code == status
    await review_action(run.id, ReviewActionRequest(action="rejected"), session)
    with pytest.raises(HTTPException) as error:
        await review_action(run.id, ReviewActionRequest(action="rejected"), session)
    assert error.value.status_code == 409


async def test_concurrent_reviews_record_one_decision(database):
    session, factory = database
    run = await make_run(session)

    async def decide():
        async with factory() as other:
            try:
                await review_action(run.id, ReviewActionRequest(action="rejected"), other)
                return 200
            except HTTPException as error:
                return error.status_code

    assert sorted(await asyncio.gather(decide(), decide())) == [200, 409]
    assert len((await session.execute(select(Review))).scalars().all()) == 1

from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy import select

from app.db.models import Case, Email, Run
from app.workers.process import reconcile_pending


async def test_reconciliation_recovers_undispatched_email_and_skips_invalid_or_terminal(
    database, monkeypatch
):
    from app.workers import process

    session, factory = database
    monkeypatch.setattr(process, "get_sessionmaker", lambda: factory)
    case = Case(token="INS-7K3M-2XQ9", contact_email="demo@example.test")
    session.add(case)
    await session.flush()
    emails = []
    for raw in [{}, {"unparseable": True}, {}]:
        email = Email(
            case_id=case.id,
            message_id=str(uuid4()),
            direction="inbound",
            sender=case.contact_email,
            recipient="inbox@example.test",
            raw_payload=raw,
        )
        session.add(email)
        emails.append(email)
    await session.flush()
    session.add(
        Run(email_id=emails[2].id, case_id=case.id, thread_id=str(uuid4()), status="approved")
    )
    await session.commit()
    redis = AsyncMock()
    assert await reconcile_pending({"redis": redis}) == 1
    redis.enqueue_job.assert_awaited_once_with(
        "process_email", emails[0].id, _job_id=f"email:{emails[0].id}"
    )
    assert await session.scalar(select(Run.id).where(Run.email_id == emails[0].id)) is None

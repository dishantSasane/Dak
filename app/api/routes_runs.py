"""Run events endpoint — 05-api-and-ui.md §1.2.

GET /api/runs/{run_id}/events with ?after_seq=N so the UI polls for new
events rather than refetching the whole trace.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunEvent
from app.db.session import get_session
from app.models.schemas import RunEventItem, RunEventsResponse

router = APIRouter(tags=["runs"])


@router.get("/api/runs/{run_id}/events", response_model=RunEventsResponse)
async def get_run_events(
    run_id: int,
    after_seq: int = Query(default=0, ge=0),
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RunEventsResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    events = (
        (
            await session.execute(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
                .order_by(RunEvent.seq)
            )
        )
        .scalars()
        .all()
    )

    return RunEventsResponse(
        run_id=run.id,
        status=run.status,
        events=[
            RunEventItem(
                seq=e.seq,
                node=e.node,
                event_type=e.event_type,
                payload=e.payload,
                duration_ms=e.duration_ms,
                created_at=e.created_at,
            )
            for e in events
        ],
    )


@router.get("/api/runs")
async def recent_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=30, ge=1, le=200),
) -> dict:
    """Synthetic demo workspace; never expose real customer data here."""
    from app.db.models import Case, Email

    rows = (
        await session.execute(
            select(Run, Email, Case.token)
            .join(Email, Email.id == Run.email_id)
            .join(Case, Case.id == Run.case_id)
            .order_by(Run.started_at.desc())
            .limit(limit)
        )
    ).all()
    return {
        "items": [
            dict(_run_summary(run), subject=email.subject, **{"from": email.sender}, token=token)
            for run, email, token in rows
        ]
    }


def _run_summary(run: Run) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "category": run.category,
        "confidence": float(run.confidence) if run.confidence is not None else None,
        "route": run.route,
        "escalation_reason": run.escalation_reason,
        "started_at": run.started_at.isoformat(),
        "duration_ms": run.duration_ms,
    }


@router.get("/api/runs/{run_id}/detail")
async def run_detail(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Full email for the synthetic reviewer/demo workspace, not public cases."""
    from app.db.models import Case, Email

    row = (
        await session.execute(
            select(Run, Email, Case.token)
            .join(Email, Email.id == Run.email_id)
            .join(Case, Case.id == Run.case_id)
            .where(Run.id == run_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    run, email, token = row
    return {
        "run": _run_summary(run),
        "token": token,
        "email": {
            "subject": email.subject,
            "body_plain": email.body_plain,
            "from": email.sender,
            "received_at": email.received_at.isoformat(),
        },
    }

"""Run events endpoint — 05-api-and-ui.md §1.2.

GET /api/runs/{run_id}/events with ?after_seq=N so the UI polls for new
events rather than refetching the whole trace.
"""

from __future__ import annotations

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
    session: AsyncSession = Depends(get_session),
) -> RunEventsResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    events = (
        await session.execute(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq)
        )
    ).scalars().all()

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

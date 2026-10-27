"""Review queue endpoints — 05-api-and-ui.md §1.3.

GET /api/review/queue, GET /api/review/{run_id}, POST /api/review/{run_id}/action.
v1 records the decision; it does not send email.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Case, CaseFile, Draft, Email, Review, Run, RunEvent
from app.db.session import get_session
from app.models.schemas import ReviewActionRequest

router = APIRouter(tags=["review"])


@router.get("/api/review/queue")
async def review_queue(
    status: str = Query(default="pending_review"),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    conditions = [Run.status == status]
    if category:
        conditions.append(Run.category == category)

    total = await session.scalar(select(func.count()).select_from(Run).where(*conditions))

    rows = (
        await session.execute(
            select(Run, Case.token, Email.subject, Email.sender, Draft.validation_passed)
            .join(Case, Case.id == Run.case_id)
            .join(Email, Email.id == Run.email_id)
            .outerjoin(
                Draft,
                (Draft.run_id == Run.id)
                & (
                    Draft.attempt
                    == select(func.max(Draft.attempt))
                    .where(Draft.run_id == Run.id)
                    .correlate(Run)
                    .scalar_subquery()
                ),
            )
            .where(*conditions)
            .order_by(Run.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    items = [
        {
            "run_id": run.id,
            "token": token,
            "category": run.category,
            "confidence": float(run.confidence) if run.confidence is not None else None,
            "subject": subject,
            "from": sender,
            "escalation_reason": run.escalation_reason,
            "waiting_since": run.started_at.isoformat(),
            "validation_passed": validation_passed,
        }
        for run, token, subject, sender, validation_passed in rows
    ]
    return {"total": int(total or 0), "items": items}


@router.get("/api/review/{run_id}")
async def review_detail(
    run_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    email = await session.get(Email, run.email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="email not found")

    drafts = (
        (await session.execute(select(Draft).where(Draft.run_id == run_id).order_by(Draft.attempt)))
        .scalars()
        .all()
    )
    events = (
        (
            await session.execute(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    case_file = await session.scalar(select(CaseFile).where(CaseFile.run_id == run_id))

    # citations resolved from the latest draft's clause refs
    citations: list[dict] = []
    if drafts:
        latest = drafts[-1]
        used: dict[str, list[int]] = {}
        for idx, sentence in enumerate(latest.sentences):
            cite = sentence.get("cite")
            if cite:
                used.setdefault(cite, []).append(idx)
        # Resolve only against chunks actually retrieved for this attempt. A
        # corpus lookup by clause ID can silently display a different version.
        snapshot = []
        for event in events:
            if event.event_type == "node_end" and "retrieved_chunks" in event.payload:
                snapshot = event.payload["retrieved_chunks"]
        citations = [
            {
                "clause_id": chunk["clause_id"],
                "clause_title": chunk["clause_title"],
                "content": chunk["content"],
                "used_in_sentences": used[chunk["clause_id"]],
            }
            for chunk in snapshot
            if chunk.get("clause_id") in used
        ]

    triage_payload: dict = {}
    for e in events:
        if e.node == "triage" and e.event_type == "node_end":
            triage_payload = e.payload

    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "category": run.category,
            "confidence": float(run.confidence) if run.confidence is not None else None,
            "route": run.route,
            "escalation_reason": run.escalation_reason,
            "reroute_count": run.reroute_count,
            "validator_retry_count": run.validator_retry_count,
            "started_at": run.started_at.isoformat(),
        },
        "email": {
            "subject": email.subject,
            "body_plain": email.body_plain,
            "from": email.sender,
            "received_at": email.received_at.isoformat(),
        },
        "triage": triage_payload,
        "drafts": [
            {
                "attempt": d.attempt,
                "rendered_text": d.rendered_text,
                "sentences": d.sentences,
                "validation_passed": d.validation_passed,
                "violations": d.violations,
            }
            for d in drafts
        ],
        "citations": citations,
        "case_file": (
            {
                "policy_status": case_file.policy_status,
                "coverage_assessment": case_file.coverage_assessment,
                "eligibility": case_file.eligibility,
                "missing_documents": case_file.missing_documents,
                "recommendation": case_file.recommendation,
            }
            if case_file
            else None
        ),
        "internal_note": next(
            (
                e.payload["internal_note"]
                for e in reversed(events)
                if e.payload.get("internal_note")
            ),
            None,
        ),
        "escalation_brief": next(
            (
                e.payload["escalation_brief"]
                for e in reversed(events)
                if e.payload.get("escalation_brief")
            ),
            None,
        ),
        "events": [
            {
                "seq": e.seq,
                "node": e.node,
                "event_type": e.event_type,
                "payload": e.payload,
                "duration_ms": e.duration_ms,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.post("/api/review/{run_id}/action")
async def review_action(
    run_id: int,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status not in {"pending_review", "escalated"}:
        raise HTTPException(status_code=409, detail="run is not awaiting review")
    if body.action == "edited" and not (body.edited_text or "").strip():
        raise HTTPException(status_code=422, detail="edited_text must not be empty")
    if body.action == "approved":
        latest = await session.scalar(
            select(Draft).where(Draft.run_id == run_id).order_by(Draft.attempt.desc()).limit(1)
        )
        if latest is None or not latest.validation_passed:
            raise HTTPException(status_code=409, detail="approval requires a validated draft")

    existing = await session.scalar(select(Review).where(Review.run_id == run_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="already reviewed")

    session.add(
        Review(
            run_id=run_id,
            action=body.action,
            edited_text=body.edited_text,
            reviewer_note=body.reviewer_note,
        )
    )
    run.status = body.action  # approved | rejected map onto run statuses; edited -> approved
    if body.action == "edited":
        run.status = "approved"
    await session.commit()
    return {"status": "recorded"}

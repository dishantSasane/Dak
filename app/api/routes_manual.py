"""POST /api/manual-email — the browser "paste an email" path, §1.1.

Same pipeline as the webhook (case resolution → insert → enqueue), with
IP rate limiting of 10/hour because it is a public endpoint that costs
model quota. Returns 202 {token, run_id}.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Email, Run
from app.db.session import get_session
from app.inbound.cloudmailin import ParsedEmail
from app.models.schemas import ManualEmailRequest
from app.redis_client import enqueue_email_processing
from app.services.cases import resolve_case

router = APIRouter(tags=["ingestion"])

# In-process sliding-window limiter. Sufficient for a single-container free
# tier; swap for Redis if the API ever scales horizontally.
_WINDOW_SECONDS = 3600
_MAX_PER_WINDOW = 10
_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    if len(q) >= _MAX_PER_WINDOW:
        return True
    q.append(now)
    return False


@router.post("/api/manual-email", status_code=202)
async def manual_email(
    request: Request, body: ManualEmailRequest, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        return JSONResponse(
            status_code=429, content={"status": "rate_limited", "limit": "10/hour"}
        )

    parsed = ParsedEmail(
        sender=body.sender,
        recipient="support@claims.thebreakpoint.online",
        subject=body.subject,
        plain=body.body,
        html="",
        message_id=f"manual-{uuid.uuid4()}@local",
        in_reply_to=None,
        headers={},
    )

    case, _created = await resolve_case(
        session, subject=parsed.subject, sender=parsed.sender, body=parsed.plain
    )

    email = Email(
        case_id=case.id,
        message_id=parsed.message_id,
        direction="inbound",
        sender=parsed.sender,
        recipient=parsed.recipient,
        subject=parsed.subject,
        body_plain=parsed.plain,
        raw_payload={"source": "manual"},
    )
    session.add(email)
    await session.flush()

    # Create the run row up front so we can return its id with the 202.
    run = Run(
        email_id=email.id,
        case_id=case.id,
        thread_id=str(uuid.uuid4()),
        status="running",
    )
    session.add(run)
    await session.commit()

    try:
        await enqueue_email_processing(email.id)
    except Exception:  # noqa: BLE001 - queue outage must not lose the submission
        pass

    return JSONResponse(status_code=202, content={"token": case.token, "run_id": run.id})

"""POST /webhook/email — T1.4, 05-api-and-ui.md §1.1, 02-architecture.md §1.1.

Ordering is load-bearing: signature → parse → case resolution → INSERT email
(unique on message_id) → commit → enqueue → 200. Never 500 on a parse failure:
store the raw payload, mark unparseable, return 200.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Case, Email
from app.db.session import get_session
from app.inbound.cloudmailin import SIGNATURE_HEADER, ParsedEmail, parse_payload, verify_signature
from app.redis_client import enqueue_email_processing
from app.services.cases import resolve_case

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


async def _insert_email(
    session: AsyncSession, case_id: int, parsed: ParsedEmail, raw_payload: dict
) -> tuple[int, bool]:
    """INSERT ... ON CONFLICT (message_id) DO NOTHING. Returns (email_id, inserted)."""
    stmt = (
        pg_insert(Email)
        .values(
            case_id=case_id,
            message_id=parsed.message_id,
            direction="inbound",
            sender=parsed.sender,
            recipient=parsed.recipient,
            subject=parsed.subject,
            body_plain=parsed.plain,
            body_html=parsed.html,
            in_reply_to=parsed.in_reply_to,
            raw_payload=raw_payload,
        )
        .on_conflict_do_nothing(index_elements=["message_id"])
        .returning(Email.id)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        existing_id = await session.scalar(select(Email.id).where(Email.message_id == parsed.message_id))
        return int(existing_id), False
    return int(row[0]), True


@router.post("/webhook/email")
async def webhook_email(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    settings = get_settings()
    body = await request.body()

    # 1. Verify provider signature (ALLOW_UNSIGNED_WEBHOOK is local-testing only).
    if not settings.ALLOW_UNSIGNED_WEBHOOK:
        signature = request.headers.get(SIGNATURE_HEADER)
        if not verify_signature(body, signature, settings.CLOUDMAILIN_SECRET):
            logger.warning("webhook signature verification failed")
            return JSONResponse(status_code=401, content={"status": "unauthorized"})

    # 2. Parse provider payload. Never 500 on parse failure.
    raw_json: dict = {}
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            raw_json = payload
        parsed = parse_payload(raw_json)
        unparseable = False
    except Exception:  # noqa: BLE001 - boundary: any provider payload shape must yield 200
        parsed = None
        unparseable = True

    if parsed is None:
        # Store the raw payload, mark unparseable, return 200 so the provider
        # does not retry an email that will fail identically every time.
        import hashlib

        from app.tokens import generate_token

        digest = hashlib.sha256(body).hexdigest()[:16]
        case = await session.scalar(select(Case).where(Case.contact_email == "unknown@unparseable.local"))
        if case is None:
            case = Case(token=generate_token(), contact_email="unknown@unparseable.local")
            session.add(case)
            await session.flush()
        stmt = (
            pg_insert(Email)
            .values(
                case_id=case.id,
                message_id=f"unparseable-{digest}",
                direction="inbound",
                sender="unknown@unparseable.local",
                recipient="",
                subject="",
                body_plain="",
                body_html="",
                raw_payload={"unparseable": True, "raw": body.decode("utf-8", "replace")[:65536]},
            )
            .on_conflict_do_nothing(index_elements=["message_id"])
        )
        await session.execute(stmt)
        await session.commit()
        return JSONResponse(status_code=200, content={"status": "accepted", "token": case.token})

    # 3. Resolve or create the case (four steps, spec order — T1.3).
    case, _created = await resolve_case(
        session,
        subject=parsed.subject,
        sender=parsed.sender,
        in_reply_to=parsed.in_reply_to,
        references=parsed.headers.get("references"),
        body=parsed.plain,
    )

    # 4. INSERT email (idempotent on message_id) BEFORE enqueue.
    email_id, inserted = await _insert_email(session, case.id, parsed, raw_json)
    await session.commit()

    if not inserted:
        return JSONResponse(status_code=200, content={"status": "duplicate"})

    # 5. Enqueue {email_id} — only after the insert committed.
    try:
        await enqueue_email_processing(email_id)
    except Exception as exc:  # noqa: BLE001 - queue outage must not bounce the provider
        logger.error("enqueue failed for email %s: %s", email_id, exc)

    # 6. Return 200.
    return JSONResponse(status_code=200, content={"status": "accepted", "token": case.token})

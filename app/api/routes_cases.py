"""Public case view and minimal case page — T1.6, 05-api-and-ui.md §1.2.

GET /api/cases/{token} — no auth; the token is the credential.
Never returns body_plain in full, never returns a draft before review.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Case, Email, Run
from app.db.session import get_session
from app.models.schemas import CaseEmailItem, CasePublicResponse, CaseRunItem

router = APIRouter(tags=["cases"])


async def _get_case(session: AsyncSession, token: str) -> Case:
    case = await session.scalar(select(Case).where(Case.token == token))
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@router.get("/api/cases/{token}", response_model=CasePublicResponse)
async def get_case(token: str, session: AsyncSession = Depends(get_session)) -> CasePublicResponse:
    case = await _get_case(session, token)

    emails = (
        await session.execute(
            select(Email).where(Email.case_id == case.id).order_by(Email.received_at)
        )
    ).scalars().all()
    runs = (
        await session.execute(
            select(Run).where(Run.case_id == case.id).order_by(Run.started_at)
        )
    ).scalars().all()

    return CasePublicResponse(
        token=case.token,
        status=case.status,
        created_at=case.created_at,
        emails=[
            CaseEmailItem(
                direction=e.direction,
                subject=e.subject,
                received_at=e.received_at,
                # preview only — never body_plain in full on a public page
                preview=(e.body_plain or "")[:200],
            )
            for e in emails
        ],
        runs=[
            CaseRunItem(
                id=r.id,
                status=r.status,
                category=r.category,
                confidence=float(r.confidence) if r.confidence is not None else None,
                route=r.route,
                escalation_reason=r.escalation_reason,
                duration_ms=r.duration_ms,
            )
            for r in runs
        ],
    )


@router.get("/t/{token}", response_class=HTMLResponse)
async def case_page(token: str, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    """Plain HTML case listing (React comes in Phase 7)."""
    case = await _get_case(session, token)
    emails = (
        await session.execute(
            select(Email).where(Email.case_id == case.id).order_by(Email.received_at)
        )
    ).scalars().all()

    items = "\n".join(
        f"<li><strong>{_esc(e.subject) or '(no subject)'}</strong> — "
        f"{_esc(e.sender)} at {e.received_at.isoformat()}<br>"
        f"<code>{_esc((e.body_plain or '')[:200])}</code></li>"
        for e in emails
    )
    html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Case {_esc(case.token)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem}}
code{{white-space:pre-wrap}}</style></head>
<body>
<h1>Case {_esc(case.token)}</h1>
<p>Status: <strong>{_esc(case.status)}</strong></p>
<p>All data is synthetic. Do not send real personal or policy information.</p>
<h2>Emails ({len(emails)})</h2>
<ul>{items or '<li>No emails yet.</li>'}</ul>
</body></html>"""
    return HTMLResponse(html)


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

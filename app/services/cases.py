"""Case resolution — 02-architecture.md §1.1 step 3, T1.3.

Four steps, evaluated in order (the ordering is the specification):
  a. token in subject line     → that case
  b. In-Reply-To / References  → thread lookup
  c. sender + policy number    → open case for that pair
  d. otherwise                 → new case, new token (retry on collision)
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Case, Email
from app.tokens import generate_token, parse_token_from_subject

POLICY_NUMBER_RE = re.compile(r"\b(ASP|MOT|TRM)[\s_-]?(\d{4})[\s_-]?(\d{4})\b", re.IGNORECASE)


def extract_policy_number(text: str) -> str | None:
    """Find and normalise a policy number (ASP-YYYY-NNNN style) in free text."""
    match = POLICY_NUMBER_RE.search(text)
    if match is None:
        return None
    return f"{match.group(1).upper()}-{match.group(2)}-{match.group(3)}"


async def _case_by_token(session: AsyncSession, token: str) -> Case | None:
    result = await session.execute(select(Case).where(Case.token == token))
    return result.scalar_one_or_none()


async def _case_by_thread_ref(session: AsyncSession, ref: str) -> Case | None:
    result = await session.execute(
        select(Case).join(Email, Email.case_id == Case.id).where(Email.message_id == ref).limit(1)
    )
    return result.scalar_one_or_none()


async def _open_case_for_pair(
    session: AsyncSession, email_addr: str, policy_number: str
) -> Case | None:
    result = await session.execute(
        select(Case)
        .where(
            Case.contact_email == email_addr,
            Case.policy_number == policy_number,
            Case.status == "open",
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _create_case(
    session: AsyncSession, contact_email: str, policy_number: str | None
) -> Case:
    """New case with a fresh token; retry on unique-constraint collision."""
    for _attempt in range(5):
        case = Case(
            token=generate_token(), contact_email=contact_email, policy_number=policy_number
        )
        try:
            async with session.begin_nested():
                session.add(case)
                await session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            continue
        return case
    raise RuntimeError("Could not allocate a unique case token after five attempts")


async def resolve_case(
    session: AsyncSession,
    *,
    subject: str,
    sender: str,
    in_reply_to: str | None = None,
    references: str | None = None,
    body: str = "",
) -> tuple[Case, bool]:
    """Resolve the case for an inbound email, creating one if needed.

    Returns ``(case, created)``. Steps are tried strictly in spec order;
    a subject token wins even when In-Reply-To is present (and even when
    In-Reply-To has been mangled by forwarding or mobile clients).
    """
    # a. token in subject line
    token = parse_token_from_subject(subject)
    if token is not None:
        case = await _case_by_token(session, token)
        if case is not None:
            return case, False

    # b. In-Reply-To / References → thread lookup
    for ref in filter(None, [in_reply_to, *(references.split() if references else [])]):
        case = await _case_by_thread_ref(session, ref.strip())
        if case is not None:
            return case, False

    # c. sender + policy number → open case for that pair
    policy_number = extract_policy_number(f"{subject}\n{body}")
    if policy_number is not None:
        case = await _open_case_for_pair(session, sender, policy_number)
        if case is not None:
            return case, False

    # d. otherwise → new case, new token
    case = await _create_case(session, sender, policy_number)
    return case, True

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Claim, Grievance, Policy
from app.models.schemas import CaseHistory, CaseHistoryEntry, PolicyLookupResult, PolicyRecord
from app.tools.base import ToolContext, ToolResult


async def lookup_policy(session: AsyncSession, policy_number: str) -> PolicyLookupResult:
    policy = await session.get(Policy, policy_number)
    if policy is None:
        return PolicyLookupResult(found=False, active=False)
    record = PolicyRecord.model_validate(policy, from_attributes=True)
    return PolicyLookupResult(
        found=True,
        active=policy.status == "active",
        product_code=policy.product_code,
        policy=record,
    )


async def get_policy_details(session: AsyncSession, policy_number: str) -> PolicyLookupResult:
    return await lookup_policy(session, policy_number)


async def get_case_history(session: AsyncSession, policy_number: str) -> CaseHistory:
    claims = (
        await session.scalars(select(Claim).where(Claim.policy_number == policy_number))
    ).all()
    grievances = (
        await session.scalars(select(Grievance).where(Grievance.policy_number == policy_number))
    ).all()
    return CaseHistory(
        claims=[
            CaseHistoryEntry(
                kind="claim",
                ref_id=row.claim_id,
                date=row.intimation_date,
                status=row.status,
                summary=row.description,
                disputed_internally=row.disputed_internally,
                rejection_reason=row.rejection_reason,
            )
            for row in claims
        ],
        grievances=[
            CaseHistoryEntry(
                kind="grievance",
                ref_id=row.grievance_id,
                date=row.raised_date,
                status=row.status,
                summary=row.summary,
            )
            for row in grievances
        ],
    )


class PolicyTools:
    """Agent-facing tools; customer markers cannot be omitted by callers."""

    def __init__(self, context: ToolContext) -> None:
        self.context = context

    async def lookup_policy(self, policy_number: str) -> ToolResult[PolicyLookupResult]:
        return await self.context.call(
            "lookup_policy",
            {"policy_number": policy_number},
            lambda: lookup_policy(self.context.session, policy_number),
            PolicyLookupResult,
        )

    async def get_policy_details(self, policy_number: str) -> ToolResult[PolicyLookupResult]:
        return await self.context.call(
            "get_policy_details",
            {"policy_number": policy_number},
            lambda: get_policy_details(self.context.session, policy_number),
            PolicyLookupResult,
            customer=True,
        )

    async def get_case_history(self, policy_number: str) -> ToolResult[CaseHistory]:
        return await self.context.call(
            "get_case_history",
            {"policy_number": policy_number},
            lambda: get_case_history(self.context.session, policy_number),
            CaseHistory,
            customer=True,
        )

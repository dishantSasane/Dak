import re
from datetime import date, datetime
from decimal import Decimal

from app.agents import prompts
from app.agents.contracts import ClaimFacts, ClaimOutput
from app.agents.runtime import AgentContext, ToolFailure, refusal
from app.models.schemas import AttachmentReport, EligibilityResult
from app.tools.attachments import check_attachments
from app.tools.eligibility import calculate_eligibility


def _name(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def supported_event_date(text: str, proposed: date | None) -> bool:
    if proposed is None:
        return False
    patterns = [
        (r"\b\d{4}-\d{2}-\d{2}\b", ["%Y-%m-%d"]),
        (r"\b\d{1,2}/\d{1,2}/\d{4}\b", ["%d/%m/%Y"]),
        (r"\b\d{1,2}[- ](?:[A-Za-z]{3,9})[- ]\d{4}\b", ["%d %B %Y", "%d %b %Y"]),
    ]
    for pattern, formats in patterns:
        for match in re.findall(pattern, text):
            for format_ in formats:
                try:
                    candidate = (
                        match if format_ in ("%Y-%m-%d", "%d/%m/%Y") else match.replace("-", " ")
                    )
                    if datetime.strptime(candidate, format_).date() == proposed:
                        return True
                except ValueError:
                    continue
    return False


async def run(ctx: AgentContext) -> dict:
    policy = ctx.policy()
    if policy is None:
        return refusal("unidentifiable")
    details = await ctx.policies.get_policy_details(policy.policy_number)
    if not details.ok or details.value is None or details.value.policy is None:
        raise ToolFailure(details.error or "Policy details unavailable")
    policy = details.value.policy
    attachments = await ctx.tools.call(
        "check_attachments",
        {},
        lambda: check_attachments(ctx.state["raw_payload"]),
        AttachmentReport,
        ttl=0,
    )
    if not attachments.ok or attachments.value is None:
        raise ToolFailure(attachments.error or "Attachment inventory failed")
    chunks = await ctx.retrieve(policy.product_code)
    if not chunks:
        return refusal("no_relevant_context")
    facts = await ctx.model(
        ClaimFacts, prompts.CLAIM_FACTS, {"clauses": [chunk.model_dump() for chunk in chunks]}
    )
    event_date = facts.event_date
    if event_date is None or not supported_event_date(
        f"{ctx.state['subject']} {ctx.state['body']}", facts.event_date
    ):
        return {
            **refusal("unidentifiable"),
            "internal_note": (
                "The event date is missing; request it before calculating eligibility."
            ),
        }
    triage = ctx.state.get("triage", {})
    amount = (
        Decimal(str(triage["claim_amount"])) if triage.get("claim_amount") is not None else None
    )

    async def eligibility() -> EligibilityResult:
        assert facts.event_date is not None
        return calculate_eligibility(
            policy, facts.event_date, amount_claimed=amount, pre_existing=facts.pre_existing
        )

    result = await ctx.tools.call(
        "calculate_eligibility",
        {"event_date": event_date.isoformat()},
        eligibility,
        EligibilityResult,
        ttl=0,
    )
    if not result.ok or result.value is None:
        raise ToolFailure(result.error or "Eligibility calculation failed")
    missing = [
        name
        for name in facts.required_documents
        if not any(_name(name) in _name(present) for present in attachments.value.present)
    ]
    conflict = (
        facts.accidental
        and "initial_waiting_period" in result.value.blocking_conditions
        and any(chunk.clause_id in ("ASP-C08", "TRM-C05") for chunk in chunks)
    )
    output = await ctx.model(
        ClaimOutput,
        prompts.CLAIM,
        {
            "clauses": [chunk.model_dump() for chunk in chunks],
            "eligibility": result.value.model_dump(mode="json"),
            "facts": facts.model_dump(mode="json"),
            "attachments": attachments.value.model_dump(),
            "missing_documents": missing,
            "violations": ctx.state.get("violations", []),
            "conflict": conflict,
        },
    )
    identifiers = {chunk.clause_id for chunk in chunks}
    if not set(output.coverage_assessment.supporting_clauses).issubset(identifiers):
        return refusal("no_relevant_context")
    recommendation = (
        "refer_underwriting"
        if conflict or result.value.blocking_conditions
        else ("need_documents" if missing else "proceed")
    )
    return {
        "draft": output.draft.model_dump(mode="json"),
        "retrieved_chunks": [chunk.model_dump() for chunk in chunks],
        "product_code": policy.product_code,
        "escalate_flag": bool(conflict),
        "escalation_reason": "routing_conflict" if conflict else None,
        "case_file": {
            "policy_status": policy.status,
            "coverage_assessment": output.coverage_assessment.model_dump(mode="json"),
            "eligibility": result.value.model_dump(mode="json"),
            "missing_documents": missing,
            "recommendation": recommendation,
        },
    }

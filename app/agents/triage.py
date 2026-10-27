import re

from app.agents import prompts
from app.agents.runtime import AgentContext, ToolFailure
from app.models.schemas import InjectionReport, TriageAssessment
from app.services.cases import extract_policy_number
from app.tools.injection import detect_injection


async def run(ctx: AgentContext) -> dict:
    text = f"{ctx.state['subject']}\n{ctx.state['body']}"
    report = await ctx.tools.call(
        "detect_injection", {}, lambda: detect_injection(text), InjectionReport, ttl=0
    )
    if not report.ok or report.value is None:
        raise ToolFailure(report.error or "Injection screening failed")
    if report.value.detected:
        assessment = TriageAssessment(
            category="unknown",
            confidence=1,
            policy_number_present=False,
            sentiment="neutral",
            urgency="low",
            regulatory_language=False,
            injection_detected=True,
            reasoning="Deterministic screening flagged: "
            + ", ".join(report.value.matched_patterns),
        )
        return {"triage": assessment.model_dump(mode="json"), "policy_found": None}
    assessment = await ctx.model(TriageAssessment, prompts.TRIAGE, light=True)
    actual = extract_policy_number(text)
    assessment.policy_number = actual
    assessment.policy_number_present = bool(actual) or assessment.policy_number_present
    assessment.regulatory_language = assessment.regulatory_language or bool(
        re.search(
            r"\b(irdai|ombudsman|consumer\s+court|legal\s+notice|lawyer|formal\s+proceedings)\b",
            text,
            re.I,
        )
    )
    updates: dict = {"triage": assessment.model_dump(mode="json"), "policy_found": None}
    if actual:
        result = await ctx.policies.lookup_policy(actual)
        if not result.ok or result.value is None:
            raise ToolFailure(result.error or "Policy lookup failed")
        updates["policy_found"] = result.value.found
        updates["policy_record"] = (
            result.value.policy.model_dump(mode="json") if result.value.policy else None
        )
        updates["product_code"] = result.value.product_code
    return updates

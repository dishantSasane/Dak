import re

from app.agents import prompts
from app.agents.contracts import SpecialistOutput
from app.agents.runtime import AgentContext, ToolFailure, refusal


async def run(ctx: AgentContext) -> dict:
    product = ctx.product()
    if not product:
        return refusal("unidentifiable")
    personal = bool(
        re.search(
            r"\b(my|our)\b.{0,40}\b(balance|remaining|insured|premium|date|end|expire|waiting|copay|co-pay)\b"
            r"|\b(when does|when will)\b.{0,30}\b(my|our)\b",
            ctx.state["body"],
            re.I,
        )
    )
    # Bypass the global cache before fetching personal data; no private record is
    # provided to a generic drafting prompt even though triage looked up a policy.
    if not personal and not ctx.state.get("violations"):
        cached = await ctx.cached(product)
        if cached:
            draft, chunks = cached
            return {
                "draft": draft,
                "retrieved_chunks": [chunk.model_dump() for chunk in chunks],
                "product_code": product,
                "cache_hit": True,
            }
    chunks = await ctx.retrieve(product)
    if not chunks:
        return {**refusal("no_relevant_context"), "retrieved_chunks": []}
    context: dict = {
        "clauses": [chunk.model_dump() for chunk in chunks],
        "violations": ctx.state.get("violations", []),
    }
    policy = ctx.policy()
    if personal:
        if policy is None:
            return refusal("unidentifiable")
        result = await ctx.policies.get_policy_details(policy.policy_number)
        if not result.ok or result.value is None or result.value.policy is None:
            raise ToolFailure(result.error or "Policy details unavailable")
        context["policy"] = result.value.policy.model_dump(mode="json")
    output = await ctx.model(SpecialistOutput, prompts.QUERY, context)
    updates = {
        "draft": output.draft.model_dump(mode="json"),
        "product_code": product,
        "retrieved_chunks": [chunk.model_dump() for chunk in chunks],
        "reject_route": output.reject_route.model_dump() if output.reject_route else None,
        "cache_hit": False,
    }
    if output.draft.cannot_answer and not output.reject_route:
        updates["escalation_reason"] = "no_relevant_context"
    return updates

from app.agents import prompts
from app.agents.contracts import SpecialistOutput
from app.agents.runtime import AgentContext, ToolFailure, refusal
from app.models.schemas import GrievanceType


async def run(ctx: AgentContext) -> dict:
    subtype = await ctx.tools.call(
        "classify_grievance",
        {},
        lambda: ctx.model(
            GrievanceType, "Classify the grievance subtype; do not draft.", light=True
        ),
        GrievanceType,
        ttl=0,
    )
    if not subtype.ok or subtype.value is None:
        raise ToolFailure(subtype.error or "Grievance classification failed")
    policy = ctx.policy()
    if policy is None:
        return refusal("unidentifiable")
    history = await ctx.policies.get_case_history(policy.policy_number)
    if not history.ok or history.value is None:
        raise ToolFailure(history.error or "Case history unavailable")
    reason = None
    prior = [entry for entry in history.value.grievances if entry.status in ("open", "closed")]
    if len(prior) >= 2:
        reason = "repeat_complainant"
    text = f"{ctx.state['subject']} {ctx.state['body']}".lower()
    disputed = [
        entry
        for entry in history.value.claims
        if entry.disputed_internally and entry.ref_id.lower() in text
    ]
    if disputed:
        reason = "potentially_valid_grievance"
    chunks = await ctx.retrieve(policy.product_code)
    if not chunks:
        return refusal("no_relevant_context")
    output = await ctx.model(
        SpecialistOutput,
        prompts.COMPLAINT,
        {
            "grievance": subtype.value.model_dump(),
            "history": history.value.model_dump(mode="json"),
            "clauses": [chunk.model_dump() for chunk in chunks],
            "violations": ctx.state.get("violations", []),
            "review_reason": reason,
        },
    )
    return {
        "draft": output.draft.model_dump(mode="json"),
        "retrieved_chunks": [chunk.model_dump() for chunk in chunks],
        "internal_note": output.internal_note,
        "reject_route": output.reject_route.model_dump() if output.reject_route else None,
        "escalate_flag": bool(reason),
        "escalation_reason": reason,
        "product_code": policy.product_code,
    }

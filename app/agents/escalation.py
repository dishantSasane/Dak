from app.agents import prompts
from app.agents.runtime import AgentContext
from app.llm.gemini import ModelError, ModelRateLimited
from app.models.schemas import EscalationBrief


def fallback(ctx: AgentContext, reason: str) -> EscalationBrief:
    return EscalationBrief(
        headline=f"Human review required: {reason.replace('_', ' ')}",
        reason_code=reason,
        what_arrived=ctx.state["subject"][:240] or "Email without subject",
        what_system_determined=ctx.state.get("internal_note")
        or (
            ctx.state.get("triage", {}).get("reasoning") or "No validated assessment was available."
        ),
        what_system_could_not_determine=ctx.state.get("error")
        or ("A supported final answer or claim decision has not been established."),
        suggested_next_step=(
            "Read the email and the recorded evidence, then record a review decision."
        ),
        confidence_in_brief=1,
    )


async def run(ctx: AgentContext) -> dict:
    reason = ctx.state.get("escalation_reason") or "unclassifiable"
    # Injection short-circuits the entire model path, including briefing.
    if reason == "injection_detected" or ctx.state.get("error"):
        brief = fallback(ctx, reason)
    else:
        try:
            brief = await ctx.model(
                EscalationBrief,
                prompts.ESCALATION,
                {
                    "reason": reason,
                    "triage": ctx.state.get("triage"),
                    "internal_note": ctx.state.get("internal_note"),
                    "case_file": ctx.state.get("case_file"),
                },
                light=True,
            )
            brief.reason_code = reason
        except ModelRateLimited:
            raise
        except ModelError:
            brief = fallback(ctx, reason)
    return {
        "escalation_brief": brief.model_dump(mode="json"),
        "status": "escalated",
        "escalation_reason": reason,
    }

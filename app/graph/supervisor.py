"""Deterministic routing. Hard-stop order is the architecture's contract."""

from app.config import get_settings
from app.graph.state import RunState
from app.models.schemas import TriageAssessment


def route_decision(state: RunState) -> tuple[str, str]:
    if not state.get("triage"):
        return "escalation_agent", state.get("escalation_reason") or "model_output_invalid"
    triage = TriageAssessment.model_validate(state["triage"])
    checks = [
        (triage.injection_detected, "injection_detected"),
        (triage.regulatory_language, "regulatory_language"),
        (triage.confidence < get_settings().CONFIDENCE_THRESHOLD, "low_confidence"),
        (triage.category == "mixed", "mixed_intent"),
        (triage.category == "unknown", "unclassifiable"),
        (triage.policy_number_present and not state.get("policy_found"), "policy_not_found"),
    ]
    for condition, reason in checks:
        if condition:
            return "escalation_agent", reason
    if state.get("tool_error"):
        return "escalation_agent", "tool_failure"
    if state.get("escalation_reason"):
        return "escalation_agent", str(state["escalation_reason"])
    rejected = state.get("reject_route")
    if rejected:
        if state.get("reroute_count", 0) >= get_settings().MAX_REROUTES:
            return "escalation_agent", "routing_conflict"
        suggestion = rejected.get("suggested", "")
        target = {
            "query": "query_agent",
            "complaint": "complaint_agent",
            "claim": "claim_agent",
        }.get(suggestion, suggestion)
        if target not in ("query_agent", "complaint_agent", "claim_agent"):
            return "escalation_agent", "routing_conflict"
        return target, rejected.get("reason", "specialist requested reroute")
    return {"query": "query_agent", "complaint": "complaint_agent", "claim": "claim_agent"}[
        triage.category
    ], f"classified as {triage.category}"


def route(state: RunState) -> str:
    return route_decision(state)[0]

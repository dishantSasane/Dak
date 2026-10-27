import pytest

from app.graph.supervisor import route_decision


def state(**updates):
    triage = dict(
        category="query",
        confidence=0.95,
        policy_number=None,
        policy_number_present=False,
        sentiment="neutral",
        urgency="low",
        regulatory_language=False,
        injection_detected=False,
        reasoning="fixture",
    )
    triage.update(updates)
    return {"triage": triage, "policy_found": True, "reroute_count": 0}


@pytest.mark.parametrize(
    "updates,reason",
    [
        ({"injection_detected": True, "regulatory_language": True}, "injection_detected"),
        ({"regulatory_language": True, "confidence": 0.1}, "regulatory_language"),
        ({"confidence": 0.1, "category": "mixed"}, "low_confidence"),
        ({"category": "mixed"}, "mixed_intent"),
        ({"category": "unknown"}, "unclassifiable"),
    ],
)
def test_hard_stops_in_order(updates, reason):
    assert route_decision(state(**updates)) == ("escalation_agent", reason)


@pytest.mark.parametrize("category", ["query", "complaint", "claim"])
def test_normal_routing(category):
    assert route_decision(state(category=category))[0] == category + "_agent"


def test_lookup_and_bounded_reroute():
    current = state(policy_number_present=True, policy_number="ASP-2024-0000")
    current["policy_found"] = False
    assert route_decision(current)[1] == "policy_not_found"
    current = state()
    current["reject_route"] = {"suggested": "claim", "reason": "an incident happened"}
    assert route_decision(current)[0] == "claim_agent"
    current["reroute_count"] = 1
    assert route_decision(current)[1] == "routing_conflict"

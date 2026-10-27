import json
from datetime import date
from pathlib import Path

from scripts.seed import _rng, generate_claims, generate_policies, validate


def test_generated_claims_never_overdraw_sum_insured() -> None:
    random = _rng()
    policies = generate_policies(random, date(2026, 10, 10))
    claims = generate_claims(random, policies)
    assert validate(policies, claims, []) == []


def test_checked_in_data_reconciles() -> None:
    root = Path("data/seeds")
    rows = [
        json.loads((root / f"{name}.json").read_text())
        for name in ["policies", "claims", "grievances"]
    ]
    assert validate(*rows) == []


def test_unknown_policy_is_rejected() -> None:
    errors = validate(
        [], [{"claim_id": "bad", "policy_number": "unknown", "status": "rejected"}], []
    )
    assert "unknown does not exist" in errors[0]

"""Seed data generator + loader — T2.1.

Generates the synthetic Vantara dataset (policies, claims, grievances) and
loads it into Postgres. Referential integrity is validated BEFORE inserting:

  * every claim/grievance policy_number must exist in policies
  * sum_insured_remaining must reconcile with settled claims
    (sum_insured - Σ amount_settled over settled claims)

Refuses to load on mismatch and prints what failed.

Usage:
    python scripts/seed.py generate   # write data/seeds/*.json
    python scripts/seed.py load       # validate + insert
    python scripts/seed.py check      # validate only
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEEDS_DIR = ROOT / "data" / "seeds"

PRODUCTS = {
    "ASP": "Arogya Sanjeevani Health Insurance",
    "MOT": "Comprehensive Motor Insurance",
    "TRM": "Term Life Insurance",
}

FIRST_NAMES = [
    "Aarav", "Diya", "Rohan", "Meera", "Kabir", "Ananya", "Vikram", "Sana",
    "Arjun", "Priya", "Imran", "Neha", "Sanjay", "Lakshmi", "Farhan", "Isha",
    "Rahul", "Tara", "Dev", "Zoya", "Manish", "Kavya", "Omar", "Ritu",
]
LAST_NAMES = [
    "Sharma", "Iyer", "Khan", "Patel", "Reddy", "Gupta", "Nair", "Singh",
    "Bose", "Menon", "Qureshi", "Joshi", "Rao", "Verma", "Chopra", "Das",
]
CITIES = ["Pune", "Chennai", "Hyderabad", "Mumbai", "Bengaluru", "Kolkata",
          "Delhi", "Ahmedabad", "Jaipur", "Kochi"]

CLAIM_TYPES = {
    "ASP": ["hospitalisation", "day_procedure", "pre_existing_treatment", "accident_injury"],
    "MOT": ["own_damage", "third_party", "theft", "breakdown"],
    "TRM": ["death_claim"],
}
GRIEVANCE_CATEGORIES = ["claim_delay", "rejection_dispute", "premium_dispute",
                        "service_quality", "mis-selling"]

REJECT_REASONS = [
    ("Pre-existing condition inside waiting period", True),
    ("Policy lapsed at date of loss", False),
    ("Consumables not covered under policy wording", True),
    ("Claim intimated after deadline", False),
    ("Treatment not medically necessary per policy definition", True),
    ("Excluded condition under Section II exclusions", False),
]


def _rng() -> random.Random:
    return random.Random(20261010)


def generate_policies(rnd: random.Random, today: date) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    n = 40
    used_numbers: set[str] = set()
    for i in range(n):
        code = ["ASP", "MOT", "TRM"][i % 3]
        year = rnd.choice([2022, 2023, 2024, 2025])
        while True:
            num = f"{code}-{year}-{rnd.randint(1000, 9999)}"
            if num not in used_numbers:
                used_numbers.add(num)
                break
        first, last = rnd.choice(FIRST_NAMES), rnd.choice(LAST_NAMES)
        start = today - timedelta(days=rnd.randint(60, 900))
        end = date(start.year + 1, start.month, min(start.day, 28))
        status = "active"
        cancelled_date = None
        if i % 13 == 5:
            status = "cancelled"
            cancelled_date = (start + timedelta(days=rnd.randint(30, 200))).isoformat()
        elif end <= today:
            status = "lapsed" if rnd.random() < 0.6 else "active"
            if status == "active":  # renew it
                start = today - timedelta(days=rnd.randint(30, 300))
                end = date(start.year + 1, start.month, min(start.day, 28))
        si = rnd.choice([100000, 250000, 400000, 500000, 750000, 1000000, 1500000])
        sum_insured = Decimal(si)
        co_pay = rnd.choice([0, 0, 0, 5, 10, 20])
        wp_days = rnd.choice([30, 30, 30, 60, 90])
        pe_wp = rnd.choice([None, 240, 365, 730])
        policies.append({
            "policy_number": num,
            "holder_name": f"{first} {last}",
            "holder_email": f"{first.lower()}.{last.lower()}{i}@example.test",
            "holder_phone": f"+91-9{rnd.randint(100000000, 999999999)}",
            "product_code": code,
            "product_name": PRODUCTS[code],
            "status": status,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "waiting_period_end": (start + timedelta(days=wp_days)).isoformat(),
            "pre_existing_waiting_period_end": (
                (start + timedelta(days=pe_wp)).isoformat() if pe_wp else None
            ),
            "sum_insured": str(sum_insured),
            # patched below once claims are generated
            "sum_insured_remaining": str(sum_insured),
            "premium": str(Decimal(rnd.randint(4000, 35000))),
            "payment_frequency": rnd.choice(["monthly", "quarterly", "annual"]),
            "last_payment_date": (today - timedelta(days=rnd.randint(5, 90))).isoformat(),
            "co_pay_percent": co_pay,
            "riders": rnd.sample(
                ["critical_illness", "accident_cover", "maternity", "road_assistance"],
                k=rnd.randint(0, 2),
            ),
            "nominee_name": f"{rnd.choice(FIRST_NAMES)} {last}" if code == "TRM" else None,
            "nominee_relation": rnd.choice(["spouse", "parent", "sibling"]) if code == "TRM" else None,
            "city": rnd.choice(CITIES),
            "cancelled_date": cancelled_date,
        })
    return policies


def generate_claims(rnd: random.Random, policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    cid = 0
    for p in policies:
        for _ in range(rnd.randint(0, 3)):
            cid += 1
            code = p["product_code"]
            start = date.fromisoformat(p["start_date"])
            end = date.fromisoformat(p["end_date"])
            window_start = max(start, date(2024, 1, 1))
            if window_start > end:
                continue
            event = window_start + timedelta(
                days=rnd.randint(0, max(1, (min(end, date(2026, 9, 30)) - window_start).days))
            )
            si = Decimal(p["sum_insured"])
            amount = Decimal(min(int(si), rnd.randint(15000, int(si))))
            status = rnd.choices(["settled", "rejected", "in_progress"], weights=[5, 3, 2])[0]
            rejection_reason = None
            disputed = False
            settled_amount = None
            settled_date = None
            if status == "rejected":
                rejection_reason, disputed = rnd.choice(REJECT_REASONS)
            if status == "settled":
                settled_amount = str((amount * Decimal("0.9")).quantize(Decimal("0.01")))
                settled_date = (event + timedelta(days=rnd.randint(20, 90))).isoformat()
            claims.append({
                "claim_id": f"CLM-{2024 + (cid % 3)}-{10000 + cid}",
                "policy_number": p["policy_number"],
                "intimation_date": event.isoformat(),
                "claim_type": rnd.choice(CLAIM_TYPES[code]),
                "description": f"{rnd.choice(CLAIM_TYPES[code]).replace('_', ' ').title()} event on {event}.",
                "amount_claimed": str(amount),
                "amount_settled": settled_amount,
                "status": status,
                "rejection_reason": rejection_reason,
                "disputed_internally": disputed,
                "settled_date": settled_date,
            })
    # reconcile sum_insured_remaining
    by_policy: dict[str, Decimal] = {}
    for c in claims:
        if c["status"] == "settled" and c["amount_settled"] is not None:
            by_policy[c["policy_number"]] = (
                by_policy.get(c["policy_number"], Decimal(0)) + Decimal(c["amount_settled"])
            )
    for p in policies:
        remaining = Decimal(p["sum_insured"]) - by_policy.get(p["policy_number"], Decimal(0))
        p["sum_insured_remaining"] = str(max(remaining, Decimal(0)))
    return claims


def generate_grievances(rnd: random.Random, policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grievances: list[dict[str, Any]] = []
    gid = 0
    for p in rnd.sample(policies, k=15):
        for _ in range(rnd.randint(1, 3)):
            gid += 1
            raised = date(2025, 1, 1) + timedelta(days=rnd.randint(0, 600))
            status = rnd.choice(["open", "closed", "escalated"])
            grievances.append({
                "grievance_id": f"GRV-{raised.year}-{1000 + gid}",
                "policy_number": p["policy_number"],
                "raised_date": raised.isoformat(),
                "category": rnd.choice(GRIEVANCE_CATEGORIES),
                "summary": "Customer unhappy with handling; details in linked case.",
                "status": status,
                "resolution": "Acknowledged and resolved." if status == "closed" else None,
                "closed_date": (raised + timedelta(days=rnd.randint(3, 30))).isoformat()
                if status == "closed" else None,
            })
    return grievances


def generate_corpus() -> None:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    rnd = _rng()
    today = date(2026, 10, 10)
    policies = generate_policies(rnd, today)
    claims = generate_claims(rnd, policies)
    grievances = generate_grievances(rnd, policies)
    (SEEDS_DIR / "policies.json").write_text(json.dumps(policies, indent=1))
    (SEEDS_DIR / "claims.json").write_text(json.dumps(claims, indent=1))
    (SEEDS_DIR / "grievances.json").write_text(json.dumps(grievances, indent=1))
    print(f"generated {len(policies)} policies, {len(claims)} claims, "
          f"{len(grievances)} grievances in {SEEDS_DIR}")


def validate(policies: list[dict], claims: list[dict], grievances: list[dict]) -> list[str]:
    """Return a list of human-readable integrity failures (empty = OK)."""
    errors: list[str] = []
    known = {p["policy_number"] for p in policies}
    for c in claims:
        if c["policy_number"] not in known:
            errors.append(f"claim {c['claim_id']}: policy {c['policy_number']} does not exist")
    for g in grievances:
        if g["policy_number"] not in known:
            errors.append(f"grievance {g['grievance_id']}: policy {g['policy_number']} does not exist")
    settled_by_policy: dict[str, Decimal] = {}
    for c in claims:
        if c["status"] == "settled" and c.get("amount_settled") is not None:
            settled_by_policy[c["policy_number"]] = (
                settled_by_policy.get(c["policy_number"], Decimal(0)) + Decimal(c["amount_settled"])
            )
    for p in policies:
        expected = Decimal(p["sum_insured"]) - settled_by_policy.get(p["policy_number"], Decimal(0))
        actual = Decimal(p["sum_insured_remaining"])
        if expected != actual:
            errors.append(
                f"policy {p['policy_number']}: sum_insured_remaining {actual} "
                f"does not reconcile with settled claims (expected {expected})"
            )
    return errors


async def load(policies: list[dict], claims: list[dict], grievances: list[dict]) -> None:
    from app.db.models import Claim, Grievance, Policy
    from app.db.session import get_sessionmaker

    async with get_sessionmaker()() as session:
        for p in policies:
            session.add(Policy(
                policy_number=p["policy_number"], holder_name=p["holder_name"],
                holder_email=p["holder_email"], holder_phone=p["holder_phone"],
                product_code=p["product_code"], product_name=p["product_name"],
                status=p["status"], start_date=date.fromisoformat(p["start_date"]),
                end_date=date.fromisoformat(p["end_date"]),
                waiting_period_end=(date.fromisoformat(p["waiting_period_end"])
                                    if p.get("waiting_period_end") else None),
                pre_existing_waiting_period_end=(
                    date.fromisoformat(p["pre_existing_waiting_period_end"])
                    if p.get("pre_existing_waiting_period_end") else None),
                sum_insured=Decimal(p["sum_insured"]),
                sum_insured_remaining=Decimal(p["sum_insured_remaining"]),
                premium=Decimal(p["premium"]), payment_frequency=p["payment_frequency"],
                last_payment_date=(date.fromisoformat(p["last_payment_date"])
                                   if p.get("last_payment_date") else None),
                co_pay_percent=p["co_pay_percent"], riders=p["riders"],
                nominee_name=p.get("nominee_name"), nominee_relation=p.get("nominee_relation"),
                city=p.get("city"),
                cancelled_date=(date.fromisoformat(p["cancelled_date"])
                                if p.get("cancelled_date") else None),
            ))
        await session.flush()
        for c in claims:
            session.add(Claim(
                claim_id=c["claim_id"], policy_number=c["policy_number"],
                intimation_date=date.fromisoformat(c["intimation_date"]),
                claim_type=c["claim_type"], description=c["description"],
                amount_claimed=Decimal(c["amount_claimed"]),
                amount_settled=Decimal(c["amount_settled"]) if c.get("amount_settled") else None,
                status=c["status"], rejection_reason=c.get("rejection_reason"),
                disputed_internally=c["disputed_internally"],
                settled_date=(date.fromisoformat(c["settled_date"])
                              if c.get("settled_date") else None),
            ))
        for g in grievances:
            session.add(Grievance(
                grievance_id=g["grievance_id"], policy_number=g["policy_number"],
                raised_date=date.fromisoformat(g["raised_date"]), category=g["category"],
                summary=g["summary"], status=g["status"], resolution=g.get("resolution"),
                closed_date=(date.fromisoformat(g["closed_date"])
                             if g.get("closed_date") else None),
            ))
        await session.commit()
    print(f"loaded {len(policies)} policies, {len(claims)} claims, {len(grievances)} grievances")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "generate"
    if cmd == "generate":
        generate_corpus()
        return 0
    policies = json.loads((SEEDS_DIR / "policies.json").read_text())
    claims = json.loads((SEEDS_DIR / "claims.json").read_text())
    grievances = json.loads((SEEDS_DIR / "grievances.json").read_text())
    errors = validate(policies, claims, grievances)
    if errors:
        print("REFUSING TO LOAD — referential integrity failures:")
        for e in errors:
            print("  -", e)
        return 1
    if cmd == "check":
        print("validation OK")
        return 0
    if cmd == "load":
        asyncio.run(load(policies, claims, grievances))
        return 0
    print(f"unknown command {cmd!r}; use generate|check|load")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

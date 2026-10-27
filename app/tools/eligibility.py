"""Deterministic eligibility, advisory only; never decides a claim."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.models.schemas import EligibilityResult, PolicyRecord


def calculate_eligibility(
    policy: PolicyRecord,
    event_date: date,
    *,
    amount_claimed: Decimal | None = None,
    pre_existing: bool = False,
) -> EligibilityResult:
    if amount_claimed is not None and amount_claimed < 0:
        raise ValueError("amount_claimed must be nonnegative")
    if not 0 <= policy.co_pay_percent <= 100:
        raise ValueError("co_pay_percent must be between zero and 100")
    if policy.product_code not in ("ASP", "MOT", "TRM"):
        raise ValueError("Unknown product code")
    blocked: list[str] = []
    in_term = policy.start_date <= event_date <= policy.end_date
    cancelled = policy.status == "cancelled" and (
        policy.cancelled_date is None or event_date >= policy.cancelled_date
    )
    active = in_term and not cancelled
    if event_date < policy.start_date:
        blocked.append("event_before_policy_start")
    elif event_date > policy.end_date:
        blocked.append("policy_lapsed")
    if cancelled:
        blocked.append("policy_cancelled")
    initial = (
        policy.product_code == "MOT"
        or policy.waiting_period_end is None
        or event_date > policy.waiting_period_end
    )
    existing = (
        policy.product_code != "ASP"
        or policy.pre_existing_waiting_period_end is None
        or event_date > policy.pre_existing_waiting_period_end
    )
    if not initial:
        blocked.append("initial_waiting_period")
    if pre_existing and not existing:
        blocked.append("pre_existing_waiting_period")
    remaining = max(Decimal(0), policy.sum_insured_remaining)
    if remaining == 0:
        blocked.append("sum_insured_exhausted")
    payable = None
    if amount_claimed is not None and policy.product_code == "ASP":
        payable = (
            Decimal(0)
            if blocked
            else (min(amount_claimed, remaining) * (100 - policy.co_pay_percent) / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    return EligibilityResult(
        policy_active_on_event_date=active,
        initial_waiting_period_elapsed=initial,
        pre_existing_waiting_period_elapsed=existing,
        sum_insured_remaining=remaining,
        co_pay_percent=policy.co_pay_percent,
        indicative_payable=payable,
        blocking_conditions=blocked,
    )

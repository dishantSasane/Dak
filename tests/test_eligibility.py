from datetime import date
from decimal import Decimal

import pytest

from app.models.schemas import PolicyRecord
from app.tools.eligibility import calculate_eligibility


@pytest.fixture
def policy() -> PolicyRecord:
    return PolicyRecord(
        policy_number="ASP-2026-1000",
        holder_name="Demo",
        holder_email="demo@example.test",
        product_code="ASP",
        product_name="Demo health",
        status="active",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        waiting_period_end=date(2026, 1, 31),
        pre_existing_waiting_period_end=date(2026, 3, 1),
        sum_insured=Decimal("500000"),
        sum_insured_remaining=Decimal("240000"),
        premium=Decimal("10000"),
        payment_frequency="annual",
        co_pay_percent=10,
    )


@pytest.mark.parametrize(
    "event,blocked",
    [
        (date(2025, 12, 31), True),
        (date(2026, 1, 31), True),
        (date(2026, 2, 1), False),
        (date(2027, 1, 1), True),
    ],
)
def test_event_boundaries(policy, event, blocked):
    result = calculate_eligibility(policy, event)
    assert bool(result.blocking_conditions) is blocked


def test_remaining_and_copay(policy):
    result = calculate_eligibility(policy, date(2026, 4, 1), amount_claimed=Decimal("300000"))
    assert result.indicative_payable == Decimal("216000.00")
    assert result.sum_insured_remaining == Decimal("240000")


def test_exhaustion_cancellation_and_preexisting(policy):
    event = date(2026, 2, 1)
    exhausted = policy.model_copy(update={"sum_insured_remaining": Decimal("0")})
    assert "sum_insured_exhausted" in calculate_eligibility(exhausted, event).blocking_conditions
    cancelled = policy.model_copy(update={"status": "cancelled", "cancelled_date": event})
    assert "policy_cancelled" in calculate_eligibility(cancelled, event).blocking_conditions
    result = calculate_eligibility(policy, event, pre_existing=True)
    assert "pre_existing_waiting_period" in result.blocking_conditions
    assert (
        calculate_eligibility(policy, date(2026, 3, 2), pre_existing=True).blocking_conditions == []
    )


def test_motor_ignores_health_waits_and_nonhealth_payment_is_unassessed(policy):
    motor = policy.model_copy(update={"product_code": "MOT"})
    result = calculate_eligibility(
        motor, date(2026, 1, 10), amount_claimed=Decimal("10000"), pre_existing=True
    )
    assert result.initial_waiting_period_elapsed
    assert result.pre_existing_waiting_period_elapsed
    assert not result.blocking_conditions
    assert result.indicative_payable is None
    life = policy.model_copy(update={"product_code": "TRM"})
    assert (
        calculate_eligibility(
            life, date(2026, 4, 1), amount_claimed=Decimal("10000")
        ).indicative_payable
        is None
    )

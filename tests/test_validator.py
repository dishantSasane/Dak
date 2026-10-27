from datetime import date
from decimal import Decimal

import pytest

from app.models.schemas import Chunk, Draft, DraftSentence, PolicyRecord
from app.validator.citations import normalise_numbers, validate_draft


def chunk(text):
    return Chunk(clause_id="ASP-C01", clause_title="Test", content=text, score=0.9)


def draft(text, kind="factual", cite="ASP-C01"):
    return Draft(sentences=[DraftSentence(text=text, kind=kind, cite=cite)])


def codes(result):
    return {v.code for v in result.violations}


@pytest.mark.parametrize(
    "text", ["Rs 5,00,000", "Rs. 500,000", "₹500000", "INR 500000", "5 lakh", "5 lac", "0.05 crore"]
)
def test_money_normalisation(text):
    assert normalise_numbers(text) == {500000}


def test_decimal_expansion_and_separate_percentages():
    assert normalise_numbers("5.5 lakh and 10%") == {550000}


@pytest.mark.parametrize(
    "text,source",
    [
        ("The limit is Rs 5,00,000.", "The limit is 5 lakh."),
        ("The fee is ₹10.25.", "Fee: INR 10.25."),
        ("The co-pay is 10%.", "Co-pay is 10 percent."),
    ],
)
def test_grounded_figures_pass(text, source):
    assert validate_draft(draft(text), [chunk(source)]).passed


@pytest.mark.parametrize(
    "text,source",
    [
        ("The fee is ₹10.25.", "Fee is ₹10.20."),
        ("The co-pay is 10%.", "Fee is 10 rupees."),
        ("Your remaining balance is ₹500.", "Balance depends on your schedule."),
    ],
)
def test_unsupported_figures_block(text, source):
    assert "UNSOURCED_FIGURE" in codes(validate_draft(draft(text), [chunk(source)]))


def test_missing_and_phantom_citations_are_collected():
    value = Draft(
        sentences=[
            DraftSentence(text="Coverage applies.", kind="factual"),
            DraftSentence(text="We will review.", kind="commitment", cite="BOGUS"),
        ]
    )
    assert {"MISSING_CITATION", "PHANTOM_CITATION"} <= codes(validate_draft(value, []))


def test_courtesy_without_cite_passes_with_substantive_content():
    value = Draft(
        sentences=[
            DraftSentence(text="Thank you.", kind="courtesy"),
            DraftSentence(text="Please provide the discharge summary.", kind="procedural"),
        ]
    )
    assert validate_draft(value, []).passed


@pytest.mark.parametrize(
    "value",
    [
        Draft(),
        Draft(cannot_answer=True),
        Draft(sentences=[DraftSentence(text="Thank you.", kind="courtesy")]),
    ],
)
def test_empty_or_cannot_answer_fails_closed(value):
    assert not validate_draft(value, []).passed


@pytest.mark.parametrize("kind", ["factual", "courtesy", "procedural", "commitment"])
@pytest.mark.parametrize(
    "text",
    [
        "Your claim is approved.",
        "We have rejected your claim.",
        "The claim will be payable.",
        "We are pleased to approve your claim.",
        "We cannot approve your claim.",
    ],
)
def test_decisions_block_in_every_kind(kind, text):
    assert "UNAUTHORISED_DECISION" in codes(validate_draft(draft(text, kind), [chunk(text)]))


def test_historical_report_is_not_a_present_decision():
    text = "You said your claim was rejected; we will review your complaint."
    assert "UNAUTHORISED_DECISION" not in codes(validate_draft(draft(text), [chunk(text)]))


@pytest.mark.parametrize(
    "source,passes",
    [
        ("We respond within 7 working days.", True),
        ("We respond within 7 months.", False),
        ("The fee is 7 rupees.", False),
    ],
)
def test_commitment_requires_matching_timeline_units(source, passes):
    result = validate_draft(
        draft("We will respond within 7 working days.", "commitment"), [chunk(source)]
    )
    assert ("UNGROUNDED_COMMITMENT" not in codes(result)) == passes


def test_configured_sla_can_ground_timeline():
    assert validate_draft(
        draft("We will respond within 2 business days.", "commitment"),
        [chunk("Service standard.")],
        sla_texts=["Respond within 2 working days."],
    ).passed


@pytest.mark.parametrize(
    "source,passes", [("Effective 19 October 2026.", True), ("Effective 2026-10-18.", False)]
)
def test_dates_use_canonical_calendar_values(source, passes):
    result = validate_draft(draft("Effective 2026-10-19."), [chunk(source)])
    assert ("UNSOURCED_DATE" not in codes(result)) == passes


def test_policy_dates_are_allowed_but_personal_money_is_not():
    policy = PolicyRecord(
        policy_number="ASP-X",
        holder_name="A",
        holder_email="a@example.com",
        product_code="ASP",
        product_name="Health",
        status="active",
        start_date=date(2026, 10, 19),
        end_date=date(2027, 10, 18),
        sum_insured=Decimal(500),
        sum_insured_remaining=Decimal(500),
        premium=Decimal(10),
        payment_frequency="annual",
        co_pay_percent=0,
    )
    assert validate_draft(draft("Effective 19/10/2026."), [chunk("See schedule.")], policy).passed
    assert "UNSOURCED_FIGURE" in codes(
        validate_draft(draft("Your balance is ₹500."), [chunk("See schedule.")], policy)
    )


@pytest.mark.parametrize("text", ["We will reply by 2026-10-20.", "We will reply tomorrow."])
def test_unsupported_calendar_deadlines_block(text):
    assert "UNGROUNDED_COMMITMENT" in codes(
        validate_draft(draft(text, "commitment"), [chunk("Service standard.")])
    )


def test_historical_acknowledgement_does_not_hide_new_decision():
    text = "You said your claim was rejected; your claim is approved now."
    assert "UNAUTHORISED_DECISION" in codes(validate_draft(draft(text), [chunk(text)]))


@pytest.mark.parametrize("text", ["Rs500000", "INR500000", "Rs.500000", "5lakh"])
def test_currency_and_unit_without_spaces(text):
    assert normalise_numbers(text) == {500000}

"""Deterministic, fail-closed validation of customer-facing sentence drafts."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.models.schemas import Chunk, Draft, PolicyRecord, ValidationResult, Violation

_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lac|crore)s?\b)?", re.I)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per cent\b)", re.I)
_DATE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b"
)
_TIMELINE = re.compile(
    r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|thirty)"
    r"\s*[- ]?\s*((?:working|business|calendar)\s+)?"
    r"(hours?|days?|weeks?|months?|years?)\b",
    re.I,
)
_WORD_NUMBERS = dict(
    zip(
        "one two three four five six seven eight nine ten fifteen thirty".split(),
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 30),
        strict=True,
    )
)
_MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "january february march april may june july august september october november december"
        ).split(),
        1,
    )
}


def _dates(text: str) -> tuple[set[date], str]:
    found = set()

    def replace(match: re.Match) -> str:
        raw = match.group()
        try:
            if re.fullmatch(r"\d{4}-\d+-\d+", raw):
                year, month, day = map(int, raw.split("-"))
            elif re.search(r"[A-Za-z]", raw):
                day_text, month_text, year_text = raw.split()
                day, year = int(day_text), int(year_text)
                month = next(v for k, v in _MONTHS.items() if k.startswith(month_text.lower()))
            else:
                day, month, year = map(int, re.split(r"[/-]", raw))
            found.add(date(year, month, day))
        except (ValueError, StopIteration):
            # Preserve invalid date text so it cannot silently pass as grounded.
            return raw
        return " "

    return found, _DATE.sub(replace, text)


def _figures(text: str) -> tuple[set[Decimal], set[Decimal]]:
    _, without_dates = _dates(text)
    percentages = {Decimal(m.group(1)) for m in _PERCENT.finditer(without_dates)}
    ordinary = _PERCENT.sub(" ", without_dates)
    ordinary = re.sub(r"\b(?:INR|Rs\.?)(?=\s*\d)", " ", ordinary, flags=re.I)
    values = set()
    for match in _NUMBER.finditer(ordinary):
        parts = match.group().lower().replace(",", "").split()
        # Unit may be adjacent, e.g. 5lakh.
        unit_match = re.fullmatch(
            r"([\d.]+)\s*(lakh|lac|crore)s?", match.group().lower().replace(",", "")
        )
        if unit_match:
            number, unit = unit_match.groups()
            values.add(Decimal(number) * (10000000 if unit == "crore" else 100000))
        else:
            values.add(Decimal(parts[0]))
    return values, percentages


def normalise_numbers(text: str) -> set[int]:
    """Return integral ordinary figures; dates and percentages are separate domains.

    Fractional values remain exact Decimals inside validation and are never rounded.
    """
    values, _ = _figures(text)
    return {int(value) for value in values if value == value.to_integral_value()}


normalize_numbers = normalise_numbers


def _timelines(text: str) -> set[tuple[Decimal, str, str]]:
    result = set()
    for match in _TIMELINE.finditer(text):
        quantity, qualifier, unit = match.groups()
        amount = (
            Decimal(_WORD_NUMBERS[quantity.lower()])
            if quantity.lower() in _WORD_NUMBERS
            else Decimal(quantity)
        )
        qualifier = (qualifier or "").strip().lower().replace("business", "working")
        result.add((amount, qualifier, unit.lower().rstrip("s")))
    return result


def _decision(text: str) -> bool:
    # Only exempt reported historical clauses, never a subsequent present decision.
    text = re.sub(
        r"\b(?:you\s+(?:said|reported|mentioned|stated)|according to your (?:email|message))"
        r"\b[^.;!?]*?\b(?:was|had been)\s+(?:approved|rejected|denied|payable)\b",
        "",
        text,
        flags=re.I,
    )
    decision_word = r"(?:approv\w*|reject\w*|deni(?:ed|al)|payable)"
    return bool(
        re.search(
            rf"\bclaim\b[^.;!?]{{0,100}}\b{decision_word}\b|\b{decision_word}\b[^.;!?]{{0,100}}\bclaim\b",
            text,
            re.I,
        )
    )


def validate_draft(
    draft: Draft,
    chunks: list[Chunk],
    policy: PolicyRecord | None = None,
    sla_texts: list[str] | None = None,
) -> ValidationResult:
    """Collect every violation against only this run's retrieved corpus and SLA."""
    violations: list[Violation] = []

    def add(code: str, index: int, detail: str) -> None:
        violations.append(Violation(code=code, sentence_index=index, detail=detail))

    if draft.cannot_answer or not any(
        s.text.strip() and s.kind != "courtesy" for s in draft.sentences
    ):
        add("EMPTY_DRAFT", -1, "Draft cannot answer or contains no substantive response.")
    retrieved = {chunk.clause_id: chunk.content for chunk in chunks}
    policy_dates = {
        value
        for value in (policy.model_dump().values() if policy else [])
        if isinstance(value, date)
    }
    timeline_sources = "\n".join([*retrieved.values(), *(sla_texts or [])])
    grounded_timelines = _timelines(timeline_sources)
    for index, sentence in enumerate(draft.sentences):
        text = sentence.text
        source = retrieved.get(sentence.cite or "", "")
        if sentence.kind in {"factual", "commitment"} and not sentence.cite:
            add("MISSING_CITATION", index, "Factual and commitment sentences require a citation.")
        if sentence.cite and sentence.cite not in retrieved:
            add("PHANTOM_CITATION", index, f"Clause {sentence.cite} was not retrieved in this run.")
        if sentence.kind == "factual":
            figures, percentages = _figures(text)
            source_figures, source_percentages = _figures(source)
            if figures - source_figures or percentages - source_percentages:
                add(
                    "UNSOURCED_FIGURE",
                    index,
                    "A figure or percentage is absent from the cited clause.",
                )
            dates, _ = _dates(text)
            source_dates, _ = _dates(source)
            if dates - source_dates - policy_dates or any(_DATE.finditer(_dates(text)[1])):
                add(
                    "UNSOURCED_DATE",
                    index,
                    "A date is absent from the cited clause and policy record.",
                )
        if _decision(text):
            add("UNAUTHORISED_DECISION", index, "Customer drafts must not decide claim outcomes.")
        # Enforce across sentence kinds so a mislabeled courtesy cannot promise a deadline.
        timelines = _timelines(text)
        promises = sentence.kind == "commitment" or re.search(
            r"\b(?:we will|we shall|we'll|within|by|no later than)\b", text, re.I
        )
        deadline_dates, _ = _dates(text)
        source_deadline_dates, _ = _dates(timeline_sources)
        relative_deadlines = set(
            re.findall(
                r"\b(?:today|tomorrow|immediately|next week|next month|same day)\b", text, re.I
            )
        )
        unsupported_relative = any(
            deadline.lower() not in timeline_sources.lower() for deadline in relative_deadlines
        )
        if promises and (
            timelines - grounded_timelines
            or deadline_dates - source_deadline_dates
            or unsupported_relative
        ):
            add(
                "UNGROUNDED_COMMITMENT",
                index,
                "Timeline quantity and units require policy or configured SLA support.",
            )
    return ValidationResult(passed=not violations, violations=violations)

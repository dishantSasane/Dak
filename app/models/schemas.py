"""Pydantic schemas and JSON contracts from 03-data-model.md §4, plus API
request/response models from 05-api-and-ui.md.

No invented fields: contract shapes match the data model exactly.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["query", "complaint", "claim", "mixed", "unknown"]
SentenceKind = Literal["courtesy", "factual", "procedural", "commitment"]
Sentiment = Literal["neutral", "frustrated", "angry"]
Urgency = Literal["low", "medium", "high"]

ESCALATION_REASONS = (
    "injection_detected",
    "regulatory_language",
    "low_confidence",
    "mixed_intent",
    "unclassifiable",
    "policy_not_found",
    "routing_conflict",
    "validation_failed",
    "no_relevant_context",
    "tool_failure",
    "model_output_invalid",
    "unidentifiable",
    "out_of_scope",
    "repeat_complainant",
    "potentially_valid_grievance",
)


# ---------------------------------------------------------------------------
# §4.1 TriageAssessment — policy_found is NOT here; the supervisor sets it
# from the lookup_policy tool result.
# ---------------------------------------------------------------------------


class TriageAssessment(BaseModel):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    policy_number: str | None = None
    policy_number_present: bool
    claim_amount: float | None = None
    sentiment: Sentiment
    urgency: Urgency
    regulatory_language: bool
    injection_detected: bool
    reasoning: str


# ---------------------------------------------------------------------------
# §4.2 Draft
# ---------------------------------------------------------------------------


class DraftSentence(BaseModel):
    text: str
    kind: SentenceKind
    cite: str | None = None


class Draft(BaseModel):
    sentences: list[DraftSentence] = Field(default_factory=list)
    cannot_answer: bool = False
    cannot_answer_reason: str | None = None


# ---------------------------------------------------------------------------
# §4.3 ValidationResult
# ---------------------------------------------------------------------------


class Violation(BaseModel):
    code: str
    sentence_index: int
    detail: str


class ValidationResult(BaseModel):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §4.4 CoverageAssessment
# ---------------------------------------------------------------------------


class CoverageAssessment(BaseModel):
    event_described: str
    potentially_covered: bool
    supporting_clauses: list[str] = Field(default_factory=list)
    exclusions_triggered: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# §4.5 EligibilityResult — deterministic, no model
# ---------------------------------------------------------------------------


class EligibilityResult(BaseModel):
    policy_active_on_event_date: bool
    initial_waiting_period_elapsed: bool
    pre_existing_waiting_period_elapsed: bool
    sum_insured_remaining: Decimal
    co_pay_percent: int
    indicative_payable: Decimal | None = None
    blocking_conditions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §4.6 EscalationBrief
# ---------------------------------------------------------------------------


class EscalationBrief(BaseModel):
    headline: str
    reason_code: str
    what_arrived: str
    what_system_determined: str
    what_system_could_not_determine: str
    suggested_next_step: str
    confidence_in_brief: float


# ---------------------------------------------------------------------------
# Tool result objects (04-agent-specs.md §8)
# ---------------------------------------------------------------------------


class PolicyRecord(BaseModel):
    """A policy row, as returned by tools."""

    policy_number: str
    holder_name: str
    holder_email: str
    cancelled_date: date | None = None
    product_code: str
    product_name: str
    status: str
    start_date: date
    end_date: date
    waiting_period_end: date | None = None
    pre_existing_waiting_period_end: date | None = None
    sum_insured: Decimal
    sum_insured_remaining: Decimal
    premium: Decimal
    payment_frequency: str
    last_payment_date: date | None = None
    co_pay_percent: int
    riders: list[str] = Field(default_factory=list)


class PolicyLookupResult(BaseModel):
    found: bool
    active: bool
    product_code: str | None = None
    policy: PolicyRecord | None = None


class CaseHistoryEntry(BaseModel):
    kind: Literal["claim", "grievance"]
    ref_id: str
    date: date
    status: str
    summary: str
    disputed_internally: bool = False
    rejection_reason: str | None = None


class CaseHistory(BaseModel):
    claims: list[CaseHistoryEntry] = Field(default_factory=list)
    grievances: list[CaseHistoryEntry] = Field(default_factory=list)


class AttachmentReport(BaseModel):
    present: list[str] = Field(default_factory=list)
    count: int = 0


class InjectionReport(BaseModel):
    detected: bool
    matched_patterns: list[str] = Field(default_factory=list)


class GrievanceType(BaseModel):
    sub_type: str
    reasoning: str = ""


class Chunk(BaseModel):
    clause_id: str
    clause_title: str
    content: str
    score: float


# ---------------------------------------------------------------------------
# API models (05-api-and-ui.md)
# ---------------------------------------------------------------------------


class ManualEmailRequest(BaseModel):
    sender: str
    subject: str
    body: str


class WebhookAccepted(BaseModel):
    status: Literal["accepted", "duplicate"]
    token: str | None = None


class CaseEmailItem(BaseModel):
    direction: str
    subject: str
    received_at: datetime
    preview: str


class CaseRunItem(BaseModel):
    id: int
    status: str
    category: str | None
    confidence: float | None
    route: str | None
    escalation_reason: str | None
    duration_ms: int | None


class CasePublicResponse(BaseModel):
    token: str
    status: str
    created_at: datetime
    emails: list[CaseEmailItem]
    runs: list[CaseRunItem]


class RunEventItem(BaseModel):
    seq: int
    node: str
    event_type: str
    payload: dict
    duration_ms: int | None = None
    created_at: datetime


class RunEventsResponse(BaseModel):
    run_id: int
    status: str
    events: list[RunEventItem]


class ReviewQueueItem(BaseModel):
    run_id: int
    token: str
    category: str | None
    confidence: float | None
    subject: str
    from_: str = Field(alias="from")
    escalation_reason: str | None
    waiting_since: datetime
    validation_passed: bool | None


class ReviewQueueResponse(BaseModel):
    total: int
    items: list[ReviewQueueItem]


class ReviewActionRequest(BaseModel):
    action: Literal["approved", "edited", "rejected"]
    edited_text: str | None = None
    reviewer_note: str | None = None


class HealthResponse(BaseModel):
    status: str
    db: bool
    redis: bool

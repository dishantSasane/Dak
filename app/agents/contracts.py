"""Agent-local output contracts; no new persistence columns are introduced."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas import CoverageAssessment, Draft


class RejectRoute(BaseModel):
    suggested: Literal["query", "complaint", "claim"]
    reason: str


class SpecialistOutput(BaseModel):
    draft: Draft
    reject_route: RejectRoute | None = None
    internal_note: str | None = None


class ClaimFacts(BaseModel):
    event_date: date | None = None
    accidental: bool = False
    pre_existing: bool = False
    required_documents: list[str] = Field(default_factory=list)


class ClaimOutput(BaseModel):
    draft: Draft
    coverage_assessment: CoverageAssessment

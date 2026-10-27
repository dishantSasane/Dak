"""Create explicitly labelled recorded-fixture runs for local UI verification.

No Gemini call is made. Tools, retrieval, eligibility, validation, checkpoints,
run events and persistence execute normally. Never use these runs as live eval.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta
from html import unescape
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from app.db.models import Case, Email, Policy, Run
from app.db.session import get_engine, get_sessionmaker
from app.graph.build import process_run
from app.llm.gemini import GeminiAdapter
from app.llm.rate_limit import RateLimiter
from app.tokens import generate_token


class NoWait(RateLimiter):
    async def acquire(self, *, eval_run: bool = False) -> None:
        return None


def fixture_adapter(category: str, event_date: str | None = None) -> GeminiAdapter:
    async def transport(model: str, system: str, prompt: str, schema: type) -> SimpleNamespace:
        context = {}
        if "<data_context>" in prompt:
            context = json.loads(
                unescape(prompt.split("<data_context>\n", 1)[1].split("\n</data_context>")[0])
            )
        if schema.__name__ == "TriageAssessment":
            parsed = dict(
                category=category,
                confidence=0.96,
                policy_number_present=True,
                policy_number=None,
                sentiment="neutral",
                urgency="medium",
                regulatory_language=False,
                injection_detected=False,
                reasoning="Recorded fixture category for local UI verification.",
            )
        elif schema.__name__ == "GrievanceType":
            parsed = {
                "sub_type": "service_quality",
                "reasoning": "Recorded service-review fixture.",
            }
        elif schema.__name__ == "ClaimFacts":
            parsed = {
                "event_date": event_date,
                "accidental": False,
                "pre_existing": False,
                "required_documents": ["claim form", "discharge summary", "itemised hospital bill"],
            }
        elif schema.__name__ in ("SpecialistOutput", "ClaimOutput"):
            chunks = context.get("clauses", [])
            preferred = (
                "ASP-C07"
                if category == "query"
                else ("ASP-C13" if category == "claim" else "ASP-C17")
            )
            chosen = next((chunk for chunk in chunks if chunk["clause_id"] == preferred), chunks[0])
            sentence = chosen["content"].split(". ")[0].rstrip(".") + "."
            parsed = {
                "draft": {
                    "sentences": [
                        {
                            "text": sentence,
                            "kind": "procedural" if category != "query" else "factual",
                            "cite": chosen["clause_id"],
                        }
                    ]
                },
                "internal_note": "RECORDED FIXTURE: review supplied policy/history evidence.",
            }
            if category == "claim":
                parsed["coverage_assessment"] = {
                    "event_described": "Recorded hospital admission fixture",
                    "potentially_covered": False,
                    "supporting_clauses": [chosen["clause_id"]],
                    "exclusions_triggered": [],
                    "notes": "Advisory only; inspect the computed blockers.",
                }
        elif schema.__name__ == "EscalationBrief":
            reason = context["reason"]
            parsed = dict(
                headline=f"Recorded fixture: {reason.replace('_', ' ')}",
                reason_code=reason,
                what_arrived="A synthetic local verification email.",
                what_system_determined=(
                    "See the actual tool results and draft attempts in this trace."
                ),
                what_system_could_not_determine=(
                    "No live model inference or claim decision was made."
                ),
                suggested_next_step="Review the recorded evidence and save a decision.",
                confidence_in_brief=1,
            )
        else:
            raise ValueError(f"Unexpected fixture schema: {schema.__name__}")
        return SimpleNamespace(
            parsed=parsed,
            text=None,
            usage_metadata=SimpleNamespace(prompt_token_count=0, candidates_token_count=0),
        )

    return GeminiAdapter(transport=transport, limiter=NoWait())


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create",
        action="store_true",
        required=True,
        help="Explicitly create recorded fixture runs in the configured synthetic DB",
    )
    parser.parse_args()
    factory = get_sessionmaker()
    try:
        for category in ["query", "complaint", "claim"]:
            async with factory() as session:
                policy = await session.scalar(
                    select(Policy)
                    .where(
                        Policy.product_code == "ASP",
                        Policy.status == ("lapsed" if category == "claim" else "active"),
                    )
                    .order_by(Policy.policy_number)
                    .limit(1)
                )
                if policy is None:
                    raise ValueError("Load synthetic seeds before creating fixtures")
                event_date = (policy.end_date + timedelta(days=1)).isoformat()
                text = {
                    "query": "What is the initial illness waiting period for my health product?",
                    "complaint": (
                        "I am unhappy about service on my hospital claim. "
                        "Please review my complaint."
                    ),
                    "claim": (
                        f"I was admitted to hospital on {event_date}. "
                        "I would like to notify a claim."
                    ),
                }[category]
                case = Case(
                    token=generate_token(),
                    contact_email=policy.holder_email,
                    policy_number=policy.policy_number,
                )
                session.add(case)
                await session.flush()
                email = Email(
                    case_id=case.id,
                    message_id=f"fixture-{uuid4()}@local",
                    direction="inbound",
                    sender=policy.holder_email,
                    recipient="demo@example.test",
                    subject=f"[RECORDED FIXTURE] {category.title()} - {policy.policy_number}",
                    body_plain=f"{text}\nPolicy: {policy.policy_number}",
                    raw_payload={"source": "recorded_fixture", "attachments": []},
                )
                session.add(email)
                await session.flush()
                run = Run(
                    email_id=email.id, case_id=case.id, thread_id=str(uuid4()), status="running"
                )
                session.add(run)
                await session.commit()
                run_id = run.id
            result = await process_run(
                run_id, factory, client=fixture_adapter(category, event_date)
            )
            print(f"{category}: run {run_id}, {result['status']}; /runs/{run_id}")
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())

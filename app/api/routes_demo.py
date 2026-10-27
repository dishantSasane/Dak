"""Configuration for the synthetic local demo; no live inbound address assumed."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Policy
from app.db.session import get_session

router = APIRouter(tags=["demo"])


@router.get("/api/demo/config")
async def demo_config(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    today = date.today()
    in_term = (Policy.start_date <= today, Policy.end_date >= today)
    scenarios = {
        "active": (
            Policy.status == "active",
            *in_term,
            (Policy.product_code == "MOT")
            | Policy.waiting_period_end.is_(None)
            | (Policy.waiting_period_end < today),
        ),
        "lapsed": (Policy.status == "lapsed", Policy.end_date < today),
        "waiting_period": (
            Policy.status == "active",
            *in_term,
            Policy.product_code.in_(("ASP", "TRM")),
            Policy.waiting_period_end >= today,
        ),
    }
    policies = []
    for scenario, conditions in scenarios.items():
        policy = await session.scalar(
            select(Policy).where(*conditions).order_by(Policy.policy_number).limit(1)
        )
        if policy is not None:
            policies.append((scenario, policy))
    prompts = (
        (
            "Coverage query",
            "Question about general coverage",
            "Could you explain the general coverage and exclusions",
        ),
        (
            "Complaint",
            "Complaint about a service delay",
            "I am unhappy with the delay in receiving a response. Please review my complaint",
        ),
        (
            "Claim request",
            "Claim document checklist",
            "I need to register a claim. Please explain the required documents",
        ),
    )
    return {
        "product_name": "Dak",
        "inbound_address": None,
        "repository_url": None,
        "synthetic": True,
        "sample_policies": [
            {
                "policy_number": p.policy_number,
                "product_code": p.product_code,
                "product_name": p.product_name,
                "status": p.status,
                "scenario": scenario,
            }
            for scenario, p in policies
        ],
        "samples": [
            {
                "label": prompts[index][0],
                "sender": p.holder_email,
                "subject": f"{prompts[index][1]} — {p.policy_number}",
                "body": f"{prompts[index][2]} for policy {p.policy_number}. "
                "This is a synthetic demonstration.",
            }
            for index, (_, p) in enumerate(policies)
        ],
    }

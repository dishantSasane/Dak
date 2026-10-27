"""Narrow, traced dependencies made available to one agent node at a time."""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any, cast

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.semantic import lookup_answer
from app.graph.state import RunState
from app.llm.gemini import ModelClient
from app.models.schemas import Chunk, PolicyRecord
from app.rag.retrieve import search_policy_docs
from app.tools.base import ToolContext, write_event
from app.tools.policy import PolicyTools


class RetrievedContext(BaseModel):
    chunks: list[Chunk] = Field(default_factory=list)


class ToolFailure(RuntimeError):
    pass


class AgentContext:
    def __init__(
        self, state: RunState, session: AsyncSession, client: ModelClient, node: str
    ) -> None:
        self.state = state
        self.session = session
        self.client = client
        self.node = node
        self.tools = ToolContext(session, state["run_id"], cast(dict[str, Any], state))
        self.policies = PolicyTools(self.tools)

    def policy(self) -> PolicyRecord | None:
        value = self.state.get("policy_record")
        return PolicyRecord.model_validate(value) if value else None

    def product(self) -> str | None:
        policy = self.policy()
        if policy:
            return policy.product_code
        text = f"{self.state['subject']} {self.state['body']}".lower()
        groups = {
            "ASP": (
                r"\b(health|hospital|hospitalisation|hospitalization|medical|"
                r"co-pay|copay|arogya)\b"
            ),
            "MOT": r"\b(motor|car|vehicle|garage|towing|roadside)\b",
            "TRM": r"\b(term life|life insurance|life cover|death|nominee|bereavement)\b",
        }
        matches = [code for code, pattern in groups.items() if re.search(pattern, text)]
        return matches[0] if len(matches) == 1 else None

    async def model[T: BaseModel](
        self,
        schema: type[T],
        instruction: str,
        context: dict | None = None,
        *,
        light: bool = False,
    ) -> T:
        from app.agents.prompts import BASE

        # Escape delimiter characters so a sender cannot close the data block.
        email = escape(f"Subject: {self.state['subject']}\n{self.state['body']}", quote=False)
        prompt = f"<customer_email>\n{email}\n</customer_email>"
        if context:
            prompt += "\n<data_context>\n" + escape(json.dumps(context, default=str), quote=False)
            prompt += "\n</data_context>"
        return await self.client.generate(
            session=self.session,
            run_id=self.state["run_id"],
            node=self.node,
            schema=schema,
            system=BASE + instruction,
            prompt=prompt,
            light=light,
        )

    async def retrieve(self, product_code: str) -> list[Chunk]:
        async def operation() -> RetrievedContext:
            return RetrievedContext(
                chunks=await search_policy_docs(
                    self.session,
                    f"{self.state['subject']}\n{self.state['body']}",
                    product_code,
                )
            )

        result = await self.tools.call(
            "search_policy_docs", {"product_code": product_code}, operation, RetrievedContext, ttl=0
        )
        if not result.ok or result.value is None:
            raise ToolFailure(result.error or "Retrieval failed")
        return result.value.chunks

    async def cached(self, product_code: str) -> tuple[dict, list[Chunk]] | None:
        result = await lookup_answer(
            self.session,
            f"{self.state['subject']}\n{self.state['body']}",
            product_code,
        )
        if result is None:
            return None
        await write_event(
            self.session,
            self.state["run_id"],
            self.node,
            "decision",
            {
                "reason": "semantic_cache_hit",
                "cache_hit": True,
                "retrieved_chunks": [chunk.model_dump() for chunk in result.chunks],
            },
        )
        return result.draft.model_dump(mode="json"), result.chunks


def refusal(reason: str) -> dict:
    return {
        "draft": {"sentences": [], "cannot_answer": True, "cannot_answer_reason": reason},
        "escalation_reason": reason,
    }

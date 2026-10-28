"""Bounded LangGraph execution with durable node receipts and PostgreSQL checkpoints."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import claim, complaint, escalation, query, triage
from app.agents.runtime import AgentContext, ToolFailure
from app.cache.semantic import write_answer
from app.config import get_settings
from app.db.models import Case, CaseFile, Email, Run, RunEvent
from app.db.models import Draft as DraftRow
from app.graph.state import RunState
from app.graph.supervisor import route_decision
from app.llm.gemini import GeminiAdapter, ModelClient, ModelError, ModelRateLimited
from app.models.schemas import Chunk, Draft, TriageAssessment
from app.tools.base import write_event
from app.validator.citations import validate_draft

logger = logging.getLogger(__name__)
Node = Callable[[AgentContext], Awaitable[dict]]


async def _supervisor(ctx: AgentContext) -> dict:
    target, reason = route_decision(ctx.state)
    reroutes = ctx.state.get("reroute_count", 0)
    rejected = ctx.state.get("reject_route")
    if rejected and target != "escalation_agent":
        reroutes += 1
    await write_event(
        ctx.session,
        ctx.state["run_id"],
        "supervisor",
        "decision",
        {"next_node": target, "reason": reason, "reroute_count": reroutes},
    )
    await ctx.session.execute(
        update(Run)
        .where(Run.id == ctx.state["run_id"])
        .values(
            route=target,
            reroute_count=reroutes,
        )
    )
    await ctx.session.commit()
    result = {
        "next_node": target,
        "reject_route": None,
        "reroute_count": reroutes,
        "route_history": ctx.state.get("route_history", []) + [{"node": target, "reason": reason}],
    }
    if target == "escalation_agent":
        result["escalation_reason"] = reason
    else:
        result["originating_agent"] = target
    return result


async def _validator(ctx: AgentContext) -> dict:
    draft = Draft.model_validate(ctx.state.get("draft") or {"cannot_answer": True})
    chunks = [Chunk.model_validate(value) for value in ctx.state.get("retrieved_chunks", [])]
    validation = validate_draft(draft, chunks, ctx.policy())
    attempt = ctx.state.get("validator_retry_count", 0) + 1
    values = dict(
        run_id=ctx.state["run_id"],
        attempt=attempt,
        sentences=[sentence.model_dump() for sentence in draft.sentences],
        rendered_text=" ".join(sentence.text for sentence in draft.sentences),
        citations=[chunk.model_dump() for chunk in chunks],
        validation_passed=validation.passed,
        violations=[item.model_dump() for item in validation.violations],
    )
    await ctx.session.execute(
        insert(DraftRow)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["run_id", "attempt"])
    )
    await ctx.session.commit()
    result: dict[str, Any] = {
        "validation": validation.model_dump(mode="json"),
        "violations": [item.model_dump() for item in validation.violations],
    }
    if validation.passed:
        if ctx.state.get("escalate_flag"):
            result["next_node"] = "escalation_agent"
        else:
            result.update(next_node="finalize", status="pending_review")
        if (
            ctx.state.get("originating_agent") == "query_agent"
            and not ctx.state.get("cache_hit")
            and ctx.state.get("product_code")
        ):
            await write_answer(
                ctx.session,
                f"{ctx.state['subject']}\n{ctx.state['body']}",
                str(ctx.state["product_code"]),
                draft,
                validation,
                chunks,
                used_customer_tools=ctx.state.get("used_customer_tools", False),
                numbers_from_policy_record=ctx.state.get("numbers_from_policy_record", False),
            )
    elif ctx.state.get("validator_retry_count", 0) < get_settings().MAX_VALIDATOR_RETRIES:
        result.update(
            next_node=ctx.state["originating_agent"],
            validator_retry_count=ctx.state.get("validator_retry_count", 0) + 1,
        )
        await write_event(
            ctx.session,
            ctx.state["run_id"],
            "validator",
            "decision",
            {"reason": "validator_retry", "violations": result["violations"]},
        )
    else:
        result.update(next_node="escalation_agent", escalation_reason="validation_failed")
    return result


async def _finalize(ctx: AgentContext) -> dict:
    run = await ctx.session.get(Run, ctx.state["run_id"])
    if run is None:
        raise RuntimeError("Run disappeared during finalization")
    status = "escalated" if ctx.state.get("escalation_reason") else "pending_review"
    run.status = status
    run.escalation_reason = ctx.state.get("escalation_reason")
    run.validator_retry_count = ctx.state.get("validator_retry_count", 0)
    started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=UTC)
    run.finished_at = datetime.now(UTC)
    run.duration_ms = int((run.finished_at - started).total_seconds() * 1000)
    if ctx.state.get("cache_hit"):
        run.cache_hits += 1
    case = await ctx.session.get(Case, run.case_id)
    if case is not None and status == "escalated":
        case.status = "escalated"
    await ctx.session.commit()
    return {"status": status}


def build_graph(
    factory: async_sessionmaker[AsyncSession],
    client: ModelClient,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    builder = StateGraph(RunState)

    def node(name: str, operation: Node) -> Callable[[RunState], Awaitable[dict]]:
        async def invoke(state: RunState) -> dict:
            began = monotonic()
            # A receipt makes a completed DB side effect recoverable if a process
            # dies after commit but before LangGraph writes its next checkpoint.
            key = (
                f"{name}:{state.get('reroute_count', 0)}:"
                f"{state.get('validator_retry_count', 0)}:{len(state.get('route_history', []))}"
            )
            async with factory() as session:
                events = (
                    await session.scalars(
                        select(RunEvent)
                        .where(
                            RunEvent.run_id == state["run_id"],
                            RunEvent.node == name,
                            RunEvent.event_type.in_(["node_start", "node_end"]),
                        )
                        .order_by(RunEvent.seq)
                    )
                ).all()
                for event in reversed(events):
                    if (
                        event.event_type == "node_end"
                        and event.payload.get("checkpoint_key") == key
                    ):
                        return event.payload["state_update"]
                if not any(event.payload.get("checkpoint_key") == key for event in events):
                    await write_event(
                        session, state["run_id"], name, "node_start", {"checkpoint_key": key}
                    )
                working = RunState(**state)
                context = AgentContext(working, session, client, name)
                try:
                    result = await operation(context)
                except ModelRateLimited:
                    raise
                except (ModelError, ToolFailure) as exc:
                    reason = (
                        "tool_failure" if isinstance(exc, ToolFailure) else "model_output_invalid"
                    )
                    result = {
                        "escalation_reason": reason,
                        "error": str(exc),
                        "next_node": "escalation_agent",
                    }
                    await write_event(
                        session,
                        state["run_id"],
                        name,
                        "error",
                        {"reason": reason, "detail": str(exc)},
                    )
                for marker in ("used_customer_tools", "numbers_from_policy_record", "tool_error"):
                    if marker in working:
                        result[marker] = working[marker]
                if name == "triage" and result.get("triage"):
                    assessment = TriageAssessment.model_validate(result["triage"])
                    await session.execute(
                        update(Run)
                        .where(Run.id == state["run_id"])
                        .values(
                            category=assessment.category,
                            confidence=assessment.confidence,
                        )
                    )
                    await session.commit()
                if result.get("case_file"):
                    values = dict(run_id=state["run_id"], **result["case_file"])
                    await session.execute(
                        insert(CaseFile)
                        .values(**values)
                        .on_conflict_do_update(index_elements=["run_id"], set_=result["case_file"])
                    )
                    await session.commit()
                payload = {**result, "checkpoint_key": key, "state_update": result}
                await write_event(
                    session,
                    state["run_id"],
                    name,
                    "node_end",
                    payload,
                    int((monotonic() - began) * 1000),
                )
                return result

        return invoke

    operations = {
        "triage": triage.run,
        "supervisor": _supervisor,
        "query_agent": query.run,
        "complaint_agent": complaint.run,
        "claim_agent": claim.run,
        "validator": _validator,
        "escalation_agent": escalation.run,
        "finalize": _finalize,
    }
    for name, operation in operations.items():
        builder.add_node(name, RunnableLambda(node(name, operation)))
    builder.add_edge(START, "triage")
    builder.add_edge("triage", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["next_node"],
        ["query_agent", "complaint_agent", "claim_agent", "escalation_agent"],
    )

    def after_specialist(state: RunState) -> str:
        if state.get("error") or state.get("tool_error"):
            return "escalation_agent"
        if state.get("reject_route"):
            return "supervisor"
        draft = state.get("draft")
        if draft is None or draft.get("cannot_answer"):
            return "escalation_agent"
        return "validator"

    for specialist in ("query_agent", "complaint_agent", "claim_agent"):
        builder.add_conditional_edges(
            specialist, after_specialist, ["supervisor", "validator", "escalation_agent"]
        )
    builder.add_conditional_edges(
        "validator",
        lambda state: state["next_node"],
        ["query_agent", "complaint_agent", "claim_agent", "escalation_agent", "finalize"],
    )
    builder.add_edge("escalation_agent", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)


async def setup_checkpoint_schema() -> None:
    """Apply LangGraph's Postgres migrations before the worker accepts jobs."""
    dsn = (
        make_url(get_settings().DATABASE_URL)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    logger.info("initializing LangGraph checkpoint schema")
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
    logger.info("LangGraph checkpoint schema ready")


async def process_run(
    run_id: int,
    factory: async_sessionmaker[AsyncSession],
    client: ModelClient | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    initialize_checkpointer: bool = True,
    use_postgres_checkpointer: bool = True,
) -> RunState:
    async with factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError("Unknown run")
        email = await session.get(Email, run.email_id)
        case = await session.get(Case, run.case_id)
        if email is None or case is None:
            raise ValueError("Run has no source email or case")
        initial = RunState(
            run_id=run.id,
            email_id=email.id,
            case_id=case.id,
            token=case.token,
            subject=email.subject,
            body=email.body_plain,
            raw_payload=email.raw_payload,
            reroute_count=0,
            validator_retry_count=0,
            used_customer_tools=False,
            numbers_from_policy_record=False,
            route_history=[],
            status="running",
        )
        thread_id = run.thread_id

    async def execute(saver: BaseCheckpointSaver | None) -> RunState:
        graph = build_graph(factory, client or GeminiAdapter(), saver)
        config: Any = {"configurable": {"thread_id": thread_id}, "recursion_limit": 32}
        snapshot = await graph.aget_state(config) if saver else None
        if snapshot and snapshot.values and not snapshot.next:
            return cast(RunState, snapshot.values)
        result = await graph.ainvoke(None if snapshot and snapshot.values else initial, config)
        return cast(RunState, result)

    if checkpointer is not None:
        return await execute(checkpointer)
    if not use_postgres_checkpointer:
        return await execute(None)
    dsn = (
        make_url(get_settings().DATABASE_URL)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        if initialize_checkpointer:
            await saver.setup()
        return await execute(saver)

"""Metrics endpoints — 05-api-and-ui.md §1.4.

GET /api/metrics/summary (window-based operational metrics from runs) and
GET /api/metrics/eval/{eval_run_id} (corpus-run metrics computed from
per-email eval_results rows).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Draft, EvalEmail, EvalResult, EvalRun, Run
from app.db.session import get_session

router = APIRouter(tags=["metrics"])

TERMINAL_STATUSES = ("pending_review", "approved", "rejected", "escalated", "failed")


@router.get("/api/metrics/summary")
async def metrics_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    window_days: int = Query(default=7, ge=1, le=365),
) -> dict:
    since = datetime.now(UTC) - timedelta(days=window_days)
    runs = (await session.execute(select(Run).where(Run.started_at >= since))).scalars().all()

    processed = len(runs)
    by_category: dict[str, int] = defaultdict(int)
    escalation_reasons: dict[str, int] = defaultdict(int)
    escalated = 0
    prompt_tokens = completion_tokens = model_calls_total = 0
    durations: list[int] = []
    cache_hits = 0

    for r in runs:
        if r.status == "escalated":
            escalated += 1
            if r.escalation_reason:
                escalation_reasons[r.escalation_reason] += 1
        elif r.category:
            by_category[r.category] += 1
        else:
            by_category["escalated"] += 1
        prompt_tokens += r.total_prompt_tokens
        completion_tokens += r.total_completion_tokens
        model_calls_total += r.model_calls
        cache_hits += r.cache_hits
        if r.duration_ms is not None:
            durations.append(r.duration_ms)

    # validator block rate + per-agent blocks from drafts
    draft_rows = (
        await session.execute(
            select(Draft.run_id, Draft.validation_passed, Run.route, Draft.sentences)
            .join(Run, Run.id == Draft.run_id)
            .where(Run.started_at >= since)
        )
    ).all()
    blocked_attempts = sum(1 for _, passed, _, _ in draft_rows if not passed)
    blocks_by_agent: dict[str, int] = defaultdict(int)
    grounded_total = grounded_ok = 0
    for _, passed, route, sentences in draft_rows:
        if not passed:
            if route:
                blocks_by_agent[route] += 1
            continue
        for sentence in sentences or []:
            if sentence.get("kind") in ("factual", "commitment"):
                grounded_total += 1
                grounded_ok += bool(sentence.get("cite"))
    citation_grounding_rate = grounded_ok / grounded_total if grounded_total else None

    def percentile(values: list[int], p: float) -> int | None:
        if not values:
            return None
        ordered = sorted(values)
        idx = min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))
        return ordered[idx]

    # Run.cache_hits includes tool-cache activity; model_calls is not the
    # number of eligible semantic lookups. Do not fabricate a semantic rate.

    return {
        "window": f"{window_days}d",
        "emails_processed": processed,
        "by_category": dict(by_category),
        "escalation_rate": round(escalated / processed, 4) if processed else None,
        "escalation_reasons": dict(escalation_reasons),
        "validator_block_rate": round(blocked_attempts / len(draft_rows), 4)
        if draft_rows
        else None,
        "validator_blocks_by_agent": dict(blocks_by_agent),
        "citation_grounding_rate": round(citation_grounding_rate, 4)
        if citation_grounding_rate is not None
        else None,
        "cache": {"semantic_hit_rate": None, "hits": cache_hits},
        "latency_ms": {"p50": percentile(durations, 50), "p95": percentile(durations, 95)},
        "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
        "model_calls_per_email": round(model_calls_total / processed, 2) if processed else None,
    }


@router.get("/api/metrics/eval/{eval_run_id}")
async def eval_metrics(
    eval_run_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    eval_run = await session.get(EvalRun, eval_run_id)
    if eval_run is None:
        raise HTTPException(status_code=404, detail="eval run not found")

    results = (
        (await session.execute(select(EvalResult).where(EvalResult.eval_run_id == eval_run_id)))
        .scalars()
        .all()
    )
    if not results:
        return {"error": "no results", "eval_run_id": eval_run_id}

    expected = {
        e.id: e
        for e in (
            await session.execute(
                select(EvalEmail).where(EvalEmail.id.in_([x.eval_email_id for x in results]))
            )
        )
        .scalars()
        .all()
    }

    n = len(results)
    acc = sum(1 for r in results if r.category_correct) / n
    by_diff: dict[str, list[bool]] = defaultdict(list)
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    route_ok = 0
    tp_esc = fp_esc = fn_esc = 0
    grounded = 0
    with_draft = 0
    pairs: list[tuple[float, bool]] = []

    for r in results:
        exp = expected.get(r.eval_email_id)
        if exp is None:
            continue
        by_diff[exp.difficulty].append(r.category_correct)
        pred_cat = r.predicted_category or "unknown"
        confusion[exp.expected_category][pred_cat] += 1
        if r.route_correct:
            route_ok += 1
        pred_esc = r.predicted_route == "escalation_agent"
        if exp.expected_escalate and pred_esc:
            tp_esc += 1
        elif exp.expected_escalate and not pred_esc:
            fn_esc += 1
        elif not exp.expected_escalate and pred_esc:
            fp_esc += 1
        if r.citation_grounded:
            grounded += 1
        if not exp.expected_escalate:
            with_draft += 1
        if r.predicted_confidence is not None:
            pairs.append((float(r.predicted_confidence), bool(r.category_correct)))

    # out-of-scope refusal: emails probing unanswerable questions that escalated
    oos = [
        r
        for r in results
        if (exp := expected.get(r.eval_email_id)) and exp.probes == "out_of_scope"
    ]
    oos_refused = sum(1 for r in oos if r.predicted_route == "escalation_agent")

    ece, bins = _expected_calibration_error(pairs)

    return {
        "accuracy_overall": round(acc, 4),
        "accuracy_by_difficulty": {d: round(sum(v) / len(v), 4) for d, v in by_diff.items() if v},
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "route_accuracy": round(route_ok / n, 4),
        "escalation_precision": round(tp_esc / (tp_esc + fp_esc), 4) if tp_esc + fp_esc else None,
        "escalation_recall": round(tp_esc / (tp_esc + fn_esc), 4) if tp_esc + fn_esc else None,
        "citation_grounding_rate": round(grounded / with_draft, 4) if with_draft else None,
        "out_of_scope_refusal_rate": round(oos_refused / len(oos), 4) if oos else None,
        "calibration": {"ece": ece, "bins": bins},
    }


def _expected_calibration_error(
    pairs: list[tuple[float, bool]], n_bins: int = 10
) -> tuple[float | None, list[dict]]:
    """Bin predictions by confidence, compare predicted vs observed accuracy."""
    if not pairs:
        return None, []
    total = len(pairs)
    bins_out = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        bucket = [(c, ok) for c, ok in pairs if (lo <= c < hi) or (hi == 1.0 and c == 1.0)]
        if not bucket:
            continue
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        observed = sum(1 for _, ok in bucket if ok) / len(bucket)
        weight = len(bucket) / total
        ece += weight * abs(observed - avg_conf)
        bins_out.append(
            {
                "range": f"{lo:.1f}-{hi:.1f}",
                "predicted": round(avg_conf, 4),
                "observed": round(observed, 4),
                "n": len(bucket),
            }
        )
    return round(ece, 4), bins_out


@router.get("/api/eval/runs")
async def list_eval_runs(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    runs = (await session.execute(select(EvalRun).order_by(EvalRun.started_at.desc()))).scalars()
    return {
        "items": [
            {
                "id": r.id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "model_triage": r.model_triage,
                "model_draft": r.model_draft,
                "corpus_version": r.corpus_version,
                "notes": r.notes,
            }
            for r in runs
        ]
    }


@router.get("/api/eval/runs/{eval_run_id}/results")
async def eval_results(
    eval_run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    if await session.get(EvalRun, eval_run_id) is None:
        raise HTTPException(status_code=404, detail="eval run not found")
    rows = (
        await session.execute(
            select(EvalResult, EvalEmail)
            .join(EvalEmail, EvalEmail.id == EvalResult.eval_email_id)
            .where(EvalResult.eval_run_id == eval_run_id)
            .order_by(EvalEmail.id)
        )
    ).all()
    return {
        "total": len(rows),
        "items": [
            {
                "email_id": e.id,
                "run_id": None,
                "subject": e.subject,
                "difficulty": e.difficulty,
                "expected_category": e.expected_category,
                "predicted_category": r.predicted_category,
                "expected_route": e.expected_route,
                "predicted_route": r.predicted_route,
                "confidence": float(r.predicted_confidence)
                if r.predicted_confidence is not None
                else None,
                "category_correct": r.category_correct,
                "route_correct": r.route_correct,
            }
            for r, e in rows
        ],
    }

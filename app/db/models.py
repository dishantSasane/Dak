"""SQLAlchemy 2.0 declarative models — every table in 03-data-model.md §1–§3.

Columns and indexes match the spec exactly; no invented fields.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    TextClause,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _pg_default(expr: str) -> object:
    """Server default written Postgres-style; SQLite-compatible at DDL time.

    ``'{}'::jsonb`` and ``false`` are not valid SQLite literals, so we keep a
    Postgres text clause and an equivalent literal clause for other dialects.
    """
    sqlite_expr = {
        "'{}'::jsonb": "'{}'",
        "'[]'::jsonb": "'[]'",
        "false": "0",
        "true": "1",
    }.get(expr, expr)
    return FallbackDefault(pg=text(expr), lit=sqlite_expr)


class FallbackDefault(TextClause):  # type: ignore[misc]
    """Emits the Postgres text clause on PG, a plain literal elsewhere."""

    inherit_cache = True
    stringify_dialects: set[str] = set()

    def __init__(self, pg: TextClause, lit: str) -> None:
        self.pg = pg
        self.lit = lit


@compiles(FallbackDefault)
def _compile_fallback_default(element: FallbackDefault, compiler: object, **kw: object) -> str:
    if compiler.dialect.name == "postgresql":  # type: ignore[attr-defined]
        return str(compiler.process(element.pg, **kw))
    return element.lit


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_: JSONB, compiler: object, **kw: object) -> str:
    """SQLite renders PostgreSQL JSONB as JSON (used by the local test DB)."""
    return "JSON"


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_: Vector, compiler: object, **kw: object) -> str:
    """SQLite has no pgvector; store embeddings as BLOB in the local test DB."""
    return "BLOB"


# ---------------------------------------------------------------------------
# §1 Operational tables
# ---------------------------------------------------------------------------


class Case(Base):
    """§1.1 cases — a conversation: one case, many emails, many runs."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    policy_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # open | awaiting_customer | resolved | escalated
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'open'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_cases_token", "token"),
        Index("ix_cases_contact_email_status", "contact_email", "status"),
        Index("ix_cases_policy_number", "policy_number"),
    )


class Email(Base):
    """§1.2 emails — immutable, never updated by the pipeline."""

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    message_id: Mapped[str] = mapped_column(String(998), unique=True, nullable=False)
    # inbound | outbound
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    body_plain: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    body_html: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    in_reply_to: Mapped[str | None] = mapped_column(String(998), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=_pg_default("'{}'::jsonb")
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_emails_case_id", "case_id"),
        Index("ix_emails_received_at_desc", text("received_at DESC")),
    )


class Run(Base):
    """§1.3 runs — one pass of the graph over one email."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # running | pending_review | approved | rejected | escalated | failed
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'running'")
    )
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    reroute_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    validator_retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    total_prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    total_completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    model_calls: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    cache_hits: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_runs_email_id", "email_id"),
        Index("ix_runs_status_started_at", "status", text("started_at DESC")),
        Index("ix_runs_case_id", "case_id"),
    )


class RunEvent(Base):
    """§1.4 run_events — the trace. Every transition, one row."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(32), nullable=False)
    # node_start | node_end | tool_call | tool_result | model_call | decision | error
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=_pg_default("'{}'::jsonb")
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_run_events_run_id_seq"),
        Index("ix_run_events_run_id_seq", "run_id", "seq"),
    )


class Draft(Base):
    """§1.5 drafts — both attempts are kept."""

    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    sentences: Mapped[list] = mapped_column(JSONB, nullable=False)
    rendered_text: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=_pg_default("'[]'::jsonb")
    )
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    violations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=_pg_default("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("run_id", "attempt", name="uq_drafts_run_id_attempt"),)


class Review(Base):
    """§1.6 reviews — approved | edited | rejected."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False, unique=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CaseFile(Base):
    """§1.7 case_files — claims only. recommendation is advisory."""

    __tablename__ = "case_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False, unique=True)
    policy_status: Mapped[str] = mapped_column(String(16), nullable=False)
    coverage_assessment: Mapped[dict] = mapped_column(JSONB, nullable=False)
    eligibility: Mapped[dict] = mapped_column(JSONB, nullable=False)
    missing_documents: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=_pg_default("'[]'::jsonb")
    )
    # proceed | need_documents | likely_not_covered | refer_underwriting
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# §2 Reference tables
# ---------------------------------------------------------------------------


class Policy(Base):
    """§2.1 policies."""

    __tablename__ = "policies"

    policy_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    holder_name: Mapped[str] = mapped_column(String(128), nullable=False)
    holder_email: Mapped[str] = mapped_column(String(320), nullable=False)
    holder_phone: Mapped[str] = mapped_column(String(24), nullable=False)
    # ASP | MOT | TRM
    product_code: Mapped[str] = mapped_column(String(8), nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # active | lapsed | cancelled
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    waiting_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    pre_existing_waiting_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    sum_insured: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sum_insured_remaining: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    premium: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    last_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    co_pay_percent: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    riders: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=_pg_default("'[]'::jsonb"))
    nominee_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nominee_relation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancelled_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        Index("ix_policies_holder_email", "holder_email"),
        Index("ix_policies_product_code_status", "product_code", "status"),
    )


class Claim(Base):
    """§2.2 claims."""

    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    policy_number: Mapped[str] = mapped_column(ForeignKey("policies.policy_number"), nullable=False)
    intimation_date: Mapped[date] = mapped_column(Date, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_claimed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_settled: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # settled | rejected | in_progress
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    disputed_internally: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=_pg_default("false")
    )
    settled_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Grievance(Base):
    """§2.3 grievances — open | closed | escalated."""

    __tablename__ = "grievances"

    grievance_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    policy_number: Mapped[str] = mapped_column(ForeignKey("policies.policy_number"), nullable=False)
    raised_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (Index("ix_grievances_policy_number", "policy_number"),)


# ---------------------------------------------------------------------------
# §3 Vector and cache tables
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 384


class PolicyChunk(Base):
    """§3.1 policy_chunks — clause-level chunks with embeddings.

    clause_id is the citation target (ASP-C14, MOT-C03); stable across
    re-ingestion, derived from the document's own section numbering.
    """

    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_code: Mapped[str] = mapped_column(String(8), nullable=False)
    clause_id: Mapped[str] = mapped_column(String(32), nullable=False)
    clause_title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    corpus_version: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "product_code", "clause_id", "corpus_version", name="uq_policy_chunks_clause"
        ),
        Index(
            "ix_policy_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_policy_chunks_product_version", "product_code", "corpus_version"),
    )


class SemanticCache(Base):
    """§3.2 semantic_cache — generic answers only, write guard enforced in code."""

    __tablename__ = "semantic_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_norm: Mapped[str] = mapped_column(Text, nullable=False)
    question_emb: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    product_code: Mapped[str] = mapped_column(String(8), nullable=False)
    corpus_version: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_sentences: Mapped[list] = mapped_column(JSONB, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_semantic_cache_question_emb_hnsw",
            "question_emb",
            postgresql_using="hnsw",
            postgresql_ops={"question_emb": "vector_cosine_ops"},
        ),
        Index("ix_semantic_cache_product_version", "product_code", "corpus_version"),
    )


# ---------------------------------------------------------------------------
# §5 Eval tables
# ---------------------------------------------------------------------------


class EvalEmail(Base):
    """§5.1 eval_emails."""

    __tablename__ = "eval_emails"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    batch: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_category: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_route: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_escalate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_escalation_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    golden_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_citation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # easy | medium | hard
    difficulty: Mapped[str] = mapped_column(String(8), nullable=False)
    probes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # synthetic | real
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'synthetic'"))


class EvalRun(Base):
    """§5.2 eval_runs."""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_triage: Mapped[str] = mapped_column(String(64), nullable=False)
    model_draft: Mapped[str] = mapped_column(String(64), nullable=False)
    corpus_version: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvalResult(Base):
    """§5.2 eval_results — per-email rows, not aggregates."""

    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    eval_run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id"), nullable=False)
    eval_email_id: Mapped[str] = mapped_column(ForeignKey("eval_emails.id"), nullable=False)
    predicted_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    predicted_route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    predicted_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    category_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    citation_grounded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[str | None] = mapped_column(String(64), nullable=True)

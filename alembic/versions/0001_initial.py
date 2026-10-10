"""Initial schema: every table in 03-data-model.md §1–§3, §5.

T0.5: one migration creating everything, with CREATE EXTENSION IF NOT EXISTS
vector first and the HNSW indexes last.
"""
from __future__ import annotations

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable,
                     server_default=sa.text("now()"))


def upgrade() -> None:
    # --- extension first ----------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # --- §1.1 cases ---------------------------------------------------------
    op.create_table(
        "cases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(16), nullable=False),
        sa.Column("policy_number", sa.String(32), nullable=True),
        sa.Column("contact_email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'open'")),
        _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("token", name="uq_cases_token"),
    )
    op.create_index("ix_cases_token", "cases", ["token"])
    op.create_index("ix_cases_contact_email_status", "cases", ["contact_email", "status"])
    op.create_index("ix_cases_policy_number", "cases", ["policy_number"])

    # --- §1.2 emails --------------------------------------------------------
    op.create_table(
        "emails",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("message_id", sa.String(998), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("sender", sa.String(320), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("body_plain", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("in_reply_to", sa.String(998), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        _ts("received_at"),
        sa.UniqueConstraint("message_id", name="uq_emails_message_id"),
    )
    op.create_index("ix_emails_case_id", "emails", ["case_id"])
    op.create_index("ix_emails_received_at_desc", "emails", [sa.text("received_at DESC")])

    # --- §1.3 runs ----------------------------------------------------------
    op.create_table(
        "runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email_id", sa.BigInteger(), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'running'")),
        sa.Column("category", sa.String(16), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("route", sa.String(32), nullable=True),
        sa.Column("escalation_reason", sa.String(48), nullable=True),
        sa.Column("reroute_count", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("validator_retry_count", sa.SmallInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("total_prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_completion_tokens", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("model_calls", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("cache_hits", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        _ts("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_runs_email_id", "runs", ["email_id"])
    op.create_index("ix_runs_status_started_at", "runs", ["status", sa.text("started_at DESC")])
    op.create_index("ix_runs_case_id", "runs", ["case_id"])

    # --- §1.4 run_events ------------------------------------------------------
    op.create_table(
        "run_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("node", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        _ts("created_at"),
        sa.UniqueConstraint("run_id", "seq", name="uq_run_events_run_id_seq"),
    )
    op.create_index("ix_run_events_run_id_seq", "run_events", ["run_id", "seq"])

    # --- §1.5 drafts ----------------------------------------------------------
    op.create_table(
        "drafts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("sentences", postgresql.JSONB(), nullable=False),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("validation_passed", sa.Boolean(), nullable=False),
        sa.Column("violations", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        _ts("created_at"),
        sa.UniqueConstraint("run_id", "attempt", name="uq_drafts_run_id_attempt"),
    )

    # --- §1.6 reviews ---------------------------------------------------------
    op.create_table(
        "reviews",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("runs.id"), nullable=False, unique=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("edited_text", sa.Text(), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        _ts("reviewed_at"),
    )

    # --- §1.7 case_files ------------------------------------------------------
    op.create_table(
        "case_files",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("runs.id"), nullable=False, unique=True),
        sa.Column("policy_status", sa.String(16), nullable=False),
        sa.Column("coverage_assessment", postgresql.JSONB(), nullable=False),
        sa.Column("eligibility", postgresql.JSONB(), nullable=False),
        sa.Column("missing_documents", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("recommendation", sa.String(32), nullable=False),
        _ts("created_at"),
    )

    # --- §2.1 policies --------------------------------------------------------
    op.create_table(
        "policies",
        sa.Column("policy_number", sa.String(32), primary_key=True),
        sa.Column("holder_name", sa.String(128), nullable=False),
        sa.Column("holder_email", sa.String(320), nullable=False),
        sa.Column("holder_phone", sa.String(24), nullable=False),
        sa.Column("product_code", sa.String(8), nullable=False),
        sa.Column("product_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("waiting_period_end", sa.Date(), nullable=True),
        sa.Column("pre_existing_waiting_period_end", sa.Date(), nullable=True),
        sa.Column("sum_insured", sa.Numeric(14, 2), nullable=False),
        sa.Column("sum_insured_remaining", sa.Numeric(14, 2), nullable=False),
        sa.Column("premium", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_frequency", sa.String(16), nullable=False),
        sa.Column("last_payment_date", sa.Date(), nullable=True),
        sa.Column("co_pay_percent", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("riders", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("nominee_name", sa.String(128), nullable=True),
        sa.Column("nominee_relation", sa.String(32), nullable=True),
        sa.Column("city", sa.String(64), nullable=True),
        sa.Column("cancelled_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_policies_holder_email", "policies", ["holder_email"])
    op.create_index("ix_policies_product_code_status", "policies", ["product_code", "status"])

    # --- §2.2 claims ----------------------------------------------------------
    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(32), primary_key=True),
        sa.Column("policy_number", sa.String(32), sa.ForeignKey("policies.policy_number"),
                  nullable=False),
        sa.Column("intimation_date", sa.Date(), nullable=False),
        sa.Column("claim_type", sa.String(48), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_claimed", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_settled", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("disputed_internally", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settled_date", sa.Date(), nullable=True),
    )

    # --- §2.3 grievances ------------------------------------------------------
    op.create_table(
        "grievances",
        sa.Column("grievance_id", sa.String(32), primary_key=True),
        sa.Column("policy_number", sa.String(32), sa.ForeignKey("policies.policy_number"),
                  nullable=False),
        sa.Column("raised_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("closed_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_grievances_policy_number", "grievances", ["policy_number"])

    # --- §5.1 eval_emails -----------------------------------------------------
    op.create_table(
        "eval_emails",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("batch", sa.SmallInteger(), nullable=False),
        sa.Column("from_name", sa.String(128), nullable=True),
        sa.Column("from_email", sa.String(320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("expected_category", sa.String(16), nullable=False),
        sa.Column("expected_route", sa.String(32), nullable=False),
        sa.Column("expected_escalate", sa.Boolean(), nullable=False),
        sa.Column("expected_escalation_reason", sa.String(48), nullable=True),
        sa.Column("golden_answer", sa.Text(), nullable=True),
        sa.Column("expected_citation", sa.String(32), nullable=True),
        sa.Column("difficulty", sa.String(8), nullable=False),
        sa.Column("probes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default=sa.text("'synthetic'")),
    )

    # --- §5.2 eval_runs / eval_results ---------------------------------------
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _ts("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_triage", sa.String(64), nullable=False),
        sa.Column("model_draft", sa.String(64), nullable=False),
        sa.Column("corpus_version", sa.Integer(), nullable=False),
        sa.Column("confidence_threshold", sa.Numeric(4, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "eval_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("eval_run_id", sa.BigInteger(), sa.ForeignKey("eval_runs.id"), nullable=False),
        sa.Column("eval_email_id", sa.String(16), sa.ForeignKey("eval_emails.id"), nullable=False),
        sa.Column("predicted_category", sa.String(16), nullable=True),
        sa.Column("predicted_route", sa.String(32), nullable=True),
        sa.Column("predicted_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("category_correct", sa.Boolean(), nullable=False),
        sa.Column("route_correct", sa.Boolean(), nullable=False),
        sa.Column("citation_grounded", sa.Boolean(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(64), nullable=True),
    )

    # --- vector tables (need the extension, created above) --------------------
    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.String(8), nullable=False),
        sa.Column("clause_id", sa.String(32), nullable=False),
        sa.Column("clause_title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.SmallInteger(), nullable=True),
        sa.Column("corpus_version", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("product_code", "clause_id", "corpus_version",
                            name="uq_policy_chunks_clause"),
    )
    op.create_index("ix_policy_chunks_product_version", "policy_chunks",
                    ["product_code", "corpus_version"])

    op.create_table(
        "semantic_cache",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("question_norm", sa.Text(), nullable=False),
        sa.Column("question_emb", pgvector.sqlalchemy.Vector(384), nullable=False),
        sa.Column("product_code", sa.String(8), nullable=False),
        sa.Column("corpus_version", sa.Integer(), nullable=False),
        sa.Column("answer_sentences", postgresql.JSONB(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        _ts("created_at"),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_semantic_cache_product_version", "semantic_cache",
                    ["product_code", "corpus_version"])

    # --- HNSW indexes last ----------------------------------------------------
    op.create_index(
        "ix_policy_chunks_embedding_hnsw", "policy_chunks", ["embedding"],
        postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_semantic_cache_question_emb_hnsw", "semantic_cache", ["question_emb"],
        postgresql_using="hnsw", postgresql_ops={"question_emb": "vector_cosine_ops"},
    )


def downgrade() -> None:
    for table in (
        "semantic_cache", "policy_chunks",
        "eval_results", "eval_runs", "eval_emails",
        "grievances", "claims", "policies",
        "case_files", "reviews", "drafts",
        "run_events", "runs", "emails", "cases",
    ):
        op.drop_table(table)

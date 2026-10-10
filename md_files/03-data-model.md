# Data Model

**System:** Inbox Triage · **Version:** 1.0 · **Date:** 2026-10-10

Every table and every JSON contract. Implement exactly this. If you need a field that is not here, stop and say so rather than adding one.

Conventions: Postgres 16, `TIMESTAMPTZ` everywhere (never naive), SQLAlchemy 2.0 declarative with `Mapped[]` annotations, Alembic for migrations, snake_case.

---

## 1. Operational tables

### 1.1 `cases`

A case is a conversation. One case, many emails, many runs.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `token` | `VARCHAR(16) UNIQUE NOT NULL` | `INS-7K3M-2XQ9`, customer-facing |
| `policy_number` | `VARCHAR(32) NULL` | nullable — may be unknown at creation |
| `contact_email` | `VARCHAR(320) NOT NULL` | |
| `status` | `VARCHAR(24) NOT NULL DEFAULT 'open'` | `open` \| `awaiting_customer` \| `resolved` \| `escalated` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Indexes: `token`, `(contact_email, status)`, `policy_number`

**Token generation.** Crockford Base32 — alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ`, which excludes `I`, `L`, `O`, `U`. Format `INS-XXXX-XXXX`, 8 random characters from `secrets.choice`. Never sequential: a sequential token tells anyone who looks how many emails you have processed. Retry on unique-constraint collision.

### 1.2 `emails`

Immutable. Never updated by the pipeline.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `case_id` | `BIGINT FK cases(id) NOT NULL` | |
| `message_id` | `VARCHAR(998) UNIQUE NOT NULL` | idempotency key |
| `direction` | `VARCHAR(8) NOT NULL` | `inbound` \| `outbound` |
| `sender` | `VARCHAR(320) NOT NULL` | |
| `recipient` | `VARCHAR(320) NOT NULL` | |
| `subject` | `TEXT NOT NULL DEFAULT ''` | |
| `body_plain` | `TEXT NOT NULL DEFAULT ''` | |
| `body_html` | `TEXT NOT NULL DEFAULT ''` | |
| `in_reply_to` | `VARCHAR(998) NULL` | |
| `raw_payload` | `JSONB NOT NULL DEFAULT '{}'` | exactly as the provider sent it |
| `received_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Indexes: `message_id` (unique), `case_id`, `received_at DESC`

Keep `raw_payload`. Provider payloads change, parsing improves, and the ability to reprocess any email through a newer pipeline without asking the sender to write again is worth the storage.

If `body_plain` is empty and `body_html` is not, derive plain text from the HTML at ingestion and store it in `body_plain`. Agents never see raw HTML.

### 1.3 `runs`

One pass of the graph over one email.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `email_id` | `BIGINT FK emails(id) NOT NULL` | |
| `case_id` | `BIGINT FK cases(id) NOT NULL` | |
| `thread_id` | `VARCHAR(64) NOT NULL` | LangGraph checkpoint thread id |
| `status` | `VARCHAR(24) NOT NULL DEFAULT 'running'` | `running` \| `pending_review` \| `approved` \| `rejected` \| `escalated` \| `failed` |
| `category` | `VARCHAR(16) NULL` | from triage |
| `confidence` | `NUMERIC(4,3) NULL` | |
| `route` | `VARCHAR(32) NULL` | node the supervisor chose |
| `escalation_reason` | `VARCHAR(48) NULL` | |
| `reroute_count` | `SMALLINT NOT NULL DEFAULT 0` | |
| `validator_retry_count` | `SMALLINT NOT NULL DEFAULT 0` | |
| `total_prompt_tokens` | `INTEGER NOT NULL DEFAULT 0` | |
| `total_completion_tokens` | `INTEGER NOT NULL DEFAULT 0` | |
| `model_calls` | `SMALLINT NOT NULL DEFAULT 0` | |
| `cache_hits` | `SMALLINT NOT NULL DEFAULT 0` | |
| `duration_ms` | `INTEGER NULL` | |
| `started_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `finished_at` | `TIMESTAMPTZ NULL` | |

Indexes: `email_id`, `(status, started_at DESC)`, `case_id`

`escalation_reason` is a closed set: `injection_detected`, `regulatory_language`, `low_confidence`, `mixed_intent`, `unclassifiable`, `policy_not_found`, `routing_conflict`, `validation_failed`, `no_relevant_context`, `tool_failure`, `model_output_invalid`, `unidentifiable`, `out_of_scope`.

### 1.4 `run_events`

The trace. Every transition, one row. This drives the live run view.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `run_id` | `BIGINT FK runs(id) NOT NULL` | |
| `seq` | `INTEGER NOT NULL` | monotonic within run, starts at 1 |
| `node` | `VARCHAR(32) NOT NULL` | |
| `event_type` | `VARCHAR(24) NOT NULL` | `node_start` \| `node_end` \| `tool_call` \| `tool_result` \| `model_call` \| `decision` \| `error` |
| `payload` | `JSONB NOT NULL DEFAULT '{}'` | |
| `duration_ms` | `INTEGER NULL` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Unique: `(run_id, seq)`. Index: `(run_id, seq)`

`payload` by `event_type`:
- `tool_call` → `{"tool": "lookup_policy", "args": {...}}`
- `tool_result` → `{"tool": "...", "ok": true, "summary": "...", "cache_hit": false}`
- `model_call` → `{"model": "...", "prompt_tokens": 0, "completion_tokens": 0, "cache_hit": false}`
- `decision` → `{"from": "supervisor", "to": "claim_agent", "reason": "category=claim"}`
- `error` → `{"kind": "...", "message": "..."}`

Never put raw email content or full model output in `payload`. Summaries and identifiers only — this table is read constantly by the UI.

### 1.5 `drafts`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `run_id` | `BIGINT FK runs(id) NOT NULL` | |
| `attempt` | `SMALLINT NOT NULL DEFAULT 1` | 1 or 2 |
| `sentences` | `JSONB NOT NULL` | the structured draft, §3.2 |
| `rendered_text` | `TEXT NOT NULL` | sentences joined, what a human reads |
| `citations` | `JSONB NOT NULL DEFAULT '[]'` | resolved clause refs |
| `validation_passed` | `BOOLEAN NOT NULL` | |
| `violations` | `JSONB NOT NULL DEFAULT '[]'` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Unique: `(run_id, attempt)`

Both attempts are kept. The first draft and why it was blocked is the most interesting thing in the whole system to show someone.

### 1.6 `reviews`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `run_id` | `BIGINT FK runs(id) NOT NULL UNIQUE` | |
| `action` | `VARCHAR(16) NOT NULL` | `approved` \| `edited` \| `rejected` |
| `edited_text` | `TEXT NULL` | present when `edited` |
| `reviewer_note` | `TEXT NULL` | |
| `reviewed_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

`edited` is the valuable signal: the delta between what the agent wrote and what a human sent is training data and an eval metric.

### 1.7 `case_files` (claims only)

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `run_id` | `BIGINT FK runs(id) NOT NULL UNIQUE` | |
| `policy_status` | `VARCHAR(16) NOT NULL` | |
| `coverage_assessment` | `JSONB NOT NULL` | §3.4 |
| `eligibility` | `JSONB NOT NULL` | output of `calculate_eligibility`, §3.5 |
| `missing_documents` | `JSONB NOT NULL DEFAULT '[]'` | |
| `recommendation` | `VARCHAR(32) NOT NULL` | `proceed` \| `need_documents` \| `likely_not_covered` \| `refer_underwriting` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

`recommendation` is advisory. Nothing in this system approves or rejects a claim.

---

## 2. Reference tables (seeded from generated data)

### 2.1 `policies`

| Column | Type |
|---|---|
| `policy_number` | `VARCHAR(32) PK` |
| `holder_name` | `VARCHAR(128) NOT NULL` |
| `holder_email` | `VARCHAR(320) NOT NULL` |
| `holder_phone` | `VARCHAR(24) NOT NULL` |
| `product_code` | `VARCHAR(8) NOT NULL` — `ASP` \| `MOT` \| `TRM` |
| `product_name` | `VARCHAR(128) NOT NULL` |
| `status` | `VARCHAR(16) NOT NULL` — `active` \| `lapsed` \| `cancelled` |
| `start_date` | `DATE NOT NULL` |
| `end_date` | `DATE NOT NULL` |
| `waiting_period_end` | `DATE NULL` |
| `pre_existing_waiting_period_end` | `DATE NULL` |
| `sum_insured` | `NUMERIC(14,2) NOT NULL` |
| `sum_insured_remaining` | `NUMERIC(14,2) NOT NULL` |
| `premium` | `NUMERIC(12,2) NOT NULL` |
| `payment_frequency` | `VARCHAR(16) NOT NULL` |
| `last_payment_date` | `DATE NULL` |
| `co_pay_percent` | `SMALLINT NOT NULL DEFAULT 0` |
| `riders` | `JSONB NOT NULL DEFAULT '[]'` |
| `nominee_name` | `VARCHAR(128) NULL` |
| `nominee_relation` | `VARCHAR(32) NULL` |
| `city` | `VARCHAR(64) NULL` |
| `cancelled_date` | `DATE NULL` |

Indexes: `holder_email`, `(product_code, status)`

`product_code` is the join to the corpus. Retrieval always filters on it.

### 2.2 `claims`

| Column | Type |
|---|---|
| `claim_id` | `VARCHAR(32) PK` |
| `policy_number` | `VARCHAR(32) FK policies NOT NULL` |
| `intimation_date` | `DATE NOT NULL` |
| `claim_type` | `VARCHAR(48) NOT NULL` |
| `description` | `TEXT NOT NULL` |
| `amount_claimed` | `NUMERIC(14,2) NOT NULL` |
| `amount_settled` | `NUMERIC(14,2) NULL` |
| `status` | `VARCHAR(16) NOT NULL` — `settled` \| `rejected` \| `in_progress` |
| `rejection_reason` | `TEXT NULL` |
| `disputed_internally` | `BOOLEAN NOT NULL DEFAULT false` |
| `settled_date` | `DATE NULL` |

`disputed_internally = true` marks rejections that do not hold up against the policy wording. These exist so the Complaint Agent can find a genuinely justified grievance and escalate it with evidence. Without them, every complaint resolves to "the rejection was correct" and the complaint path never demonstrates anything.

### 2.3 `grievances`

| Column | Type |
|---|---|
| `grievance_id` | `VARCHAR(32) PK` |
| `policy_number` | `VARCHAR(32) FK policies NOT NULL` |
| `raised_date` | `DATE NOT NULL` |
| `category` | `VARCHAR(32) NOT NULL` |
| `summary` | `TEXT NOT NULL` |
| `status` | `VARCHAR(16) NOT NULL` — `open` \| `closed` \| `escalated` |
| `resolution` | `TEXT NULL` |
| `closed_date` | `DATE NULL` |

Index: `policy_number`

---

## 3. Vector and cache tables

### 3.1 `policy_chunks`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE policy_chunks (
    id              BIGSERIAL PRIMARY KEY,
    product_code    VARCHAR(8)   NOT NULL,
    clause_id       VARCHAR(32)  NOT NULL,
    clause_title    VARCHAR(256) NOT NULL,
    content         TEXT         NOT NULL,
    page_number     SMALLINT     NULL,
    corpus_version  INTEGER      NOT NULL,
    embedding       vector(384)  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ON policy_chunks (product_code, clause_id, corpus_version);
CREATE INDEX ON policy_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON policy_chunks (product_code, corpus_version);
```

**`clause_id` is the citation target** — `ASP-C14`, `MOT-C03`. It must be stable across re-ingestion, so derive it from the document's own section numbering, never from chunk position.

**Chunk by clause, not by character count.** Fixed-size chunking splits a clause across two chunks and the citation stops meaning anything. Each chunk is one clause or sub-clause, with its heading preserved in `clause_title`.

### 3.2 `semantic_cache`

```sql
CREATE TABLE semantic_cache (
    id               BIGSERIAL PRIMARY KEY,
    question_norm    TEXT         NOT NULL,
    question_emb     vector(384)  NOT NULL,
    product_code     VARCHAR(8)   NOT NULL,
    corpus_version   INTEGER      NOT NULL,
    answer_sentences JSONB        NOT NULL,
    citations        JSONB        NOT NULL,
    hit_count        INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_hit_at      TIMESTAMPTZ  NULL
);

CREATE INDEX ON semantic_cache USING hnsw (question_emb vector_cosine_ops);
CREATE INDEX ON semantic_cache (product_code, corpus_version);
```

Write guard — all must hold, checked in code:

```python
def cacheable(state: RunState) -> bool:
    return (
        state["validation"].passed
        and not state["used_customer_tools"]     # set by the tool layer, not inferred
        and not state["draft_contains_record_data"]
    )
```

`used_customer_tools` is set to `True` by the tool wrapper itself whenever `get_policy_details` or `get_case_history` runs. Do not try to detect this by inspecting the draft text.

---

## 4. JSON contracts

### 4.1 `TriageAssessment`

Produced by the triage agent under `response_schema`.

```json
{
  "category": "query | complaint | claim | mixed | unknown",
  "confidence": 0.87,
  "policy_number": "ASP-2024-4471",
  "policy_number_present": true,
  "claim_amount": 142000,
  "sentiment": "neutral | frustrated | angry",
  "urgency": "low | medium | high",
  "regulatory_language": false,
  "injection_detected": false,
  "reasoning": "One or two sentences."
}
```

`policy_found` is **not** in this object. The model does not get to decide whether a policy exists — the supervisor sets it from the `lookup_policy` tool result. A model asked to confirm existence will confirm it.

`confidence` is the model's own estimate and is not calibrated. Treat the threshold as provisional until measured. See the eval spec.

### 4.2 `Draft`

```json
{
  "sentences": [
    {"text": "...", "kind": "courtesy | factual | procedural | commitment", "cite": "ASP-C14 | null"}
  ],
  "cannot_answer": false,
  "cannot_answer_reason": null
}
```

`cannot_answer: true` with an empty `sentences` array is a valid and expected output when retrieval returns nothing relevant. It must be modelled explicitly — if the only way to express "I don't know" is to write prose, the model will write confident prose instead.

### 4.3 `ValidationResult`

```json
{
  "passed": false,
  "violations": [
    {"code": "UNSOURCED_FIGURE", "sentence_index": 2,
     "detail": "Figure 500000 not present in cited chunk ASP-C14"}
  ]
}
```

### 4.4 `CoverageAssessment`

```json
{
  "event_described": "Laparoscopic cholecystectomy, 3-day admission",
  "potentially_covered": true,
  "supporting_clauses": ["ASP-C11", "ASP-C14"],
  "exclusions_triggered": [],
  "notes": "Day-care procedure; sub-limits may apply."
}
```

### 4.5 `EligibilityResult` — deterministic, no model

```json
{
  "policy_active_on_event_date": true,
  "initial_waiting_period_elapsed": true,
  "pre_existing_waiting_period_elapsed": false,
  "sum_insured_remaining": 240000,
  "co_pay_percent": 5,
  "indicative_payable": null,
  "blocking_conditions": ["pre_existing_waiting_period_not_elapsed"]
}
```

`indicative_payable` stays `null` unless every blocking condition is clear. A number here is the closest this system comes to a financial statement, so it is produced only by arithmetic and only when nothing is in doubt.

### 4.6 `EscalationBrief`

```json
{
  "headline": "Claim on a lapsed policy",
  "reason_code": "policy_not_found",
  "what_arrived": "Customer intimating hospitalisation claim for ~Rs 1.4L",
  "what_system_determined": "Policy ASP-2024-9912 not found. Nearest match ASP-2024-9921 belongs to a different holder.",
  "what_system_could_not_determine": "Whether this is a typo or a different policy.",
  "suggested_next_step": "Confirm policy number with the customer before proceeding.",
  "confidence_in_brief": 0.9
}
```

---

## 5. Eval tables

### 5.1 `eval_emails`

| Column | Type |
|---|---|
| `id` | `VARCHAR(16) PK` — `B03-07` |
| `batch` | `SMALLINT NOT NULL` |
| `from_name` | `VARCHAR(128)` |
| `from_email` | `VARCHAR(320)` |
| `subject` | `TEXT` |
| `body` | `TEXT` |
| `expected_category` | `VARCHAR(16) NOT NULL` |
| `expected_route` | `VARCHAR(32) NOT NULL` |
| `expected_escalate` | `BOOLEAN NOT NULL` |
| `expected_escalation_reason` | `VARCHAR(48) NULL` |
| `golden_answer` | `TEXT NULL` |
| `expected_citation` | `VARCHAR(32) NULL` |
| `difficulty` | `VARCHAR(8) NOT NULL` — `easy` \| `medium` \| `hard` |
| `probes` | `TEXT NULL` |
| `source` | `VARCHAR(16) NOT NULL DEFAULT 'synthetic'` — `synthetic` \| `real` |

`source = 'real'` is how genuine emails from strangers enter the corpus after you label them. That is the mechanism by which the eval set stops being something you designed.

### 5.2 `eval_runs` / `eval_results`

`eval_runs`: `id`, `started_at`, `finished_at`, `model_triage`, `model_draft`, `corpus_version`, `confidence_threshold`, `notes`.

`eval_results`: `id`, `eval_run_id` FK, `eval_email_id` FK, `predicted_category`, `predicted_route`, `predicted_confidence`, `category_correct` BOOL, `route_correct` BOOL, `citation_grounded` BOOL, `cache_hit` BOOL, `tokens`, `latency_ms`, `error` NULL.

Storing per-email results rather than aggregates is what lets you ask "which emails regressed between run 4 and run 5" — which is the question you will actually have.

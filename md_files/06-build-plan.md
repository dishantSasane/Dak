# Build Plan

**System:** Inbox Triage · **Version:** 1.0 · **Date:** 2026-10-10

Sequenced tasks. `[Q]` = Qwen Coder. `[CC]` = Claude Code. Work one task at a time and check the acceptance criteria before moving on — they are written to be verified by running something, not by reading code.

**Give Qwen per task:** the task block, the doc sections it names, and any file it modifies in full. Not the whole doc set.

---

## Phase 0 — Foundation

### T0.1 `[Q]` Repo skeleton and tooling
Create the structure in `01-prd.md` §7. `pyproject.toml` with uv, Python 3.12. Dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `redis`, `arq`, `langgraph`, `langgraph-checkpoint-postgres`, `google-genai`, `sentence-transformers`, `pgvector`, `pdfplumber`, `langfuse`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

**Done when:** `uv sync` succeeds, `ruff check .` and `mypy app` pass on an empty skeleton.

### T0.2 `[Q]` Config
`app/config.py` using `pydantic-settings`. Every variable from `02-architecture.md` §11. Fail loudly at startup on a missing required value. `.env.example` committed, `.env` gitignored.

**Done when:** importing `settings` with an incomplete `.env` raises a clear error naming the missing variable.

### T0.3 `[Q]` Docker Compose
Postgres 16 with pgvector (`pgvector/pgvector:pg16`), Redis 7, api, worker. Named volumes. Healthchecks on both data services; api depends on them being healthy.

**Done when:** `docker compose up` brings all four up, `docker compose exec postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;"` succeeds.

### T0.4 `[Q]` SQLAlchemy models
Every table in `03-data-model.md` §1, §2, §3. SQLAlchemy 2.0 `Mapped[]` style. Exactly the specified columns and indexes.

**Done when:** `mypy` passes and every table in the doc has a model with matching column names and types.

### T0.5 `[Q]` Alembic migrations
Initialise Alembic for async. One migration creating everything, with `CREATE EXTENSION IF NOT EXISTS vector` first and the HNSW indexes last.

**Done when:** `alembic upgrade head` on an empty DB creates every table; `alembic downgrade base` drops them cleanly.

---

## Phase 1 — Ingestion (de-risking phase)

Nothing else matters until an email sent from a phone shows up on a public URL.

### T1.1 `[Q]` Case tokens
`app/tokens.py`. Crockford Base32 per `03-data-model.md` §1.1. `generate_token()`, `parse_token_from_subject(subject) -> str | None`.

**Done when:** unit tests show 10,000 generated tokens are unique and contain no `I`, `L`, `O` or `U`; the subject parser extracts a token from `Re: something [INS-7K3M-2XQ9]` and returns None for text with no token.

### T1.2 `[Q]` Provider parsing and signature verification
`app/inbound/cloudmailin.py`. Verify the shared secret, parse the payload into `ParsedEmail`. Derive plain text from HTML when `plain` is empty. Fall back to a content-hash message id when the header is absent.

**Done when:** tests cover a valid payload, a bad signature, an HTML-only payload, and a payload with no Message-ID.

### T1.3 `[Q]` Case resolution
`app/services/cases.py`. The four-step resolution in `02-architecture.md` §1.1 step 3, in that order.

**Done when:** tests cover each of the four paths, including a reply whose `In-Reply-To` is mangled but whose subject carries the token.

### T1.4 `[Q]` The webhook
`POST /webhook/email` per `05-api-and-ui.md` §1.1. Insert before enqueue. `ON CONFLICT (message_id) DO NOTHING` → return `duplicate`.

**Done when:** posting the same payload twice creates one email row and returns `accepted` then `duplicate`; response time under 500ms locally; an unparseable payload returns 200 with the raw stored.

### T1.5 `[Q]` Worker skeleton
ARQ worker with a `process_email(email_id)` job that currently just creates a `runs` row and marks it `failed` with reason `not_implemented`.

**Done when:** posting to the webhook results in a `runs` row within two seconds.

### T1.6 `[Q]` Minimal case page
`GET /api/cases/{token}` and a plain HTML page at `/t/{token}` listing the emails. No React yet.

**Done when:** you email the address from your phone and see it at the URL within ten seconds.

> **Stop here and verify end to end before continuing.** Register the CloudMailin subdomain, point the MX records, deploy, and send a real email. If this does not work, nothing downstream will.

---

## Phase 2 — Reference data and tools

### T2.1 `[Q]` Seed loader
`scripts/seed.py` — load the Kimi-generated `policies`, `claims`, `grievances` JSON. Validate referential integrity before inserting: every claim and grievance policy number must exist, and `sum_insured_remaining` must reconcile with settled claims. Refuse to load on mismatch and print what failed.

**Done when:** loading the real generated data succeeds; a deliberately broken fixture is rejected with a specific message.

### T2.2 `[Q]` Tool base and event logging
`app/tools/base.py` — async base with typed args, a result object carrying `ok`, automatic `tool_call`/`tool_result` events, and Redis caching via decorator.

**Done when:** a dummy tool writes both events and a second identical call reports `cache_hit: true`.

### T2.3 `[Q]` Policy tools
`lookup_policy`, `get_policy_details`, `get_case_history` per `04-agent-specs.md` §8. The latter two set `used_customer_tools`.

**Done when:** unit tests against seeded data cover found, not-found, lapsed and cancelled; and `used_customer_tools` is set only by the two that should set it.

### T2.4 `[CC]` Eligibility calculator
`calculate_eligibility` — pure Python. Waiting periods, remaining sum insured, co-pay, blocking conditions. No model.

Claude Code because the arithmetic is correctness-critical and the edge cases (event on the waiting-period boundary, mid-year sum insured, co-pay interaction) are where silent wrongness lives.

**Done when:** tests cover event-before-start, event-on-waiting-period-end-date, event-one-day-after, exhausted sum insured, partially used sum insured, lapsed at event date, and cancelled; every blocking condition is reachable by some test.

### T2.5 `[Q]` Injection detection
`detect_injection` — deterministic patterns and heuristics. No model.

**Done when:** it fires on all four injection variants in eval batch 9 and does not fire on any of the 120 clean emails in batches 1–6.

---

## Phase 3 — RAG

### T3.1 `[CC]` Clause-aware chunking
`app/rag/ingest.py`. PDF → clauses, preserving section numbering as `clause_id` and heading as `clause_title`.

Claude Code because clause boundary detection is document-specific and fiddly, and getting it wrong silently degrades every citation in the system.

**Done when:** the Arogya Sanjeevani document produces chunks whose `clause_id`s match the document's own numbering; no chunk splits a clause mid-sentence; spot-checking ten chunks against the PDF shows correct boundaries.

### T3.2 `[Q]` Embedding and indexing
Embed chunks with `all-MiniLM-L6-v2`, insert into `policy_chunks` with `corpus_version` from config. Idempotent — re-running at the same version replaces rather than duplicates.

**Done when:** all three documents ingest; `SELECT count(*) FROM policy_chunks GROUP BY product_code` shows all three; re-running does not duplicate.

### T3.3 `[Q]` Retrieval
`search_policy_docs(question, product_code, k=5)`. Cosine similarity, **always filtered by `product_code` and `corpus_version`**. Returns `clause_id`, `clause_title`, `content`, `score`. Returns empty below a score floor.

**Done when:** a health question with `product_code="MOT"` returns no health clauses; ten hand-written questions each return their expected clause in the top 3; a nonsense question returns empty.

### T3.4 `[Q]` Semantic cache
`app/cache/semantic.py` — lookup and write per `03-data-model.md` §3.2, with the write guard in code.

**Done when:** a test proves a run that called `get_policy_details` is **not** cached; two differently-worded versions of the same generic question produce a hit; bumping `CORPUS_VERSION` makes every prior entry miss.

---

## Phase 4 — Agents

### T4.1 `[Q]` Gemini adapter
`app/llm/gemini.py` — schema-constrained calls via `response_schema`, token accounting, `model_call` events, retry with backoff on malformed output (max 2) and on 429.

**Done when:** a call with a Pydantic schema returns a validated instance; malformed output retries then raises a typed error; token counts land in the `runs` row.

### T4.2 `[Q]` Rate limiter
Token bucket in the worker, `RPM_LIMIT` from config, separate lower-priority bucket for eval runs.

**Done when:** 30 rapid calls at `RPM_LIMIT=10` take about three minutes and produce zero 429s.

### T4.3 `[Q]` Graph state
`app/graph/state.py` — the `RunState` TypedDict covering everything in `04-agent-specs.md`.

**Done when:** `mypy` passes and every field written by any agent is present.

### T4.4 `[CC]` Triage agent
`app/agents/triage.py` per `04-agent-specs.md` §1, including the order of operations.

Claude Code: the prompt needs iteration against the corpus, and the injection short-circuit must be right.

**Done when:** running batches 1–6 gives ≥ 85% category accuracy; `policy_found` is never set by the model; injection cases short-circuit before any model call.

### T4.5 `[CC]` Query agent
Per §3, including the empty-retrieval branch.

**Done when:** every out-of-scope question in batch 8 returns `cannot_answer` rather than a drafted answer; normal queries produce drafts where every factual sentence has a citation.

### T4.6 `[CC]` Complaint agent
Per §4, including the `disputed_internally` check.

**Done when:** all four batch-4 emails referencing disputed claims set `escalate_flag`; a third complaint from the same policy escalates as a repeat.

### T4.7 `[CC]` Claim agent
Per §5, including the eligibility-vs-retrieval conflict detection.

**Done when:** no draft ever contains an approval or rejection; a claim on a lapsed policy produces a case file with the blocking condition and a neutral acknowledgement.

### T4.8 `[Q]` Escalation agent
Per §6. Simplest of the five.

**Done when:** every escalation reason produces a brief naming the specific reason, not a generic one.

---

## Phase 5 — Graph

### T5.1 `[CC]` Supervisor
`app/graph/supervisor.py` — the rule order in `02-architecture.md` §3 exactly. No model call. Writes a `decision` event with a reason for every choice.

**Done when:** a table-driven test covers every rule, including ordering (an injection email with high confidence still escalates for injection, not routing).

### T5.2 `[CC]` Graph assembly
`app/graph/build.py` — nodes, conditional edges, both back-edges, `PostgresSaver` checkpointing. Bound: `MAX_REROUTES`, `MAX_VALIDATOR_RETRIES`.

**Done when:** a visualised graph matches `02-architecture.md` §2.2; killing the worker mid-run and restarting resumes from the last checkpoint rather than re-running completed nodes.

### T5.3 `[Q]` Worker wiring
Replace the T1.5 stub with a real graph invocation. Update the `runs` row throughout.

**Done when:** a webhook post runs the full graph and leaves a terminal status.

---

## Phase 6 — Validator

### T6.1 `[CC]` Number normalisation
Per `04-agent-specs.md` §7. **Write the tests first.**

**Done when:** `Rs 5,00,000`, `₹500000`, `5 lakh`, `5.5 lakh`, `500,000` and `INR 5,00,000.00` all normalise correctly; percentages are not converted.

### T6.2 `[CC]` The validator
All six checks per `02-architecture.md` §5.2. Collects all violations. Fails closed.

**Done when:** each check has a positive and a negative control; a draft citing a clause that was not retrieved this run is blocked with `PHANTOM_CITATION`; a correct draft passes.

### T6.3 `[CC]` Retry and escalation path
Wire the validator into the graph: first failure returns to the agent with violations, second escalates with both attempts stored.

**Done when:** both `drafts` rows exist after a double failure, and the run status is `escalated` with reason `validation_failed`.

---

## Phase 7 — UI

### T7.1 `[Q]` Frontend scaffold
Vite + React 18 + TypeScript. Routing, API client, the state colour tokens from `05-api-and-ui.md` §2.6. Dark mode via `prefers-color-scheme`.

**Done when:** it builds, routes resolve, both themes render.

### T7.2 `[Q]` Landing page
Per §2.1 including the synthetic-data notice and the three samples.

**Done when:** a sample click produces a run and navigates to its run view; readable on a phone.

### T7.3 `[Q]` Run view
Per §2.2. Polls `?after_seq=N` every 1.5s while active, stops on terminal.

**Done when:** events appear live during a run; a validator block is visually prominent; polling stops when the run ends.

### T7.4 `[Q]` Review queue
Per §2.3. Two panes, clickable citations revealing clause text inline, three actions.

**Done when:** clicking a cited sentence shows the clause it came from; approve/edit/reject each write a `reviews` row; the blocked first attempt is visible in a collapsed panel.

### T7.5 `[Q]` Dashboard
Per §2.4.

**Done when:** it shows recent runs and the summary metrics, and each row links to its run view.

---

## Phase 8 — Evaluation

### T8.1 `[Q]` Corpus loader and label validator
Load `eval_emails`. The validation script from the data-generation step: cross-references resolve, every query has a golden answer and citation, category and route agree, no banned phrases, length distribution matches, no duplicate bodies.

**Done when:** the real corpus loads; a fixture with a deliberately wrong label is rejected with a specific message.

### T8.2 `[CC]` Eval harness
Run the full corpus through the graph, record per-email results in `eval_results`. Uses the low-priority rate bucket. Resumable — a run interrupted at email 140 continues rather than restarting.

**Done when:** a full run completes within quota and produces one result row per email.

### T8.3 `[CC]` Metrics
Accuracy overall and by difficulty, confusion matrix, route accuracy, escalation precision and recall, citation grounding rate, out-of-scope refusal rate, and **ECE with reliability bins**.

**Done when:** `/api/metrics/eval/{id}` returns everything in `05-api-and-ui.md` §1.4; the ECE calculation is unit-tested against a hand-computed example.

### T8.4 `[Q]` Eval page
Per §2.5, including the reliability diagram with the diagonal drawn.

**Done when:** the diagram renders, axes are labelled, ECE is shown, and the failures table filters and links to runs.

### T8.5 `[CC]` Tune the threshold
Run the corpus, read the calibration curve, choose `CONFIDENCE_THRESHOLD` from it, and write down in the README what you chose and why.

**Done when:** the README contains the chosen value, the ECE at that value, and the escalation-rate/error-rate trade it represents.

---

## Phase 9 — Deploy

### T9.1 `[Q]` Production container
Multi-stage Dockerfile, frontend built and served by the API. Non-root user. Under 1GB.

**Done when:** it builds and runs locally with production settings.

### T9.2 `[Q]` Cloud Run deploy
Deploy with Neon and Upstash connection strings. Secrets via Secret Manager, not environment literals. Min instances 0.

**Done when:** a public URL serves the landing page; `/health` returns ok; a real email from a phone completes a full run and appears on its case page.

### T9.3 `[Q]` Worker on Cloud Run
The worker as a second service, or an in-process asyncio task if the free tier makes a second service awkward. Document which and why.

**Done when:** emails process end to end in deployment, not just locally.

### T9.4 `[CC]` README
What it is, the live link, the email address, architecture diagram, the metrics table from the latest eval run with the difficulty split, known limitations, and what you would do next.

**Done when:** someone who has never seen the project can read it in three minutes and know what it does, how well, and where it falls short.

---

## Why the split is where it is

`[CC]` tasks are the ones where being subtly wrong is invisible: eligibility arithmetic, clause boundaries, the supervisor rule order, number normalisation, the validator, calibration. Each of those fails silently and produces a system that looks like it works.

`[Q]` tasks are the ones where wrong is obvious: the thing doesn't compile, the endpoint 404s, the page doesn't render.

That is roughly 30 `[Q]` to 15 `[CC]`, but `[Q]` carries far more lines of code — close to the 80/20 you wanted, split by risk rather than by volume.

---

## Honest schedule

Part-time alongside final year:

| Phase | Realistic |
|---|---|
| 0–1 Foundation and ingestion | 1 week |
| 2–3 Data, tools, RAG | 1 week |
| 4–5 Agents and graph | 1.5 weeks |
| 6 Validator | 3 days |
| 7 UI | 1 week |
| 8 Eval | 4 days |
| 9 Deploy | 2 days |

About six weeks. If you compress, compress Phase 7 — a plainer UI still demos. Do not compress Phase 6 or Phase 8; the validator and the measurement are the entire reason this project is worth more than the three you already have.

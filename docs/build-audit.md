# Dak build audit

Updated 2026-10-19 against `md_files/07-codex-completion-plan.md`. This is an evidence ledger, not a completion percentage. All pre-existing uncommitted work was preserved. Public setup is deferred by explicit owner instruction. Synthetic policy generation supersedes the old direct-real-policy corpus requirement.

## Historical local baseline (superseded by 2026-10-20 verification)

- Python 3.12.3. A project `.venv` holds ingestion/dev dependencies plus PDF tools. Full ML dependencies remain uninstalled; `uv.lock` resolves them but is not evidence of a successful full sync.
- `ruff check .` and `mypy app` passed before this corpus slice. Previously executed integration suite: 40 passing tests.
- `docker compose --env-file .env.example ps`: PostgreSQL/pgvector and Redis healthy, using host ports 55432 and 56379. API/worker containers were not jointly validated.
- Disposable database `inbox_triage_test`: migration upgrade/downgrade/upgrade passed; `alembic check` reported no drift. Integration tests truncate only the selected test database; never use a real dataset.
- New corpus commands: `python -m scripts.build_corpus`, `python -m scripts.build_corpus --check`, `pytest tests/test_corpus.py`. Every PDF clause is compared against its original Markdown. See final verification below.
- No frontend exists. No browser screenshots, live model evaluation or public deployment are claimed. PDF previews were rendered locally and inspected separately from browser QA.

## Original task ledger

| Requirement/task | Existing paths | Status | Executable evidence | Gap | Next action |
|---|---|---|---|---|---|
| T0.1 — Repo skeleton and tooling | pyproject.toml; uv.lock | Verified | Complete installed environment; uv pip check, Ruff and mypy pass | Production image still separate | See current next work |
| T0.2 — Config | app/config.py; .env.example; tests/test_ingestion_unit.py | Verified | Missing-variable subprocess test passes | None for startup contract | Keep |
| T0.3 — Docker Compose | docker-compose.yml; Dockerfile | Partial | docker compose ps: Postgres/Redis healthy at alternate host ports | API/worker image services not smoke-tested together | Verify four-service startup |
| T0.4 — SQLAlchemy models | app/db/models.py; app/models/schemas.py | Verified | mypy app; alembic check pass | Agent-specific additions still require explicit reconciliation | Keep schema |
| T0.5 — Alembic migrations | alembic/versions/0001_initial.py | Verified | Disposable PostgreSQL upgrade/downgrade/upgrade; no drift | No deployment migration executed | Keep |
| T1.1 — Case tokens | app/tokens.py; tests/test_ingestion_unit.py | Verified | 10,000-token uniqueness and subject parsing tests pass | None for current contract | Keep |
| T1.2 — Provider parsing and signature verification | app/inbound/cloudmailin.py; tests/test_ingestion_unit.py | Verified | Header/HTML/hash/malformed/HMAC/Bearer tests pass | Live provider delivery deferred | Keep; configure provider later |
| T1.3 — Case resolution | app/services/cases.py; tests/test_ingestion_integration.py | Verified | Real PostgreSQL tests cover token/thread/references/policy pair/new case | Concurrent creation of different messages in same thread not tested | Keep; broaden concurrency coverage during dispatch reconciliation |
| T1.4 — The webhook | app/api/webhook.py; tests/test_ingestion_integration.py | Partial | Duplicate persistence, malformed input, signature and queue-retry tests pass | Crash without provider retry and concurrent delivery acceptance pending | Implement durable reconciliation; test concurrency and latency |
| T1.5 — Worker skeleton | app/workers/process.py | Verified | Real ARQ graph dispatch, terminal idempotency and recovery tests | Live provider inference unverified | See current next work |
| T1.6 — Minimal case page | app/api/routes_cases.py | Partial | Restricted case JSON/escaped HTML/404 integration tests pass | Real phone email and public URL deferred by owner | Keep local page; verify public path later |
| T2.1 — Seed loader | scripts/seed.py; data/seeds; tests/test_seed.py | Verified | Real loader: 40 policies, 53 claims, 33 grievances; validation tests pass | Loader is one-time, not upsert | Keep |
| T2.2 — Tool base and event logging | app/tools/base.py; app/agents/runtime.py | Verified | Traced tool/model events and agent integration tests | No production telemetry verification | See current next work |
| T2.3 — Policy tools | app/tools/policy.py; tests/test_ingestion_integration.py | Verified | Seeded active/lapsed/cancelled/not-found lookups and customer flags pass | Thread-memory tool still to be integrated with agents | Keep |
| T2.4 — Eligibility calculator | app/tools/eligibility.py; app/agents/claim.py | Verified | Product-aware arithmetic and supported-date claim tests | Advisory only; no premium ledger | See current next work |
| T2.5 — Injection detection | app/tools/injection.py; tests/test_injection.py | Partial | Five attack examples and four clean examples pass | Original batch-9/120-clean eval acceptance corpus absent | Generate and validate labelled corpus |
| T3.1 — Clause-aware chunking | app/rag/ingest.py; data/corpus; tests/test_corpus.py | Verified | Every synthetic PDF clause roundtrips against Markdown; malformed/duplicate/wrong-product sources rejected | Controlled synthetic layout only; owner superseded real-PDF requirement | Keep; no claim of arbitrary PDF parsing |
| T3.2 — Embedding and indexing | app/rag/embeddings.py; app/rag/index.py; scripts/index_corpus.py | Verified | Real pinned MiniLM CPU indexing: 54 clauses; PostgreSQL idempotence/version-retention tests pass | Full application graph integration pending | Keep; model revision changes require corpus-version change |
| T3.3 — Retrieval | app/rag/retrieve.py; docs/retrieval-report.json | Verified | 15/15 authored expected-clause top-3 hits with real MiniLM; nonsense empty; product/version isolation tested | Smoke probes are not held-out evaluation or semantic entailment evidence | Keep; integrate traced agent wrapper |
| T3.4 — Semantic cache | app/cache/semantic.py; app/agents/runtime.py | Verified | Validator integration, current clauses and conservative privacy admission tests | No semantic entailment guarantee | See current next work |
| T4.1 — Gemini adapter | app/llm/gemini.py | Partial | Structured schema, accounting, bounded retries and failure tests | Live Gemini credentials/model identifiers unverified | See current next work |
| T4.2 — Rate limiter | app/llm/rate_limit.py | Verified | Actual Redis atomic global/eval pacing tests | Live quota behavior unverified | See current next work |
| T4.3 — Graph state | app/graph/state.py | Verified | Typed JSON-safe state and checkpoint tests | None for local contract | See current next work |
| T4.4 — Triage agent | app/agents/triage.py | Partial | Injection-before-model and typed classification integration | Held-out classification quality unmeasured | See current next work |
| T4.5 — Query agent | app/agents/query.py | Partial | Grounded query, empty retrieval refusal and cache tests | Live drafting quality unmeasured | See current next work |
| T4.6 — Complaint agent | app/agents/complaint.py | Partial | Repeat grievance escalation, history and review persistence | Live drafting quality unmeasured | See current next work |
| T4.7 — Claim agent | app/agents/claim.py | Partial | Lapsed case file and hallucinated-date refusal tests | Live extraction quality unmeasured | See current next work |
| T4.8 — Escalation agent | app/agents/escalation.py | Partial | Typed brief, deterministic injection/error fallback | Live brief quality unmeasured | See current next work |
| T5.1 — Supervisor | app/graph/supervisor.py | Verified | Ordered routing and bounded reroute tests | Evaluation corpus absent | See current next work |
| T5.2 — Graph assembly | app/graph/build.py | Verified | Actual PostgreSQL crash/resume without duplicate triage | Production recovery unverified | See current next work |
| T5.3 — Worker wiring | app/workers/process.py | Verified | Real graph wiring, advisory lock, dispatch reconciliation | Hosted lifecycle deferred | See current next work |
| T6.1 — Number normalisation | app/validator/citations.py | Verified | Decimal currency/percentage/date normalization tests | None for deterministic contract | See current next work |
| T6.2 — The validator | app/validator/citations.py | Verified | 54 validator tests; six checks plus empty draft | Does not prove semantic entailment | See current next work |
| T6.3 — Retry and escalation path | app/graph/build.py | Verified | Both draft attempts persisted; second failure escalates | Live quality unmeasured | See current next work |
| T7.1 — Frontend scaffold | frontend/ | Verified | TypeScript/Vite build and 11 browser tests | Production bundle hosting pending | See current next work |
| T7.2 — Landing page | frontend/; app/api/routes_demo.py | Verified | Actual API compose, seeded scenarios and responsive browser checks | Public inbound address deferred | See current next work |
| T7.3 — Run view | frontend/; app/api/routes_runs.py | Verified | Polling lifecycle, trace and real API browser checks | Live Gemini trace pending | See current next work |
| T7.4 — Review queue | frontend/; app/api/routes_review.py | Verified | Actual edit/save persistence, original retained, citation isolation | Synthetic local reviewer has no production auth | See current next work |
| T7.5 — Dashboard | frontend/; app/api/routes_metrics.py | Verified | Actual list/metrics, honest empty states and browser checks | No measured live evaluation | See current next work |
| T8.1 — Corpus loader and label validator | app/db/models.py: EvalEmail | Missing | Schema only; retrieval probes are not eval emails | 200-email corpus/loader/label validation absent | Generate synthetic labelled emails and manually review labels |
| T8.2 — Eval harness | app/db/models.py: EvalRun/EvalResult | Missing | Schema only | Resumable harness and held-out split absent | Implement after graph |
| T8.3 — Metrics | app/api/routes_metrics.py | Partial | Empty denominators and persisted review metrics tested | ECE/held-out quality evidence pending harness | See current next work |
| T8.4 — Eval page | frontend/; app/api/routes_demo.py | Verified | Eval list/results APIs and browser empty/data states | Actual evaluation runs absent | See current next work |
| T8.5 — Tune the threshold | app/config.py; README.md | Blocked | Threshold explicitly provisional at 0.70 | No measured calibration/held-out inference results | Calibrate only after labelled corpus and live quota available |
| T9.1 — Production container | Dockerfile; docker-compose.yml | Partial | Ingestion image scaffold only | Frontend build/full runtime dependencies/size smoke tests pending | Prepare and verify production container |
| T9.2 — Cloud Run deploy | No deployment manifests | Blocked | No public deployment performed | Domain/provider/project/credentials deferred by owner | Guide owner when local project ready |
| T9.3 — Worker on Cloud Run | app/workers/process.py | Blocked | Only local ARQ lifecycle tested | Production lifecycle and hosting availability not selected | Verify hosting constraints and recovery later |
| T9.4 — README | README.md | Partial | Current local setup, scope and verification documented | Live link/evaluation pending | See current next work |

## Current next work

1. Supply a valid local Gemini key and verify provider model identifiers and live inference.
2. Author and review the 200-email labelled corpus, implement resumable evaluation and measure calibration on separate held-out data.
3. Verify production packaging and hosted worker lifecycle; guide deferred public domain/provider/deployment setup.

## Latest verification — 2026-10-20

150 backend tests pass against real PostgreSQL and Redis (one upstream ARQ shutdown warning). Mypy passes 55 source files. Ruff, dependency compatibility and diff whitespace checks pass. Frontend build and 11 browser tests pass. Actual API browser checks exercised compose, citations, case files and persisted edited approval; screenshots are in `frontend/test-results/`.

Five agents and the checkpointed worker are running locally with the frontend at http://localhost:5173 and API at http://localhost:8000. Recorded fixture examples are explicitly labelled, including event provider provenance; they are not live inference. The missing real Gemini key produces honest escalation. No live model quality, 200-email evaluation or public deployment is claimed.

## Earlier executed verification (63-test checkpoint)

- Full suite: **63 passed**, one upstream ARQ/Redis shutdown deprecation warning. PostgreSQL and Redis are real local services; retrieval/cache isolation tests use controlled vectors for deterministic assertions.
- Real model run: `python -m scripts.index_corpus --check-probes` indexed all **54 clauses** in the local `inbox_triage` application database using CPU MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. **15/15** authored probes found an expected clause in the top three. Nonsense retrieval was empty. Full results and runtime versions are in `docs/retrieval-report.json`.
- The real cache smoke used a manually source-checked generic sentence, not the unimplemented deterministic validator. A differently worded question produced a cache hit at the configured 0.95 threshold; a customer-specific write was refused. This proves cache mechanics, not end-to-end graph validation.
- `python -m scripts.build_corpus --check`: PDFs and manifests reproduce byte-for-byte. Every clause remains on one page and all source/PDF text matches. First-page previews of all three documents were visually inspected.
- `ruff check .`, `mypy app` and `git diff --check` pass after the final source edits.
- Application remains local-only with the Phase 1 worker skeleton. No live Gemini inference, frontend browser QA, full labelled email eval or deployment has been performed.

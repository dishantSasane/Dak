# Phase 1 — Actual implementation audit

Audit date: 21 October 2026. Scope: the repository as it exists, compared with the business workflow supplied in this conversation. No application code, schema, provider configuration, or deployment was changed for this audit.

## Verdict

Dak is an implemented synthetic **email ingestion → classification → evidence retrieval → draft → human decision record** application. It is not yet an automated email response system. The dedicated review page exists, but approval records a decision rather than delivering an email.

This is partly a scope difference, not simply broken code. The repository's later decision log explicitly selected “Draft/review-only v1” (`../decision-log.md`). The original PRD discusses conditional sending, whereas the current code and frontend deliberately say no email is sent. This audit treats the user's latest workflow as the target and the execution path as evidence of current behavior.

## Evidence standards

- **Fully implemented**: the scoped capability is connected to its execution path and supported by relevant executed tests. This does not certify production operation or model accuracy.
- **Partially implemented**: a meaningful part works, but required behavior is absent or incomplete.
- **Missing**: no connected implementation was found.
- **Implemented differently**: the code deliberately behaves differently from the requested workflow.
- **Not verified**: code or historical reports exist, but the claimed integration or quality was not demonstrated in this audit.

File references below are relative to the repository root. Tests named below were inspected and the backend suite was executed. A passing mocked test is identified as such; it does not establish a live provider integration.

## Requirements comparison

| Requirement | Existing implementation | Status | Evidence/file location | Gap |
|---|---|---|---|---|
| Receive customer email through Mailin | `/webhook/email` accepts a CloudMailin-style JSON payload, Bearer shared secret or legacy HMAC | Implemented differently | `app/api/webhook.py:webhook_email`; `app/inbound/cloudmailin.py:parse_payload`; `tests/test_ingestion_unit.py`; `tests/test_ingestion_integration.py:test_cloudmailin_bearer_authorization` | Confirm whether “Mailin” means CloudMailin or a different service. A different provider's schema is not verified. |
| Actual provider account delivers incoming email | Local HTTP tests cover normalized payloads and authentication | Not verified | `tests/test_ingestion_integration.py`; `app/api/routes_demo.py:demo_config` returns no inbound address | No demonstrated account, MX/domain, public webhook, or real incoming email. |
| Preserve original message, sender, recipient, headers | Stores plain/HTML bodies, addresses, threading references and original JSON; HTML-only input is converted to text | Fully implemented | `app/api/webhook.py:_insert_email`; `app/inbound/cloudmailin.py:parse_payload`; `app/db/models.py:Email`; parsing/inbound tests | Applies to supported JSON input; not arbitrary MIME parsing. |
| Extract policy/customer/insurance context | Policy-number regex, typed model triage, seeded holder records; claim amount/date extraction | Partially implemented | `app/services/cases.py:extract_policy_number`; `app/agents/triage.py:run`; `app/agents/claim.py:supported_event_date` | Only ASP/MOT/TRM number formats; no complete customer-extraction contract or identity verification. |
| Match sender to policyholder before using personal context | Policy lookup uses the supplied policy number | Missing | `app/tools/policy.py:lookup_policy`; `app/agents/runtime.py:AgentContext.model`; `app/graph/build.py:process_run` | No sender/holder authorization check. A number's existence is not proof that the sender owns the policy. |
| Retrieve policy and claim/grievance records | SQLAlchemy queries PostgreSQL reference tables; seed loader checks references and balance reconciliation | Fully implemented | `app/tools/policy.py`; `scripts/seed.py`; `tests/test_ingestion_integration.py:test_seed_loader_and_policy_tools` | Verified against synthetic local records; no live insurer/CRM connector. |
| Retrieve authoritative policy wording | Version/product-filtered pgvector retrieval from controlled fictional Vantara documents | Implemented differently | `app/rag/index.py:index_corpus`; `app/rag/retrieve.py:search_policy_docs`; `data/corpus/README.md`; `tests/test_rag.py` | Integrity checks verify fixture consistency, not real policy correctness or current regulatory compliance. |
| Main triage and orchestrator | Model creates a typed assessment; deterministic supervisor chooses a specialist or escalation | Fully implemented | `app/agents/triage.py`; `app/graph/supervisor.py:route_decision`; `app/graph/build.py:build_graph`; supervisor and pipeline tests | Routing mechanics tested; real-world classification quality remains unverified. |
| General query specialist | Product identification, generic cache, clause retrieval, optional personal-policy tool call, draft output | Fully implemented | `app/agents/query.py:run`; `tests/test_agents_pipeline.py:test_query_persists_validated_draft_and_trace` | Pipeline test uses scripted model output and mocked retrieval. |
| Complaint specialist | Grievance subtype, history, repeat/disputed-claim checks, clauses, draft and internal note | Fully implemented | `app/agents/complaint.py:run`; `tests/test_agents_pipeline.py:test_repeated_complaint_escalates_with_internal_note` | Verified mechanics, not live model quality. |
| Service/technical issues specialist | Service complaints can be classified as complaint; no separate service/technical category or agent | Missing | `app/models/schemas.py:Category`; `app/agents/`; `app/graph/supervisor.py` | Needs an explicit product decision and tested category/route if required separately. |
| Reimbursement/claim specialist | Claim facts, explicit-date guard, filename inventory, deterministic advisory eligibility, case file and acknowledgement | Partially implemented | `app/agents/claim.py:run`; `app/tools/eligibility.py`; claim pipeline and eligibility tests | No separate reimbursement category, no claim payment/action, no general reimbursement detector. |
| Unknown/other handling | `unknown` and `mixed` route to an escalation brief | Implemented differently | `app/models/schemas.py:Category`; `app/graph/supervisor.py`; `app/agents/escalation.py` | No dedicated “other” response specialist. Early escalation may have a brief but no customer reply draft. |
| Every specialist receives original email and relevant context | Shared state preserves subject/body/raw JSON and fetched data; each model gets subject/body and explicitly selected context | Partially implemented | `app/graph/state.py:RunState`; `app/agents/runtime.py:AgentContext.model`; specialist `run` functions | Sender is not a dedicated model/state field; attachment contents and prior email conversation are not automatically supplied. Context differs by specialist. |
| Generate responses with policy evidence | Typed sentence drafts, retrieved clause snapshots, deterministic citation/figure/date/commitment guards | Partially implemented | `app/validator/citations.py:validate_draft`; `app/graph/build.py:_validator`; `tests/test_validator.py` | Structural checks do not establish semantic support. A contradictory sentence with a valid citation passed an audit probe. |
| Determine confidence | Model returns a bounded category-confidence value | Implemented differently | `app/models/schemas.py:TriageAssessment`; `app/agents/prompts.py:TRIAGE`; `app/agents/triage.py` | Confidence is the model's estimate of classification correctness, not measured probability that the reply is safe or correct. |
| Confidence/safety decision before auto-send | Low-confidence threshold and safety routing exist; auto-send settings are declarations only | Partially implemented | `app/graph/supervisor.py:route_decision`; `app/config.py:Settings`; `app/graph/build.py:_finalize` | No integrated send-eligibility decision. `AUTO_SEND_ENABLED` and `AUTO_SEND_MIN_CONFIDENCE` have no sending consumer. |
| High-confidence eligible low-risk auto-response | Every successful finalization waits for a human | Missing | `app/graph/build.py:_validator`, `_finalize` | No auto-send branch, provider adapter, delivery record or outbox. Changing an environment flag cannot enable sending. |
| Low-confidence/sensitive cases require HITL | Confidence < 0.70, injection, legal/regulatory, mixed/unknown, missing policy, failure/conflict checks escalate | Fully implemented | `app/graph/supervisor.py`; `app/agents/complaint.py`; `tests/test_supervisor.py`; pipeline tests | Rule mechanics verified. Sensitive-case detection still depends partly on model/heuristics. |
| All reimbursements/claims must go directly to HITL | All runs currently stop for review, but claims normally run the claim specialist first | Implemented differently | `app/graph/supervisor.py:route_decision`; `app/agents/claim.py`; `app/graph/build.py:_finalize` | No explicit mandatory-HITL claim/reimbursement send exclusion. Current safety comes from sending being absent globally. |
| Dedicated HITL dashboard page | `/review` has Drafts/Escalations queues and a selected case | Fully implemented | `frontend/src/main.tsx`; `frontend/src/pages/Review.tsx:ReviewPage`; `frontend/tests/workspace.spec.ts` | Existing browser checks cover synthetic responses, not production access control. |
| Read original customer email in HITL | Subject, sender, received time, complete plain body | Fully implemented | `app/api/routes_review.py:review_detail`; `frontend/src/ui.tsx:EmailPanel`; review/browser tests | Original HTML and attachments are not rendered here. |
| Read verified policy and customer details in HITL | Claim case file and raw triage/tool evidence contain some policy context | Partially implemented | `review_detail`; `ReviewDetail` → `JsonDetail`; `app/graph/build.py` node events | No dedicated policy/customer panel or explicit normalized policy response. Personal records can be buried in trace/evidence JSON. |
| Read/download relevant attachments in HITL | Claim tool lists filenames in internal tool events | Missing | `app/tools/attachments.py:check_attachments`; review API/UI | No attachment viewer/download endpoint, object storage, content verification or scan flow. Raw provider JSON is retained. |
| See classification and escalation reason | Classification/confidence shown; escalation brief available as expandable JSON and route trace | Partially implemented | `ReviewDetail`; `review_detail`; `app/agents/escalation.py` | Reason is not prominent in queue cards. Triage reasoning has a nesting mismatch: backend returns the node payload, UI reads `data.triage.reasoning` rather than `data.triage.triage.reasoning`. |
| Read AI draft and sources | Latest draft, earlier blocked attempts and actual retrieved clause text | Fully implemented | `review_detail`; `ReviewDetail`; `tests/test_review_api.py:test_latest_attempt_and_snapshot_citations`; browser citation test | No draft can be guaranteed when the graph escalates before drafting. |
| Approve sends existing draft | Requires latest validated draft; creates `Review`; sets run to `approved`; sends nothing | Implemented differently | `app/api/routes_review.py:review_action`; `ReviewDetail.act` | Delivery integration is absent. `approved` must not be interpreted as `sent`. |
| Edit, review final version, send | Editable textarea; Save edit & approve stores edited text and marks run approved | Partially implemented | `ReviewDetail`; `review_action`; browser edited-approval test | No separate final-send preview or delivery. Backend only requires nonempty edit, including when there is no draft; no revalidation of edited text. |
| Reject without sending; retain follow-up | Stores rejection/note, sets run rejected, preserves data | Partially implemented | `review_action`; review tests; `ReviewPage` queue filters | No send occurs, but rejected cases disappear from the default pending/escalated queues; no dedicated follow-up workflow or reassignment. Case status is not updated by review actions. |
| Review history with reviewer identity | One `Review` row per run records action/edit/note/time | Partially implemented | `app/db/models.py:Review`; `review_action`, `review_detail` | No reviewer identity, review history endpoint/page, or multiple review/version history. Detail response does not include the persisted review. |
| Delivery status and delivery audit | Run status records processing/review state | Missing | `app/db/models.py`; API routes | No message-provider ID, send attempt/status, delivery/bounce callback, or sent/failed-delivery history. |
| Prevent duplicate approval | Run row lock, unique review/run constraint and status check | Fully implemented | `review_action`; `tests/test_review_api.py:test_concurrent_reviews_record_one_decision` | This prevents duplicate decision records, not duplicate sending. |
| Prevent duplicate outbound messages | No outgoing messages are sent | Missing | No sending path; `Email.direction` merely permits an outbound value | Requires an outbound idempotency/outbox design before sending exists. |
| Prevent unauthorized review/approval | Review/run/metrics/manual APIs have no login or role checks | Missing | `app/main.py`; review routes; `frontend/src/api.ts`; audit HTTP probe | Bearer protection on the inbound webhook is not reviewer authentication. CORS is wildcard and is not access control. |
| Duplicate webhook protection | Unique Message-ID, conflict-safe insert, stable hash fallback; retry re-enqueues same durable email | Fully implemented | `webhook_email`, `_insert_email`; inbound integration tests | Does not deduplicate the same real email if a provider changes Message-ID or fallback payload contents. Sender ownership is separate. |
| Queue outage/lost dispatch recovery | Email commit precedes enqueue; webhook returns 503 on queue outage; worker startup/minutely reconciliation requeues unfinished emails | Fully implemented | `webhook_email`; `app/redis_client.py`; `reconcile_pending`; ingestion/recovery tests | Recovery requires a running worker. Manual submission returns 202 even if enqueue fails. |
| General processing failure/retry recovery | Model-output retries, 429 backoff, checkpoints and terminal failure state | Partially implemented | `app/llm/gemini.py`; `app/workers/process.py`; checkpoint and quota tests; audit crash probe | An unexpected exception marks the run `failed`; later worker calls and reconciliation skip it. No supported retry UI/API or dead-letter resolution. |
| Failed delivery and recovery | No delivery operation exists | Missing | No outbound adapter/queue/status models or tests found | A failed outbound delivery scenario cannot currently be exercised as a real integration. |
| Processing audit records | Ordered node/tool/model/decision/error events, attempts, tokens and timings persist | Fully implemented | `RunEvent`, `Draft`; `app/tools/base.py:write_event`; graph/pipeline tests | Database records are not an immutable/compliance audit store; review actor/delivery auditing absent. |
| External tracing | Langfuse dependency and settings exist | Missing | `pyproject.toml`; `app/config.py`; no runtime client/callback found | Database traces work; external Langfuse publishing is not connected. |
| LLM integration and quality | Schema-constrained Gemini adapter implemented and tested with injected transport | Not verified | `app/llm/gemini.py`; `tests/test_gemini.py`; `tests/test_agents_pipeline.py` | No valid-key live inference demonstrated; default model IDs/account access/quotas unverified. |
| Evaluation dashboard and confidence calibration | Evaluation tables, metric readers, UI and mocked browser test exist | Partially implemented | `app/api/routes_metrics.py`; `frontend/src/pages/Eval.tsx`; eval models | No completed 200-email labelled run/harness found; no held-out accuracy or calibrated send threshold demonstrated. |
| Docker application packaging | Dockerfile and Compose define API, worker, PostgreSQL, Redis | Partially implemented | `Dockerfile`; `docker-compose.yml`; `pyproject.toml` | Image omits `sentence-transformers` and the policy corpus/model assets; does not build/serve React. Application containers were not built/tested in this audit. Cloud readiness is Phase 3. |

## Executed verification and limits

### Fresh checks in this audit

1. Created `dak_audit_20261021_01_test` in the existing local PostgreSQL container, separate from the demo database. Used previously empty Redis logical database 14; the application uses database 0.
2. Applied `0001_initial` successfully with the installed Alembic executable.
3. Executed the existing suite using synthetic `test-only` provider values: **150 passed in 19.46 seconds**, with one upstream ARQ Redis `close()` deprecation warning.
4. Ran `npm run build` in `frontend`: TypeScript and Vite build passed.
5. Ran extra synthetic HTTP/function probes, described below. No real model or mail service was contacted. HTTP tests used an in-process ASGI client, not a public server.

The backend test command used this isolated database and Redis database, with `GEMINI_API_KEY=test-only` and `CLOUDMAILIN_SECRET=test-only`. These are audit-only placeholder values, not existing secrets. Tests truncate operational/reference tables in the selected test database, so the demo database was not used. The audit database is retained locally as disposable evidence; no cloud resources were created.

### Extra probes: observed results

| Probe | Observed result | What it establishes |
|---|---|---|
| GET a synthetic review without credentials | HTTP 200 | The review API is unauthenticated. |
| POST `action=edited` to an escalated run with no draft, without credentials | HTTP 200; text saved; run becomes approved | Edit bypasses the validated-draft requirement and requires no actor authentication. It still sends no email. |
| Attempt a second review on the same run | HTTP 409 | Duplicate decision is rejected. |
| Inspect review-detail response after a decision | No `review`/`reviews` field | Persisted decision history is not returned by this endpoint. |
| Inject a synthetic unexpected exception into `process_run`, then call worker again | Run remains failed; graph called only once | A second processing attempt skips the failed run. This differs from direct checkpoint-resume tests. |
| Cite a synthetic clause saying “Cosmetic surgery is excluded” with a draft saying “Cosmetic surgery is always covered” | `validate_draft(...).passed` is true | Existing validator checks syntax/figures and selected safety patterns, not semantic entailment. |
| Inventory an attachment with a filename and invalid contents | Filename counted as present | Inventory does not verify document contents or validity. |

The temporary probe driver was `/tmp/dak_phase1_probes.py`; application source was not modified. Its worker crash was deliberately simulated and logged as an error.

### Existing tests: what is actually real

- Ingestion tests use HTTPX ASGI transport, synthetic payloads and mostly mocked queue dispatch. One test executes an actual local ARQ/Redis worker, reaching the safe escalation path with a placeholder model key.
- Agent pipeline tests use real PostgreSQL writes and scripted `GeminiAdapter` transport. Retrieval/cache calls are mocked in that suite. Normal tests use a memory checkpointer; the crash/resume test uses actual PostgreSQL checkpoints.
- Retrieval/cache tests use controlled embedding fixtures for database mechanics. Historical `docs/retrieval-report.json` records real CPU embedding smoke probes; those 15 authored probes were not rerun as part of this audit and do not establish held-out answer quality.
- Earlier in this conversation, the unchanged frontend passed **15 Playwright checks**, covering six routes, five widths, both themes, axe accessibility and core interactions. API responses in these browser tests are mocked. This audit reran the frontend build, not that browser suite.
- The tests do not prove public Mailin/CloudMailin integration, live Gemini behavior, unauthorized-access protection, outbound sending, delivery retries, or cloud operation.

## Observed local environment

Ubuntu 24.04.5 LTS; project Python 3.12.3; Node.js 22.23.2; npm 10.9.8; Docker Compose 5.6.0. PostgreSQL/pgvector 16 and Redis containers were healthy on host ports 55432 and 56379. No local `.env` file was present. This is inspection, not completion of a setup phase. No secret values were printed.

The application API, frontend and long-running worker remain stopped. Audit tests launched a short-lived local worker only. Existing database/Redis containers remain running.

## Scope boundary and next step

Phase 1 is complete. Read [architecture-explained.md](architecture-explained.md) for the ten architecture questions and [gaps-and-recommendations.md](gaps-and-recommendations.md) for priorities. Phase 2 requires the user's confirmation and must advance one confirmed setup step at a time. Real automatic replies, approve-and-send, edited sending and delivery recovery must be explicitly marked unavailable until implemented and verified; setup alone cannot enable them.

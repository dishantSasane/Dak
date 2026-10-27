# Execution checklist

- [x] Read specifications and inventory generated files.
- [x] Establish Python tooling and baseline lint/type results (T0.1).
- [x] Reproduce and fix startup configuration errors (T0.2).
- [x] Test tokens, parsing, signatures, header normalization and malformed inputs (T1.1–T1.2).
- [x] Test case resolution and webhook idempotency against PostgreSQL (T1.3–T1.4).
- [x] Verify migrations up/down/up and Compose configuration (T0.3–T0.5).
- [x] Verify queue/worker and public case endpoints locally (T1.5–T1.6).
- [x] Document setup, verification evidence and remaining defects.
- [ ] Public real-email checkpoint: deferred by user until project is ready.
- [x] T2.1: seed loader validation and generated balance repair; real loader tested.
- [x] T2.2–T2.3: typed tool boundary, event logging, Redis cache and guarded policy/history tools.
- [x] T2.4: deterministic eligibility calculator and boundary/co-pay tests.
- [x] T2.5 implementation: deterministic injection screening and clean/adversarial example tests.
- [ ] T2.5 corpus acceptance: the specified batch-9 and 120 clean eval emails are absent.
- [x] Corpus preparation: three original synthetic Markdown/PDF wordings with official reference metadata (owner updated requirement).
- [x] T3.1: controlled clause-aware extraction; all 54 clauses preserve full text, IDs, titles and page provenance.
- [x] T3.2–T3.3 components: real CPU embedding/indexing, product/version-filtered retrieval; 15/15 authored probe top-3 hits.
- [x] T3.4 components: guarded cache writes, current-wording rehydration, version invalidation and real paraphrase smoke check.
- [x] T3.4 integration: traced cache hits, current-run clause rehydration and validator gate.
- [x] Phases 4–7 implementation: five agents, graph, validator, worker and frontend.
- [ ] Phase 8: labelled evaluation corpus, harness and live calibration.
- [ ] Phase 9: production packaging and deferred public deployment.

## Verification evidence

2026-10-19: 40 tests pass against PostgreSQL 16 + pgvector and Redis 7. Real ARQ burst worker processes queued email. `mypy app` passes. Migration upgrade → downgrade → upgrade passes; `alembic check` reports no drift. Ruff passes after configured formatting/dependency annotation repairs. `uv.lock` resolves 149 packages; complete ML environment sync and production container remain unverified.

## Compatibility decisions

CloudMailin uses configured Authorization headers rather than the scaffold's assumed HMAC header. Bearer authentication added; legacy HMAC retained for local callers. Queue failure responds 503 after commit so retry can recover durable email; duplicate processing is guarded by stable queue IDs and a database row lock. Waiting-period end dates are inclusive (eligibility starts the following day). Co-pay applies to the lesser of claimed amount and remaining insured amount; this is advisory and must be checked against the selected corpus before any live claim workflow.

## Completion-plan alignment

`md_files/07-codex-completion-plan.md` read and applied. `docs/build-audit.md` covers all 48 original tasks; `docs/decision-log.md` records the listed contract conflicts and distinguishes resolved representations from pending implementation. Public setup remains deferred. Owner authorized autonomous routine work on 2026-10-19; enforced environment approval boundaries still apply.

## Active Phase 3 continuation

- [x] Generate and verify three synthetic PDFs, 54 clauses, manifest and official-reference metadata.
- [x] Add full original-task audit and contract decisions required by 07.
- [x] Implement local CPU embedder and idempotent PostgreSQL indexing with source checksum verification.
- [x] Implement mandatory product/version filters, score floor and retrieval cache; measure the authored probes using real embeddings.
- [x] Implement semantic-cache write guards, corpus invalidation and current-run citation rehydration tests.

Latest checkpoint (2026-10-20): 150 backend tests pass; 11 browser tests and the frontend build pass. Ruff, mypy (55 files), dependency compatibility and diff whitespace checks pass. Five agents and the real checkpointed worker replace the skeleton. Live Gemini, the labelled evaluation and deployment remain outstanding. Real MiniLM measurements remain in `docs/retrieval-report.json`.

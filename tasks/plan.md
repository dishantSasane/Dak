# Inbox Triage completion plan

Source of truth: `md_files/00-README.md` through `06-build-plan.md`.

## Initial audit (2026-10-19; historical)
- Phase 0: configuration, Compose, models and migration exist; no verification evidence.
- Phase 1: token/parser/case/webhook/worker/case page exist; no tests. Worker intentionally returns `not_implemented`.
- Phase 2: seed JSON and loader exist; tool modules absent.
- Phases 3–6: package placeholders only; retrieval, agents, graph and validator absent.
- Phase 7: API routes exist; frontend absent.
- Phase 8: schema/routes exist; corpus, harness and calibration absent.
- Phase 9: Docker scaffold exists; deployment and README absent.

## Execution order
1. Verify foundation and ingestion before adding downstream features.
2. Fix observed defects with regression tests; verify migrations against PostgreSQL + pgvector.
3. Verify signed webhook → committed email → Redis → worker → case URL locally.
4. Public real-email checkpoint deferred by user on 2026-10-19; continue local development.
5. Follow Phase 2 tools, Phase 3 retrieval/cache, Phase 4 agents, Phase 5 graph, Phase 6 validator, Phase 7 UI, Phase 8 eval, Phase 9 deployment in dependency order.

The public checkpoint needs a configured inbound email account, domain/MX, deployment destination and credentials. These are not present in the repository. Do not claim later phases complete from skeleton files. No email sending in v1; all reference and demo data stays synthetic.

Detailed acceptance criteria remain in `md_files/06-build-plan.md`; execution evidence and immediate tasks are in `tasks/todo.md`.

## Current checkpoint

Foundation/ingestion regression fixes and Phase 2 reference tools are implemented. See README for exact scope and verification. Public setup is deferred by user authorization, not a prerequisite for further local work. Phase 3 now has the owner-authorized synthetic policy corpus, sourced references, generated PDFs and verified clause extraction. Local CPU indexing and filtered retrieval are verified; guarded semantic-cache functions pass component tests. Agent/graph/validator integration and the frontend are implemented and locally verified. Phase 8 still needs a hand-checked email eval corpus.

## Active slice: synthetic policy corpus (owner instruction, 2026-10-19)

Use `md_files/07-codex-completion-plan.md` as the completion workflow. The owner explicitly replaced direct use of real policy PDFs with original synthetic documents informed by insurer references. Preserve Vantara, ASP/MOT/TRM, current seeds and database contracts. No regulatory approval or live insurance offering is implied.

1. Record the original-task audit and contract decisions required by Phase A/B.
2. Consult official insurer wordings; record exact URLs and observed document identifiers.
3. Author three original versioned Markdown policy wordings with stable product-prefixed clause IDs. Separate configurable customer schedule values from generic clauses; include exclusions, evidence requirements, waiting periods and escalation examples.
4. Generate PDFs and machine-readable clauses deterministically; validate IDs, product isolation, source/PDF text parity, checksums and golden retrieval probes.
5. Implement clause-aware ingestion for these controlled synthetic PDFs; verify every clause boundary and retain document provenance in the corpus manifest without silently changing the database schema.
6. Update the audit/checklist with executed checks; continue remaining backend work in dependency order. Public deployment stays deferred.

## Active slice: five agents and parallel frontend

Owner explicitly requested five agents plus frontend in another shell. Backend and frontend work proceed concurrently with separate file ownership; existing uncommitted work is preserved.

1. Implement typed Gemini adapter, quota pacing, strict total call budget, and test doubles for reproducible offline integration.
2. Implement triage/query/complaint/claim/escalation agents against existing tools and synthetic corpus, with injection-before-model and empty-context refusal.
3. Implement deterministic supervisor, fail-closed citation validator, bounded reroute/redraft, PostgreSQL checkpoint graph and durable worker integration.
4. Complete supporting review/run/demo APIs; build original Dak React frontend against those APIs in parallel.
5. Run deterministic agent/graph/PostgreSQL tests and actual browser interactions; verify live Gemini separately only if valid credentials are available. Keep public deployment deferred and all v1 output draft/review only.

## Verified checkpoint — 2026-10-20

Five agents, bounded checkpointed graph, citation gate, durable worker recovery, review APIs and frontend are implemented. 150 backend tests and 11 browser tests pass, with actual API review persistence verified. Live Gemini needs a valid local key. Next: labelled evaluation corpus and harness, live calibration, production packaging, then deferred public setup.

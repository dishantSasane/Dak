# GCP deployment plan — Phase 3 pending

No cloud deployment analysis, current-price estimate, resource creation or deployment has been performed in Phase 1. This file reserves the requested deliverable without advancing beyond the user's instruction to audit first.

Repository facts for the later analysis:

- A Python Dockerfile and Compose services exist for API, ARQ worker, PostgreSQL/pgvector and Redis.
- Background processing depends on a separate polling worker, Redis jobs and PostgreSQL graph checkpoints.
- PostgreSQL stores operational records and vector search; the application is not a SQLite-only system.
- The current image omits the CPU embedding dependency/corpus assets and does not package the React frontend. The API command uses fixed port 8000. Container deployment must be built and verified before declaring compatibility with a platform.
- Reviewer authentication and outbound delivery do not exist. A public deployment would not complete the requested business workflow.

Phase 3 must evaluate Cloud Run lifecycle, frontend/backend packaging, worker/queue choices, retained versus managed PostgreSQL, secret management, storage, limits, regional costs and free-tier qualifications using then-current official sources. Compare Azure/AWS only at that stage. No free-tier or zero-cost guarantee is implied here. Do not provision paid services or deploy without explicit approval.

See [implementation-audit.md](implementation-audit.md) for audited evidence and [gaps-and-recommendations.md](gaps-and-recommendations.md) for prerequisites. This is not a completed deployment plan.

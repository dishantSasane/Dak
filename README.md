# Inbox Triage

A synthetic insurance email triage project for Vantara General Insurance. The intended system classifies incoming email, retrieves policy clauses, drafts cited replies, and routes high-stakes cases to human review. It never sends email in v1.

**Current status:** five agents (triage, query, complaint, claim and escalation), PostgreSQL-checkpointed LangGraph processing, citation validation, durable ARQ dispatch and the React review frontend are implemented. Local verification previously passed 150 backend tests and 11 browser tests. Live Gemini inference and the 200-email evaluation remain unverified. All replies stay drafts for human review; no outbound sender is configured.

The requirements are in [md_files](md_files/00-README.md). The completion workflow is [07-codex-completion-plan.md](md_files/07-codex-completion-plan.md). The [task audit](docs/build-audit.md), [contract decisions](docs/decision-log.md), [continuation plan](tasks/plan.md) and [checklist](tasks/todo.md) track actual progress.

## Local setup

Requires Python 3.12+, uv, Node.js/npm and Docker Compose.

```bash
uv sync --extra dev
cp .env.example .env
```

Set `DATABASE_URL` and `REDIS_URL` in `.env`. Set `GEMINI_API_KEY` for live model inference and `CLOUDMAILIN_SECRET` before using the inbound webhook. A valid Gemini key is required for live inference. Placeholder keys produce a safe escalation rather than a fabricated answer. Keep `ALLOW_UNSIGNED_WEBHOOK=0`.

```bash
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

In a second terminal:

```bash
uv run arq app.workers.process.WorkerSettings
```

Docker API and worker services are also available with `docker compose up --build api worker`, after migrating the database. The Render image bundles the production dashboard with the API and runs the worker as a separate service.

If ports are occupied, use `POSTGRES_PORT=55432 REDIS_PORT=56379 docker compose up -d postgres redis` and update host-side `DATABASE_URL`/`REDIS_URL` to those ports. Container-to-container connections continue to use 5432 and 6379.

## Send a local synthetic email

CloudMailin should eventually use JSON Normalized delivery and `Authorization: Bearer <CLOUDMAILIN_SECRET>` in its Authorization Settings. This follows its [documented inbound authentication contract](https://docs.cloudmailin.com/receiving_email/securing_your_email_url_target/). The old scaffold's `X-CM-Signature` SHA-256 HMAC is retained for existing local callers; it is not described as a CloudMailin header.

```bash
curl http://localhost:8000/webhook/email \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer replace-with-your-local-shared-secret' \
  -d '{"envelope":{"from":"demo@example.test","to":"inbox@example.test"},"headers":{"message_id":"<demo-1@example.test>","subject":"Coverage question"},"plain":"What is the initial waiting period?"}'
```

The returned token opens `/t/{token}`. Duplicate Message-IDs create no new email or case. Queue outages return 503 after storing the email; provider retry safely requeues it. ARQ jobs use a stable email-based id and worker retries reuse the same run. Unparseable authenticated payloads are stored and acknowledged without model processing.

## Reference data

```bash
uv run python scripts/seed.py check
uv run python scripts/seed.py load
```

The loader refuses invalid references or non-reconciling balances before writing anything. Loading is a one-time operation on an empty reference database, not an upsert. The generator now caps synthetic settlements at the remaining insured amount; five existing overdrawn records were corrected. Keep strict validation enabled.

## Verification

The integration tests require real PostgreSQL/pgvector and Redis. Use a disposable database whose name ends in `_test`; the tests truncate its operational and reference tables. Never point them at a database containing work you want to keep.

```bash
POSTGRES_PORT=55432 REDIS_PORT=56379 docker compose --env-file .env.example up -d postgres redis
docker compose exec postgres createdb -U postgres inbox_triage_test
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/inbox_triage_test
export REDIS_URL=redis://localhost:56379/15
export GEMINI_API_KEY=test-only
export CLOUDMAILIN_SECRET=test-only
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run mypy app
```

For a database already created, omit `createdb`. Settings in `.env` do not override these environment variables. PostgreSQL migration upgrade, downgrade and re-upgrade were exercised against this disposable database; `alembic check` reported no schema drift. The suite includes real ARQ/Redis processing and corpus integrity/PDF roundtrip checks; the latest run is recorded in `docs/build-audit.md`. ARQ emits one upstream Redis deprecation warning during worker shutdown.

The CPU embedding runtime, complete installed dependency environment, graph and PostgreSQL checkpoint recovery have been exercised. `uv pip check`, Ruff and mypy pass. The backend suite has one upstream ARQ/Redis shutdown deprecation warning. Live Gemini inference, provider quotas, production images and public delivery have not been verified. Configured model identifiers still need confirmation with the actual provider account.

## Frontend and local review

Run in another terminal while the API and worker are running:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open **http://localhost:5173** (API: http://localhost:8000). The landing page accepts synthetic email; run traces, review decisions, claim case files, dashboard and evaluation views use the API. Approval saves a decision and never sends email. Public case views omit unreviewed drafts and internal notes. The hosted dashboard uses a shared reviewer password; use synthetic demo messages only.

To inspect explicitly recorded examples without live model credentials, after loading seeds and indexing the corpus:

```bash
uv run python scripts/index_corpus.py --check-probes
uv run python scripts/demo_fixtures.py --create
```

These fixtures run real tools, retrieval and validation with recorded model responses. Their subjects and events identify them as fixtures; they are not live inference or evaluation results.

```bash
cd frontend
npm run build
npm run test:browser
```

Verified: 11 browser tests across mobile/tablet/desktop and both themes, plus actual API review edits and persisted decisions. Browser artifacts are in `frontend/test-results/`; design rationale is in `docs/design-direction.md`.

## Render demo deployment

`render.yaml` describes a single-origin Docker web service (React dashboard plus FastAPI), a separate ARQ worker, Render Postgres, and Render Key Value. The web service sleeps on the free plan; Render starts it when CloudMailin calls the webhook. The worker uses the project's local embedding stack and is configured as a paid 2 GB worker because Render has no free background-worker plan and 512 MB is not a safe assumption for this model.

The initial Blueprint uses free Postgres and free Key Value for a synthetic demo. Free Postgres expires after 30 days, and free Key Value loses queued/cache data on restart. Postgres is the durable source of inbound email state; ARQ reconciliation scans it and restores lost queue dispatches. Upgrade Postgres before relying on the inbox beyond the demo window. The configured 1 CPU/2 GB worker currently costs about $25/month; check Render's plan screen before creating it and set a workspace spend limit. No resources are created by this repository.

The worker applies migrations and safely bootstraps the synthetic policies and policy corpus before starting ARQ. The web process waits for that bootstrap, then serves the bundled dashboard and API on Render's `PORT`. Set `CLOUDMAILIN_SECRET`, `DASHBOARD_PASSWORD` (16+ characters), and `GEMINI_API_KEY` through Render's environment-variable UI; never commit them. Set CloudMailin's target to `https://<web-service>.onrender.com/webhook/email`, select JSON Normalized, and configure `Authorization: Bearer <same CLOUDMAILIN_SECRET>`. A CloudMailin-generated address does not require any Zoho or Hostinger DNS change.

Only send synthetic messages to this demo. Email ingestion, policy lookup and draft generation are active; review decisions are recorded in the dashboard but no reply is sent.

## Remaining work

The 200-email labelled evaluation corpus, resumable evaluation harness, measured calibration and held-out quality results remain outstanding. The 0.70 confidence threshold is provisional. Existing 15/15 retrieval probes are authored smoke checks, not a held-out evaluation. Live model verification requires a valid key in the local gitignored `.env`. Production packaging, domain/provider setup and deployment follow later, as requested by the owner.

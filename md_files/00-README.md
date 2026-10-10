# Inbox Triage — documentation set

Build documentation for a multi-agent insurance email triage system.

**Working name:** Inbox Triage
**Fictional insurer in all test data:** Vantara General Insurance — change this once, everywhere, before generating data.
**Date:** 2026-10-10

---

## The documents

| File | What it is | Who reads it |
|---|---|---|
| `01-prd.md` | Problem, goal, scope, success criteria | You, and anyone evaluating the project |
| `02-architecture.md` | System design, graph topology, state machine, failure handling | You + Claude Code |
| `03-data-model.md` | Every table, every JSON contract | Qwen Coder |
| `04-agent-specs.md` | Per-agent I/O contracts, tools, prompts | Qwen Coder + Claude Code |
| `05-api-and-ui.md` | Endpoints and screens | Qwen Coder |
| `06-build-plan.md` | Sequenced tasks with acceptance criteria, split by who builds what | You |

---

## How to use these with Qwen Coder

**Do not paste all six documents and say "build this."** You will get a plausible-looking project that doesn't run.

Work one task at a time from `06-build-plan.md`. For each task, give Qwen:

1. The task block from `06-build-plan.md` (it names its own dependencies)
2. Only the sections of `03-data-model.md` / `04-agent-specs.md` / `05-api-and-ui.md` that the task references
3. Any file the task modifies, in full

Then check the acceptance criteria before moving on. Each task has criteria that are verifiable by running something, not by reading the code.

**Rules to repeat to Qwen on every task**, because coding models drift without them:

- Implement only what this task specifies. Do not add features, endpoints, config options or abstractions that were not asked for.
- Do not invent schema fields. If a field is needed and not in `03-data-model.md`, stop and say so.
- Every function that touches the database or an external service is `async`.
- No bare `except:`. Catch specific exceptions.
- Type-hint every function signature.
- If a spec is ambiguous, stop and ask rather than choosing.

---

## What Qwen builds vs what Claude Code builds

Roughly 80/20, but the split is by *kind of work*, not volume.

**Qwen Coder — mechanical, well-specified:**
CRUD, schemas, migrations, the webhook endpoint, provider adapters, caches, API routes, React components, Docker and deploy config, the seed scripts.

**Claude Code — subtle, correctness-critical:**
The LangGraph supervisor and its conditional edges, the citation validator, agent prompt engineering, the eval harness and metrics, and debugging anything that spans components.

`06-build-plan.md` tags every task `[Q]` or `[CC]`.

---

## Build order summary

```
Phase 0  Repo, Docker, config, DB schema, migrations
Phase 1  Webhook ingestion + case tokens + raw storage        ← ship and verify before anything else
Phase 2  Policy DB, seed data, tool layer
Phase 3  RAG corpus ingestion and retrieval
Phase 4  Agents, one at a time
Phase 5  Supervisor graph and routing
Phase 6  Citation validator
Phase 7  UI — review queue, live run view, case status
Phase 8  Eval harness and dashboard
Phase 9  Deploy
```

Phase 1 is the de-risking phase. Until a real email sent from a phone appears on a public URL, nothing else matters.

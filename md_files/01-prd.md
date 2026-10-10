# PRD + Architecture Overview

**System Name:** Inbox Triage
**Version:** 1.0
**Date:** 2026-10-10
**Status:** Ready for Planning

---

## 1. Problem Statement

Insurance operations teams receive high volumes of unstructured email that mix three fundamentally different workloads: customers asking what their policy covers, customers complaining about service or a rejected claim, and customers intimating a new claim. Each needs a different response, from a different person, with a different level of care — and a wrong answer about a policy term is a commitment the insurer has made in writing.

A single-prompt LLM classifier cannot do this job. The routing decision depends on information the email does not contain: whether the quoted policy number is real, whether the policy is active, whether the waiting period has elapsed, whether this person has complained twice already. That requires tool calls against live records, and the result of one call changes which call comes next. The reply then has to be grounded in actual policy wording rather than plausible-sounding policy wording, which requires retrieval plus verification.

This is why it is an agent system rather than a script: the path through the work is decided at runtime from retrieved state, agents can disagree with the route they were given, and a high-stakes action is gated behind a human.

---

## 2. Goal & Success Criteria

**Primary Goal:** Receive a customer email, determine what it is and whether the system is competent to answer it, draft a grounded reply where it is, and escalate to a human where it is not — with every factual claim in every reply traceable to a specific policy clause.

**Success Criteria:**

- [ ] A stranger can email a public address and watch their email processed on a public URL, with no account and no setup
- [ ] Classification accuracy ≥ 85% on a 200-email labelled corpus, measured against hand-checked labels
- [ ] Citation grounding rate = 100% on sent replies — enforced structurally, not measured after the fact
- [ ] Zero auto-sent replies on claims, complaints, or anything containing regulatory language
- [ ] Out-of-scope questions escalate rather than receive an invented answer (measured on a dedicated subset of the corpus)
- [ ] Runs within a free-tier LLM quota: ≤ 8 model calls per email, ≥ 30% semantic cache hit rate at steady state
- [ ] Full run trace visible per email: every agent, tool call, routing decision and retry

**Explicitly not a success criterion:** reply quality as judged by an LLM. Every headline metric is derived from execution or from hand-labelled ground truth.

---

## 3. Inputs & Outputs

| | Description | Format |
|---|---|---|
| **Input** | Customer email, pushed by an inbound-parse provider | JSON POST (sender, recipient, subject, plain, html, headers) |
| **Input** | Policy records, claims history, grievance history | Postgres rows, reached via tools |
| **Input** | Policy wording corpus | PDF → chunked → pgvector |
| **Output** | A drafted reply with per-sentence citations | JSON → rendered email text |
| **Output** | A case file (claims only) — policy status, coverage assessment, missing documents | Structured JSON |
| **Output** | A routing decision with reason, or an escalation with a human-readable briefing | DB rows + UI |
| **Output** | A full execution trace per run | DB rows + Langfuse |

---

## 4. Agent Type

**Classification:** Hybrid — supervised multi-agent system with RAG and tool use

**Reasoning Pattern:** Supervisor-routed. A triage agent produces a typed assessment; a supervisor decides the next node from that assessment plus live record state; specialist agents act with their own tool sets; a deterministic validator gates the output. Back-edges allow a specialist to reject its routing and a failed validation to retry once.

**Memory:**
- **Run state** — LangGraph state, checkpointed to Postgres, lives for one email's processing
- **Thread memory** — prior emails and sent drafts in the same case, fetched as a tool call
- **Case memory** — claims and grievance history, fetched as a tool call
- **Semantic cache** — embedding-keyed, for generic policy answers only

---

## 5. Capability Requirements

### 5a. RAG / Knowledge Retrieval — **REQUIRED**

- **Source:** Real IRDAI standardised policy wordings (Arogya Sanjeevani health, motor own-damage + third-party, term life). Real documents, so citations point at real clauses.
- **Chunking:** By clause/section, not fixed size. Each chunk retains its clause identifier, which is what the citation references. Fixed-size chunking breaks the citation mechanism and must not be used.
- **Vector store:** pgvector, in the same Postgres instance as everything else
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, run locally
- **Retrieval:** top-k=5, filtered by `product_code` so a motor query never retrieves health clauses

### 5b. Tools

| Tool | Purpose | Implementation | Available to |
|---|---|---|---|
| `lookup_policy` | Does this policy exist, is it active, what type | Postgres query | Triage |
| `detect_injection` | Flag prompt-injection patterns | Deterministic pattern match + heuristics | Triage |
| `get_policy_details` | Full record: sum insured, dates, co-pay, riders | Postgres query | Query, Claim |
| `search_policy_docs` | Retrieve clauses, returns text + clause id | pgvector similarity, product-filtered | Query, Complaint, Claim |
| `get_case_history` | Prior grievances and claims for this policy | Postgres query | Complaint, Claim |
| `classify_grievance` | Grievance sub-type | Model call, typed output | Complaint |
| `check_attachments` | Which required documents are present | Parse email payload | Claim |
| `calculate_eligibility` | Waiting periods, co-pay, remaining sum insured | **Deterministic Python. No model involvement.** | Claim |

### 5c. MCP Integration — **REQUIRED (v1.1, not v1)**

The policy and case tools are exposed as an MCP server once the direct implementation works. This is deliberately deferred: MCP is a transport change, and debugging transport while also debugging agent logic is a bad trade. Design the tool layer so the MCP wrapper is additive.

- Server: `policy-tools`, exposing `lookup_policy`, `get_policy_details`, `get_case_history`
- Transport: stdio locally, streamable HTTP in deployment

### 5d. Memory & State

LangGraph `State` object, checkpointed to Postgres via `PostgresSaver` after every node. A crashed run resumes from its last checkpoint rather than restarting, and any run can be replayed step by step for debugging.

Agents never pass data to each other directly. They read from and write to state; the supervisor decides who runs next. This is what allows a new agent to be added without touching the existing ones.

---

## 6. High-Level Architecture

```
              Customer email
                    │
                    ▼
        ┌───────────────────────┐
        │  CloudMailin (SMTP)   │   MX on claims.<domain>
        └───────────┬───────────┘
                    │ HTTP POST (JSON)
                    ▼
        ┌───────────────────────┐
        │  POST /webhook/email  │   verify signature
        │       (FastAPI)       │   assign case token
        │                       │   store raw
        │   returns 200 in      │   enqueue
        │       < 1s            │
        └───────────┬───────────┘
                    │
                    ▼
            ┌───────────────┐
            │  ARQ worker   │
            └───────┬───────┘
                    │
                    ▼
        ╔═══════════════════════════════════════════╗
        ║           LANGGRAPH                       ║
        ║                                           ║
        ║            ┌──────────┐                   ║
        ║            │  TRIAGE  │                   ║
        ║            └─────┬────┘                   ║
        ║                  │                        ║
        ║            ┌─────▼──────┐                 ║
        ║            │ SUPERVISOR │◄──────┐         ║
        ║            └─────┬──────┘       │         ║
        ║     ┌───────┬────┴───┬────────┐ │         ║
        ║     ▼       ▼        ▼        ▼ │         ║
        ║  ┌─────┐ ┌──────┐ ┌─────┐ ┌────────┐      ║
        ║  │QUERY│ │COMPL.│ │CLAIM│ │ESCALATE│      ║
        ║  └──┬──┘ └───┬──┘ └──┬──┘ └───┬────┘      ║
        ║     │        │       │        │           ║
        ║     └────────┴───┬───┘        │   reject  ║
        ║                  │            │   route   ║
        ║                  ▼            │           ║
        ║         ┌─────────────────┐   │           ║
        ║         │    VALIDATOR    │   │           ║
        ║         │  (deterministic)│   │           ║
        ║         │   fails closed  │   │           ║
        ║         └────────┬────────┘   │           ║
        ║            pass  │  fail ─────┘           ║
        ║                  │   (1 retry then escal.) ║
        ╚══════════════════╪════════════════════════╝
                           ▼
                 ┌──────────────────┐
                 │  REVIEW QUEUE    │  human approves,
                 │      (UI)        │  edits or rejects
                 └──────────────────┘

   Postgres + pgvector   │   Redis   │   Gemini API   │   Langfuse
   records, checkpoints,     tool &      inference        traces
   corpus, semantic cache    retrieval
                             cache
```

---

## 7. Component Breakdown

| Component | Responsibility | Key libraries |
|---|---|---|
| `app/api/webhook.py` | Receive, verify, persist, enqueue | `fastapi` |
| `app/api/routes_*.py` | Cases, review queue, metrics endpoints | `fastapi` |
| `app/graph/build.py` | LangGraph topology, conditional edges | `langgraph` |
| `app/graph/state.py` | The `RunState` TypedDict | `langgraph`, `pydantic` |
| `app/agents/*.py` | One module per agent | `google-genai`, `pydantic` |
| `app/tools/*.py` | Tool implementations | `sqlalchemy`, `pgvector` |
| `app/validator/citations.py` | The gate. Deterministic. | stdlib |
| `app/rag/ingest.py` | PDF → clause chunks → embeddings | `pdfplumber`, `sentence-transformers` |
| `app/rag/retrieve.py` | Product-filtered similarity search | `sqlalchemy`, `pgvector` |
| `app/cache/semantic.py` | Embedding-keyed answer cache | `pgvector` |
| `app/llm/gemini.py` | Provider adapter, schema-constrained calls | `google-genai` |
| `app/workers/process.py` | ARQ job, rate limiting | `arq` |
| `app/db/models.py` | SQLAlchemy models | `sqlalchemy` 2.0 |
| `frontend/` | Dashboard, review queue, case page | React + Vite + TypeScript |

---

## 8. Tech Stack

- **Language:** Python 3.12
- **LLM:** Google Gemini via AI Studio free tier — `gemini-3.1-flash-lite` for triage, `gemini-3-flash` for drafting. Schema-constrained output via `response_schema`.
- **SDK:** `google-genai`
- **Orchestration:** LangGraph with `PostgresSaver` checkpointing
- **API:** FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg
- **Data:** Postgres 16 + pgvector (Neon in deployment), Redis (Upstash in deployment)
- **Queue:** ARQ
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`
- **Tracing:** Langfuse
- **Frontend:** React 18 + TypeScript + Vite
- **Inbound email:** CloudMailin
- **Deployment:** Google Cloud Run, container scales to zero
- **Local:** Docker Compose

---

## 9. Out of Scope for v1

- **Sending email.** The system drafts; a human approves; nothing leaves the building. Draft-and-review is safer, faster to build, and demos better than auto-send.
- **MCP transport.** Deferred to v1.1 for the reason in §5c.
- **Auto-send on the high-confidence query path.** The routing logic supports it; the flag stays off until the eval numbers justify turning it on.
- **Authentication.** Case tokens are bearer credentials in a URL. Acceptable because all data is synthetic; the landing page must say so.
- **Multi-intent splitting.** Mixed-intent emails escalate rather than being decomposed.
- **Real-time streaming of partial agent output.** The run view polls; token-level streaming adds complexity for little demo value.
- **Attachment content parsing.** The system detects whether attachments are present, not what is in them.

---

## 10. Open Questions / Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Free-tier RPM (10–15) throttles batch eval | Full corpus replay takes ~1,200 calls against a 1,500/day cap | Rate-limit in the worker; cache aggressively; replay from recorded fixtures for logic tests |
| Cold start on Cloud Run exceeds webhook timeout | Dropped emails | CloudMailin retries; dedupe on Message-ID makes retries safe |
| Synthetic corpus is too easy, inflating accuracy | Metrics mean nothing | 35% of the corpus is adversarial by design; report accuracy split by difficulty tag |
| Mislabelled corpus caps measured accuracy invisibly | Hours lost chasing phantom model failures | Validation script over labels before any eval run |
| Gemini free tier may use submitted data | Not an issue for synthetic data | Landing page warns against sending real information |
| Clause-level chunking fails on some PDFs | Citations degrade to page-level | Manual review of chunk boundaries for the three corpus documents; they are small enough |

---

**→ Next:** `02-architecture.md` for the graph topology and failure semantics, then `06-build-plan.md` to start.

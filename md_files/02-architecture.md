# Architecture & Design Requirements

**System:** Inbox Triage
**Version:** 1.0
**Date:** 2026-10-10

This document defines runtime behaviour: the graph, the routing rules, the state machine, and what happens when things fail. `03-data-model.md` defines the shapes; this defines the movement.

---

## 1. Request lifecycle

### 1.1 Ingestion (synchronous, must complete in under 1 second)

```
POST /webhook/email
  │
  ├─ 1. Verify provider signature.           Fail → 401, log, stop.
  ├─ 2. Parse provider payload → ParsedEmail
  ├─ 3. Resolve or create Case:
  │        a. token in subject line   →  that case      (regex `\[INS-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}\]`)
  │        b. In-Reply-To / References → thread lookup
  │        c. sender + policy number  → open case for that pair
  │        d. otherwise               → new case, new token
  ├─ 4. INSERT email (unique on message_id). Conflict → 200, do nothing.
  ├─ 5. Enqueue job {email_id}
  └─ 6. Return 200
```

Step 4 before step 5 is not optional. If the enqueue succeeds and the insert has not committed, the worker reads a row that does not exist.

**Why the subject-line token is checked first:** `In-Reply-To` headers are mangled by forwarding, mobile clients and webmail. A token in the subject survives all of it. This is how real ticketing systems thread.

### 1.2 Processing (asynchronous)

The worker loads the email, builds the initial `RunState`, and invokes the graph. Every node transition writes a checkpoint and appends a `run_event` row.

---

## 2. Graph topology

### 2.1 Nodes

| Node | Type | Writes to state |
|---|---|---|
| `triage` | agent | `triage` assessment |
| `supervisor` | router (pure function, no model call) | `route_history`, `next_node` |
| `query_agent` | agent | `draft`, `citations`, or `reject_route` |
| `complaint_agent` | agent | `draft`, `citations`, `internal_note`, `escalate_flag` |
| `claim_agent` | agent | `draft`, `citations`, `case_file` |
| `validator` | deterministic | `validation`, `violations` |
| `escalation_agent` | agent | `escalation_brief` |
| `finalize` | deterministic | terminal status |

**The supervisor makes no model call.** It is a Python function over the triage assessment and live record state. A model call here would make routing non-deterministic and unexplainable, and routing is the thing you most need to explain.

### 2.2 Edges

```
START → triage → supervisor

supervisor ─┬→ query_agent
            ├→ complaint_agent
            ├→ claim_agent
            └→ escalation_agent

query_agent ─┬→ validator
             └→ supervisor          (reject_route set — back-edge)

complaint_agent → validator
claim_agent     → validator

validator ─┬→ finalize              (passed)
           ├→ <originating agent>   (failed, retry_count < 1 — back-edge)
           └→ escalation_agent      (failed, retry_count >= 1)

escalation_agent → finalize
finalize → END
```

The two back-edges are what make this a graph rather than a pipeline. Both are bounded: `reject_route` can fire at most once per run, and the validator retry at most once.

---

## 3. Supervisor routing rules

Evaluated **in order**. First match wins. This ordering is the specification — do not reorder.

```python
def route(state: RunState) -> str:
    t = state["triage"]

    # --- Hard stops, regardless of category ---
    if t.injection_detected:
        return escalate("injection_detected")
    if t.regulatory_language:
        return escalate("regulatory_language")
    if t.confidence < CONFIDENCE_THRESHOLD:        # 0.70
        return escalate("low_confidence")
    if t.category == "mixed":
        return escalate("mixed_intent")
    if t.category == "unknown":
        return escalate("unclassifiable")
    if t.policy_number_present and not t.policy_found:
        return escalate("policy_not_found")

    # --- Agent rejected its own routing ---
    if state.get("reject_route"):
        if state["reroute_count"] >= 1:
            return escalate("routing_conflict")
        return state["reject_route"]["suggested"]

    # --- Normal routing ---
    return {
        "query":     "query_agent",
        "complaint": "complaint_agent",
        "claim":     "claim_agent",
    }[t.category]
```

**Why these are hard stops.** Regulatory language means the customer has invoked IRDAI, the Ombudsman or a court — a templated reply there is a compliance problem regardless of how reasonable the rest of the email is. A policy number that does not resolve is either a typo or an attempt; both need eyes. Injection never gets processed, and the instruction inside it is never followed, even to the extent of acknowledging it.

**The confidence threshold is a tuned parameter, not a guess.** Set it from the calibration curve once the eval corpus has been run: pick the point where the escalation rate and the error rate trade acceptably. Record the chosen value and the reasoning in the README. Until then it is 0.70 provisionally.

---

## 4. Auto-send policy

| Category | Confidence | Validator | Outcome |
|---|---|---|---|
| query | ≥ 0.90 | passed | eligible for auto-send — **flag OFF in v1** |
| query | 0.70–0.90 | passed | draft → review queue |
| complaint | any | passed | draft → review queue, **never auto** |
| claim | any | passed | case file + draft → review queue, **never auto** |
| anything | any | failed twice | escalated, no draft |

The decision axis is consequence, not category. A wrong answer to "what's the waiting period" is embarrassing; a wrong answer about a claim is a financial commitment. Only the first is ever a candidate for autonomy, and even then the flag stays off until eval data justifies it.

---

## 5. The citation validator

Deterministic. No model involvement. Fails closed.

### 5.1 Input contract

The drafting agent must return sentences, not prose:

```json
{
  "sentences": [
    {"text": "Thanks for writing in.", "kind": "courtesy", "cite": null},
    {"text": "Your policy covers hospitalisation up to Rs 5,00,000.",
     "kind": "factual", "cite": "ASP-C14"},
    {"text": "A 30-day initial waiting period applies from policy start.",
     "kind": "factual", "cite": "ASP-C07"}
  ]
}
```

`kind` is one of `courtesy`, `factual`, `procedural`, `commitment`.

### 5.2 Checks

Run all, collect all violations, do not stop at the first.

| # | Check | Violation code |
|---|---|---|
| 1 | Every `factual` and `commitment` sentence has a non-null `cite` | `MISSING_CITATION` |
| 2 | Every `cite` matches a `clause_id` that was retrieved **in this run** | `PHANTOM_CITATION` |
| 3 | Every number in a `factual` sentence appears in the cited chunk's text | `UNSOURCED_FIGURE` |
| 4 | Every date in a `factual` sentence appears in the cited chunk or in the policy record | `UNSOURCED_DATE` |
| 5 | No sentence states a claim decision (approved / rejected / payable) | `UNAUTHORISED_DECISION` |
| 6 | No sentence promises a timeline not present in the policy or a configured SLA list | `UNGROUNDED_COMMITMENT` |

Check 2 matters more than it looks. A model will invent a plausible clause id as readily as it invents a number. Validating against *what was actually retrieved in this run* is the only way to catch it.

Check 3 needs number normalisation before comparison: `Rs 5,00,000`, `₹500000`, `5 lakh` and `500,000` are the same figure. Normalise both sides to an integer before comparing. Getting this wrong produces false blocks on correct drafts, which is the failure mode that will waste the most of your time.

### 5.3 On failure

First failure: return to the originating agent with the violation list and the specific sentences at fault. The agent redrafts knowing exactly what was wrong.

Second failure: escalate with reason `validation_failed`, attach both attempts and both violation lists. A human sees what the system tried and why it was stopped.

**Never**: strip the offending sentence and send the rest. A reply that silently lost its substantive content is worse than no reply.

---

## 6. Memory and cache

### 6.1 Four layers

| Layer | Scope | Storage | Access |
|---|---|---|---|
| Run state | one email | LangGraph checkpoint (Postgres) | direct |
| Thread memory | one case | Postgres | tool call |
| Case memory | one policy, all time | Postgres | tool call |
| Semantic cache | global, generic answers | pgvector | lookup before generation |

Thread and case memory are tool calls, not injected context. The agent decides when they are relevant, you only pay the tokens when they are, and the trace records that the agent looked.

### 6.2 Semantic cache

**Lookup:** embed the normalised question, cosine similarity against cached questions, hit at ≥ 0.95 **and** matching `product_code` **and** matching `corpus_version`.

**Write — only when all of these hold:**
1. Validator passed
2. No tool returned customer-specific data during the run (`get_policy_details`, `get_case_history` were not called)
3. No number in the draft came from the policy record rather than the corpus

**This is a hard check in code, not a prompt instruction.** The failure it prevents: caching "your remaining sum insured is ₹2,40,000" and serving it to a different customer. That is a data breach, not a bug.

**Invalidation:** every cache row carries `corpus_version`. Re-ingesting the corpus bumps the version and every prior entry misses naturally. No flush, no stale answers.

### 6.3 Tool and retrieval cache

Redis, keyed on the call signature. Tool results: 5-minute TTL, scoped to the run. Retrieval results: 6-hour TTL, keyed on `(normalised_query, product_code, corpus_version)`.

---

## 7. Failure handling

| Failure | Behaviour |
|---|---|
| Provider signature invalid | 401, log, no processing |
| Duplicate `message_id` | 200, no-op. Idempotency is why retries are safe. |
| Model returns malformed JSON | Retry twice with backoff. Then escalate `model_output_invalid`. **Count these — the rate is a reported metric.** |
| Model rate-limited (429) | Worker backs off and requeues. Not an escalation. |
| Tool raises | Node catches, writes `tool_error` to state, supervisor escalates `tool_failure` |
| Retrieval returns nothing | Not an error. Agent must report it cannot answer; supervisor escalates `no_relevant_context`. **Never let the agent answer from parametric knowledge.** |
| Worker dies mid-run | Checkpoint survives. On restart the run resumes from its last completed node. |
| Validator blocks twice | Escalate `validation_failed` with both attempts attached |

The retrieval-empty case deserves emphasis. A model asked a policy question with no retrieved context will answer anyway, from training data, fluently and without hedging. That is the single most dangerous failure in the system, and the only defence is that the agent is instructed to return a null draft and the validator blocks anything with uncited factual content.

---

## 8. Rate limiting

Free-tier Gemini gives roughly 10–15 RPM. At 4–8 calls per email that is about two emails a minute.

- A token-bucket limiter in the ARQ worker, not retry-on-429. Pace requests; do not fire and apologise.
- Worker concurrency capped at 2.
- Batch eval runs use a separate, lower-priority bucket so a corpus replay cannot starve live traffic.
- Every model call records `model`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `cache_hit`.

---

## 9. Observability

Two layers, different audiences.

**Langfuse** — engineering. Full traces, prompts, token counts, latencies.

**`run_events` in Postgres** — the product. Every state transition as a row: which node, what it decided, which tools it called, how long it took. This powers the live run view, and it is what a recruiter actually watches.

Do not try to drive the UI from Langfuse. Write both.

---

## 10. Security

- Webhook signature verification is mandatory. `ALLOW_UNSIGNED_WEBHOOK=1` exists for local testing only and must be absent in deployment.
- Case tokens are bearer credentials in a URL — acceptable only because every record is synthetic. The landing page must say so plainly.
- Injection detection runs before any email content reaches a drafting prompt.
- Email content is always passed to models as data inside a delimited block, never concatenated into instructions.
- Secrets from environment only. Nothing in the repo, including the sample corpus metadata.

---

## 11. Configuration

```
DATABASE_URL, REDIS_URL
GEMINI_API_KEY
GEMINI_MODEL_TRIAGE=gemini-3.1-flash-lite
GEMINI_MODEL_DRAFT=gemini-3-flash
CLOUDMAILIN_SECRET
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
CONFIDENCE_THRESHOLD=0.70
AUTO_SEND_ENABLED=false
AUTO_SEND_MIN_CONFIDENCE=0.90
SEMANTIC_CACHE_THRESHOLD=0.95
CORPUS_VERSION=1
MAX_VALIDATOR_RETRIES=1
MAX_REROUTES=1
WORKER_CONCURRENCY=2
RPM_LIMIT=10
INSURER_NAME="Vantara General Insurance"
ALLOW_UNSIGNED_WEBHOOK=0
```

Every threshold is configuration, not a literal in code. You will tune `CONFIDENCE_THRESHOLD` and `SEMANTIC_CACHE_THRESHOLD` from eval data, and having to redeploy to change a number is how tuning stops happening.

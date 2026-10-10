# API & UI Specification

**System:** Inbox Triage · **Version:** 1.0 · **Date:** 2026-10-10

---

## Part 1 — API

FastAPI. All responses JSON. All DB access async. Pydantic v2 response models on every route.

### 1.1 Ingestion

#### `POST /webhook/email`
Called by CloudMailin. Must return in under one second.

Request: provider JSON (see `app/inbound/cloudmailin.py` for the parse contract).

Responses:
- `200 {"status": "accepted", "token": "INS-7K3M-2XQ9"}`
- `200 {"status": "duplicate"}` — known `message_id`, nothing done
- `401` — signature verification failed

Never return 500 for a parse failure. Store the raw payload, mark the email `unparseable`, return 200. A 500 makes the provider retry an email that will fail identically every time.

#### `POST /api/manual-email`
The browser "paste an email" path. Same pipeline, `source: manual`.

```json
{"sender": "...", "subject": "...", "body": "..."}
```
→ `202 {"token": "...", "run_id": 123}`

Rate-limit by IP: 10/hour. It is a public endpoint that costs model quota.

### 1.2 Public case view

#### `GET /api/cases/{token}`
No auth — the token is the credential.

```json
{
  "token": "INS-7K3M-2XQ9",
  "status": "pending_review",
  "created_at": "...",
  "emails": [
    {"direction": "inbound", "subject": "...", "received_at": "...",
     "preview": "first 200 chars"}
  ],
  "runs": [
    {"id": 123, "status": "pending_review", "category": "query",
     "confidence": 0.91, "route": "query_agent",
     "escalation_reason": null, "duration_ms": 8400}
  ]
}
```

Never return `body_plain` in full here, and never return the draft before review. A case page is public to anyone with the link.

#### `GET /api/runs/{run_id}/events`
The trace. Drives the live run view.

```json
{
  "run_id": 123,
  "status": "pending_review",
  "events": [
    {"seq": 1, "node": "triage", "event_type": "node_start",
     "payload": {}, "created_at": "..."},
    {"seq": 2, "node": "triage", "event_type": "tool_call",
     "payload": {"tool": "lookup_policy", "args": {"policy_number": "ASP-2024-4471"}}},
    {"seq": 3, "node": "triage", "event_type": "tool_result",
     "payload": {"tool": "lookup_policy", "ok": true, "summary": "found, active"},
     "duration_ms": 12}
  ]
}
```

Supports `?after_seq=N` so the UI polls for new events rather than refetching the whole trace.

### 1.3 Review queue

#### `GET /api/review/queue`
Query params: `status` (default `pending_review`), `category`, `limit`, `offset`.

```json
{
  "total": 14,
  "items": [
    {"run_id": 123, "token": "INS-7K3M-2XQ9", "category": "claim",
     "confidence": 0.88, "subject": "...", "from": "...",
     "escalation_reason": null, "waiting_since": "...",
     "validation_passed": true}
  ]
}
```

#### `GET /api/review/{run_id}`
Everything the reviewer needs on one screen.

```json
{
  "run": {...},
  "email": {"subject": "...", "body_plain": "...", "from": "...", "received_at": "..."},
  "triage": {...},
  "drafts": [
    {"attempt": 1, "rendered_text": "...", "sentences": [...],
     "validation_passed": false, "violations": [...]},
    {"attempt": 2, "rendered_text": "...", "sentences": [...],
     "validation_passed": true, "violations": []}
  ],
  "citations": [
    {"clause_id": "ASP-C14", "clause_title": "Sum Insured",
     "content": "...", "used_in_sentences": [2, 5]}
  ],
  "case_file": {...},
  "internal_note": "...",
  "escalation_brief": {...},
  "events": [...]
}
```

Return **both** draft attempts. The blocked first draft with its violations is the most informative thing on the screen.

#### `POST /api/review/{run_id}/action`
```json
{"action": "approved | edited | rejected",
 "edited_text": "...", "reviewer_note": "..."}
```
→ `200 {"status": "recorded"}`

In v1 this records the decision. It does not send email.

### 1.4 Metrics

#### `GET /api/metrics/summary`
```json
{
  "window": "7d",
  "emails_processed": 212,
  "by_category": {"query": 94, "complaint": 51, "claim": 48, "escalated": 19},
  "escalation_rate": 0.09,
  "escalation_reasons": {"low_confidence": 7, "policy_not_found": 5},
  "validator_block_rate": 0.11,
  "validator_blocks_by_agent": {"query_agent": 12, "claim_agent": 4},
  "citation_grounding_rate": 1.0,
  "cache": {"semantic_hit_rate": 0.34, "retrieval_hit_rate": 0.61},
  "latency_ms": {"p50": 7200, "p95": 18400},
  "tokens": {"prompt": 412000, "completion": 38000},
  "model_calls_per_email": 5.3,
  "malformed_output_rate": 0.02
}
```

#### `GET /api/metrics/eval/{eval_run_id}`
```json
{
  "accuracy_overall": 0.89,
  "accuracy_by_difficulty": {"easy": 0.97, "medium": 0.91, "hard": 0.74},
  "confusion_matrix": {"query": {"query": 88, "complaint": 4, "claim": 2}},
  "route_accuracy": 0.86,
  "escalation_precision": 0.81,
  "escalation_recall": 0.93,
  "citation_grounding_rate": 1.0,
  "out_of_scope_refusal_rate": 0.95,
  "calibration": {
    "ece": 0.14,
    "bins": [{"range": "0.9-1.0", "predicted": 0.95, "observed": 0.88, "n": 62}]
  }
}
```

**`accuracy_by_difficulty` matters more than the headline.** A single number hides whether you are good at easy emails and useless at hard ones.

**`out_of_scope_refusal_rate`** is the share of the deliberately-unanswerable questions that correctly escalated instead of getting an invented answer. This is the honesty metric.

**`calibration.ece`** — Expected Calibration Error. Bin predictions by confidence, compare predicted against observed accuracy in each bin. This tells you whether `CONFIDENCE_THRESHOLD = 0.70` means anything, and it is where the threshold value should come from.

### 1.5 Health

`GET /health` → `{"status": "ok", "db": true, "redis": true}` — no auth, used by the keep-warm ping.

---

## Part 2 — UI

React 18 + TypeScript + Vite. No component library — the whole point is that it doesn't look like a template. Keep it to a handful of components you own.

Polling, not WebSockets. Run events poll `?after_seq=N` every 1.5 seconds while a run is active, stop when terminal. WebSockets on a scale-to-zero container are more trouble than the smoothness is worth.

### 2.1 Landing — `/`

The only page most visitors see. Must answer "what is this and how do I try it" in about five seconds.

- One-line statement of what the system does
- **The email address, large and copyable** — `support@claims.thebreakpoint.online`
- Three test policy numbers with a note on what each demonstrates (one active, one lapsed, one inside a waiting period)
- A "paste an email instead" box → `POST /api/manual-email` → straight to the run view
- Three one-click samples: a clean query, an angry complaint, a messy claim
- **A clear notice: all data is synthetic, do not send real personal or policy information**
- A link to the live dashboard and to the GitHub repo

### 2.2 Run view — `/t/{token}` and `/runs/{run_id}`

The demo. Split layout.

**Left:** the email — from, subject, body, timestamp.

**Right:** the trace, streaming in. Each event a row:

```
▸ triage                                      1.2s
    🔧 lookup_policy(ASP-2024-4471)           12ms  → found, active
    🤖 gemini-3.1-flash-lite                  980ms  → claim, 0.88

▸ supervisor                                  0ms
    → claim_agent   (category=claim, confidence above threshold)

▸ claim_agent                                 4.1s
    🔧 get_policy_details                     18ms
    🔧 check_attachments                       2ms  → 0 of 3 present
    🔧 search_policy_docs                    140ms  → 5 clauses
    🔧 calculate_eligibility                   1ms  → 1 blocking condition
    🤖 gemini-3-flash                        3.9s

▸ validator                                   8ms
    ✗ BLOCKED — UNSOURCED_FIGURE (sentence 4)

▸ claim_agent  (retry 1)                      3.4s
▸ validator                                   7ms
    ✓ passed

▸ pending review
```

Nodes expand to show detail. The validator block must be visually prominent — a recruiter who sees the system catch its own error and recover has seen the entire value proposition in one screen.

Terminal states each read clearly: `pending review`, `escalated — policy_not_found`, `approved`.

### 2.3 Review queue — `/review`

Two panes. Left: the queue list, with category, confidence, how long it has been waiting, and a marker for validator-blocked items. Right: the selected run.

The detail pane shows, in order:
1. The customer email
2. The triage assessment, with confidence rendered as a bar, not a bare number
3. **The draft, with each cited sentence clickable** — clicking reveals the clause text it came from, inline. This is the demonstration that citations are real rather than decorative.
4. If there was a blocked attempt: a collapsed panel showing it and the violations
5. Case file, for claims
6. Internal note, for complaints
7. Three buttons: Approve · Edit & Approve · Reject, with a note field

Edit mode is a textarea seeded with the rendered draft. On save, store both the original and the edit — the diff between them is a metric.

### 2.4 Dashboard — `/dashboard`

Live feed of recent runs, newest first: token, category, confidence, status, duration. Clicking opens the run view.

A header strip of the current numbers from `/api/metrics/summary`.

### 2.5 Eval — `/eval`

Not live data. The results of corpus runs.

- Run selector
- Accuracy overall and **split by difficulty** — the split is the point
- Confusion matrix as a small heatmap
- **A reliability diagram** — predicted confidence on x, observed accuracy on y, with the diagonal drawn. ECE printed beside it.
- Per-email results table, filterable to failures, each row linking to its run

The reliability diagram is the most sophisticated thing on the site. Make it readable: label the axes, draw the perfect-calibration diagonal, size the points by bin count.

### 2.6 Visual direction

Dense and quiet. This is a tool, not a marketing page.

- One accent colour, used only for state. Everything else greyscale.
- State colours consistent everywhere: running, passed, blocked, escalated, approved.
- Monospace for tokens, clause ids, timings, policy numbers. Sans for prose.
- Timings always visible — they are evidence the thing really ran.
- Dark mode via `prefers-color-scheme`, with both themes actually checked.
- Mobile: the landing page and run view must work on a phone. A recruiter will open the link on a phone. The review queue may be desktop-only.

# Dak — Codex audit and completion plan

Prepared 19 October 2026. Use alongside the seven numbered specifications and the interview-planning history.

## Objective and starting point

Complete the existing, partially built insurance email triage application. Audit what actually runs, preserve working implementation, repair gaps, and deliver a coherent frontend with verified end-to-end behaviour. Do not scaffold a replacement application just because the documentation describes a greenfield build.

The repository was not supplied with this planning request. No implementation percentage, passing test, deployment, or existing feature is verified by this document. “Half built” is the owner's description; Codex must establish the actual baseline.

Use **Dak** as the product name, subject to existing repository branding. The specifications use Inbox Triage. Preserve the existing synthetic insurer identity unless inconsistent; do not regenerate data just to rename it. The historical discussion suggests Mailroom/Dak and alternative insurer names but does not establish a final insurer choice.

## Model recommendation

Use **GPT-6.1 Sol** in Codex as the default for frontend implementation and completion work. My recommended settings: medium reasoning for routine components; high for the repository audit, design composition, graph integration, and difficult failures. Consider GPT-6 Astra for a stubborn architecture or visual review problem if available, rather than switching every task to a more expensive model.

This is a practical recommendation, not a measured frontend beauty benchmark. Official documentation positions Sol as near-Astra performance at lower cost for complex coding and computer use. A model alone will not prevent generic design: supply the reference, a design brief, real content, and a browser screenshot iteration loop.

These are coding-assistant choices. Keep the application's Gemini runtime provider and configuration unless the audit establishes a compatibility problem. Verify configured model identifiers, current quotas, SDK versions, and deployment constraints against current official provider documentation; the October specs contain time-sensitive assumptions.

Sources: https://developers.openai.com/api/docs/models/gpt-6.1-sol and https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4

## Source hierarchy

1. Current owner instructions and applicable repository instructions.
2. `01-prd.md`: scope and outcomes; `02-architecture.md`: runtime rules.
3. `03-data-model.md`: persistence and typed contracts; `04-agent-specs.md`: agent/tool contracts.
4. `05-api-and-ui.md`: API and required screens; `06-build-plan.md`: original acceptance criteria.
5. `00-README.md`: background workflow; interview-preparation history: rationale only where consistent with the specifications.

The old Qwen/Claude task labels are historical assignments. Codex owns verification and completion across both. Existing code is evidence of current behaviour, not automatic authority over specified behaviour. Log conflicts before changing contracts; use small documented migrations where necessary. Ask only for decisions that materially change scope or cannot safely be inferred; keep independent work moving.

## Phase A — Verify the existing build

Read repository instructions, inspect git status and preserve uncommitted work. Identify actual backend/frontend entrypoints, manifests, lockfiles, migrations, Compose services, seeds, corpus, tests, CI, and deployment configuration. Do not expose secrets while inspecting configuration.

Run the documented startup and existing checks before editing. Capture exact commands, outcomes, stack traces where useful, and missing environment requirements. Verify the real database and queue integration; a mocked unit test does not establish that ingestion works.

Create `docs/build-audit.md` with one row for each original T0.1–T9.4 task:

| Requirement/task | Existing paths | Status | Executable evidence | Gap | Next action |
|---|---|---|---|---|---|
| Original task identifier | Actual files | Verified / partial / broken / missing / blocked | Command and result | Specific failure | Keep / repair / implement |

Check frontend screens in the browser as well as source code. Identify dead buttons, fake traces, hardcoded metrics, mismatched response types, unused implementations, and services that never start. Do not infer completion from filenames or TODO counts.

**Exit:** reproducible baseline, dependency-ordered backlog, and explicit blockers. Continue directly into implementation after recording the audit.

## Phase B — Reconcile contracts before widening implementation

Investigate these conflicts already visible in the supplied documents:

| Conflict | Required decision and verification |
|---|---|
| Webhook spec requires storing an unparseable email, but `emails` has mandatory fields and no unparseable status | Define a minimal durable raw-payload/error representation; document any migration and confirm malformed payloads cannot enter normal processing. |
| Case API example says `pending_review`, while case status enum uses open/awaiting_customer/resolved/escalated | Distinguish case status from run status in persistence, API types, and badges. |
| Public case API restricts body and draft disclosure; run-view design asks for a full email body | Define separate public and reviewer representations. Keep the public response restricted; resolve how the run view receives allowed content. |
| Complaint agent emits `repeat_complainant` and `potentially_valid_grievance`, absent from closed escalation-reason set | Reconcile agent output, stored enums, routing and labels explicitly. |
| Draft example uses policy-specific sum insured, but numeric validation requires numbers in a cited corpus clause | Define provenance rules; do not bypass validation to make an example pass. Until resolved, keep unsupported personal figures out of customer drafts. |
| Eval UI needs a run selector and per-email failure table; API section only defines summary by eval run | Identify existing support; document minimal missing list/detail contracts if needed. |
| Tool section says all tools async and error-wrapped, but eligibility is a pure synchronous function | Keep pure arithmetic testable; use async tool wrappers where required and reconcile return types. |
| Draft/review-only v1 conflicts with success language about sent replies | Approval records a human decision; no email is sent. Label grounding metrics by validated drafts, with denominators. |

Also verify save/enqueue durability: persistence before enqueue is necessary but leaves a commit-to-enqueue failure window. Use an existing recovery mechanism if present; otherwise propose the smallest durable reconciliation/outbox solution and document its schema impact. A webhook retry must recover lost dispatch without creating duplicate runs or empty duplicate cases.

**Exit:** a short decision log with agreed interpretations and corresponding code/API/schema changes. No silent schema invention.

## Phase C — Complete the backend in dependency order

Skip work already verified, but run integration checks across its boundaries.

| Order | Work | Acceptance evidence |
|---|---|---|
| 1 | Foundation: configuration, Postgres/pgvector, Redis, migrations, seeds | Clean local startup, upgrade from the existing schema, useful readiness failure when a dependency is unavailable. |
| 2 | Inbound provider parsing/signature verification, threading, deduplication, manual input, durable queue dispatch | Signed fixture creates exactly one email/run; duplicate and concurrent delivery remain idempotent; invalid signature rejected; worker restart/queue outage tested. |
| 3 | Policy/history tools, attachment-presence checks, deterministic eligibility | Active/lapsed/waiting-period examples use real seeded records; arithmetic checked at date and monetary boundaries. No attachment-content parsing. |
| 4 | Clause-aware ingestion, local embeddings, product-filtered retrieval | Clause identifiers and document provenance survive ingestion; motor cannot retrieve health clauses; empty retrieval cannot generate an unsupported answer. |
| 5 | Typed Gemini adapter and individual agents | Schema errors, exhausted retries, 429 handling and tool failure are observable; provider calls are paced and counted. |
| 6 | Deterministic supervisor, bounded graph loops, checkpoints, run events | Hard-stop routing order matches architecture; at most one reroute and one validator redraft; resume after worker crash without duplicate events or reviews. |
| 7 | Citation validator and safe caches | Positive and negative controls for all six checks; Indian/Western monetary formats, percentages and dates handled; customer-specific drafts cannot enter global semantic cache. Cache hits still satisfy current-run provenance requirements. |
| 8 | Cases, review, metrics and eval APIs | Typed responses match frontend needs; reviewer decisions persist once; unreviewed drafts/internal notes stay out of public representations. |

Do not claim that deterministic citation checks prove semantic entailment. Describe exactly what the gate verifies and retain human review. Enforce the model-call budget across nested calls and retries; document exceptions rather than hiding them in totals.

**Backend milestone:** manual email → durable run → route → grounded draft or escalation → review decision → persisted trace. Then verify the same path using an actual inbound email when credentials and provider configuration are available.

## Phase D — Design and implement the frontend

### Reference and visual intent

Reference: https://dribbble.com/shots/27820957-ORDO-Landing-Page

The planning environment could not retrieve this page. No colours, typography, layout, or animation below are claimed to have been observed in ORDO. Codex should inspect the reference directly; if unavailable, continue with this independent direction and record that limitation. A screenshot from the owner can later improve fidelity without blocking functional completion.

Before styling, write `docs/design-direction.md`: observed reference traits if accessible, chosen tokens, typography, spacing, composition, interaction, and how these translate to Dak. Use the reference for visual principles; produce original product-specific work rather than copying branding or assets.

**Proposed direction:** an editorial mailroom aesthetic. Warm white canvas, near-black text, restrained borders, a deliberate typographic hierarchy, compact operational tables, and one muted brand accent. Use semantic status colours consistently with text/icon labels. Mono for policy numbers, clause IDs, tokens and durations; a readable sans for operational content. A distinctive display treatment may appear on the landing page without reducing app readability.

Avoid purple-gradient heroes, gratuitous glass panels, identical rounded cards, decorative dashboard metrics, stock AI sparkle icons, oversized empty headings, and decorative animated agent networks. Create interest through alignment, typography, actual email content, evidence, and interaction. Do not add a new component framework; preserve useful existing components and the React/TypeScript/Vite architecture.

### Screen completion order

1. **Review workspace `/review`:** the design anchor. Queue rail plus selected case; readable email/draft hierarchy; clickable citations reveal actual clauses inline. Expose both attempts and violations, claim case file, complaint internal note and escalation briefing where applicable. Approve, edit-and-approve, reject and notes must persist; show that approval records a decision. Editing retains the original draft.
2. **Live run `/runs/{run_id}` and public case `/t/{token}`:** a chronological trace with expandable tool details and timings. Make a validator block and bounded retry easy to understand. Use incremental polling every 1.5 seconds while active, stop at terminal states, and handle errors, tab lifecycle and reconnect without duplicate events. Public case uses the restricted contract resolved in Phase B.
3. **Landing `/`:** clear product statement, copyable configured inbound address, three valid test policies, manual email form and three working sample actions. Provide visible synthetic-data notice plus dashboard and configured repository links. Use a real product preview or clearly labelled fixture, with a direct path into the demo. Never show the specification's domain as live unless verified.
4. **Dashboard `/dashboard`:** recent runs as a useful table/feed, summary metrics with units and time window. No invented uptime, customer counts, accuracy, or cache rates.
5. **Evaluation `/eval`:** actual eval-run selector, accuracy by difficulty, labelled confusion heatmap, reliability chart with diagonal and bin sizes, ECE and filterable failure rows linking to runs. An empty state is preferable to fabricated results.

All screens need loading, empty, failure, and successful states. Forms need labels and useful validation; async actions need pending and error states. Keyboard navigation, visible focus, accessible status labels, readable contrast and reduced-motion behaviour are required. Respect `prefers-color-scheme` and verify both themes.

### Visual acceptance loop

Use a browser to inspect at approximately 390, 768 and 1440px. Landing and run view must work on phones; review may remain desktop-oriented per the spec, but narrow layouts must show an intentional fallback. Capture screenshots for internal comparison, inspect alignment, density, line length, clipping, contrast, focus and actual interactions; repair issues and recheck affected screens. Aim for at least one deliberate visual review after the first functional implementation. Report screenshots and browser execution honestly; do not substitute a successful compile for visual QA.

## Phase E — Evaluation and production readiness

Load and validate the 200-email labelled corpus, policy cross-references, golden citations, difficulty distribution and duplicate-body checks. Use recorded fixtures for deterministic regression tests; run live model evaluation separately within available quota. Report accuracy, route accuracy, escalation precision/recall, refusal rate, validator checks, cache performance, latency and malformed output with sample counts and model/corpus versions.

Validate ECE against a hand-computed example. Calibrate thresholds on a defined calibration split and report final performance on held-out examples, rather than tuning and reporting on the same emails. Target classification accuracy ≥85%; report actual results if unmet. Treat ≥30% steady-state semantic cache rate as a measured target, not a guaranteed result. Zero eligible observations must display N/A rather than 100%.

Inspect the Cloud Run worker lifecycle carefully. A continuously polling ARQ worker must remain available independently of incoming HTTP requests; do not assume scale-to-zero HTTP hosting runs background jobs reliably. Verify current official hosting constraints and document the chosen lifecycle, CPU/billing implications and delivery recovery. Reuse existing viable hosting when possible; do not silently change platform or introduce cost.

Prepare production containers, migration instructions, secrets configuration, readiness checks, SPA route handling, provider setup and rollback notes. Verify a public demo only when deployment access is available. Never describe local-only or fixture-only evidence as deployed success.

## Definition of complete

- Existing work is preserved and every original task is audited with evidence.
- API, database, worker, graph, retrieval, validation and review operate together.
- No outgoing email path is enabled in v1; MCP transport remains deferred to v1.1.
- Routing hard stops, cache isolation, retry limits, ingestion idempotency and restart behaviour are tested.
- Every required screen is connected to real APIs and browser-checked in both themes.
- Eval figures are reproducible and labelled by dataset/model version; unmet targets remain visible.
- README explains startup, demo steps, architecture, measured results and limits.
- Final handoff lists changed files, commands/check outcomes, unresolved blockers, and exact deployment status.

## Paste this into Codex with repository access

```text
Complete the existing Dak project using 07-codex-completion-plan.md and the supplied 00–06 specifications. This is a partially built repository. First read applicable repository instructions and audit the real implementation; preserve working code and uncommitted user changes. Do not create a replacement scaffold or assume a feature works because a file exists.

Create docs/build-audit.md mapping every original build task to existing code, executable evidence, status and next action. Run existing checks and startup before edits. Reconcile the documented contract conflicts in a decision log, then continue autonomously through backend completion, frontend, integration, evaluation and deployment preparation. Complete one verifiable slice at a time and keep the audit current. Ask only for material decisions or genuinely unavailable access, while continuing independent work.

For frontend, inspect https://dribbble.com/shots/27820957-ORDO-Landing-Page if accessible and translate its relevant design principles into original Dak screens. If inaccessible, use the proposed editorial mailroom direction and say so. Establish a small design system, start with the review workspace and live trace, then landing, dashboard and eval. Build a purposeful, polished interface with real content and working interactions. Follow the visual constraints and browser review loop in the completion plan. Do not stop at a mockup or a build that merely compiles.

Preserve draft-and-review-only v1, Gemini runtime configuration, deterministic routing and eligibility, fail-closed citation checks, bounded retries, checkpoint resume and customer-safe caching. Keep MCP deferred. Never fabricate metrics, traces, test results or deployment claims. End with changes, verification evidence, remaining blockers and demo instructions.
```

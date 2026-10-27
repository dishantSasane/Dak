# Phase 1 — Gaps and recommendations

These are suggested changes, not work implemented or authorized by this audit. Existing functionality was preserved. The target is the latest business workflow, which extends the repository's explicitly draft-only v1 scope.

## Priority 0: boundaries before real customers or sending

| Gap | Why it matters | Suggested smallest useful change | Acceptance evidence needed |
|---|---|---|---|
| No outbound delivery path | No requested send scenario can complete | Add one provider adapter behind a disabled-by-default delivery boundary; persist an outbox/send attempt and provider ID | Synthetic sandbox message reaches a controlled test inbox; status reflects actual provider result |
| No reviewer authentication/authorization | Anyone reaching review routes can read messages and record approvals; confirmed by HTTP probe | Protect read/write reviewer APIs; derive reviewer identity on the server; apply role permissions | Anonymous/incorrect-role requests fail; authorized reviewer can act; actor recorded |
| No explicit mandatory-HITL send policy | Claims are safe today because nothing sends; unused config is not a guard | One deterministic eligibility function shared by auto-send and review delivery; explicitly exclude claims/reimbursements, restricted/sensitive categories and unvalidated drafts | Adversarial category/flag combinations cannot auto-send; restricted cases cannot bypass via a different route |
| No outbound idempotency | Review-row uniqueness does not prevent duplicate provider delivery | Transactional outbox plus stable send key tied to approved content/version; provider reconciliation for ambiguous timeouts | Concurrent approval/retry/crash tests deliver once or expose an explicit uncertain state without blind resending |
| Sender/policy ownership not verified | Knowing a policy number gives access to personal context in the processing path | Define approved identity checks before personal details can be used or disclosed; keep generic answers separate | Mismatched sender/policy and spoofed thread/token cases do not reveal another customer's details |
| Validator cannot prove cited text supports prose | A synthetically contradictory cited sentence passed | Keep structural guards, strengthen answer-evidence checks and human evidence review; evaluate grounded correctness independently | Counterexamples tested; held-out measured results and residual limits documented before auto-send |

Do not enable auto-send merely by adding a provider credential or changing `AUTO_SEND_ENABLED`. The current flags have no execution path. Authentication of the inbound provider does not authorize the customer or human reviewer.

## Priority 1: make the requested end-to-end workflow complete

1. **Define actual categories and provider.** Confirm whether Mailin means CloudMailin. Add service/technical handling and explicit reimbursement coverage if required. Current literal categories are query, complaint, claim, mixed and unknown. Retain existing agents and extend contracts/routes/tests rather than replacing the system.
2. **Finish the reviewer information contract.** Return a clear policy/customer snapshot, attachment inventory/access metadata, escalation reason and persisted decision history. Correct triage payload nesting. Add readable panels instead of relying on raw event JSON. Show reviewer identity and timestamps.
3. **Make edited sending explicit.** Preserve original and final approved versions, show the final version before sending, validate recipient/content permissions on the backend and record the content version actually sent. The current direct edited-action API accepts nonempty text even without a validated original draft; decide how explicitly authorized manual authoring should work.
4. **Keep rejection actionable.** Add a rejected/follow-up view, ownership and next-step state. Current rejection preserves records but removes them from the default review queues and leaves case status untouched. Do not equate a rejected draft with a resolved customer case.
5. **Implement attachment access deliberately.** Current code counts filenames only. Add size/type limits, secure storage/access, scanning, retention and safe viewing before using real documents. Do not treat a filename as proof that the required document is valid or complete.
6. **Add a failed-run recovery path.** A worker exception marks `failed`, which all subsequent worker calls/reconciliation treat as terminal. Provide an authorized retry/resume action that preserves history and uses existing checkpoints; distinguish infrastructure retries from permanent model failures. Test the actual worker path, not only direct `process_run` resume.
7. **Complete delivery operations.** Add retryable versus permanent send failure states, capped retries, provider-status reconciliation, delivery/bounce events and a human recovery view. A provider acceptance response is not proof of inbox delivery. Never retry an uncertain send blindly.
8. **Verify real integrations with synthetic messages.** Tests currently inject model output and inbound HTTP payloads. Verify configured Gemini model IDs/account access, inbound webhook delivery and the chosen outbound sandbox/test inbox separately. Do not request secret values in chat.
9. **Measure quality.** Complete the labelled evaluation set and repeatable evaluation runner before interpreting confidence as send safety. The evaluation UI reads results; it does not create a validated evaluation by itself. The authored retrieval smoke set is not held-out evaluation.

## Priority 2: reliability and packaging follow-up

- **Fix application image completeness.** Dockerfile manually installs a subset of Python dependencies, omits `sentence-transformers`, does not copy policy corpus/model assets, and does not package React. Source deployments using the local venv can work even when this image cannot execute retrieval. Build/smoke-test API plus worker before any cloud plan is approved. Do not treat healthy database containers as validation of application images.
- **Plan persistent worker lifecycle.** ARQ polling, reconciliation and LLM processing depend on a live separate worker and Redis. Preserve this requirement in Phase 3 rather than assuming a request-only web service runs all work after returning HTTP 200.
- **Harden ingress limits.** Manual submission has an in-process per-IP limiter, no shared scale-out limit, and no server-side field length/email-format constraints in `ManualEmailRequest`. Webhook body/attachment size limits are not implemented here. Add measured limits and trusted proxy handling for public operation.
- **Make audit records complete.** Existing RunEvents are useful but include potentially personal tool/state data, can duplicate state in receipts, and have no retention/redaction or immutable storage policy. Add reviewer/delivery audit records and controlled access. Langfuse currently has settings but no runtime integration; decide whether database traces suffice before adding another service.
- **Clarify metrics.** `emails_processed` counts runs in the time window, including unfinished ones. Escalation rate is based on current run status and changes when an escalated run is approved. Citation grounding rate measures citation presence in passed drafts, not semantic truth. Preserve accurate labels/denominators.
- **Connect config to behavior.** `RETRIEVAL_TOP_K` is declared but agent retrieval uses the function's default `k=5`; auto-send fields are unused. Remove ambiguity in a later code change rather than presenting these as operational controls.
- **Refresh stale documentation.** Some corpus/script comments still say graph/validator integration is pending, although graph tests show it exists. Historical build ledgers include superseded “no frontend” statements. Keep historical evidence, but label it clearly and make the current audit discoverable.
- **Treat current data as fixtures.** The synthetic policy corpus is not a legal policy engine, identity system or live insurer source. Product-specific grace/revival/payment facts and full conversation history require explicit data contracts if the business needs them.

## Scenario readiness today

| Requested scenario | What can be demonstrated now | What is unavailable |
|---|---|---|
| Simple query gets automatic reply | Scripted/live-if-configured query processing can produce a validated review draft | Automatic send and received reply |
| Low-confidence query goes to HITL | Deterministic low-confidence route tested | Measured real-world confidence calibration |
| Reimbursement goes directly to HITL | Claim processing ends for review because every run does | Explicit reimbursement detection and direct mandatory-HITL send guard |
| Human approves draft | Saved approval, original draft retained | Sending, delivery status and reviewer identity |
| Human edits and sends | Saved edited text and approval status | Final delivery and delivery audit |
| Human rejects with no send | Saved rejection; no send path exists | Dedicated follow-up/rejected-case workflow |
| Failed delivery recovery | Nothing can attempt outbound delivery | Provider failure simulation/integration and recovery mechanism |

## Recommended order after Phase 1

First, wait for the user's confirmation to begin Phase 2. Run the **existing draft-only application** in small, user-confirmed steps and explain its limits honestly. A local recorded-fixture demonstration and a real provider test must be labelled separately. Setup cannot fill missing sending functionality.

Missing features need a separately agreed implementation scope. Build and verify the smallest complete authorized path on top of existing modules. Keep mandatory-HITL decisions and outbound deduplication central. Phase 3 cloud/cost analysis follows only when requested; no provisioning or deployment has occurred.

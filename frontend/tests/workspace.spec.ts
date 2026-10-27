import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const run = {
  id: 1,
  status: "pending_review",
  category: "query",
  confidence: 0.9,
  route: "query_agent",
  escalation_reason: null,
  duration_ms: 1200,
  token: "TEST-CASE",
  subject: "Test policy question",
  started_at: "2026-10-19T12:00:00Z",
};
const email = {
  subject: run.subject,
  from: "synthetic@example.com",
  body_plain: "Can you explain the waiting period under ASP-TEST?",
  received_at: run.started_at,
};
const draft = {
  attempt: 2,
  rendered_text: "The waiting period is 30 days.",
  sentences: [
    {
      text: "The waiting period is 30 days.",
      kind: "factual",
      cite: "ASP-C01",
    },
  ],
  validation_passed: true,
  violations: [],
};
const events = [
  {
    seq: 1,
    node: "validator",
    event_type: "validation_blocked",
    payload: { passed: false },
    duration_ms: 8,
    created_at: run.started_at,
  },
];
async function fixtures(page: import("@playwright/test").Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname;
    let body: unknown = {};
    if (p === "/api/demo/config")
      body = {
        product_name: "Dak",
        inbound_address: null,
        repository_url: null,
        synthetic: true,
        sample_policies: [
          {
            policy_number: "ASP-TEST",
            product_code: "ASP",
            product_name: "Synthetic Health",
          },
        ],
        samples: [
          {
            label: "A clean query",
            sender: email.from,
            subject: email.subject,
            body: email.body_plain,
          },
          {
            label: "An angry complaint",
            sender: email.from,
            subject: "A complaint",
            body: "Synthetic complaint",
          },
          {
            label: "A messy claim",
            sender: email.from,
            subject: "A claim",
            body: "Synthetic claim",
          },
        ],
      };
    else if (p === "/api/review/queue")
      body = {
        total: 1,
        items: [
          {
            ...run,
            run_id: 1,
            from: email.from,
            waiting_since: run.started_at,
            validation_passed: false,
          },
        ],
      };
    else if (p === "/api/review/1")
      body = {
        run,
        email,
        triage: { reasoning: "A synthetic query." },
        drafts: [
          {
            ...draft,
            attempt: 1,
            validation_passed: false,
            violations: [{ code: "UNSOURCED_FIGURE" }],
          },
          draft,
        ],
        citations: [
          {
            clause_id: "ASP-C01",
            clause_title: "Initial waiting period",
            content: "A waiting period of 30 days applies.",
            used_in_sentences: [0],
          },
        ],
        events,
        internal_note: null,
        case_file: null,
        escalation_brief: null,
      };
    else if (p === "/api/review/1/action") body = { status: "recorded" };
    else if (p === "/api/runs/1/detail")
      body = { run, email, token: "TEST-CASE" };
    else if (p === "/api/runs/1/events")
      body = { status: "pending_review", run_id: 1, events };
    else if (p === "/api/runs") body = { items: [run] };
    else if (p === "/api/cases/TEST-CASE")
      body = {
        token: "TEST-CASE",
        status: "open",
        created_at: run.started_at,
        emails: [
          {
            direction: "inbound",
            subject: email.subject,
            preview: "Restricted preview only.",
            received_at: run.started_at,
          },
        ],
        runs: [run],
      };
    else if (p === "/api/metrics/summary")
      body = {
        window: "7d",
        emails_processed: 1,
        escalation_rate: 0,
        validator_block_rate: 1,
        latency_ms: { p50: 1200, p95: 1200 },
      };
    else if (p === "/api/eval/runs") body = { items: [] };
    else if (p === "/api/manual-email")
      body = { run_id: 1, token: "TEST-CASE" };
    await route.fulfill({
      json: body,
      status: p === "/api/manual-email" ? 202 : 200,
    });
  });
}
for (const theme of ["light", "dark"] as const) {
  for (const width of [320, 390, 768, 1024, 1440])
    test(`screens ${theme} ${width}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme });
      await page.setViewportSize({ width, height: 1000 });
      await fixtures(page);
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      for (const path of [
        "/",
        "/review",
        "/runs/1",
        "/dashboard",
        "/eval",
        "/t/TEST-CASE",
      ]) {
        await page.goto(path);
        await expect(page.locator("h1")).toBeVisible();
        await expect(page.getByText("Loading the mailroom…")).toHaveCount(0);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        ).toBeTruthy();
        const issues = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa"])
          .analyze();
        expect(
          issues.violations.map(
            (v) =>
              `${path} ${v.id}: ${JSON.stringify(v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary })))}`,
          ),
        ).toEqual([]);
        if (
          (width === 1440 || width === 390) &&
          ["/", "/review", "/runs/1"].includes(path)
        )
          await page.screenshot({
            path: `test-results/${path === "/" ? "landing" : path.replaceAll("/", "-")}-${theme}-${width}.png`,
            fullPage: true,
          });
      }
      expect(errors).toEqual([]);
    });
}
test("sample compose submits to real client contract and navigates", async ({
  page,
}) => {
  await fixtures(page);
  await page.goto("/");
  await page.getByRole("button", { name: /A clean query/ }).click();
  await expect(
    page.getByRole("button", { name: /A clean query/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("From", { exact: true })).toHaveValue(
    email.from,
  );
  const req = page.waitForRequest((r) => r.url().includes("/api/manual-email"));
  await page.getByRole("button", { name: /Submit for triage/ }).click();
  expect((await req).postDataJSON()).toEqual({
    sender: email.from,
    subject: email.subject,
    body: email.body_plain,
  });
  await expect(page).toHaveURL(/\/runs\/1$/);
});
test("citations reveal source and edited approval persists exact text", async ({
  page,
}) => {
  await fixtures(page);
  await page.goto("/review");
  await page.getByRole("button", { name: /ASP-C01/ }).click();
  await expect(
    page.getByText("A waiting period of 30 days applies."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit & approve" }).click();
  await page
    .getByLabel("Edited response")
    .fill("Reviewer edited synthetic response.");
  await page.getByLabel("Reviewer note").fill("Checked source.");
  const req = page.waitForRequest((r) => r.url().includes("/action"));
  await page.getByRole("button", { name: "Save edit & approve" }).click();
  expect((await req).postDataJSON()).toEqual({
    action: "edited",
    edited_text: "Reviewer edited synthetic response.",
    reviewer_note: "Checked source.",
  });
  await expect(page.getByRole("status")).toContainText("Decision recorded");
});
test("load failure gives useful retry state", async ({ page }) => {
  await page.route("**/api/demo/config", (r) =>
    r.fulfill({ status: 503, json: { detail: "Service unavailable" } }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Service unavailable");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
test("evaluation renders actual counts, calibrated bins and failure filters", async ({
  page,
}) => {
  await fixtures(page);
  await page.route("**/api/eval/runs", (r) =>
    r.fulfill({
      json: {
        items: [
          {
            id: 7,
            started_at: run.started_at,
            corpus_version: "test-v1",
            model_triage: "test-triage",
            model_draft: "test-draft",
          },
        ],
      },
    }),
  );
  await page.route("**/api/metrics/eval/7", (r) =>
    r.fulfill({
      json: {
        accuracy_overall: 0.5,
        accuracy_by_difficulty: { easy: 1, hard: 0 },
        confusion_matrix: { query: { query: 1 }, claim: { query: 1 } },
        route_accuracy: 0.5,
        escalation_precision: null,
        escalation_recall: null,
        out_of_scope_refusal_rate: null,
        calibration: {
          ece: 0.25,
          bins: [{ range: "0.8-1.0", predicted: 0.9, observed: 0.5, n: 2 }],
        },
      },
    }),
  );
  await page.route("**/api/eval/runs/7/results", (r) =>
    r.fulfill({
      json: {
        total: 2,
        items: [
          {
            email_id: 1,
            run_id: null,
            subject: "Correct synthetic email",
            difficulty: "easy",
            expected_category: "query",
            predicted_category: "query",
            confidence: 0.9,
            category_correct: true,
            route_correct: true,
          },
          {
            email_id: 2,
            run_id: 1,
            subject: "Incorrect synthetic email",
            difficulty: "hard",
            expected_category: "claim",
            predicted_category: "query",
            confidence: 0.9,
            category_correct: false,
            route_correct: false,
          },
        ],
      },
    }),
  );
  await page.goto("/eval");
  await expect(
    page.getByRole("img", { name: /Reliability diagram/ }),
  ).toBeVisible();
  await expect(page.getByText("ECE 0.250")).toBeVisible();
  await expect(page.getByText("No linked run")).toBeVisible();
  await page.getByLabel("Failures only").check();
  await expect(
    page.getByText("Correct synthetic email", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("Incorrect synthetic email")).toBeVisible();
  const a = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(a.violations).toEqual([]);
});
test("incremental polling deduplicates and stops at terminal state", async ({
  page,
}) => {
  await fixtures(page);
  let requests = 0;
  const after: string[] = [];
  await page.route("**/api/runs/1/events?*", (r) => {
    requests++;
    after.push(new URL(r.request().url()).searchParams.get("after_seq") || "");
    return r.fulfill({
      json: {
        run_id: 1,
        status: after.at(-1) === "0" ? "processing" : "pending_review",
        events,
      },
    });
  });
  await page.goto("/runs/1");
  await expect(page.locator(".trace li")).toHaveCount(1);
  await expect(
    page.getByText("Draft prepared. A human decision is required."),
  ).toBeVisible();
  expect(after[0]).toBe("0");
  expect(after.at(-1)).toBe("1");
  const terminalRequests = requests;
  await page.waitForTimeout(1700);
  expect(requests).toBe(terminalRequests);
  await expect(page.locator(".trace li")).toHaveCount(1);
});

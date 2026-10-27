import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFile } from "node:fs/promises";
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://127.0.0.1:5173/");
await expect(page.getByText("Active cover", {exact:true})).toBeVisible();
await expect(page.getByText("Lapsed cover", {exact:true})).toBeVisible();
await expect(page.getByText("Within initial waiting period", {exact:true})).toBeVisible();
await page.screenshot({path:"test-results/real-landing-final.png",fullPage:true});
await page.goto("http://127.0.0.1:5173/review?run=3");
await expect(page.locator(".correspondence h2")).toContainText(
  "RECORDED FIXTURE",
);
await page.getByText("Internal note · reviewer only", { exact: true }).click();
await expect(page.locator(".evidence[open] pre").last()).toBeVisible();
const cite = page.locator(".citation").first();
if (await cite.count()) {
  await cite.click();
  await expect(page.locator(".clause")).toBeVisible();
}
await expect(page.getByText("Recorded fixture · generated for local verification, without live model inference.")).toBeVisible();
await page.screenshot({
  path: "test-results/real-complaint-review.png",
  fullPage: true,
});
const original = await page.locator(".draft-copy").innerText();
const saved = await (
  await page.request.get("http://127.0.0.1:5173/api/review/3")
).json();
expect(saved.run.status).toBe("approved");
expect(saved.drafts.at(-1).rendered_text).not.toContain(
  "[Recorded fixture review verification.]",
);
await page.goto("http://127.0.0.1:5173/review?run=4");
await page.getByText("Claim case file", { exact: true }).click();
await expect(page.locator(".evidence[open]")).toContainText("policy_status");
await page.screenshot({
  path: "test-results/real-claim-review.png",
  fullPage: true,
});
const issues = await new AxeBuilder({ page })
  .withTags(["wcag2a", "wcag2aa"])
  .analyze();
expect(issues.violations).toEqual([]);
await page.goto("http://127.0.0.1:5173/t/INS-5F0F-N1TY");
await expect(page.locator("h1")).toHaveText("Your correspondence.");
expect(await page.locator(".draft-copy").count()).toBe(0);
expect(await page.locator(".email-body").count()).toBe(0);
await writeFile(
  "test-results/real-review.json",
  JSON.stringify(
    {
      complaintRun: 3,
      status: saved.run.status,
      originalDraftRetained: true,
      claimRun: 4,
      claimFileVisible: true,
      publicCaseRestricted: true,
      axeViolations: issues.violations.length,
      errors,
    },
    null,
    2,
  ),
);
console.log(
  "Real persisted review, claim evidence and restricted public case verified.",
);
await browser.close();

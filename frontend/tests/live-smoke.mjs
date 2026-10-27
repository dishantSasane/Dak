// Explicit real local API smoke; no route interception or live-model claim.
import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await mkdir("test-results", { recursive: true });
const results = [];
for (const path of ["/", "/dashboard", "/review", "/eval"]) {
  await page.goto(`http://127.0.0.1:5173${path}`);
  await page.waitForTimeout(1000);
  results.push({
    path,
    title: await page.locator("h1").innerText(),
    alerts: await page.getByRole("alert").allTextContents(),
  });
  await page.screenshot({
    path: `test-results/real-${path === "/" ? "landing" : path.slice(1)}.png`,
    fullPage: true,
  });
}
await page.goto("http://127.0.0.1:5173/");
await page.getByRole("button", { name: /Coverage query/ }).click();
await page.getByRole("button", { name: /Submit for triage/ }).click();
await page.waitForURL(/\/runs\/\d+$/);
await page.waitForTimeout(2000);
results.push({
  submittedRun: page.url(),
  status: await page.locator(".page-title .badge").innerText(),
});
await page.screenshot({ path: "test-results/real-run.png", fullPage: true });
await writeFile(
  "test-results/real-smoke.json",
  JSON.stringify({ results, errors }, null, 2),
);
console.log(JSON.stringify({ results, errors }, null, 2));
await browser.close();

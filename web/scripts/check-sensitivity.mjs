// Verifies the "What matters most" chart renders from scenario.sensitivity and hides when it is empty.
// Usage: node scripts/check-sensitivity.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const file = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "fixtures", "scenarios", "suez-2021.json");
const browser = await chromium.launch();
let ok = true;

for (const empty of [false, true]) {
  const context = await browser.newContext({ viewport: { width: 1840, height: 810 } });
  if (empty) {
    const s = JSON.parse(readFileSync(file, "utf8"));
    s.sensitivity = [];
    await context.route("**/data/real/scenarios/suez-2021.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(s) }));
  }
  const page = await context.newPage();
  await page.goto(`${base}/?scenario=suez-2021`);
  await page.waitForSelector("[data-ready='true']");
  const rows = await page.locator(".sens-row").allInnerTexts();
  const pass = empty ? rows.length === 0 : rows.length === 3 && rows[0].includes("Air freight capacity");
  if (!pass) ok = false;
  console.log(`${empty ? "empty sensitivity" : "fixture sensitivity"}: ${rows.length} rows ${JSON.stringify(rows.map((r) => r.replace(/\s+/g, " ")))} -> ${pass ? "OK" : "FAIL"}`);
  await context.close();
}
await browser.close();
console.log(ok ? "OK" : "FAIL");
process.exit(ok ? 0 : 1);

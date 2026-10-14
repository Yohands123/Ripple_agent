// Verifies forecast fan charts render from forecasts.json, and that a missing file shows a quiet empty state.
// Usage: node scripts/check-forecasts.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3000";
const browser = await chromium.launch();
let ok = true;

for (const missing of [false, true]) {
  const context = await browser.newContext({ viewport: { width: 1840, height: 810 } });
  if (missing) await context.route("**/data/*/forecasts.json", (r) => r.fulfill({ status: 404, body: "" }));
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/?node=assembly-zhengzhou`);
  await page.waitForSelector("[data-ready='true']");
  await page.waitForTimeout(300);
  const fans = await page.locator("svg[data-fan]").count();
  const empty = await page.getByText("Cost forecasts are not available yet.").count();
  const pass = errors.length === 0 && (missing ? fans === 0 && empty === 1 : fans > 0 && empty === 0);
  if (!pass) ok = false;
  console.log(`${missing ? "file missing" : "file present"}: ${fans} fan charts, empty note ${empty}, page errors ${errors.length} -> ${pass ? "OK" : "FAIL"}`);
  if (!missing) await page.screenshot({ path: `${process.env.TEMP}/ripple-shots/forecast.png` });
  await context.close();
}
await browser.close();
console.log(ok ? "OK" : "FAIL");
process.exit(ok ? 0 : 1);

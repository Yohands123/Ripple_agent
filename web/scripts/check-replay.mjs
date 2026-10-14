// Verifies scrubbing the Suez replay updates the map and the panel.
// Usage: node scripts/check-replay.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3000";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1840, height: 810 } });
await page.goto(`${base}/?scenario=suez-2021`);
await page.waitForSelector("[data-ready='true']");

async function at(day) {
  await page.locator(".replay-range").fill(String(day));
  await page.waitForTimeout(150);
  return {
    day,
    panel: await page.innerText(".replay-day"),
    yearTag: await page.innerText(".year-sub"),
    queued: await page.locator(".mover[data-mover='ship'].enter-coins").count(),
    grey: await page.locator("[data-coin='grey']").count(),
    red: await page.locator("[data-coin='red']").count(),
    predicted: await page.locator("[data-marker='predicted']").count(),
  };
}

const first = await at(1);
const last = await at(6);
for (const s of [first, last]) console.log(JSON.stringify(s));
const ok =
  first.panel !== last.panel &&
  first.yearTag !== last.yearTag &&
  last.queued > first.queued &&
  last.grey + last.red > first.grey + first.red;
console.log(ok ? "OK" : "FAIL");
await browser.close();
process.exit(ok ? 0 : 1);

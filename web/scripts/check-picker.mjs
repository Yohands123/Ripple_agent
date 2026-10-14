// Verifies the scenario picker lists every scenario, filters by type, and switching updates map and panel.
// A second scenario is simulated by answering /data/real/* requests in the browser; nothing is written to disk.
// Usage: node scripts/check-picker.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { fixturesContext } from "./fixtures-only.mjs";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const fixtures = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "fixtures");
const read = (p) => JSON.parse(readFileSync(resolve(fixtures, p), "utf8"));
const json = (body) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

const suez = read("scenarios/suez-2021.json");
const other = {
  ...structuredClone(suez),
  id: "test-shenzhen-port",
  title: "Shenzhen port closed",
  type: "land",
  start: "2021-05-21",
  end: "2021-06-24",
  headline: "Test: Shenzhen port closed. Exports from South China are delayed.",
  shock: { nodeIds: ["port-shenzhen"], capacityLoss: 0.7 },
  affectedRoutes: { blocked: ["e-sea-asia"], detour: [], expedited: ["e-air-zhengzhou"] },
  sensitivity: [],
};
const index = [
  { id: suez.id, title: suez.title, type: suez.type, start: suez.start },
  { id: other.id, title: other.title, type: other.type, start: other.start },
];

const browser = await chromium.launch();
const context = await fixturesContext(browser, { viewport: { width: 1840, height: 810 } });
await context.route("**/data/real/scenarios/index.json", (r) => r.fulfill(json(index)));
await context.route(`**/data/real/scenarios/${other.id}.json`, (r) => r.fulfill(json(other)));
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(`${base}/?scenario=suez-2021`);
await page.waitForSelector("[data-ready='true']");

const state = async () => ({
  headline: await page.innerText(".headline"),
  options: await page.locator(".scenario-select option").count(),
  zoneAt: await page.$$eval(".shock-zone", (els) => els.map((e) => `${e.style.left},${e.style.top}`)),
  blocked: await page.$$eval("[data-state='blocked']", (els) => els.map((e) => e.getAttribute("data-route"))),
  year: await page.innerText(".year-tag"),
});

const before = await state();
await page.click("[data-filter='land']");
const landOptions = await page.locator(".scenario-select option[value]:not([value=''])").allInnerTexts();
await page.selectOption(".scenario-select", other.id);
await page.waitForFunction((h) => document.querySelector(".headline")?.textContent?.includes(h), "Shenzhen port closed");
await page.waitForTimeout(300);
const after = await state();
const url = page.url();

for (const [k, v] of Object.entries({ before, landOptions, after, url })) console.log(k, JSON.stringify(v));
const ok =
  errors.length === 0 &&
  before.options === 2 &&
  landOptions.length === 1 &&
  landOptions[0].includes("Shenzhen") &&
  before.headline !== after.headline &&
  JSON.stringify(before.zoneAt) !== JSON.stringify(after.zoneAt) &&
  after.blocked.includes("e-sea-asia") &&
  url.includes(other.id);
console.log(ok ? "OK" : `FAIL ${errors.join("; ")}`);
await page.screenshot({ path: `${process.env.TEMP}/ripple-shots/picker.png` });
await browser.close();
process.exit(ok ? 0 : 1);

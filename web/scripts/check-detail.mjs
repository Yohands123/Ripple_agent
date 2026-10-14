// Verifies the supplier detail panel on fixture data and on simulated real data.
// Real data is simulated by answering /data/real/* requests in the browser; nothing is written to disk.
// Usage: node scripts/check-detail.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const fixtures = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "fixtures");
const read = (p) => JSON.parse(readFileSync(resolve(fixtures, p), "utf8"));

const browser = await chromium.launch();
let ok = true;

async function run(name, setup, expectText) {
  const context = await browser.newContext({ viewport: { width: 1840, height: 810 } });
  await setup(context);
  const page = await context.newPage();
  await page.goto(`${base}/?scenario=suez-2021`);
  await page.waitForSelector("[data-ready='true']");
  await page.click("[data-node-id='store-london']");
  const text = await page.innerText(".panel");
  const shapRows = await page.locator(".shap-row").count();
  const pass = expectText.every((t) => text.includes(t)) && shapRows > 0;
  if (!pass) ok = false;
  console.log(`${name}: shap rows ${shapRows}, expected text ${pass ? "found" : "MISSING"} -> ${pass ? "OK" : "FAIL"}`);
  await page.keyboard.press("Escape");
  const closed = (await page.locator(".shap-row").count()) === 0;
  if (!closed) ok = false;
  console.log(`${name}: Escape closes panel -> ${closed ? "OK" : "FAIL"}`);
  await context.close();
}

await run("fixtures", async () => {}, ["Apple Store, London", "0.86", "range 0.74 to 0.93", "Depends on shocked chokepoint"]);

await run(
  "simulated real",
  async (context) => {
    const network = read("network.json");
    network.sampleData = false;
    network.nodes.find((n) => n.id === "store-london").sources = [{ title: "Example source", url: "https://example.org/" }];
    const scenario = read("scenarios/suez-2021.json");
    scenario.sampleData = false;
    scenario.actual = [{ nodeId: "store-london", hit: true, car: -0.034 }];
    const json = (body) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    await context.route("**/data/real/network.json", (r) => r.fulfill(json(network)));
    await context.route("**/data/real/scenarios/suez-2021.json", (r) => r.fulfill(json(scenario)));
  },
  ["Hit", "−3.4%", "Example source"],
);

await browser.close();
console.log(ok ? "OK" : "FAIL");
process.exit(ok ? 0 : 1);

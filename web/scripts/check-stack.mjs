// Verifies supplier stacks open from every assembly node, on fixtures and on simulated real data.
// Real data is simulated by answering /data/real/* requests in the browser; nothing is written to disk.
// Usage: node scripts/check-stack.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { fixturesContext } from "./fixtures-only.mjs";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const fixtures = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "fixtures");
const read = (p) => JSON.parse(readFileSync(resolve(fixtures, p), "utf8"));
const browser = await chromium.launch();
let ok = true;

async function run(name, url, setup, check) {
  const context = await fixturesContext(browser, { viewport: { width: 1840, height: 810 } });
  await setup(context);
  const page = await context.newPage();
  await page.goto(`${base}${url}`);
  await page.waitForSelector("[data-ready='true']");
  const ids = await page.$$eval("[data-kind='assembly']", (els) => els.map((e) => e.getAttribute("data-node-id")));
  for (const id of ids) {
    await page.click(`[data-node-id='${id}']`);
    const levels = await page.locator(".stack-overlay .stack-level").count();
    const partial = await page.locator(".stack-level.partial").count();
    const tiles = await page.$$eval(".stack-tile", (els) => els.map((e) => e.getAttribute("data-tile")));
    const active = await page.$$eval(".chute[data-active='true']", (els) => els.map((e) => e.getAttribute("data-chute")));
    const pass = levels === 3 && partial === 1 && check(id, tiles, active);
    if (!pass) ok = false;
    console.log(`${name} ${id}: levels ${levels}, tiles ${JSON.stringify(tiles)}, active chutes ${JSON.stringify(active)} -> ${pass ? "OK" : "FAIL"}`);
    if (id === "assembly-shenzhen" && name === "simulated real") await page.screenshot({ path: `${process.env.TEMP}/ripple-shots/stack.png` });
    await page.keyboard.press("Escape");
  }
  if (ids.length === 0) ok = false;
  await context.close();
}

await run("fixtures", "/", async () => {}, (id, tiles) => (id === "assembly-shenzhen" ? tiles.includes("assembly-shenzhen") && tiles.includes("supplier-taiwan") : true));

await run(
  "simulated real",
  "/?scenario=suez-2021",
  async (context) => {
    const network = read("network.json");
    network.sampleData = false;
    network.nodes.push(
      { id: "wafer-japan", name: "Sample wafer maker", kind: "supplier_minor", tier: 2, lon: 139.7, lat: 35.7, precision: "province", region: "Kanto, Japan", ticker: null, partType: "silicon wafers", appleRevenueShare: null, sources: [] },
      { id: "chips-korea", name: "Sample memory maker", kind: "supplier_major", tier: 3, lon: 127, lat: 37.5, precision: "province", region: "Gyeonggi, Korea", ticker: null, partType: "chips", appleRevenueShare: null, sources: [] },
    );
    network.edges.push(
      // Supply links (who supplies whom); transport routes never put a supplier in a stack.
      { id: "x1", from: "wafer-japan", to: "supplier-taiwan", relation: "supply", mode: null, carriesTier: 2, status: "inferred", confidence: "medium", sources: [] },
      { id: "x2", from: "chips-korea", to: "assembly-shenzhen", relation: "supply", mode: null, carriesTier: 3, status: "known", sources: [] },
      // A transport route into the factory: must not add anyone to the stack.
      { id: "x3", from: "port-singapore", to: "assembly-shenzhen", relation: "route", mode: "road", carriesTier: 3, status: "known", sources: [] },
    );
    const scenario = read("scenarios/suez-2021.json");
    scenario.predictions.push({ nodeId: "wafer-japan", pHit: 0.7, ciLow: 0.5, ciHigh: 0.85, lowConfidence: false, shap: [] });
    const json = (body) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    await context.route("**/data/real/network.json", (r) => r.fulfill(json(network)));
    await context.route("**/data/real/scenarios/suez-2021.json", (r) => r.fulfill(json(scenario)));
  },
  (id, tiles, active) =>
    id === "assembly-shenzhen"
      ? ["supplier-taiwan", "chips-korea", "wafer-japan"].every((t) => tiles.includes(t)) && !tiles.includes("port-singapore") && active.includes("1-up")
      : true,
);

await browser.close();
console.log(ok ? "OK" : "FAIL");
process.exit(ok ? 0 : 1);

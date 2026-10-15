// Verifies the app against the real export as it is now (no interception):
// tiers draw in their colors, each event loads its own network, lanes switch to real
// routes when the export has edges, company-only events list companies, and every
// scenario opens without errors.
// Usage: node scripts/check-realdata.mjs [base-url]   (app must be running; skips if there is no real data)
import { chromium } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const real = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "real");
if (!existsSync(resolve(real, "network.json"))) {
  console.log("no real data: skipped");
  process.exit(0);
}
const read = (p) => JSON.parse(readFileSync(resolve(real, p), "utf8"));
const TIER = { 1: "#c79a6b", 2: "#e8662f", 3: "#a98be8", 4: "#46c6d8" };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1840, height: 810 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};
const open = async (query = "") => {
  await page.goto(`${base}/${query}`);
  await page.waitForSelector("[data-ready='true']");
  await page.waitForTimeout(600);
};

// Default view: the default network, tier colors, lanes or routes.
const net = read("network.json");
await open();
const fills = await page.locator("[data-node-id] svg path").evaluateAll((els) => els.map((e) => (e.getAttribute("fill") ?? "").toLowerCase()));
const tiered = net.nodes.filter((n) => n.tier != null).length;
const tierFills = fills.filter((f) => Object.values(TIER).includes(f)).length;
check("tiers draw in their colors", tiered === 0 || tierFills > 0, `${tiered} nodes with a tier in the file, ${tierFills} symbols in tier colors`);
const hasEdges = net.edges.length > 0;
const lanesNote = await page.locator("[data-note='illustrative-lanes']").count();
check(
  hasEdges ? "real routes replace typical lanes" : "typical lanes while the export has no routes",
  hasEdges ? lanesNote === 0 : lanesNote === 1,
  `${net.edges.length} edges in the export, lanes note ${lanesNote ? "shown" : "hidden"}`,
);
const quotaText = await page.locator(".panel-note").first().textContent();
check("normal-week quota has no raw decimals", !/\d+\.\d{3,}/.test(quotaText ?? ""), JSON.stringify(quotaText));

// Every scenario: opens dropped, uses its own network, no errors.
const index = read("scenarios/index.json");
for (const entry of index) {
  const s = read(`scenarios/${entry.id}.json`);
  const before = errors.length;
  await open(`?scenario=${entry.id}`);
  const own = s.networkPath ? read(s.networkPath) : net;
  // Sites drawn on their own plus those inside cluster bubbles.
  const clustered = (await page.locator("[data-cluster]").evaluateAll((els) => els.map((e) => Number(e.getAttribute("data-cluster"))))).reduce((a, b) => a + b, 0);
  const shown = (await page.locator("[data-node-id]").count()) + clustered;
  const expected = own.nodes.filter((n) => n.kind !== "hq" && !n.waypoint).length;
  const lanes = own.edges.length === 0 ? (await page.locator("[data-node-id][data-kind='port'], [data-node-id][data-kind='canal'], [data-node-id][data-kind='airport']").count()) : 0;
  check(`${entry.id}: own network`, shown - lanes === expected, `${shown - lanes} sites shown, ${expected} in ${s.networkPath ?? "network.json"}`);
  if (s.predictions.length === 0 && (s.companyPredictions ?? []).length > 0) {
    const rows = await page.locator("[data-list='companies'] .affected-row").count();
    check(`${entry.id}: company-only list`, rows > 0, `${rows} companies listed`);
  }
  if (s.quota?.optionPlans?.length && s.options.length) {
    const before = await page.locator(".quota-chart path, svg[aria-label^='Weekly output']").first().getAttribute("aria-label");
    await page.locator(".option-row input").first().click();
    await page.waitForTimeout(150);
    const after = await page.locator("svg[aria-label^='Weekly output']").first().getAttribute("aria-label");
    const note = await page.locator("text=split evenly").count();
    check(`${entry.id}: exact option plans`, before !== after && note === 0, before !== after ? "chart changes with options, no equal-split note" : "chart did not change");
  }
  check(`${entry.id}: no page errors`, errors.length === before, errors.slice(before).join("; ") || "none");
}

// Replay result names distance alone with the distance baseline's own number.
const metrics = read("metrics.json");
const suez = metrics.loeo.find((e) => e.eventId === "suez-2021");
if (suez) {
  await open("?scenario=suez-2021");
  const text = (await page.locator(".model-result").textContent()) ?? "";
  const distance = (suez.distanceAuc ?? suez.baselineAuc).toFixed(2);
  if (metrics.model === "distance") check("replay names distance as the selected model", text.includes("Distance from the shock") && text.includes(`AUC ${distance}`), text.trim().slice(0, 160));
  else check("replay compares with distance alone", text.includes(`${distance} for distance alone`), text.trim().slice(0, 160));
}

await browser.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "all checks passed");
process.exit(failed ? 1 : 0);

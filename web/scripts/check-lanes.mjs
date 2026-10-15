// Verifies illustrative lanes: drawn only when the network has no edges, with ships,
// a note in the panel, and shock locations closing the right lanes.
// Usage: node scripts/check-lanes.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fixturesContext } from "./fixtures-only.mjs";

const base = process.argv[2] ?? "http://localhost:3000";
const fixtures = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "fixtures");
const read = (p) => JSON.parse(readFileSync(resolve(fixtures, p), "utf8"));
const json = (body) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

// A route-less export like the real one: suppliers only, no edges, shocks given as locations.
const network = read("network.json");
network.sampleData = false;
network.nodes = network.nodes.filter((n) => n.kind.startsWith("supplier")).map((n) => ({ ...n, tier: null }));
network.edges = [];
const base0 = read("scenarios/suez-2021.json");
const scen = (id, title, type, lon, lat) => ({
  ...structuredClone(base0),
  id,
  title,
  type,
  sampleData: false,
  shock: { nodeIds: [], capacityLoss: null, location: { lon, lat } },
  affectedRoutes: { blocked: [], detour: [], expedited: [] },
  predictions: [],
  quota: null,
  options: [],
  money: { coinUsd: 500000000, revenueAtRisk: null, delayedShare: null, assumption: false },
});
const scenarios = {
  "suez-2021": scen("suez-2021", "Suez Canal blocked", "sea", 32.55, 30.0),
  "red-sea-2023": scen("red-sea-2023", "Red Sea shipping attacks", "sea", 38.7, 20.3),
  "shanghai-2022": scen("shanghai-2022", "Shanghai lockdown", "land", 121.43, 31.22),
  "zhengzhou-2022": scen("zhengzhou-2022", "Zhengzhou restrictions", "land", 113.66, 34.76),
};
const index = Object.values(scenarios).map((s) => ({ id: s.id, title: s.title, type: s.type, start: s.start }));

const browser = await chromium.launch();
let ok = true;
const check = (name, pass, detail) => {
  if (!pass) ok = false;
  console.log(`${name}: ${detail} -> ${pass ? "OK" : "FAIL"}`);
};

async function open(url, simulated) {
  const context = await fixturesContext(browser, { viewport: { width: 1840, height: 810 } });
  if (simulated) {
    await context.route("**/data/real/network.json", (r) => r.fulfill(json(network)));
    await context.route("**/data/real/scenarios/index.json", (r) => r.fulfill(json(index)));
    for (const s of Object.values(scenarios)) await context.route(`**/data/real/scenarios/${s.id}.json`, (r) => r.fulfill(json(s)));
  }
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}${url}`);
  await page.waitForSelector("[data-ready='true']");
  await page.waitForTimeout(300);
  const routes = await page.$$eval("[data-route]", (els) => Object.fromEntries(els.map((e) => [e.getAttribute("data-route"), e.getAttribute("data-state")])));
  const ships = await page.locator("[data-mover='ship']").count();
  const note = await page.locator("[data-note='illustrative-lanes']").count();
  return { page, context, errors, routes, ships, note };
}

// Fixture data has its own edges: no illustrative lanes.
{
  const r = await open("/", false);
  check("fixtures keep their own routes", !Object.keys(r.routes).some((k) => k.startsWith("lane-")) && r.note === 0, `${Object.keys(r.routes).length} routes, note ${r.note}`);
  await r.context.close();
}

// Route-less data, free flow: lanes, ships, flights, and the note; the Cape detour stays hidden.
{
  const r = await open("/", true);
  // Eight sea lanes, and the two Asia-Europe flights as one air bundle per origin.
  const lanes = Object.keys(r.routes).filter((k) => k.startsWith("lane-"));
  const air = Object.keys(r.routes).filter((k) => k.startsWith("air-lane-"));
  check(
    "route-less free flow",
    lanes.length === 8 && air.length === 2 && !lanes.includes("lane-sea-cape") && r.ships > 5 && r.note === 1 && r.errors.length === 0,
    `${lanes.length} lanes, ${air.length} air bundles, ${r.ships} ships, note ${r.note}, errors ${r.errors.length}`,
  );
  await r.page.screenshot({ path: `${process.env.TEMP}/ripple-shots/lanes-free.png` });
  await r.context.close();
}

const expectations = {
  "suez-2021": { blocked: ["lane-sea-suez-rotterdam"], detour: "lane-sea-cape", expedited: true, queuePill: "SHIPS QUEUED IN THE RED SEA" },
  "red-sea-2023": { blocked: ["lane-sea-babelmandeb-suez", "lane-sea-suez-rotterdam"], detour: "lane-sea-cape", expedited: true },
  "shanghai-2022": { blocked: ["lane-sea-shanghai-hongkong", "lane-sea-transpacific-east", "air-lane-port-shanghai>Europe"], detour: null, expedited: false },
  "zhengzhou-2022": { blocked: [], detour: null, expedited: false },
};
for (const [id, exp] of Object.entries(expectations)) {
  const r = await open(`/?scenario=${id}`, true);
  const blocked = Object.entries(r.routes).filter(([, s]) => s === "blocked").map(([k]) => k).sort();
  const detour = Object.entries(r.routes).find(([, s]) => s === "detour")?.[0] ?? null;
  const expedited = Object.values(r.routes).includes("expedited");
  const text = await r.page.innerText(".map-overlay");
  const pass =
    JSON.stringify(blocked) === JSON.stringify([...exp.blocked].sort()) &&
    detour === exp.detour &&
    expedited === exp.expedited &&
    (!exp.queuePill || text.includes(exp.queuePill)) &&
    (!exp.detour || text.includes("DETOUR AROUND AFRICA")) &&
    r.errors.length === 0;
  check(id, pass, `blocked ${JSON.stringify(blocked)}, detour ${detour}, expedited ${expedited}, errors ${r.errors.length}`);
  if (id === "suez-2021") await r.page.screenshot({ path: `${process.env.TEMP}/ripple-shots/lanes-suez.png` });
  await r.context.close();
}

await browser.close();
console.log(ok ? "OK" : "FAIL");
process.exit(ok ? 0 : 1);

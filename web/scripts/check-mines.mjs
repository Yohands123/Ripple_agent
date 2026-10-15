// Verifies the tier 1, 2 and 7 layers on the data the app loads:
// - mines and refineries use their own symbols in tier 1 sandstone and tier 2 orange, cluster
//   at world zoom, and carry no labels there;
// - repair sites and return routes are pink, return routes dashed and flowing, behind a
//   "Returns" layer switch that is off by default (and still under reduced motion);
// - a battery maker traces upstream through refineries to mining regions, and a sales region
//   shows its return routes;
// - the cobalt scenario is in the picker and its ripple and panel work.
// Parts whose data the export lacks are reported as skipped.
// Usage: node scripts/check-mines.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const data = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data");
const root = existsSync(resolve(data, "real", "network.json")) ? "real" : "fixtures";
const read = (f) => JSON.parse(readFileSync(resolve(data, root, f), "utf8"));
const network = read("network.json");
const index = existsSync(resolve(data, root, "scenarios", "index.json")) ? read("scenarios/index.json") : [];
const byId = new Map(network.nodes.map((n) => [n.id, n]));
const supply = network.edges.filter((e) => e.relation === "supply");
const returns = network.edges.filter((e) => e.purpose === "return");
const mines = network.nodes.filter((n) => n.kind === "mine");
const refineries = network.nodes.filter((n) => n.kind === "refinery");
const repairs = network.nodes.filter((n) => n.kind === "repair");
// The battery maker with the most refinery links.
const refineryLinks = (id) => supply.filter((e) => e.to === id && byId.get(e.from)?.kind === "refinery").length;
const battery = network.nodes
  .filter((n) => n.kind.startsWith("supplier") && /batter/i.test(n.partType ?? ""))
  .sort((a, b) => refineryLinks(b.id) - refineryLinks(a.id))[0];
const salesWithReturns = network.nodes.find((n) => n.kind === "sales_region" && returns.some((e) => e.from === n.id));
const cobalt = index.find((s) => /cobalt/i.test(s.id));

const SANDSTONE = "#c79a6b";
const ORANGE = "#e8662f";
const PINK = "#f08cc0";

const browser = await chromium.launch();
const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};
const skip = (name, why) => console.log(`${name}: SKIPPED (${why})`);
const errors = [];
const open = async (path, opts = {}) => {
  const page = await browser.newPage({ viewport: { width: 1840, height: 810 }, ...opts });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}${path}`);
  await page.waitForSelector("[data-ready='true']", { timeout: 20000 });
  await page.waitForTimeout(800);
  return page;
};

// ---------- Mines and refineries ----------
if (mines.length && refineries.length) {
  const page = await open("/");
  // World zoom: refineries gather into clusters; no mine or refinery labels.
  const drawn = await page.locator("[data-kind='refinery']").count();
  const orange = await page.locator(".cluster[data-tier='2']").count();
  check("refineries cluster at world zoom", drawn < refineries.length && orange > 0, `${drawn} of ${refineries.length} drawn singly, ${orange} tier-2 clusters`);
  const mineNames = new Set(mines.map((m) => m.name.trim().toUpperCase()));
  const labels = await page.locator(".map-overlay .pill").allInnerTexts();
  const mineLabels = labels.filter((t) => mineNames.has(t.trim().toUpperCase()));
  check("no mining-region labels at world zoom", mineLabels.length === 0, mineLabels.slice(0, 3).join(", ") || "none");
  const stop = await page.locator("[data-kind='mine'] radialGradient stop").first().getAttribute("stop-color");
  check("mines are soft region markers in tier 1 sandstone", stop?.toLowerCase() === SANDSTONE, `gradient ${stop}`);
  // Zoomed into a country nothing is clustered: refinery symbols in tier 2 orange.
  const r = refineries[0];
  await page.evaluate(([lon, lat]) => window.__rippleGoTo?.(lon, lat, 6), [r.lon, r.lat]);
  await page.waitForTimeout(800);
  const fill = await page.locator("[data-kind='refinery'] rect").first().getAttribute("fill");
  check("refineries in tier 2 orange", fill?.toLowerCase() === ORANGE, `fill ${fill}`);
  const key = ["Mining region", "Refinery", "Repair and recycling", "Return route"];
  const inKey = await Promise.all(key.map((t) => page.locator(".key-item", { hasText: t }).count()));
  check("map key lists the new layers", inKey.every((n) => n === 1), key.map((t, i) => `${t} ${inKey[i]}`).join(", "));
  await page.close();
} else skip("mines and refineries", "none in the export");

// ---------- Repair sites and return routes ----------
if (repairs.length && returns.length) {
  const page = await open("/");
  const toggle = page.locator("[data-layer-toggle='returns']");
  check("Returns switch off by default", (await toggle.count()) === 1 && !(await toggle.isChecked()), "");
  const before = [await page.locator("[data-return]").count(), await page.locator("[data-kind='repair']").count()];
  check("returns hidden by default", before[0] === 0 && before[1] === 0, `${before[0]} routes, ${before[1]} repair sites`);
  await toggle.check();
  await page.waitForTimeout(500);
  const lines = await page.locator("[data-return]").evaluateAll((els) =>
    els.map((e) => ({ stroke: e.getAttribute("stroke"), dash: e.getAttribute("stroke-dasharray"), anim: getComputedStyle(e).animationName })),
  );
  check("all return routes drawn", lines.length === returns.length, `${lines.length} of ${returns.length}`);
  check("return routes pink, dashed and flowing", lines.every((l) => l.stroke?.toLowerCase() === PINK && l.dash && l.anim === "return-flow"), JSON.stringify(lines[0]));
  const backward = returns.every((e) => ["sales_region", "repair"].includes(byId.get(e.from)?.kind) && ["repair", "refinery"].includes(byId.get(e.to)?.kind));
  check("return routes run backward: sales to repair, recovered metals to refineries", backward, `${returns.length} routes`);
  const repairFill = await page.locator("[data-kind='repair'] circle").first().getAttribute("fill");
  check("repair sites pink", repairFill?.toLowerCase() === PINK, `${await page.locator("[data-kind='repair']").count()} sites, fill ${repairFill}`);
  await page.close();
  const still = await open("/", { reducedMotion: "reduce" });
  await still.locator("[data-layer-toggle='returns']").check();
  await still.waitForTimeout(300);
  const anim = await still.locator("[data-return]").first().evaluate((e) => getComputedStyle(e).animationName);
  check("return routes still under reduced motion", anim === "none", `animation ${anim}`);
  await still.close();
} else skip("returns", "no repair sites or return routes in the export");

// ---------- Trace ----------
if (battery && refineryLinks(battery.id) > 0) {
  const page = await open(`/?node=${battery.id}&stack=0`);
  const kinds = await page.locator("[data-traced='upstream']").evaluateAll((els) => els.map((e) => e.getAttribute("data-kind") ?? "cluster"));
  const traced = await page.locator("[data-trace-line='upstream']").count();
  const upIds = await page.locator("[data-traced='upstream'][data-node-id]").evaluateAll((els) => els.map((e) => e.getAttribute("data-node-id")));
  // Refineries may sit in clusters at world zoom; the trace lines reach them either way.
  const reachesMine = supply.some((e) => byId.get(e.from)?.kind === "mine" && supply.some((f) => f.from === e.to && f.to === battery.id));
  check(
    "battery maker traces through refineries to mining regions",
    traced > 0 && reachesMine && kinds.includes("mine"),
    `${battery.name}: ${traced} upstream lines, ${upIds.length} traced sites (${[...new Set(kinds)].join(", ")})`,
  );
  await page.close();
} else skip("battery trace", "no battery maker with refinery links");
if (salesWithReturns) {
  const page = await open(`/?node=${salesWithReturns.id}&stack=0`);
  const lines = await page.locator("[data-trace-line='return']").count();
  const chain = (await page.locator("[data-section='connections'] .chain").innerText()).replace(/\s+/g, " ");
  check("sales region shows its return routes", lines > 0 && /repair or recycling/.test(chain), `${lines} return lines; ${chain}`);
  await page.close();
} else skip("sales region returns", "no return routes from a sales region");

// ---------- Cobalt scenario ----------
if (cobalt) {
  const page = await open("/");
  const options = await page.locator(".scenario-picker option, select option").allInnerTexts();
  check("cobalt scenario in the picker", options.some((t) => /cobalt/i.test(t)), options.find((t) => /cobalt/i.test(t)) ?? "missing");
  await page.close();
  const ev = await open(`/?scenario=${cobalt.id}`);
  await ev.waitForTimeout(1500);
  const hops = (await ev.locator("text=/Hop 1:/").first().innerText().catch(() => "")).replace(/\s+/g, " ");
  const waves = await ev.locator("[data-layer='ripple'] path").count();
  const zone = await ev.locator(".shock-zone").count();
  check("cobalt ripple runs", waves > 0 && zone > 0 && /Hop 1: [1-9]/.test(hops), `${zone} shock zone, ${waves} waves, "${hops}"`);
  const panel = (await ev.locator(".panel, aside").first().innerText()).replace(/\s+/g, " ");
  check("cobalt dashboard explains it has no predictions", /cobalt/i.test(panel) && /No prediction/i.test(panel), panel.slice(0, 120));
  await ev.close();
} else skip("cobalt scenario", "not in the export");

check("no page errors", errors.length === 0, errors.join("; ") || "none");
await browser.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "all checks passed");
process.exit(failed ? 1 : 0);

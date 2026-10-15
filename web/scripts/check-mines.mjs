// Verifies mines and refineries: their own symbols in tier 1 and tier 2 colors, mines drawn
// as soft region markers, both in the map key, and (once the trace exists) a battery maker
// tracing upstream to its refinery and mining region.
// The test network is the real one plus test-only mines, refineries, and supply links,
// injected here because the export does not have them yet. Nothing is written to disk.
// Usage: node scripts/check-mines.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const data = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data");
const root = existsSync(resolve(data, "real", "network.json")) ? "real" : "fixtures";
const network = JSON.parse(readFileSync(resolve(data, root, "network.json"), "utf8"));
const json = (body) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

const battery = network.nodes.find((n) => /batter/i.test(n.partType ?? "")) ?? network.nodes.find((n) => n.kind.startsWith("supplier"));
const src = [{ title: "Test only", url: "https://example.org" }];
const node = (id, name, kind, tier, lon, lat, region) => ({
  id, name, kind, tier, lon, lat, precision: "province", region, ticker: null, partType: null, appleRevenueShare: null, sources: src, layer: "supplier",
});
network.nodes.push(
  node("test-mine-katanga", "Katanga copper and cobalt belt", "mine", 1, 26.5, -11.0, "Katanga, DR Congo"),
  node("test-mine-jinchuan", "Jinchuan nickel district", "mine", 1, 102.2, 38.5, "Gansu, China"),
  node("test-refinery-ganzhou", "Test cobalt refinery", "refinery", 2, 114.9, 25.8, "Jiangxi, China"),
);
const supply = (id, from, to) => ({ id, from, to, mode: "road", carriesTier: null, status: "inferred", relation: "supply", sources: src });
network.edges.push(
  supply("test-supply-1", "test-mine-katanga", "test-refinery-ganzhou"),
  supply("test-supply-2", "test-mine-jinchuan", "test-refinery-ganzhou"),
  supply("test-supply-3", "test-refinery-ganzhou", battery.id),
);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1840, height: 810 } });
await context.route(`**/data/${root}/network.json`, (r) => r.fulfill(json(network)));
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};

await page.goto(base);
await page.waitForSelector("[data-ready='true']");
await page.evaluate(() => window.__rippleGoTo?.(70, 10, 0.5));
await page.waitForTimeout(800);

if (process.env.TEMP) await page.screenshot({ path: `${process.env.TEMP}/ripple-shots/mines.png` });
const mine = page.locator("[data-node-id='test-mine-katanga']");
check("mine drawn", (await mine.count()) === 1, "Katanga marker");
const mineSvg = await mine.locator("radialGradient stop").first().getAttribute("stop-color");
check("mine is a soft region marker in tier 1 sandstone", mineSvg?.toLowerCase() === "#c79a6b", `gradient ${mineSvg}`);
const refinery = page.locator("[data-node-id='test-refinery-ganzhou']");
const refFill = await refinery.locator("rect").first().getAttribute("fill");
check("refinery drawn in tier 2 orange", refFill?.toLowerCase() === "#e8662f", `fill ${refFill}`);
check("map key lists mining regions and refineries", (await page.locator(".key-item", { hasText: "Mining region" }).count()) === 1 && (await page.locator(".key-item", { hasText: "Refinery" }).count()) === 1, "");

// The trace (when present): a battery maker traces upstream to the refinery and mining regions.
if (battery) {
  await page.evaluate(([lon, lat]) => window.__rippleGoTo?.(lon, lat, 6), [battery.lon, battery.lat]);
  await page.waitForTimeout(600);
  const target = page.locator(`[data-node-id='${battery.id}']`);
  if ((await target.count()) === 1) {
    await target.click({ force: true });
    await page.waitForTimeout(600);
    const traced = await page.locator("[data-traced='upstream']").evaluateAll((els) => els.map((e) => e.getAttribute("data-node-id")));
    if (traced.length || (await page.locator("[data-trace]").count())) {
      const ok = ["test-refinery-ganzhou", "test-mine-katanga", "test-mine-jinchuan"].every((id) => traced.includes(id));
      check("battery maker traces upstream to refinery and mines", ok, `upstream: ${traced.join(", ") || "none"}`);
    } else {
      console.log("trace not built yet: skipped");
    }
  }
}

check("no page errors", errors.length === 0, errors.join("; ") || "none");
await browser.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "all checks passed");
process.exit(failed ? 1 : 0);

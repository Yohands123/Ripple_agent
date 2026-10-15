// Verifies the interaction trace: clicking a factory highlights its suppliers upstream and its
// path downstream, dims the rest, sends pulses upstream first, lists a clickable Connections
// chain, and shows no pulses under reduced motion.
// Usage: node scripts/check-trace.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3000";
const data = resolve(dirname(fileURLToPath(import.meta.url)), "..", "public", "data");
const root = existsSync(resolve(data, "real", "network.json")) ? "real" : "fixtures";
const network = JSON.parse(readFileSync(resolve(data, root, "network.json"), "utf8"));
const factory = network.nodes.find((n) => /zhengzhou/i.test(n.id) && n.kind === "assembly") ?? network.nodes.find((n) => n.kind === "assembly");

const browser = await chromium.launch();
const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};

for (const reduced of [false, true]) {
  const page = await browser.newPage({ viewport: { width: 1840, height: 900 }, reducedMotion: reduced ? "reduce" : "no-preference" });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/?node=${factory.id}&stack=0`);
  await page.waitForSelector("[data-ready='true']");
  await page.waitForTimeout(800);
  const tag = reduced ? "reduced motion" : "motion";

  const tracing = await page.locator(".map-area.tracing").count();
  const self = await page.locator(`[data-node-id='${factory.id}'][data-traced='self']`).count();
  const lines = await page.locator("[data-trace-line]").count();
  const pulses = await page.locator("[data-pulse]").count();
  check(`${tag}: trace drawn`, tracing === 1 && self === 1 && lines > 0, `${lines} traced lines, root marked ${self === 1}`);
  if (!reduced) {
    check("pulses travel the trace", pulses > 0, `${pulses} pulses`);
    // Upstream pulses start before downstream ones.
    const starts = await page.locator("[data-pulse] animateMotion").evaluateAll((els) =>
      els.map((e) => ({ kind: e.parentElement.getAttribute("data-pulse"), t0: Number(e.getAttribute("keyTimes").split(";")[1]) })),
    );
    const up = starts.filter((s) => s.kind === "upstream").map((s) => s.t0);
    const down = starts.filter((s) => s.kind === "downstream").map((s) => s.t0);
    const ordered = up.length === 0 || down.length === 0 || Math.max(...up) < Math.min(...down);
    check("upstream pulses before downstream", ordered, `upstream from ${Math.min(...up).toFixed(2)}, downstream from ${Math.min(...down).toFixed(2)} of the cycle`);
  } else {
    check("no pulses under reduced motion", pulses === 0, `${pulses} pulses`);
  }
  // Everything off the trace dims to about 15%.
  const dim = await page.locator(".node:not([data-traced])").first().evaluate((e) => getComputedStyle(e).opacity);
  check(`${tag}: rest dimmed`, Math.abs(Number(dim) - 0.15) < 0.02, `opacity ${dim}`);

  if (!reduced) {
    const chain = (await page.locator("[data-section='connections'] .chain").innerText()).replace(/\s+/g, " ");
    check("connections chain", /suppliers?.*→.*this factory.*→.*(ports|port).*→.*sales region/i.test(chain), chain);
    const before = await page.getAttribute(".map-stage", "data-view");
    const gw = page.locator("[data-chain='gateways']");
    if (!(await gw.isDisabled())) {
      await gw.click();
      await page.waitForTimeout(300);
      const after = await page.getAttribute(".map-stage", "data-view");
      check("chain links move the map", before !== after, `${before} → ${after}`);
    }
    await page.screenshot({ path: `${process.env.TEMP ?? "."}/ripple-shots/trace.png` });
  }
  check(`${tag}: no page errors`, errors.length === 0, errors.join("; ") || "none");
  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "all checks passed");
process.exit(failed ? 1 : 0);

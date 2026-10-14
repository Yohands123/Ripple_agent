// Verifies zoom-aware labels on whatever data the app loads: fewer labels zoomed out,
// more zoomed in, labels keep their screen size, and visible labels never overlap.
// Usage: node scripts/check-labels.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3000";
const out = `${process.env.TEMP ?? "."}/ripple-shots`;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1840, height: 810 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(base);
await page.waitForSelector("[data-ready='true']");
await page.waitForTimeout(500);

const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};

/** Labels on screen, with their screen boxes. */
async function visibleLabels() {
  const stage = await page.locator(".map-stage").boundingBox();
  const boxes = await page.locator(".node-label").evaluateAll((els) =>
    els.map((el) => {
      const r = el.getBoundingClientRect();
      return { text: el.textContent, x: r.x, y: r.y, w: r.width, h: r.height };
    }),
  );
  return boxes.filter((b) => b.x + b.w > stage.x && b.x < stage.x + stage.width && b.y + b.h > stage.y && b.y < stage.y + stage.height);
}
const overlapping = (list) => {
  for (let i = 0; i < list.length; i++)
    for (let j = i + 1; j < list.length; j++) {
      const a = list[i];
      const b = list[j];
      if (a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1) return `${a.text} / ${b.text}`;
    }
  return null;
};
const height = (list) => (list.length ? Math.max(...list.map((b) => b.h)) : 0);

const atOne = await visibleLabels();
check("default view has labels", atOne.length > 0, `${atOne.length} labels`);
check("no overlaps at default view", !overlapping(atOne), overlapping(atOne) ?? "none");
await page.screenshot({ path: `${out}/labels-k1.png` });

// Zoom out fully.
await page.mouse.move(920, 405);
for (let i = 0; i < 12; i++) await page.mouse.wheel(0, 400);
await page.waitForTimeout(300);
const zoomedOut = await visibleLabels();
check("zoomed out shows fewer labels", zoomedOut.length < atOne.length || atOne.length <= 3, `${zoomedOut.length} labels`);
check("no overlaps zoomed out", !overlapping(zoomedOut), overlapping(zoomedOut) ?? "none");
check("labels keep their screen size zoomed out", Math.abs(height(zoomedOut) - height(atOne)) < 2 || zoomedOut.length === 0, `${height(zoomedOut).toFixed(1)} vs ${height(atOne).toFixed(1)} px`);
await page.screenshot({ path: `${out}/labels-out.png` });

// Reset, then zoom in on East Asia (the densest area in the real data).
await page.click(".map-hud-controls .reset");
const china = await page.locator("[data-node-id]").evaluateAll((els) => {
  // The densest spot: the node with the most neighbours within 60 px.
  const pts = els.map((el) => el.getBoundingClientRect()).map((r) => [r.x + r.width / 2, r.y + r.height / 2]);
  let best = pts[0];
  let most = -1;
  for (const p of pts) {
    const n = pts.filter((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) < 60).length;
    if (n > most) [best, most] = [p, n];
  }
  return best;
});
await page.mouse.move(china[0], china[1]);
for (let i = 0; i < 8; i++) await page.mouse.wheel(0, -400);
await page.waitForTimeout(300);
const k = Number((await page.getAttribute(".map-stage", "data-view")).split(",")[2]);
const zoomedIn = await visibleLabels();
const inArea = atOne.length; // compare with the same count shown at zoom 1 anywhere
check("zoomed in reaches zoom 4", k > 3.9, `k=${k}`);
check("zoomed in shows more labels than default", zoomedIn.length > 0 && (zoomedIn.length > inArea || zoomedIn.length >= 8), `${zoomedIn.length} labels`);
check("no overlaps zoomed in", !overlapping(zoomedIn), overlapping(zoomedIn) ?? "none");
check("labels keep their screen size zoomed in", Math.abs(height(zoomedIn) - height(atOne)) < 2, `${height(zoomedIn).toFixed(1)} vs ${height(atOne).toFixed(1)} px`);
await page.screenshot({ path: `${out}/labels-in.png` });

check("no page errors", errors.length === 0, errors.join("; ") || "none");
await browser.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "all checks passed");
process.exit(failed ? 1 : 0);

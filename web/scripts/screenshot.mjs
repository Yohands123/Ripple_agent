// Screenshots the app and the concept-art references at 1840 × 810, plus a
// side-by-side comparison image for each pair.
//
// Usage: node scripts/screenshot.mjs [--base http://localhost:3000] [--out parity] [--reduced] [--fixtures]
// --fixtures hides /data/real/ from the browser so the app shows the fixture data the references were drawn from.
// The app must already be running (npm run build && npm start).

import { chromium } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
};
const base = arg("--base", "http://localhost:3000");
const out = resolve(arg("--out", resolve(here, "..", "parity")));
const reduced = args.includes("--reduced");
const fixturesOnly = args.includes("--fixtures");
const refDir = resolve(here, "..", "..", "design", "reference");

const pairs = [
  { name: "free-flow", app: `${base}/`, ref: resolve(refDir, "free-flow.html") },
  { name: "suez-blocked", app: `${base}/?scenario=suez-2021`, ref: resolve(refDir, "suez-blocked.html") },
];

mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1840, height: 810 },
  reducedMotion: reduced ? "reduce" : "no-preference",
});
if (fixturesOnly) await context.route("**/data/real/**", (r) => r.fulfill({ status: 404, body: "" }));
const page = await context.newPage();

for (const p of pairs) {
  await page.goto(p.ref);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: resolve(out, `${p.name}.reference.png`) });

  await page.goto(p.app);
  await page.waitForSelector("[data-ready='true']", { timeout: 20000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(2200);
  await page.screenshot({ path: resolve(out, `${p.name}.app.png`) });

  const img = (f) => `data:image/png;base64,${readFileSync(resolve(out, f)).toString("base64")}`;
  const cmp = await context.newPage();
  await cmp.setViewportSize({ width: 1840, height: 1700 });
  await cmp.setContent(`<body style="margin:0;background:#000;color:#fff;font:14px sans-serif">
    <div style="padding:4px 8px">Reference: design/reference/${p.name}.html</div><img src="${img(`${p.name}.reference.png`)}" style="display:block">
    <div style="padding:4px 8px">App: ${p.app}</div><img src="${img(`${p.name}.app.png`)}" style="display:block"></body>`);
  await cmp.screenshot({ path: resolve(out, `${p.name}.side-by-side.png`), fullPage: true });
  await cmp.close();
  console.log(`saved ${p.name}`);
}

await browser.close();

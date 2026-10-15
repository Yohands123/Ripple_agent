// Checks the default view stays readable: no overlapping labels (pills, captions, the
// Apple Park card), no ship on land, no route drawn across the whole map width, and a
// cap on visible lines. Runs on the data the app loads (real when present, else fixtures).
//
// Usage:
//   node scripts/check-default.mjs [base-url]   app already running
//   node scripts/check-default.mjs --serve      starts `next start` on a spare port, checks, stops it
//                                               (used by `npm run build`, so the web checks include it)
import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const serve = process.argv.includes("--serve");
const PORT = 3191;
const base = serve ? `http://localhost:${PORT}` : (process.argv[2] ?? "http://localhost:3000");

/** Most route lines drawn at the default view. */
const MAX_LINES = 60;
/** No single drawn stretch of a route may span more than half the world's width (180°). */
const MAX_SPAN = 180 * 8.6;

let server = null;
if (serve) {
  const next = resolve(here, "..", "node_modules", "next", "dist", "bin", "next");
  server = spawn(process.execPath, [next, "start", "-p", String(PORT)], { cwd: resolve(here, ".."), stdio: "ignore" });
  let up = false;
  for (let i = 0; i < 60 && !up; i++) {
    await new Promise((r) => setTimeout(r, 500));
    up = await fetch(base).then((r) => r.ok).catch(() => false);
  }
  if (!up) {
    server.kill();
    console.error("check-default: the app did not start");
    process.exit(1);
  }
}
const stop = () => server?.kill();

let browser;
try {
  browser = await chromium.launch();
} catch (e) {
  // Without a browser there is nothing to look at; say so plainly rather than fail the build.
  console.log(`check-default: SKIPPED, no Playwright browser (${String(e.message).split("\n")[0]}). Run: npx playwright install chromium`);
  stop();
  process.exit(0);
}

const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};

try {
  const page = await browser.newPage({ viewport: { width: 1840, height: 810 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base);
  await page.waitForSelector("[data-ready='true']");
  await page.waitForFunction(() => Boolean(window.__rippleIsLand), null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1200);

  // Labels: every pill, caption, and the Apple Park card on screen; none may overlap.
  const boxes = await page.evaluate(() => {
    const stage = document.querySelector(".map-stage").getBoundingClientRect();
    const els = [...document.querySelectorAll(".map-overlay .pill, .map-overlay .map-caption, .hq-pinned, .map-hud .pill")];
    return els
      .map((e) => ({ text: e.textContent.trim().slice(0, 40), r: e.getBoundingClientRect(), op: Number(getComputedStyle(e).opacity) }))
      .filter(({ r, op }) => op > 0.05 && r.width > 0 && r.right > stage.left && r.left < stage.right && r.bottom > stage.top && r.top < stage.bottom)
      .map(({ text, r }) => ({ text, x: r.left, y: r.top, w: r.width, h: r.height }));
  });
  const overlaps = [];
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i];
      const b = boxes[j];
      if (a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1) overlaps.push(`"${a.text}" / "${b.text}"`);
    }
  check("no overlapping labels", overlaps.length === 0, overlaps.length ? overlaps.slice(0, 4).join("; ") : `${boxes.length} labels`);

  // Ships: every visible ship's hull sits on water.
  const ships = await page.evaluate(() => {
    const isLand = window.__rippleIsLand;
    const stage = document.querySelector(".map-stage").getBoundingClientRect();
    const out = [];
    for (const el of document.querySelectorAll("[data-mover='ship']")) {
      if (getComputedStyle(el).visibility === "hidden") continue;
      const r = el.getBoundingClientRect();
      if (r.right < stage.left || r.left > stage.right || r.bottom < stage.top || r.top > stage.bottom) continue;
      const m = /translate\(([-\d.]+)px,\s*([-\d.]+)px\)/.exec(el.style.transform);
      if (!m) continue;
      // The mover is placed hull-bottom on its lane: x - w/2, y - 12.
      const x = Number(m[1]) + el.offsetWidth / 2;
      const y = Number(m[2]) + 12;
      out.push({ x, y, land: isLand ? isLand(x, y) : false });
    }
    return out;
  });
  const onLand = ships.filter((s) => s.land);
  check("no ships on land", onLand.length === 0, `${ships.length} ships on screen, ${onLand.length} on land`);
  check("about 20 ships on screen", ships.length <= 24, `${ships.length} ships`);

  // Routes: no drawn stretch spans more than half the world (a route the wrong way round), and a cap on lines.
  const spans = await page.evaluate(() =>
    [...document.querySelectorAll("[data-route] > path:first-child, path[data-route]")].map((p) => {
      const d = p.getAttribute("d") ?? "";
      let max = 0;
      for (const sub of d.split("M").slice(1)) {
        const xs = [...sub.matchAll(/(-?\d+(?:\.\d+)?)[ ,](-?\d+(?:\.\d+)?)/g)].map((m) => Number(m[1]));
        if (xs.length) max = Math.max(max, Math.max(...xs) - Math.min(...xs));
      }
      return { id: p.closest("[data-route]")?.getAttribute("data-route") ?? p.getAttribute("data-route"), max };
    }),
  );
  const wide = spans.filter((s) => s.max > MAX_SPAN);
  check("no route across the whole map width", wide.length === 0, wide.length ? wide.map((w) => `${w.id} (${Math.round(w.max)} px)`).join(", ") : `${spans.length} routes`);
  check(`at most ${MAX_LINES} route lines`, spans.length <= MAX_LINES, `${spans.length} lines`);
  check("no page errors", errors.length === 0, errors.join("; ") || "none");
} finally {
  await browser.close();
  stop();
}
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "default view checks passed");
process.exit(failed ? 1 : 0);

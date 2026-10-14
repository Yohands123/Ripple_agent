// Verifies ships and coins move, and stay fixed under prefers-reduced-motion.
// Usage: node scripts/check-motion.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { fixturesContext } from "./fixtures-only.mjs";

const base = process.argv[2] ?? "http://localhost:3000";
const browser = await chromium.launch();
let failed = false;
for (const reducedMotion of ["no-preference", "reduce"]) {
  const page = await (await fixturesContext(browser, { viewport: { width: 1840, height: 810 }, reducedMotion })).newPage();
  await page.goto(base);
  await page.waitForSelector("[data-ready='true']");
  const snap = () => page.$$eval("[data-mover]", (els) => els.map((e) => e.style.transform));
  const a = await snap();
  await page.waitForTimeout(1500);
  const b = await snap();
  const moved = a.filter((t, i) => t !== b[i]).length;
  const ok = reducedMotion === "reduce" ? moved === 0 : moved === a.length && a.length > 0;
  if (!ok) failed = true;
  console.log(`${reducedMotion}: ${moved} of ${a.length} movers changed position -> ${ok ? "OK" : "FAIL"}`);
}
await browser.close();
process.exit(failed ? 1 : 0);

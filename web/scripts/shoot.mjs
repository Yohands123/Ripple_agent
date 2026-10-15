// Quick screenshots of named views, for checking work by eye.
// Usage: node scripts/shoot.mjs <out-dir> <name>=<query>[@<lon>,<lat>,<zoom>] ...
//   e.g. node scripts/shoot.mjs shots default= world=@60,20,0.4 suez=?scenario=suez-2021
// The view is set with the map's keyboard and wheel controls, so it matches what a viewer sees.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const [out = "shots", ...specs] = process.argv.slice(2);
const base = process.env.BASE ?? "http://localhost:3000";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1840, height: 810 } });
page.on("pageerror", (e) => console.log("page error:", e.message));
for (const spec of specs) {
  const cut = spec.indexOf("=");
  const name = spec.slice(0, cut);
  const rest = spec.slice(cut + 1);
  const [query, view] = rest.split("@");
  await page.goto(`${base}/${query}`);
  await page.waitForSelector("[data-ready='true']");
  if (view) {
    const [lon, lat, k] = view.split(",").map(Number);
    await page.evaluate(([lon, lat, k]) => window.__rippleGoTo?.(lon, lat, k), [lon, lat, k]);
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log("saved", name);
}
await browser.close();

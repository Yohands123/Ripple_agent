// Verifies pan and zoom: the map opens on the concept-art view, zooms out to every
// continent, pans by dragging, still selects nodes on a plain click, and resets.
// Usage: node scripts/check-panzoom.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { fixturesContext } from "./fixtures-only.mjs";

const base = process.argv[2] ?? "http://localhost:3000";
const browser = await chromium.launch();
const page = await (await fixturesContext(browser, { viewport: { width: 1840, height: 810 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(base);
await page.waitForSelector("[data-ready='true']");

const view = async () => (await page.getAttribute(".map-stage", "data-view")).split(",").map(Number);
const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};

const v0 = await view();
check("opens on concept view", v0[0] === 720 && v0[1] === 405 && v0[2] === 1, JSON.stringify(v0));

// Pinned Apple Park card shows while Cupertino is off screen.
check("pinned Apple Park card", (await page.locator(".hq-pinned").count()) === 1, "visible at default view");

// Zoom all the way out with the wheel.
await page.mouse.move(720, 405);
for (let i = 0; i < 12; i++) await page.mouse.wheel(0, 400);
await page.waitForTimeout(200);
const v1 = await view();
check("wheel zooms out", v1[2] < 0.75, JSON.stringify(v1));

// Drag east to reach the Americas: Cupertino's card on the map becomes visible, the pinned one goes.
await page.mouse.move(400, 400);
await page.mouse.down();
await page.mouse.move(900, 420, { steps: 10 });
await page.mouse.move(1400, 420, { steps: 10 });
await page.mouse.up();
await page.waitForTimeout(200);
const v2 = await view();
const realCard = await page.locator("[data-hq='real']").boundingBox();
const onScreen = realCard && realCard.x > 0 && realCard.x < 1440 && realCard.y > 0 && realCard.y < 810;
check("drag pans west to the Americas", v2[0] < v1[0] && onScreen, `view ${JSON.stringify(v2)}, Apple Park card at ${realCard ? `${Math.round(realCard.x)},${Math.round(realCard.y)}` : "none"}`);
check("pinned card hides when Apple Park is in view", (await page.locator(".hq-pinned").count()) === 0, "");
check("drag did not select a node", (await page.locator(".shap-row, .facts").count()) === 0, "");
await page.screenshot({ path: `${process.env.TEMP}/ripple-shots/zoomed-out.png` });

// Reset, then a plain click still opens a node.
await page.click(".map-hud-controls .reset");
const v3 = await view();
check("reset view", v3[0] === 720 && v3[1] === 405 && v3[2] === 1, JSON.stringify(v3));
await page.click("[data-node-id='supplier-taiwan']");
check("plain click selects a node", (await page.locator(".facts").count()) === 1, "");

// Buttons zoom in.
await page.keyboard.press("Escape");
await page.click(".map-hud-controls button[aria-label='Zoom in']");
const v4 = await view();
check("zoom-in button", v4[2] > 1, JSON.stringify(v4));

check("no page errors", errors.length === 0, errors.join("; ") || "none");
await browser.close();
const ok = results.every(Boolean);
console.log(ok ? "OK" : "FAIL");
process.exit(ok ? 0 : 1);

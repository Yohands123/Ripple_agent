// Verifies that toggling "What can be shifted" options changes the with-plan line.
// Usage: node scripts/check-panel.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";
import { fixturesContext } from "./fixtures-only.mjs";

const base = process.argv[2] ?? "http://localhost:3000";
const browser = await chromium.launch();
const page = await (await fixturesContext(browser, { viewport: { width: 1840, height: 810 } })).newPage();
await page.goto(`${base}/?scenario=suez-2021`);
await page.waitForSelector("[data-ready='true']");
const line = () => page.getAttribute("[data-line='with-plan']", "d");
const sentence = () => page.innerText(".recovery");
const states = [];
states.push(["default plan", await line(), await sentence()]);
await page.uncheck("#opt-air");
states.push(["without air", await line(), await sentence()]);
for (const id of await page.$$eval(".option-row input:checked", (els) => els.map((e) => e.id))) await page.uncheck(`#${id}`);
states.push(["no options", await line(), await sentence()]);
await page.check("#opt-detour-cape");
await page.check("#opt-air");
await page.check("#opt-inventory");
states.push(["defaults again", await line(), await sentence()]);
for (const [name, d, s] of states) console.log(`${name.padEnd(15)} ${s.padEnd(34)} ${d}`);
const ok = states[0][1] !== states[1][1] && states[1][1] !== states[2][1] && states[0][1] === states[3][1];
console.log(ok ? "OK" : "FAIL");
await browser.close();
process.exit(ok ? 0 : 1);

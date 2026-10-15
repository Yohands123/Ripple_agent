// Verifies the disruption ripple: when Suez drops, closed routes turn red, waves reach
// suppliers hop by hop (hop 1 at 0.5 s), suppliers fill with risk color, the panel shows
// "Hop 1: N suppliers, Hop 2: N suppliers", and reduced motion shows only the final state.
// Usage: node scripts/check-ripple.mjs [base-url]   (app must be running)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3000";
const browser = await chromium.launch();
const results = [];
const check = (name, ok, detail) => {
  results.push(ok);
  console.log(`${name}: ${detail} -> ${ok ? "OK" : "FAIL"}`);
};

async function drop(reduced) {
  const page = await browser.newPage({ viewport: { width: 1840, height: 810 }, reducedMotion: reduced ? "reduce" : "no-preference" });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base);
  await page.waitForSelector("[data-ready='true']");
  const picker = page.locator("select");
  if (await picker.count()) await picker.first().selectOption({ label: "Suez Canal blocked (2021)" }).catch(() => {});
  await page.waitForTimeout(400);
  await page.click(".drop-button");
  return { page, errors };
}

// With motion.
{
  const { page, errors } = await drop(false);
  await page.waitForTimeout(450);
  const red = await page
    .locator("[data-state='blocked'] > path:first-child")
    .first()
    .evaluate((e) => getComputedStyle(e).stroke)
    .catch(() => "none");
  check("closed routes turn red", /214,\s*69,\s*61/.test(red), red);
  const waves = await page.locator(".ripple-wave").evaluateAll((els) => els.map((e) => ({ hop: e.getAttribute("data-hop"), delay: getComputedStyle(e).animationDelay })));
  const hop1 = waves.filter((w) => w.hop === "1");
  check("waves reach hop 1 at 0.5 s", hop1.length > 0 && hop1.every((w) => w.delay === "0.5s"), `${hop1.length} hop-1 waves, delay ${hop1[0]?.delay}`);
  const hop2 = waves.filter((w) => w.hop === "2");
  check("hop 2 (if any) at 1 s", hop2.every((w) => w.delay === "1s"), `${hop2.length} hop-2 waves`);
  await page.waitForTimeout(2200);
  const filled = await page.locator(".ripple").count();
  const hops = await page.locator(".hop-counts").innerText();
  check("suppliers fill with risk color", filled > 0, `${filled} sites or clusters filled`);
  check("hop counts in What's affected", /Hop 1: \d+ suppliers?/.test(hops) && /Hop 2: \d+ suppliers?/.test(hops), hops.replace(/\s+/g, " "));
  await page.screenshot({ path: `${process.env.TEMP ?? "."}/ripple-shots/ripple.png` });
  check("no page errors (motion)", errors.length === 0, errors.join("; ") || "none");
  await page.close();
}

// Reduced motion: the final state, no waves or animation.
{
  const { page, errors } = await drop(true);
  await page.waitForTimeout(300);
  const waves = await page.locator(".ripple-wave").count();
  const anim = await page.locator(".ripple").first().evaluate((e) => getComputedStyle(e).animationName).catch(() => "none");
  const filled = await page.locator(".ripple").count();
  check("reduced motion: final state at once", waves === 0 && anim === "none" && filled > 0, `${waves} waves, animation ${anim}, ${filled} filled`);
  check("no page errors (reduced)", errors.length === 0, errors.join("; ") || "none");
  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} check(s) failed` : "all checks passed");
process.exit(failed ? 1 : 0);

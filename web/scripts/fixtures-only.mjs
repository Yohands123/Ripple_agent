// Browser context that hides /data/real/ so checks run against the fixture data they were written for.
// Scripts can still answer specific /data/real/ files with their own routes: routes added later win.
export async function fixturesContext(browser, options) {
  const context = await browser.newContext(options);
  await context.route("**/data/real/**", (r) => r.fulfill({ status: 404, body: "" }));
  return context;
}

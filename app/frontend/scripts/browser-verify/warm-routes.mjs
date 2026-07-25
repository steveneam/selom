import { FE_ORIGIN } from "./paths.mjs";

/**
 * Compile the routes the checks drive, BEFORE the first check starts.
 *
 * `next dev` compiles per route on first request, and the harness runs against a dev server on
 * purpose (a production build would not surface the dev-only breakages this instrument exists to
 * catch). So the FIRST test of a cold run pays every route's compile inside its own 180s budget and
 * fails as a timeout — which reads as a defect in whatever check happened to be first. It has now
 * cost three false failures (`remedy-sizing` once, `D-8` twice), each in a different check, which is
 * the tell that the cost belongs to the harness rather than to any of them.
 *
 * Playwright's `webServer.url` only proves the server ANSWERS; it compiles nothing else. This runs as
 * `globalSetup`, after both servers are up and before the first test, so the compile is paid once,
 * outside any test's clock, and every check starts warm.
 *
 * Deliberately fail-soft: a route that 404s or is slow is not a reason to refuse to run the suite —
 * the checks themselves are the gate, and one of them failing honestly is far better than the whole
 * run refusing to start over a warm-up.
 */
const ROUTES = ["/", "/extract"];

export default async function warmRoutes() {
  const started = Date.now();
  const results = [];
  for (const route of ROUTES) {
    const t0 = Date.now();
    try {
      const res = await fetch(`${FE_ORIGIN}${route}`, { redirect: "follow" });
      results.push(`${route} → ${res.status} in ${Date.now() - t0}ms`);
    } catch (e) {
      results.push(`${route} → ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  console.log(
    `[browser-verify] warmed ${ROUTES.length} route(s) in ${Date.now() - started}ms — ` +
      `${results.join(", ")}`,
  );
}

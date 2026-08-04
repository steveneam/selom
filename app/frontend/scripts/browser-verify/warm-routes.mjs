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
/**
 * `/p/[id]` is the one that matters most and was missing until 2026-08-04 — every check navigates
 * to it (it IS the project workbench and the editor), it is the heaviest compile in the app, and
 * warming `/` and `/extract` alone left the first check of each run paying for it. That cost three
 * more false 180s timeouts in one session — `param-pickers` twice and `cloud-export`'s Drive leg
 * once, each dying at `getByLabel("Project name")` immediately after the navigation, with every
 * later check in the same run passing. Same tell as the three above: three different checks, one
 * shared cause.
 *
 * A dynamic segment compiles per PATTERN, not per param, so any id warms the route. The id below is
 * deliberately not a real one — the fetch only has to make Next compile the route, and the warm is
 * fail-soft, so the 404 this returns is the expected outcome rather than a problem.
 */
const ROUTES = ["/", "/extract", "/store", "/p/warm-the-route"];

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

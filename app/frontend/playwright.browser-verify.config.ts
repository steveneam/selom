import { defineConfig, devices } from "@playwright/test";

import {
  assertPreconditions,
  BE_ORIGIN,
  BE_PORT,
  chromiumExecutable,
  DATASETS_DIR,
  DB_DIR,
  DB_URL,
  FE_ORIGIN,
  FE_PORT,
  ANNOTATION_LAYER,
} from "./scripts/browser-verify/paths.mjs";

/**
 * BROWSER-VERIFY — the harness that lands a REAL figure in the editor.
 *
 * WHY THIS EXISTS. Every layout claim in the milestone review and the Lane 3 wrap is
 * "arithmetic-backed prediction from CSS that no browser ever observed". They cannot be settled by
 * tsc/eslint/vitest (none of which can see layout) nor by `dev:mock` (which proves the wire, not the
 * content). A previous session burned itself on four shortcuts to reach the editor — demo projects,
 * an API-created project, localStorage injection, a half-driven UI run — because the editor renders
 * only when the LIVE editor store holds a spec (`figure-view.tsx` branches on `figure.spec`, not on
 * the persisted record), and that store is seeded solely by `figure.init(spec)` from `openFigure` or
 * a COMPLETED RUN. So the only thing that opens the editor is a real run through the UI, and this
 * config exists so that is built once, properly, instead of re-improvised per session
 * [[step-back-build-helpers-when-stuck]] [[compound-capability-each-task]].
 *
 * This is deliberately SEPARATE from `playwright.config.ts` (the MSW-mock gesture suite on :3011).
 * That one is a fast unit-ish smoke; this one is the real-backend, real-data instrument. Different
 * servers, different ports, different purpose — merging them would make the fast one slow and the
 * real one skippable.
 *
 * Both servers are managed by Playwright's `webServer`, so they are started on demand and STOPPED on
 * exit (the handoff rule: kill everything you start). `reuseExistingServer` keeps an inner loop fast.
 *
 * Run it via `scripts/browser-verify.sh` — it supplies the env and prints what to export if missing.
 */
assertPreconditions();

export default defineConfig({
  testDir: "./e2e/browser-verify",
  // A real run = upload 2.4MB + inspect + skill execution + Plotly render, behind a cold `next dev`
  // compile on first hit. Generous on purpose: a timeout here reads as a fake failure.
  timeout: 180_000,
  expect: { timeout: 30_000 },
  // The checks share one backend + one editor flow, and several assert exact pixel geometry.
  // Parallel workers would fight over viewport-sensitive measurements.
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  reporter: [["list"], ["json", { outputFile: "test-results/browser-verify.json" }]],
  use: {
    baseURL: FE_ORIGIN,
    headless: true,
    // Each check sets its own viewport (D-5 wants 1280×800, 1440×900 and 1920×1080). Desktop only —
    // Selom has no mobile [[selom-desktop-only]].
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { executablePath: chromiumExecutable() },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Real backend. SQLite lives in the corpus dir, never the repo (owner-directed).
      command:
        `mkdir -p "${DB_DIR}" && ` +
        `uv run uvicorn main:app --host 127.0.0.1 --port ${BE_PORT}`,
      cwd: "../backend",
      url: `${BE_ORIGIN}/health`,
      reuseExistingServer: true,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        SELOM_DATABASE_URL: DB_URL,
        SELOM_DB_AUTO_CREATE: "true",
        SELOM_DATASETS_DIR: DATASETS_DIR,
      },
    },
    {
      // Real frontend proxied at the real backend. NEXT_PUBLIC_API_MOCKING is deliberately NOT set:
      // MSW would answer the run and the content claims would be meaningless [[selom-mock-is-wire-only-verify-real]].
      command: `npx next dev --port ${FE_PORT}`,
      url: FE_ORIGIN,
      reuseExistingServer: true,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        API_PROXY_TARGET: BE_ORIGIN,
        ...(ANNOTATION_LAYER ? { NEXT_PUBLIC_ANNOTATION_LAYER: ANNOTATION_LAYER } : {}),
      },
    },
  ],
});

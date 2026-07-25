/**
 * Browser-verify harness — the ONE env reader for the harness (structure.guard's `scripts/`
 * allowance; every other harness file imports these constants instead of touching process.env).
 *
 * WHY A SEPARATE HOME. `lib/config/env.ts` is the *app bundle's* env accessor; this is build/runner
 * env, read before any app code exists — the same category as `next.config.ts`. Keeping it here
 * means the single-env-reader ratchet stays untouched rather than widened for a test harness.
 *
 * Nothing host-specific is hardcoded: the corpus location is required from the caller
 * (`scripts/browser-verify.sh` says exactly what to export), and the browser is auto-detected.
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

/** Derived lane ports (CURRENT.md "ENV / landmines"): `:8000` is eamos and `:3000` is shared. */
export const BE_PORT = Number(process.env.SELOM_BV_BE_PORT || 8152);
export const FE_PORT = Number(process.env.SELOM_BV_FE_PORT || 3152);

export const BE_ORIGIN = `http://127.0.0.1:${BE_PORT}`;

/**
 * MUST be `localhost`, never `127.0.0.1` — and this is a SILENT trap, so it is pinned here.
 *
 * Next 16 dev blocks cross-origin requests to its own dev resources, and only `localhost` is
 * allowed by default. Served over `127.0.0.1` the HTML renders and every element is visible,
 * enabled and hit-testable — but the client chunks are blocked, so React NEVER HYDRATES: no handler
 * fires, localStorage stays empty, and a click on "New project" does nothing at all. There is no
 * error overlay; it presents exactly like a dead app, and Playwright's auto-waiting cannot see it.
 * (Measured 2026-07-25: `__reactFiber$…` keys absent on `127.0.0.1`, present on `localhost`.)
 * The alternative fix — `allowedDevOrigins` in next.config.ts — would change production config to
 * suit a test harness; using the host Next already trusts does not.
 */
export const FE_ORIGIN = `http://localhost:${FE_PORT}`;

/**
 * The real-data corpus. REQUIRED — a browser check on mock data proves the wire, not the content,
 * and every §D claim is content-shaped (long axis titles, real legend text)
 * [[verify-on-real-data-not-mock]].
 */
export const DATASETS_DIR = process.env.SELOM_DATASETS_DIR || "";

/**
 * The harness's SQLite job/library store. Lives in the corpus folder, never the repo (owner-directed
 * 2026-07-25) — a stray .db in the tree is exactly what the hygiene scan and .gitignore exist to stop.
 */
export const DB_DIR = DATASETS_DIR ? join(DATASETS_DIR, "_selom-browser-verify") : "";
export const DB_URL = DB_DIR ? `sqlite:///${join(DB_DIR, "browser-verify.db")}` : "";

/**
 * Known-good responsive figure input: a real EYG_28 bulk-DE export. `/data/inspect` routes it to
 * `volcano` at score 100 ("confident"), and the run returns 3 traces with NO `layout.width` — i.e.
 * the responsive spec D-5 is about. Override for a different shape (e.g. a fixed-size ERG grid).
 */
export const FIXTURE_CSV_REL =
  "eyg28/raw/output_EYG_28_RO_human-RUVge-K4_20250602/DEG/" +
  "EYG_28_RO_human-RUVge-K4_DEGs_All_PDE6B_FS_d180_vs_Control_d180.csv";

export const FIXTURE_CSV =
  process.env.SELOM_BV_FIXTURE_CSV || (DATASETS_DIR ? join(DATASETS_DIR, FIXTURE_CSV_REL) : "");

/** `on` renders the deferred annotation layer — Plan C territory, never "shipped-and-fine". */
export const ANNOTATION_LAYER = process.env.NEXT_PUBLIC_ANNOTATION_LAYER || "";

/**
 * Resolve a Chromium binary. The bare `playwright` package resolves a build that is not installed on
 * this box, so an explicit path is needed — but hardcoding one makes the harness host-specific. So:
 * an explicit override, else the newest downloaded ms-playwright build, else let Playwright try.
 */
export function chromiumExecutable() {
  if (process.env.SELOM_BV_CHROMIUM) return process.env.SELOM_BV_CHROMIUM;
  const root = join(process.env.HOME || "", ".cache", "ms-playwright");
  if (!existsSync(root)) return undefined;
  const builds = readdirSync(root)
    .filter((n) => /^chromium-\d+$/.test(n))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const b of builds) {
    const exe = join(root, b, "chrome-linux64", "chrome");
    if (existsSync(exe)) return exe;
  }
  return undefined;
}

/** Fail loudly and actionably rather than silently checking nothing. */
export function assertPreconditions() {
  if (!DATASETS_DIR) {
    throw new Error(
      "SELOM_DATASETS_DIR is unset — the harness verifies on REAL data, never mock.\n" +
        "  export SELOM_DATASETS_DIR=/path/to/selom-data",
    );
  }
  if (!existsSync(FIXTURE_CSV)) {
    throw new Error(
      `Fixture not found: ${FIXTURE_CSV}\n` +
        "  Point SELOM_BV_FIXTURE_CSV at a real DE table (needs a fold-change + a p/padj column).",
    );
  }
}

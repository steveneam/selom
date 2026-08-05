import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Structure guard — fails when the lib/ conventions drift.
 * Rules + rationale: docs/repo-structure/plan.md §1.2. If you are deliberately changing
 * a convention, change it here on purpose; do not weaken the guard to land a stray file.
 */
const LIB = join(process.cwd(), "lib");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

describe("lib/ structure conventions", () => {
  it("has no flat module files at the lib/ root — every module lives in a feature dir", () => {
    // Modules only; *.test.ts (incl. this guard) may sit at the root.
    const rootFiles = readdirSync(LIB).filter(
      (n) =>
        /\.(ts|tsx)$/.test(n) &&
        !/\.test\.tsx?$/.test(n) &&
        statSync(join(LIB, n)).isFile(),
    );
    expect(rootFiles).toEqual([]);
  });

  it("has no barrel index.ts re-export hub anywhere under lib/ (eager-import slowdown)", () => {
    const barrels = walk(LIB)
      .filter((p) => /[\\/]index\.tsx?$/.test(p))
      .map((p) => p.slice(LIB.length + 1).replace(/\\/g, "/"));
    expect(barrels).toEqual([]);
  });

  it("lib/ modules do not import upward from components/ or app/ (layering boundary)", () => {
    // lib/ is the lower layer (domain, transport, utils) and must stay reusable + UI-free — a
    // dependency up into React components/pages inverts the layering. See CLAUDE.md repo structure.
    const upward = /from\s+["'](?:@\/(?:components|app)\/|(?:\.\.\/)+(?:components|app)\/)/;
    const offenders = walk(LIB)
      .filter((p) => /\.(ts|tsx)$/.test(p) && !/\.test\.tsx?$/.test(p))
      .filter((p) => upward.test(readFileSync(p, "utf8")))
      .map((p) => p.slice(LIB.length + 1).replace(/\\/g, "/"));
    expect(offenders).toEqual([]);
  });
});

// --- single-env-reader ratchet (M-002) ---------------------------------------------------------

const ROOT = process.cwd(); // app/frontend
const ENV_SCAN_SKIP = new Set([
  "node_modules",
  ".next",
  "coverage",
  "dist",
  ".turbo",
  ".git",
  "test-results", // Playwright output (regenerated)
  "playwright-report",
  "graphify-out", // code-graph output (regenerated)
]);

function walkAll(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (ENV_SCAN_SKIP.has(name)) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walkAll(p, out);
    else if (/\.(ts|tsx|mjs|js)$/.test(p)) out.push(p);
  }
  return out;
}

describe("frontend env-reader convention", () => {
  it("reads app-config process.env only in lib/config/env.ts", () => {
    // App-config env (NEXT_PUBLIC_*, API_PROXY_TARGET, …) is read through the single accessor
    // lib/config/env.ts, so a renamed/duplicated var has one home. Exceptions:
    //   - NODE_ENV — framework/environment detection, not app config → allowed anywhere.
    //   - next.config.ts + scripts/ — build/framework files that run before the app bundle.
    const allowFiles = new Set(["lib/config/env.ts", "next.config.ts"]);
    const allowDirs = ["scripts/"];
    const re = /process\.env\.([A-Za-z_][A-Za-z0-9_]*)/g;
    const offenders: string[] = [];
    for (const file of walkAll(ROOT)) {
      const rel = file.slice(ROOT.length + 1).replace(/\\/g, "/");
      if (rel === "lib/structure.guard.test.ts") continue; // this guard names the pattern itself
      if (allowFiles.has(rel) || allowDirs.some((d) => rel.startsWith(d))) continue;
      const src = readFileSync(file, "utf8");
      let m: RegExpExecArray | null;
      while ((m = re.exec(src)) !== null) {
        if (m[1] !== "NODE_ENV") offenders.push(`${rel}: process.env.${m[1]}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});

// --- one narrowing site for the StatsTable union (G2, docs/stats-tables/spec.md §6) -------------

describe("StatsTable union narrowing", () => {
  it("narrows StatsTable | StatsTable[] only in lib/skills/stats-tables.ts", () => {
    // A union invites `Array.isArray(...)` to sprout at every call site — D1's known failure mode,
    // and it arrives one call site at a time rather than all at once. The answer is a single
    // normalizer (`asTables`), and this is what keeps it single. Scoped to every source root this
    // contract touches: a `lib/`-only scan would miss `components/`, where the Statistics view and
    // the work rail live — the sites most likely to drift.
    const ROOTS = ["app", "components", "hooks", "lib"];
    const HOME = "lib/skills/stats-tables.ts";
    // A table-shaped identifier: `table`, `tables`, `statsTable`, `fig.table`, `f.table_stats`, …
    const TABLEISH = /Array\.isArray\(\s*[\w.?[\]]*\b(?:table|tables|tableStats|table_stats)\b[\w.?[\]]*\s*\)/i;
    const offenders: string[] = [];
    for (const root of ROOTS) {
      for (const file of walkAll(join(ROOT, root))) {
        const rel = file.slice(ROOT.length + 1).replace(/\\/g, "/");
        if (rel === HOME || rel === "lib/structure.guard.test.ts") continue;
        for (const [i, line] of readFileSync(file, "utf8").split("\n").entries()) {
          if (TABLEISH.test(line)) offenders.push(`${rel}:${i + 1}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("declares asTables exactly once", () => {
    // The other half: the guard above only stops inline narrowing. A SECOND normalizer that happens
    // to spell the three cases slightly differently is the same defect wearing the right name.
    const decls = ["app", "components", "hooks", "lib"]
      .flatMap((root) => walkAll(join(ROOT, root)))
      .map((f) => f.slice(ROOT.length + 1).replace(/\\/g, "/"))
      .filter((rel) => rel !== "lib/structure.guard.test.ts") // this guard names the pattern itself
      .filter((rel) => /export function asTables\b/.test(readFileSync(join(ROOT, rel), "utf8")));
    expect(decls).toEqual(["lib/skills/stats-tables.ts"]);
  });
});

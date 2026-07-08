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

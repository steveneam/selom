import { readdirSync, statSync } from "node:fs";
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
});

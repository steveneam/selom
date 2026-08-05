import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { plural } from "./plural";

describe("plural", () => {
  it("agrees with the count", () => {
    expect(plural(1, "row")).toBe("1 row");
    expect(plural(2, "row")).toBe("2 rows");
    expect(plural(0, "row")).toBe("0 rows");
    expect(plural(1, "column")).toBe("1 column");
  });
});

/**
 * The class, not the three incidents.
 *
 * `${n} rows` read correctly for every table the product had ever rendered, right up until
 * `confusion`'s agreement scalars and `qq`'s λ became one-row tables (docs/stats-tables/spec.md D4
 * ranks 3–4) and three separate surfaces started saying **"1 rows"**. Fixing the three sites fixes
 * the three sites; this stops the fourth, which is the only version of the fix worth having.
 */
const SCAN_ROOTS = ["components", "app", "lib", "hooks"];
// A count interpolated straight in front of a bare plural noun — `${rows.length} rows`,
// `{n} columns`. `plural()` is the one home for this.
const HARDCODED = /\$\{[^}]*\}\s+(rows|columns|cols|tables|figures)\b|\}\s+(rows|columns|cols|tables|figures)\b/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(p) && !/\.test\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

describe("no surface hardcodes a plural noun after a count", () => {
  it("every count+noun goes through plural()", () => {
    const root = process.cwd();
    const offenders: string[] = [];
    for (const dir of SCAN_ROOTS) {
      for (const file of walk(join(root, dir))) {
        readFileSync(file, "utf8")
          .split("\n")
          .forEach((line, i) => {
            // Comments are skipped, and `plural.ts`'s own docstring is why: a rule has to be able
            // to quote the thing it forbids. No rendered string is ever inside a comment, so this
            // costs the scan nothing.
            if (/^\s*(\*|\/\/|\/\*)/.test(line)) return;
            if (HARDCODED.test(line)) {
              offenders.push(`${file.slice(root.length + 1).replace(/\\/g, "/")}:${i + 1}`);
            }
          });
      }
    }
    expect(offenders, "use plural(n, noun) — a count of 1 must not read '1 rows'").toEqual([]);
  });
});

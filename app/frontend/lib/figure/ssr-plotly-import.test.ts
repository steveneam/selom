import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * SSR-safety guard for Plotly imports (architecture-consistency Task E1).
 *
 * plotly.js touches `window`/`document` at module scope, so a *value* import of
 * `plotly.js` or `react-plotly.js` anywhere in the SSR render graph crashes every page
 * with a 500 — a raw `import("plotly.js")` once did exactly that
 * ([[full-app-smoke-test-before-handoff]]). The discipline that keeps it out:
 *
 *   • `plotly.js` may be imported only as `import type …` (erased at compile, no runtime);
 *   • `react-plotly.js` may enter only via `dynamic(() => import("react-plotly.js"), { ssr: false })`
 *     — never a static `import … from "react-plotly.js"` (a static `import type` is fine, erased).
 *
 * This test scans the whole frontend source tree and fails on any static, non-type import
 * from a Plotly module. It's the durable ratchet so the regression can't sneak back in a
 * page's dependency graph and only surface in a slow full-app smoke.
 */

const ROOT = fileURLToPath(new URL("../..", import.meta.url)); // lib/figure → app/frontend
const SCAN_DIRS = ["app", "components", "hooks", "lib"];
const SKIP_DIR = new Set(["node_modules", ".next", "dist", "e2e"]);

/** Recursively collect non-test .ts/.tsx files under `dir`. */
function collectSources(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!SKIP_DIR.has(entry.name)) collectSources(path.join(dir, entry.name), out);
    } else if (/\.tsx?$/.test(entry.name) && !/\.(test|spec)\.tsx?$/.test(entry.name)) {
      out.push(path.join(dir, entry.name));
    }
  }
  return out;
}

// A static import that is NOT `import type`, pulling from a plotly module. `[^;]` spans
// newlines so multi-line `import { … }` blocks are caught; the `m` flag anchors `import`
// at a line start. The dynamic form — `import("react-plotly.js")` — has no `from`, so it
// is (correctly) not matched.
const BAD_IMPORT =
  /^import\s+(?!type\b)[^;]*?\bfrom\s*["'](?:plotly\.js|react-plotly\.js)[^"']*["']/gm;

// The dynamic form — `import("plotly.js/…")` / `import("react-plotly.js")`. SSR-safe only while
// it is never evaluated during a server render, which is a property of the CALL SITE, not of the
// import. So the escape hatch is bounded by an allow-list of files rather than left open: a new
// dynamic plotly import anywhere else fails here and has to be argued for on purpose.
const DYNAMIC_IMPORT = /\bimport\(\s*["'](?:plotly\.js|react-plotly\.js)[^"']*["']\s*\)/g;
const DYNAMIC_ALLOWED = [
  // The canvas itself — `dynamic(() => import("react-plotly.js"), { ssr:false })`.
  "components/figure/figure-canvas.tsx",
  // The container-reflow helper (W-1) — imported inside a ResizeObserver callback, browser-only.
  "lib/figure/plot-resize.ts",
];

describe("SSR-safe Plotly imports", () => {
  const files = SCAN_DIRS.flatMap((d) => collectSources(path.join(ROOT, d)));

  it("scans a non-trivial set of source files (guard against an empty/false-green scan)", () => {
    expect(files.length).toBeGreaterThan(50);
  });

  it("has no static, non-type import of plotly.js / react-plotly.js anywhere", () => {
    const offenders: string[] = [];
    for (const file of files) {
      const src = fs.readFileSync(file, "utf8");
      const hits = src.match(BAD_IMPORT);
      if (hits) offenders.push(`${path.relative(ROOT, file)} → ${hits.join(" | ")}`);
    }
    expect(offenders).toEqual([]);
  });

  it("confines dynamic plotly imports to the two files allowed to have them", () => {
    const offenders: string[] = [];
    for (const file of files) {
      const rel = path.relative(ROOT, file).replace(/\\/g, "/");
      if (DYNAMIC_ALLOWED.includes(rel)) continue;
      const hits = fs.readFileSync(file, "utf8").match(DYNAMIC_IMPORT);
      if (hits) offenders.push(`${rel} → ${hits.join(" | ")}`);
    }
    expect(offenders).toEqual([]);
  });

  it("resolves the container-reflow helper's plotly lazily, never at module scope", () => {
    const src = fs.readFileSync(path.join(ROOT, "lib", "figure", "plot-resize.ts"), "utf8");
    // The import must sit inside a function body. A top-level `await import(…)` would be evaluated
    // on the server the moment the module is pulled into a page's graph — the exact 500 the
    // static-import rule above exists to prevent, reintroduced through the dynamic form.
    expect(src).toMatch(/import\("plotly\.js\/dist\/plotly"\)/);
    expect(src).not.toMatch(/^\s*(?:const|let|var|await|export)\b[^\n]*\bimport\(["']plotly/m);
  });

  it("FigureCanvas keeps plotly.js type-only and loads react-plotly.js via dynamic(ssr:false)", () => {
    const src = fs.readFileSync(
      path.join(ROOT, "components", "figure", "figure-canvas.tsx"),
      "utf8",
    );
    // type-only plotly.js import present; react-plotly.js only via a dynamic ssr:false import
    expect(src).toMatch(/import type \{[^}]*\} from "plotly\.js"/);
    expect(src).toMatch(/dynamic\(\(\) => import\("react-plotly\.js"\)/);
    expect(src).toMatch(/ssr:\s*false/);
    expect(src).not.toMatch(/^import\s+(?!type\b)[^;]*?from\s*"react-plotly\.js"/m);
  });
});

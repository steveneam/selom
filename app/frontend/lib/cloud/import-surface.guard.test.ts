import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Source guard on the cloud-import surface.
 *
 * These are component invariants, and vitest here runs `lib/**​/*.test.ts` in a **node** environment
 * with no DOM and no testing-library — so a rendering test is not available in this repo today. A
 * regex over TSX is crude, and it is still the strongest EXECUTABLE expression available (the same
 * trade the FE/BE contract guard makes in `app/backend/tests/test_contract_cloud_providers.py`).
 * Each rule below is narrow, names the defect it re-litigates, and would have failed on the code as
 * it shipped. If component tests arrive, delete this file and assert on the rendered output instead
 * — do not keep both.
 */

const FE = process.cwd(); // app/frontend

/** Source with comment lines stripped, so a rule can't be satisfied — or tripped — by prose. */
function code(rel: string): string {
  const src = readFileSync(join(FE, rel), "utf8");
  return src
    .split("\n")
    .filter((l) => {
      const t = l.trim();
      return !t.startsWith("//") && !t.startsWith("*") && !t.startsWith("/*");
    })
    .join("\n");
}

const DATA_PANEL = "components/project/data-panel.tsx";
const IMPORT_MENU = "components/intake/cloud-import-menu.tsx";

describe("no fabricated File ever becomes the run's data (B15)", () => {
  it("the data panel constructs no File at all", () => {
    /**
     * It used to build `new File(["mock"], …)` for a re-opened dataset and `new File(["remote"], …)`
     * for a cloud import. Both rode up as the workspace's `lastFile`, which a run POSTs as the
     * analysis input — so a few bytes of the literal text "mock" could be submitted as the user's
     * dataset. The panel now passes `null`: the run either goes through run-from-dataset_id or
     * halts and asks for a re-upload. [[mock-fallback-never-fabricates-data]]
     *
     * Files with REAL bytes (a drop, a `/data/combine` result) arrive as values from elsewhere and
     * are never constructed here — so "constructs no File" is the exact, checkable rule.
     */
    expect(code(DATA_PANEL)).not.toMatch(/new\s+File\s*\(/);
  });
});

describe("the Import busy state is labelled (B22)", () => {
  it("no bare spinner stands in for a label", () => {
    /**
     * The exact prior shape: `{busy ? <Loader2 className="…animate-spin" /> : "Import"}` — the
     * button's only content while the import ran was a spinning glyph. A screen reader got nothing,
     * and a sighted user got "something is happening" without which thing. Matching the ternary
     * branch rather than the spinner itself keeps a spinner *beside* text legal, which is the fix.
     */
    expect(code(IMPORT_MENU)).not.toMatch(/\?\s*<Loader2[^>]*\/>\s*:/);
  });

  it("the busy control says what it is doing, and marks itself busy", () => {
    const src = code(IMPORT_MENU);
    expect(src).toMatch(/Importing…/);
    expect(src).toMatch(/aria-busy=/);
  });
});

describe("no client-side provider truth ever comes back (A20)", () => {
  it("neither the menu nor the provider module carries a `comingSoon` flag", () => {
    /**
     * `comingSoon: true` hardcoded in the FE registry is why Google Drive and Dropbox stayed
     * unreachable after both went live: the client had no way to learn a provider was enabled, so it
     * refused to offer one that was. `enabled` is the server's answer now — see
     * `docs/cloud-providers-contract/spec.md` rule 3.
     */
    expect(code(IMPORT_MENU)).not.toMatch(/comingSoon/);
    expect(code("lib/cloud/providers.ts")).not.toMatch(/comingSoon/);
  });
});

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

const FE = join(process.cwd());
const read = (rel: string) => readFileSync(join(FE, rel), "utf8");

const DATA_PANEL = "components/project/data-panel.tsx";

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
    const src = read(DATA_PANEL)
      .split("\n")
      .filter((l) => !l.trim().startsWith("//") && !l.trim().startsWith("*"))
      .join("\n");
    expect(src).not.toMatch(/new\s+File\s*\(/);
  });
});

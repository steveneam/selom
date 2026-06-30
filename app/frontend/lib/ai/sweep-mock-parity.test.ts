import { describe, expect, it } from "vitest";

import { mockSweepSuggestions } from "@/mocks/ai-fixture";

/**
 * Parity guard for the sweep recommender's MSW mirror.
 *
 * `mockSweepSuggestions` (mocks/ai-fixture.ts) ports `rank_sweep_space` (app/backend/ai/gateway.py)
 * so `dev:mock` preselects the SAME param the real backend would ([[mock-must-mirror-backend-contract]]).
 * It pins the ranking to the SAME representative input as the backend's
 * `test_rank_sweep_space_orders_numeric_then_select_then_switch` — if either side's algorithm drifts,
 * its pinned expectation fails here rather than the two silently diverging in dev:mock. (Lives under
 * lib/ so the `lib/**` vitest glob runs it; the function it guards lives in mocks/.)
 */
describe("mockSweepSuggestions (parity with backend rank_sweep_space)", () => {
  it("ranks numeric-by-breadth > select > switch and caps at 3 (same case as test_ai_s4.py)", () => {
    const ranked = mockSweepSuggestions({
      a_switch: { type: "switch" },
      b_select: { type: "select", options: ["x", "y", "z"] },
      c_wide: { type: "range", min: 0.0, max: 10.0, step: 0.1 }, // ~100 steps
      d_narrow: { type: "range", min: 0.0, max: 1.0, step: 0.5 }, // ~2 steps
    });
    expect(ranked.map((s) => s.param)).toEqual(["c_wide", "d_narrow", "b_select"]);
    expect(ranked[0].reason).toContain("100 steps");
    expect(ranked[2].reason).toBe("3 options");
  });

  it("infers numeric from min/max with no type, and degrades clean on junk", () => {
    expect(mockSweepSuggestions(undefined)).toEqual([]);
    expect(mockSweepSuggestions({})).toEqual([]);
    const ranked = mockSweepSuggestions({ inferred: { min: 0.01, max: 0.1 }, empty: {} });
    expect(ranked[0].param).toBe("inferred");
    expect(ranked[1].reason).toBe("no declared range");
  });
});

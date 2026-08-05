import { describe, expect, it } from "vitest";

import { buildScorecardPayload, buildSweepSpace } from "./explain-inputs";
import type { ParamField } from "@/lib/catalog/params";
import type { PaperScore, Scorecard } from "@/lib/reproduction/types";

function paperScore(over: Partial<PaperScore> = {}): PaperScore {
  return {
    paper_id: "p1",
    reproducibility: 72,
    selom_confidence: 88,
    tier: "reproduced",
    color: "#22c55e",
    n_scored: 8,
    n_in_scope: 9,
    n_out_of_scope: 1,
    n_form_only: 0,
    coverage: "8 of 9 panels",
    ...over,
  };
}

function scorecard(over: Partial<Scorecard> = {}): Scorecard {
  return {
    paper_id: "p1",
    n_panels: 9,
    n_in_scope: 9,
    totals_by_verdict: {},
    totals_by_blame: {},
    findings: { reproduced: 6, paper_irreproducible: 1 },
    provenance_divergences: [],
    panel_scores: [
      { panel_key: "1a", reproducibility: 80, selom_confidence: 90, tier: "reproduced", color: "#22c55e", attribution: "selom", provenance: "", reading_provenance: "", in_scope: true, weight: 1, note: "" },
      { panel_key: "1b", reproducibility: 60, selom_confidence: 85, tier: "recoverable", color: "#84cc16", attribution: "paper", provenance: "", reading_provenance: "", in_scope: true, weight: 1, note: "" },
    ],
    score: paperScore(),
    generated_at: "2026-06-30",
    ...over,
  };
}

describe("buildScorecardPayload", () => {
  it("flattens the nested score into the backend's flat shape", () => {
    const p = buildScorecardPayload(scorecard());
    expect(p).toEqual({
      paper_id: "p1",
      tier: "reproduced",
      panel_count: 2,
      findings: { reproduced: 6, paper_irreproducible: 1 },
      coverage: "8 of 9 panels",
      score: 72,
      selom_confidence: 88,
    });
  });

  it("carries paper_id so the operator gateway can key its recorded demo explanation", () => {
    expect(buildScorecardPayload(scorecard())).toMatchObject({ paper_id: "p1" });
  });

  it("returns null when there is no graded score yet", () => {
    expect(buildScorecardPayload(null)).toBeNull();
    expect(buildScorecardPayload(scorecard({ score: null }))).toBeNull();
  });

  it("omits null numerics so the backend uses its own n/a fallback (never sends null/100)", () => {
    const p = buildScorecardPayload(scorecard({ score: paperScore({ reproducibility: null, selom_confidence: null }) }));
    expect(p).not.toHaveProperty("score");
    expect(p).not.toHaveProperty("selom_confidence");
    expect(p).toMatchObject({ tier: "reproduced", panel_count: 2 });
  });
});

describe("buildSweepSpace", () => {
  const fields: ParamField[] = [
    { key: "resolution", label: "Cluster resolution", type: "range", default: 1.0, min: 0.1, max: 2.0, step: 0.1 },
    { key: "cluster", label: "Clustering", type: "select", default: "none", options: [
      { value: "none", label: "None" }, { value: "row", label: "Rows" },
    ] },
    { key: "normalize", label: "Normalize", type: "switch", default: true },
  ];

  it("carries each knob's declared value-space + the current value", () => {
    const space = buildSweepSpace(fields, { resolution: 1.4 });
    expect(space.resolution).toEqual({
      label: "Cluster resolution", type: "range", min: 0.1, max: 2.0, step: 0.1, current: 1.4,
    });
    expect(space.cluster).toEqual({
      label: "Clustering", type: "select", options: ["none", "row"], current: "none",
    });
    expect(space.normalize).toEqual({ label: "Normalize", type: "switch", current: true });
  });

  it("falls back to the field default when the param is unset", () => {
    const space = buildSweepSpace(fields, {});
    expect(space.resolution.current).toBe(1.0); // the field default
  });

  it("omits absent range/option metadata (text knobs degrade clean)", () => {
    const space = buildSweepSpace(
      [{ key: "gene", label: "Marker gene", type: "text", default: "" }],
      { gene: "RHO" },
    );
    expect(space.gene).toEqual({ label: "Marker gene", type: "text", current: "RHO" });
  });
});

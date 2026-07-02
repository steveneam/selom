import { describe, it, expect } from "vitest";
import { dedupById, isDataAwareRecommendation, notAFitSkills, recommendedSkills } from "./quick-apply";
import type { DataFitSummary } from "@/lib/intake/inspect";
import type { DataFit } from "@/lib/reproduction/data-fit";
import type { DataRouting } from "@/lib/skills/api";

/** A route result carrying BARE backend slugs (as /data/inspect returns them). */
const routingWith = (skillIds: string[]): DataRouting => ({
  kind: "de_results",
  steps: skillIds.map((skill_id) => ({ skill_id, role: "", reason: "" })),
  confident: true,
  note: "",
});

/** A minimal per-skill DataFit (only skill_id + compatible are read by the chips). */
const fit = (skill_id: string, compatible: boolean | null): DataFit => ({
  filename: "de.csv", skill_id, kind: "de_results", score: 80, compatible,
  verdict: "fit", qc_ok: true, reason: "", confidence: "confident", confidence_label: "",
});

const summaryWith = (fits: DataFit[]): DataFitSummary => ({
  quality: 100, confidence: "confident", columns: ["gene", "logFC", "padj"], n_numeric_cols: 2, fits,
});

const route = (skillIds: string[], fits: DataFit[] = []) => ({
  routing: routingWith(skillIds),
  dataFit: summaryWith(fits),
});

describe("recommendedSkills — data-fit route (real inspected data)", () => {
  it("resolves BARE backend slugs from the route, in the engine's order (the ad453fe fix)", () => {
    const r = recommendedSkills(route(["deg", "volcano"]), null);
    expect(r.map((s) => s.id)).toEqual(["selom.deg", "selom.volcano"]);
  });

  it("drops a skill the data is a certain mismatch for (dataFit.compatible === false)", () => {
    const r = recommendedSkills(route(["deg", "volcano"], [fit("deg", false)]), null);
    expect(r.map((s) => s.id)).toEqual(["selom.volcano"]);
  });

  it("keeps a skill whose fit is unknown (compatible === null), only certain mismatches drop", () => {
    const r = recommendedSkills(route(["deg", "volcano"], [fit("deg", null)]), null);
    expect(r.map((s) => s.id)).toEqual(["selom.deg", "selom.volcano"]);
  });

  it("drops a slug not in the catalog instead of rendering a broken chip", () => {
    const r = recommendedSkills(route(["not_a_real_skill", "deg"]), null);
    expect(r.map((s) => s.id)).toEqual(["selom.deg"]);
  });

  it("dedups by id (a skill repeated across steps → one chip) — the duplicate-React-key guard", () => {
    const r = recommendedSkills(route(["deg", "deg"]), null);
    expect(r.filter((s) => s.id === "selom.deg")).toHaveLength(1);
  });

  it("caps the chips at four", () => {
    const r = recommendedSkills(route(["umap_scrna", "deg", "volcano", "pca", "corr_heatmap"]), null);
    expect(r).toHaveLength(4);
  });
});

describe("recommendedSkills — modality mock fallback (demo/sample data, NOT inspected)", () => {
  it("uses the modality mock when there is no inspected route (route === null)", () => {
    const r = recommendedSkills(null, "bulk RNA-seq");
    expect(r.map((s) => s.id)).toContain("selom.deg");
  });

  it("is empty with neither a route nor a modality — the caller hides the row", () => {
    expect(recommendedSkills(null, null)).toEqual([]);
  });

  it("is empty when the modality mock has no steps (unknown modality)", () => {
    expect(recommendedSkills(null, "unknown")).toEqual([]);
  });
});

describe("recommendedSkills — honest no-fit for REAL inspected data (never masked by the mock)", () => {
  it("a real inspected route that resolves to nothing returns [] — NOT the modality mock", () => {
    // route present (inspected) but the only step is unresolvable → empty; we must NOT mask a real
    // no-fit with the generic modality mock even though a modality is available (the honesty promise).
    expect(recommendedSkills(route(["not_a_real_skill"]), "bulk RNA-seq")).toEqual([]);
  });

  it("a real inspected route whose every routed skill is a certain mismatch returns []", () => {
    const r = recommendedSkills(
      route(["deg", "volcano"], [fit("deg", false), fit("volcano", false)]),
      "bulk RNA-seq",
    );
    expect(r).toEqual([]);
  });
});

describe("isDataAwareRecommendation — A3 fix: never label the modality-mock fallback per-dataset", () => {
  it("is true when a real routing exists (the chips came from the inspected route)", () => {
    expect(isDataAwareRecommendation(route(["deg"]))).toBe(true);
  });

  it("is false for a real dataset whose inspect failed (routing null) — no route, no fabricated per-dataset label", () => {
    expect(isDataAwareRecommendation(null)).toBe(false);
    expect(isDataAwareRecommendation({ routing: null, dataFit: null })).toBe(false);
  });
});

describe("notAFitSkills — the dropped 'not a fit' trace (followups #3)", () => {
  const badFit = (skill_id: string, reason: string): DataFit => ({
    ...fit(skill_id, false), reason, confidence: "not_a_fit", confidence_label: "Not a fit",
  });

  it("returns the certain-mismatch skills, resolved to the catalog, with the engine's reason", () => {
    const n = notAFitSkills(route(["deg", "volcano"], [badFit("volcano", "needs a raw count matrix")]));
    expect(n.map((x) => x.skill.id)).toEqual(["selom.volcano"]);
    expect(n[0].reason).toBe("needs a raw count matrix");
    expect(n[0].confidenceLabel).toBe("Not a fit");
  });

  it("excludes fits that are compatible (true) or unknown (null) — only certain mismatches show", () => {
    const n = notAFitSkills(route(["deg", "volcano"], [fit("deg", true), fit("volcano", null)]));
    expect(n).toEqual([]);
  });

  it("is empty for the modality-mock path (no route / no dataFit — no per-dataset fitness to judge)", () => {
    expect(notAFitSkills(null)).toEqual([]);
    expect(notAFitSkills({ routing: routingWith(["deg"]), dataFit: null })).toEqual([]);
  });

  it("drops a mismatch whose slug isn't in the catalog (no broken row) + dedups by id", () => {
    const n = notAFitSkills(
      route(["volcano", "volcano", "not_a_real_skill"],
        [badFit("volcano", "x"), badFit("not_a_real_skill", "y")]),
    );
    expect(n.map((x) => x.skill.id)).toEqual(["selom.volcano"]);
  });

  it("is the complement of the recommended chips — a dropped skill appears here, not there", () => {
    const r = route(["deg", "volcano"], [badFit("volcano", "needs raw counts")]);
    expect(recommendedSkills(r, null).map((s) => s.id)).toEqual(["selom.deg"]);
    expect(notAFitSkills(r).map((x) => x.skill.id)).toEqual(["selom.volcano"]);
  });
});

describe("dedupById", () => {
  it("keeps the first occurrence and preserves order", () => {
    expect(dedupById([{ id: "a" }, { id: "b" }, { id: "a" }])).toEqual([{ id: "a" }, { id: "b" }]);
  });
});

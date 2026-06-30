import { describe, it, expect } from "vitest";
import { recommendedSkills, dedupById } from "./quick-apply";
import type { IntakeProposal } from "@/lib/intake/mock";

/** Minimal valid proposal carrying just the recommended steps (the only field recommendedSkills reads). */
const proposalWith = (skillIds: string[]): IntakeProposal => ({
  summary: "",
  cleaning: [],
  guardrails: [],
  alternatives: [],
  steps: skillIds.map((skillId) => ({ skillId, rationale: "", params: {}, confidence: 0.8 })),
});

describe("recommendedSkills", () => {
  it("returns the proposal's recommended skills, in the engine's order", () => {
    const r = recommendedSkills(proposalWith(["selom.deg", "selom.volcano"]));
    expect(r.map((s) => s.id)).toEqual(["selom.deg", "selom.volcano"]);
  });

  it("is empty with no proposal — the caller hides the row (never a popularity fallback)", () => {
    expect(recommendedSkills(null)).toEqual([]);
  });

  it("is empty when no step resolves to a verified skill (e.g. a bare slug)", () => {
    expect(recommendedSkills(proposalWith(["umap_scrna"]))).toEqual([]);
  });

  it("dedups by skill id (a skill repeated across steps → one chip) — the duplicate-React-key guard", () => {
    const r = recommendedSkills(proposalWith(["selom.deg", "selom.deg"]));
    expect(r.filter((s) => s.id === "selom.deg")).toHaveLength(1);
  });

  it("drops unresolved / non-catalog ids instead of rendering a broken chip", () => {
    const r = recommendedSkills(proposalWith(["umap_scrna", "selom.deg"]));
    expect(r.map((s) => s.id)).toEqual(["selom.deg"]);
  });

  it("caps the chips at four", () => {
    const r = recommendedSkills(
      proposalWith(["selom.umap_scrna", "selom.deg", "selom.volcano", "selom.pca", "selom.corr_heatmap"]),
    );
    expect(r).toHaveLength(4);
  });
});

describe("dedupById", () => {
  it("keeps the first occurrence and preserves order", () => {
    expect(dedupById([{ id: "a" }, { id: "b" }, { id: "a" }])).toEqual([{ id: "a" }, { id: "b" }]);
  });
});

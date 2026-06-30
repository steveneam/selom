import { describe, it, expect } from "vitest";
import { pickQuickApply, dedupById } from "./quick-apply";
import type { IntakeProposal } from "@/lib/intake/mock";

/** Minimal valid proposal carrying just the recommended steps (the only field pickQuickApply reads). */
const proposalWith = (skillIds: string[]): IntakeProposal => ({
  summary: "",
  cleaning: [],
  guardrails: [],
  alternatives: [],
  steps: skillIds.map((skillId) => ({ skillId, rationale: "", params: {}, confidence: 0.8 })),
});
const inst = (skillId: string, id = skillId) => ({ id, skillId });

describe("pickQuickApply", () => {
  it("data-aware: surfaces the proposal's recommended skills, in the engine's order", () => {
    const r = pickQuickApply(proposalWith(["selom.deg", "selom.volcano"]), [inst("selom.umap_scrna")]);
    expect(r.dataAware).toBe(true);
    expect(r.skills.map((s) => s.id)).toEqual(["selom.deg", "selom.volcano"]);
  });

  it("falls back to popularity-ranked installed favourites when there is no proposal", () => {
    const r = pickQuickApply(null, [inst("selom.umap_scrna"), inst("selom.deg"), inst("selom.volcano")]);
    expect(r.dataAware).toBe(false);
    expect(r.skills.length).toBeGreaterThan(0);
    for (let i = 1; i < r.skills.length; i++) {
      expect(r.skills[i - 1].popularity).toBeGreaterThanOrEqual(r.skills[i].popularity);
    }
  });

  it("falls back to favourites when a proposal has no resolvable verified step (never an empty row)", () => {
    // bare slug (no `selom.` prefix) does not resolve — the route-bug class
    const r = pickQuickApply(proposalWith(["umap_scrna"]), [inst("selom.deg")]);
    expect(r.dataAware).toBe(false);
    expect(r.skills.map((s) => s.id)).toContain("selom.deg");
  });

  it("dedups by skill id (a skill installed twice → one chip) — the duplicate-React-key guard", () => {
    const r = pickQuickApply(null, [inst("selom.deg", "row-a"), inst("selom.deg", "row-b")]);
    expect(r.skills.filter((s) => s.id === "selom.deg")).toHaveLength(1);
  });

  it("drops unresolved / non-catalog ids instead of rendering a broken chip", () => {
    const r = pickQuickApply(null, [inst("umap_scrna"), inst("selom.deg")]);
    expect(r.skills.map((s) => s.id)).not.toContain("umap_scrna");
    expect(r.skills.map((s) => s.id)).toContain("selom.deg");
  });

  it("caps the chips at four", () => {
    const r = pickQuickApply(
      proposalWith(["selom.umap_scrna", "selom.deg", "selom.volcano", "selom.pca", "selom.corr_heatmap"]),
      [],
    );
    expect(r.skills.length).toBe(4);
  });
});

describe("dedupById", () => {
  it("keeps the first occurrence and preserves order", () => {
    expect(dedupById([{ id: "a" }, { id: "b" }, { id: "a" }])).toEqual([{ id: "a" }, { id: "b" }]);
  });
});

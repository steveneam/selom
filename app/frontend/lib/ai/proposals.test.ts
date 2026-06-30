import { describe, expect, it } from "vitest";

/**
 * Unit tests for the pure AI-proposal derivations (S5). These are the single source of truth for
 * the banner's author-partitioned counter and the ✨ marker author map — so the state machine
 * (accept → stage → ✨AI; revert → base → decrement; all-revert → banner clears) is proven here,
 * independent of React.
 */

import {
  acceptProposal,
  applyAcceptedProposals,
  approvedActions,
  authorOf,
  dismissProposal,
  pendingCounter,
  proposalsFromTurn,
  selectedSkillFromTurn,
  unacceptProposal,
} from "./proposals";
import { getSkill } from "@/lib/catalog/seed";
import type { AiProposal, CapabilityGap, HelperTurn } from "./types";

function proposal(over: Partial<AiProposal> = {}): AiProposal {
  return {
    id: "a1",
    type: "set_param",
    tier: "recompute",
    status: "proposed",
    paramKey: "resolution",
    value: 1.2,
    rationale: "tighter clusters",
    actor: "ai",
    model: "claude-x",
    ...over,
  };
}

describe("authorOf", () => {
  const base = { resolution: 1.0 } as Record<string, string | number | boolean>;

  it("returns null when the key is not pending (staged === base)", () => {
    expect(authorOf("resolution", base, { resolution: 1.0 }, [])).toBeNull();
  });

  it("attributes a staged value to 'ai' when an accepted proposal still holds it", () => {
    const staged = { resolution: 1.2 };
    const proposals = [proposal({ status: "accepted" })];
    expect(authorOf("resolution", base, staged, proposals)).toBe("ai");
  });

  it("attributes to 'user' when pending but no matching accepted proposal", () => {
    expect(authorOf("resolution", base, { resolution: 0.8 }, [])).toBe("user");
  });

  it("flips an accepted AI value to 'user' once the user edits it to a different value", () => {
    const staged = { resolution: 1.5 }; // user changed it away from the AI's 1.2
    const proposals = [proposal({ status: "accepted", value: 1.2 })];
    expect(authorOf("resolution", base, staged, proposals)).toBe("user");
  });

  it("matches AI authorship across number/string coercion (controls stringify)", () => {
    const staged = { resolution: "1.2" }; // a control wrote the string form
    const proposals = [proposal({ status: "accepted", value: 1.2 })];
    expect(authorOf("resolution", base, staged, proposals)).toBe("ai");
  });
});

describe("pendingCounter", () => {
  const base = { resolution: 1.0, n_neighbors: 15 } as Record<string, string | number | boolean>;

  it("partitions pending params into you vs ✨AI", () => {
    const staged = { resolution: 1.2, n_neighbors: 30 }; // resolution = AI, n_neighbors = manual
    const proposals = [proposal({ id: "a1", paramKey: "resolution", value: 1.2, status: "accepted" })];
    expect(pendingCounter(base, staged, proposals)).toEqual({ total: 2, you: 1, ai: 1 });
  });

  it("decrements the ✨AI tally when an AI value is reverted to base", () => {
    const proposals = [proposal({ status: "accepted" })];
    // accepted + staged → 1 ✨AI
    expect(pendingCounter(base, { resolution: 1.2, n_neighbors: 15 }, proposals)).toEqual({ total: 1, you: 0, ai: 1 });
    // reverted to base → leaves the diff → counter clears
    expect(pendingCounter(base, { resolution: 1.0, n_neighbors: 15 }, proposals)).toEqual({ total: 0, you: 0, ai: 0 });
  });

  it("is zero when nothing is staged (the banner clears itself)", () => {
    expect(pendingCounter(base, { ...base }, [])).toEqual({ total: 0, you: 0, ai: 0 });
  });
});

describe("proposalsFromTurn", () => {
  const turn: HelperTurn = {
    goal: "tighten clusters",
    plan: {
      goal: "tighten clusters",
      notes: "",
      actions: [
        { id: "a1", type: "set_param", target: "resolution", payload: {}, rationale: "tighter clusters" },
        { id: "c1", type: "relabel", target: "title", payload: {}, rationale: "clearer title" },
      ],
    },
    results: [
      { action_id: "a1", type: "set_param", target: "resolution", tier: "recompute", status: "staged", effect: {}, errors: [], gap: null },
      { action_id: "c1", type: "relabel", target: "title", tier: "cosmetic", status: "applied", effect: {}, errors: [], gap: null },
    ],
    staged_params: { resolution: 1.2 },
    figure_spec: null,
    gaps: [],
    provenance_actions: [
      { action_id: "a1", actor: "ai", type: "set_param", target: "resolution", prompt: "tighten", model: "claude-x", approved_by: "", approved_at: "" },
    ],
  };

  it("queues only STAGED recompute actions (cosmetic applied ones are already in figure_spec)", () => {
    const out = proposalsFromTurn(turn);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      id: "a1",
      paramKey: "resolution",
      value: 1.2,
      status: "proposed",
      rationale: "tighter clusters",
      actor: "ai",
      model: "claude-x",
    });
  });
});

describe("approvedActions", () => {
  const base = { resolution: 1.0 } as Record<string, string | number | boolean>;
  const staged = { resolution: 1.2 } as Record<string, string | number | boolean>; // the AI's value, still staged

  it("builds the descriptive delta (no attribution) for accepted proposals whose value is still staged", () => {
    const proposals = [
      proposal({ id: "a1", status: "accepted" }),
      proposal({ id: "a2", status: "proposed" }), // not accepted → excluded
    ];
    const out = approvedActions(proposals, base, staged);
    expect(out).toHaveLength(1);
    // The delta carries ONLY {action_id, type, target, prompt} — the server (chokepoint) derives the
    // attribution. A forgeable actor/model/approved_by/approved_at must NOT be emitted here.
    expect(out[0]).toEqual({ action_id: "a1", type: "set_param", target: "resolution", prompt: "" });
    expect(out[0]).not.toHaveProperty("actor");
    expect(out[0]).not.toHaveProperty("approved_by");
    expect(out[0]).not.toHaveProperty("model");
  });

  it("DROPS an accepted proposal the user has since overridden (no false AI attribution)", () => {
    const proposals = [proposal({ id: "a1", status: "accepted", value: 1.2 })];
    // the user hand-edited resolution to 1.5 → it's no longer the AI's value → must not be in the delta
    expect(approvedActions(proposals, base, { resolution: 1.5 })).toEqual([]);
  });

  it("is empty when nothing is accepted (the caller falls back to a plain re-run)", () => {
    expect(approvedActions([proposal({ status: "proposed" })], base, staged)).toEqual([]);
  });
});

describe("applyAcceptedProposals", () => {
  const base = { resolution: 1.0, n_neighbors: 15 } as Record<string, string | number | boolean>;

  it("overlays accepted proposals' values onto base (re-hydration across reload)", () => {
    const proposals = [
      proposal({ id: "a1", paramKey: "n_neighbors", value: 30, status: "accepted" }),
      proposal({ id: "a2", paramKey: "resolution", value: 1.2, status: "proposed" }), // not accepted → ignored
    ];
    expect(applyAcceptedProposals(base, proposals)).toEqual({ resolution: 1.0, n_neighbors: 30 });
  });

  it("returns a copy of base when there are no accepted proposals", () => {
    const out = applyAcceptedProposals(base, [proposal({ status: "proposed" })]);
    expect(out).toEqual(base);
    expect(out).not.toBe(base);
  });
});

describe("selectedSkillFromTurn", () => {
  function baseTurn(over: Partial<HelperTurn> = {}): HelperTurn {
    return {
      goal: "which test for two groups?",
      plan: { goal: "which test for two groups?", notes: "", actions: [] },
      results: [],
      staged_params: {},
      figure_spec: null,
      gaps: [],
      provenance_actions: [],
      ...over,
    };
  }

  it("returns null when no select_skill result is present (gateway off / no route action)", () => {
    expect(selectedSkillFromTurn(baseTurn())).toEqual({ skillId: null, gap: undefined });
  });

  it("returns null when the select_skill result is rejected", () => {
    const turn = baseTurn({
      results: [
        {
          action_id: "s1",
          type: "select_skill",
          target: "umap",
          tier: "recompute",
          status: "rejected",
          effect: {},
          errors: ["unknown skill id"],
          gap: null,
        },
      ],
    });
    expect(selectedSkillFromTurn(turn)).toEqual({ skillId: null, gap: undefined });
  });

  it("extracts skillId from staged_params['_selected_skill'] (primary source)", () => {
    const turn = baseTurn({
      results: [
        {
          action_id: "s1",
          type: "select_skill",
          target: "umap_fallback",
          tier: "recompute",
          status: "staged",
          effect: {},
          errors: [],
          gap: null,
        },
      ],
      staged_params: { _selected_skill: "umap" },
    });
    expect(selectedSkillFromTurn(turn)).toEqual({ skillId: "umap" });
  });

  it("falls back to result.target when _selected_skill is absent from staged_params", () => {
    const turn = baseTurn({
      results: [
        {
          action_id: "s1",
          type: "select_skill",
          target: "volcano",
          tier: "recompute",
          status: "applied",
          effect: {},
          errors: [],
          gap: null,
        },
      ],
    });
    expect(selectedSkillFromTurn(turn)).toEqual({ skillId: "volcano" });
  });

  it("accepts status='applied' as a valid selection", () => {
    const turn = baseTurn({
      results: [
        {
          action_id: "s1",
          type: "select_skill",
          target: "deg",
          tier: "recompute",
          status: "applied",
          effect: {},
          errors: [],
          gap: null,
        },
      ],
    });
    expect(selectedSkillFromTurn(turn).skillId).toBe("deg");
  });

  it("reports a no_fitting_skill gap when present and no successful result", () => {
    const gap: CapabilityGap = {
      stage: "route",
      intent: "run a flow cytometry skill",
      unmet: "no_fitting_skill",
      attempted: {},
      context_hash: "abc123",
      skill_id: null,
    };
    const turn = baseTurn({ gaps: [gap] });
    expect(selectedSkillFromTurn(turn)).toEqual({ skillId: null, gap });
  });

  it("does not report the gap when a successful selection exists alongside it", () => {
    const gap: CapabilityGap = {
      stage: "route",
      intent: "some other intent",
      unmet: "no_fitting_skill",
      attempted: {},
      context_hash: "xyz",
      skill_id: null,
    };
    const turn = baseTurn({
      results: [
        {
          action_id: "s1",
          type: "select_skill",
          target: "gsea",
          tier: "recompute",
          status: "staged",
          effect: {},
          errors: [],
          gap: null,
        },
      ],
      gaps: [gap],
    });
    // A successful selection takes priority; the gap is not surfaced.
    expect(selectedSkillFromTurn(turn)).toEqual({ skillId: "gsea" });
  });

  it("returns the rationale from the matching plan action when present", () => {
    const turn = baseTurn({
      plan: {
        goal: "which test?",
        notes: "",
        actions: [
          {
            id: "s1",
            type: "select_skill",
            target: "volcano",
            payload: {},
            rationale: "volcano is the standard DE visualisation for two-group comparisons",
          },
        ],
      },
      results: [
        {
          action_id: "s1",
          type: "select_skill",
          target: "volcano",
          tier: "recompute",
          status: "applied",
          effect: {},
          errors: [],
          gap: null,
        },
      ],
    });
    const result = selectedSkillFromTurn(turn);
    expect(result.skillId).toBe("volcano");
    expect(result.rationale).toBe(
      "volcano is the standard DE visualisation for two-group comparisons",
    );
  });
});

/**
 * INVARIANT: the catalog is keyed `selom.<slug>`, not the bare backend slug.
 * A bare slug MUST NOT resolve directly — the route stage normalizes via `selom.${slug}`.
 * If BE/FE slug conventions drift this test fails loudly in CI before a silent no-op
 * reaches the user (the bug this guards: `onSelect("umap_scrna")` would set preselect to
 * a key that `getSkill` cannot find, silently doing nothing).
 */
describe("slug normalization invariant (route stage / FIX 1 guard)", () => {
  // "selom.umap_scrna" is verified to exist in lib/catalog/seed.ts — it is the first
  // Selom-native entry and a stable integration point for this contract.
  const bareSlug = "umap_scrna";
  const catalogId = `selom.${bareSlug}`;

  it("bare slug does NOT resolve in the catalog (direct lookup returns undefined)", () => {
    expect(getSkill(bareSlug)).toBeUndefined();
  });

  it("normalized selom.<slug> resolves to the correct catalog entry", () => {
    const skill = getSkill(catalogId);
    expect(skill).toBeDefined();
    expect(skill?.id).toBe(catalogId);
  });

  it("normalized id round-trips through getSkill and preserves the display name", () => {
    const skill = getSkill(catalogId);
    expect(skill?.name).toBe("UMAP (single-cell)");
  });
});

describe("queue transitions", () => {
  const proposals = [proposal({ id: "a1" }), proposal({ id: "a2" })];

  it("accept marks one proposal accepted, leaving others untouched", () => {
    const out = acceptProposal(proposals, "a1");
    expect(out.find((p) => p.id === "a1")?.status).toBe("accepted");
    expect(out.find((p) => p.id === "a2")?.status).toBe("proposed");
  });

  it("unaccept returns a proposal to proposed (on revert)", () => {
    const accepted = acceptProposal(proposals, "a1");
    expect(unacceptProposal(accepted, "a1").find((p) => p.id === "a1")?.status).toBe("proposed");
  });

  it("dismiss removes a proposal entirely", () => {
    expect(dismissProposal(proposals, "a1").map((p) => p.id)).toEqual(["a2"]);
  });
});

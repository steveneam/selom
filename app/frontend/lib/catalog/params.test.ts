import { describe, expect, it } from "vitest";

/**
 * Unit tests for the skill param catalog — the P2.5 additions: the `showWhen` conditional
 * reveal (`visibleParamFields`) and the new Melody `integration` schema, which must stay
 * faithful to the backend `skills/integration/skill.json` param_spec (keys + the to_bool-
 * compatible `harmony2` select values) so a Figure-data re-run round-trips correctly.
 */

import {
  defaultParams,
  skillParamSchema,
  visibleParamFields,
  type ParamField,
} from "./params";

describe("visibleParamFields", () => {
  const schema: ParamField[] = [
    { key: "mode", label: "Mode", type: "select", default: "a", options: [{ value: "a", label: "A" }, { value: "b", label: "B" }] },
    { key: "shown_always", label: "Always", type: "text", default: "" },
    { key: "only_b", label: "Only B", type: "range", default: 1, min: 0, max: 2, step: 0.1, showWhen: { key: "mode", equals: "b" } },
  ];

  it("hides a showWhen field when the gate doesn't match the current value", () => {
    const keys = visibleParamFields(schema, { mode: "a" }).map((f) => f.key);
    expect(keys).toEqual(["mode", "shown_always"]);
  });

  it("reveals a showWhen field once the gate matches", () => {
    const keys = visibleParamFields(schema, { mode: "b" }).map((f) => f.key);
    expect(keys).toEqual(["mode", "shown_always", "only_b"]);
  });

  it("uses the gate field's default when the value is unset", () => {
    // No `mode` in params → gate falls back to default "a" → conditional field hidden.
    const keys = visibleParamFields(schema, {}).map((f) => f.key);
    expect(keys).toEqual(["mode", "shown_always"]);
  });

  it("passes through fields with no showWhen unchanged", () => {
    const plain: ParamField[] = [{ key: "x", label: "X", type: "number", default: 1 }];
    expect(visibleParamFields(plain, {})).toEqual(plain);
  });
});

describe("integration (Melody) schema", () => {
  const schema = skillParamSchema("selom.integration");

  it("is keyed by the backend runtime slug (catalog id strips selom.)", () => {
    expect(skillParamSchema("integration")).toEqual(schema);
    expect(schema.length).toBeGreaterThan(0);
  });

  it("mirrors the backend param_spec keys", () => {
    const keys = schema.map((f) => f.key);
    // All present keys must exist in skills/integration/skill.json param_spec.
    expect(keys).toContain("batch_key");
    expect(keys).toContain("harmony2");
    expect(keys).toContain("theta");
    expect(keys).toContain("alpha");
    expect(keys).toContain("n_hvg");
    expect(keys).toContain("normalize");
  });

  it("exposes the engine as a Melody-branded select, never literal Harmony, with to_bool values", () => {
    const engine = schema.find((f) => f.key === "harmony2")!;
    expect(engine.type).toBe("select");
    expect(engine.options?.map((o) => o.value).sort()).toEqual(["false", "true"]);
    // Branding guard: every engine label says "Melody"; none says bare "Harmony" (GPL).
    for (const o of engine.options ?? []) {
      expect(o.label).toMatch(/Melody/);
      expect(o.label).not.toMatch(/\bHarmony\b(?!2)/);
    }
  });

  it("gates alpha to Harmony2 mode only", () => {
    const alpha = schema.find((f) => f.key === "alpha")!;
    expect(alpha.showWhen).toEqual({ key: "harmony2", equals: "true" });
    // Default engine (2019 method) hides alpha; switching to Harmony2 reveals it.
    expect(visibleParamFields(schema, defaultParams("selom.integration")).map((f) => f.key)).not.toContain("alpha");
    expect(visibleParamFields(schema, { harmony2: "true" }).map((f) => f.key)).toContain("alpha");
  });

  it("defaults the engine to the validated 2019 method (harmony2 off)", () => {
    expect(defaultParams("selom.integration").harmony2).toBe("false");
  });
});

describe("scRNA schemas mirror honoured runner params", () => {
  it("umap_scrna drops the dead resolution knob and surfaces the honoured ones", () => {
    const keys = skillParamSchema("selom.umap_scrna").map((f) => f.key);
    expect(keys).not.toContain("resolution"); // umap_scrna's Leiden ignores it
    expect(keys).toEqual(expect.arrayContaining(["normalize", "n_hvg", "n_neighbors", "n_pcs"]));
  });

  it("cluster keeps resolution (the runner honours it) plus the graph knobs", () => {
    const keys = skillParamSchema("selom.cluster").map((f) => f.key);
    expect(keys).toEqual(expect.arrayContaining(["resolution", "n_neighbors", "n_pcs", "normalize"]));
  });
});

import { describe, expect, it } from "vitest";

/**
 * Unit tests for the spec-driven skill param catalog (P2.5c). The frontend now derives
 * the param SET + types/defaults/min-max from the backend `param_spec` and only decorates
 * it with a presentation overlay — so these tests prove the merge (`paramFieldsFromSpec`):
 * a knob absent from the spec can't be offered (dead-knob guard, drift caught), defaults
 * and ranges come from the spec, and the overlay supplies labels/widget/options/showWhen.
 * The fixture specs mirror the backend `skills/<id>/skill.json` param_specs.
 */

import {
  hasParamControls,
  paramFieldsFromSpec,
  visibleParamFields,
  type BackendParamSpec,
  type ParamField,
} from "./params";
import { SKILL_PARAM_SPECS } from "@/mocks/skill-spec-fixture";

describe("visibleParamFields", () => {
  const schema: ParamField[] = [
    { key: "mode", label: "Mode", type: "select", default: "a", options: [{ value: "a", label: "A" }, { value: "b", label: "B" }] },
    { key: "shown_always", label: "Always", type: "text", default: "" },
    { key: "only_b", label: "Only B", type: "range", default: 1, min: 0, max: 2, step: 0.1, showWhen: { key: "mode", equals: "b" } },
  ];

  it("hides a showWhen field when the gate doesn't match the current value", () => {
    expect(visibleParamFields(schema, { mode: "a" }).map((f) => f.key)).toEqual(["mode", "shown_always"]);
  });

  it("reveals a showWhen field once the gate matches", () => {
    expect(visibleParamFields(schema, { mode: "b" }).map((f) => f.key)).toEqual(["mode", "shown_always", "only_b"]);
  });

  it("uses the gate field's default when the value is unset", () => {
    expect(visibleParamFields(schema, {}).map((f) => f.key)).toEqual(["mode", "shown_always"]);
  });

  it("compares the gate loosely — a boolean true and the string \"true\" are the same gate value", () => {
    const gated: ParamField[] = [
      { key: "on", label: "On", type: "select", default: false, options: [{ value: "false", label: "Off" }, { value: "true", label: "On" }] },
      { key: "extra", label: "Extra", type: "range", default: 1, showWhen: { key: "on", equals: "true" } },
    ];
    // A provenance-stored boolean (true/false), not just the select's "true"/"false" strings, gates correctly.
    expect(visibleParamFields(gated, { on: true }).map((f) => f.key)).toContain("extra");
    expect(visibleParamFields(gated, { on: false }).map((f) => f.key)).not.toContain("extra");
    expect(visibleParamFields(gated, { on: "true" }).map((f) => f.key)).toContain("extra");
  });
});

describe("paramFieldsFromSpec — spec is the source of truth", () => {
  it("drops an overlay knob that is absent from the backend spec (dead-knob guard)", () => {
    // The umap overlay lists normalize + n_hvg + n_neighbors + n_pcs; a spec missing the
    // graph knobs must yield only the field the spec actually declares.
    const spec: BackendParamSpec = { normalize: { type: "bool", default: true } };
    expect(paramFieldsFromSpec("umap_scrna", spec).map((f) => f.key)).toEqual(["normalize"]);
  });

  it("takes default + min/max from the spec, label/widget/step from the overlay", () => {
    const fields = paramFieldsFromSpec("umap_scrna", SKILL_PARAM_SPECS.umap_scrna);
    const nHvg = fields.find((f) => f.key === "n_hvg")!;
    expect(nHvg.default).toBe(0); // from the spec
    expect(nHvg.max).toBe(10000); // from the spec (not a stale FE cap) — the drift this design kills
    expect(nHvg.type).toBe("range"); // widget from the overlay
    expect(nHvg.step).toBe(250); // step from the overlay
    expect(nHvg.label).toBe("Highly variable genes");
  });

  it("prefers the overlay help over the spec note", () => {
    const spec: BackendParamSpec = { normalize: { type: "bool", default: true, note: "backend note" } };
    const f = paramFieldsFromSpec("umap_scrna", spec).find((x) => x.key === "normalize")!;
    expect(f.help).not.toBe("backend note"); // the overlay supplies a friendlier help string
  });

  it("accepts the catalog id (strips the selom. prefix)", () => {
    const a = paramFieldsFromSpec("selom.umap_scrna", SKILL_PARAM_SPECS.umap_scrna);
    const b = paramFieldsFromSpec("umap_scrna", SKILL_PARAM_SPECS.umap_scrna);
    expect(a.map((f) => f.key)).toEqual(b.map((f) => f.key));
  });
});

describe("integration (Melody) fields", () => {
  const fields = paramFieldsFromSpec("selom.integration", SKILL_PARAM_SPECS.integration);

  it("only surfaces keys the backend spec declares", () => {
    for (const f of fields) expect(SKILL_PARAM_SPECS.integration[f.key]).toBeDefined();
    expect(fields.map((f) => f.key)).toEqual(expect.arrayContaining(["batch_key", "harmony2", "theta", "alpha", "n_hvg", "normalize"]));
  });

  it("exposes the engine as a Melody-branded select, never literal Harmony, with to_bool values", () => {
    const engine = fields.find((f) => f.key === "harmony2")!;
    expect(engine.type).toBe("select");
    expect(engine.options?.map((o) => o.value).sort()).toEqual(["false", "true"]);
    for (const o of engine.options ?? []) {
      expect(o.label).toMatch(/Melody/);
      expect(o.label).not.toMatch(/\bHarmony\b(?!2)/);
    }
  });

  it("defaults the engine to the validated 2019 method and gates alpha to Harmony2 mode", () => {
    const engine = fields.find((f) => f.key === "harmony2")!;
    expect(engine.default).toBe(false); // backend bool default
    const alpha = fields.find((f) => f.key === "alpha")!;
    expect(alpha.showWhen).toEqual({ key: "harmony2", equals: "true" });
    expect(alpha.max).toBe(5); // from the spec (the FE used to cap α at 1 — drift killed)
    // Default engine hides alpha; switching to Harmony2 reveals it.
    expect(visibleParamFields(fields, {}).map((f) => f.key)).not.toContain("alpha");
    expect(visibleParamFields(fields, { harmony2: "true" }).map((f) => f.key)).toContain("alpha");
  });
});

describe("options are filtered to the backend enum (drift can't survive)", () => {
  it("annotate drops the unsupported pbmc marker set (backend offers only retinal/retinal_cepo)", () => {
    const marker = paramFieldsFromSpec("annotate", SKILL_PARAM_SPECS.annotate).find((f) => f.key === "marker_set")!;
    const values = marker.options?.map((o) => o.value);
    expect(values).toEqual(["retinal", "retinal_cepo"]);
    expect(values).not.toContain("pbmc");
  });
});

describe("scRNA fields mirror honoured runner params", () => {
  it("umap_scrna drops the dead resolution knob and surfaces the honoured ones", () => {
    const keys = paramFieldsFromSpec("selom.umap_scrna", SKILL_PARAM_SPECS.umap_scrna).map((f) => f.key);
    expect(keys).not.toContain("resolution");
    expect(keys).toEqual(expect.arrayContaining(["normalize", "n_hvg", "n_neighbors", "n_pcs"]));
  });

  it("cluster keeps resolution (the runner honours it) plus the graph knobs", () => {
    const keys = paramFieldsFromSpec("selom.cluster", SKILL_PARAM_SPECS.cluster).map((f) => f.key);
    expect(keys).toEqual(expect.arrayContaining(["resolution", "n_neighbors", "n_pcs", "normalize"]));
  });
});

describe("hasParamControls", () => {
  it("is true for skills with a presentation overlay, false otherwise", () => {
    expect(hasParamControls("selom.integration")).toBe(true);
    expect(hasParamControls("umap_scrna")).toBe(true);
    expect(hasParamControls("selom.go_graph")).toBe(false);
  });
});

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
  isFieldDisabled,
  overlayParamKeys,
  paramFieldsFromSpec,
  parsePairs,
  serializePairs,
  visibleParamFields,
  type BackendParamSpec,
  type ParamDataContext,
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

describe("enabledWhen — show-but-disable keeps the ERG spread/SEM capability discoverable", () => {
  const fields = paramFieldsFromSpec("erg_traces", SKILL_PARAM_SPECS.erg_traces);

  it("keeps Spread + Error metric VISIBLE even when Trace shows ≠ Mean (so SEM/SD/band are discoverable)", () => {
    const visibleRep = visibleParamFields(fields, { central: "representative" }).map((f) => f.key);
    expect(visibleRep).toEqual(expect.arrayContaining(["spread", "error"]));
  });

  it("disables Spread + Error metric until Trace shows = Mean of replicates", () => {
    const spread = fields.find((f) => f.key === "spread")!;
    const error = fields.find((f) => f.key === "error")!;
    expect(spread.enabledWhen).toEqual({ key: "central", equals: "mean" });
    expect(isFieldDisabled(fields, spread, { central: "representative" })).toBe(true);
    expect(isFieldDisabled(fields, spread, { central: "none" })).toBe(true);
    expect(isFieldDisabled(fields, spread, { central: "mean" })).toBe(false);
    expect(isFieldDisabled(fields, error, { central: "mean" })).toBe(false);
  });

  it("uses the gate field's default when unset (central defaults to representative → disabled)", () => {
    const spread = fields.find((f) => f.key === "spread")!;
    expect(isFieldDisabled(fields, spread, {})).toBe(true);
  });

  it("keeps the cosmetic fine-tuning HIDDEN until Mean (showWhen — no clutter on a single trace)", () => {
    const repKeys = visibleParamFields(fields, { central: "representative" }).map((f) => f.key);
    for (const k of ["band_alpha", "band_color", "boundary_lines", "error_every"]) {
      expect(repKeys).not.toContain(k);
    }
    const meanKeys = visibleParamFields(fields, { central: "mean" }).map((f) => f.key);
    expect(meanKeys).toEqual(expect.arrayContaining(["spread", "error", "band_alpha", "boundary_lines"]));
  });

  it("a field without an enabledWhen gate is never disabled", () => {
    const filter = fields.find((f) => f.key === "filter")!;
    expect(isFieldDisabled(fields, filter, { central: "representative" })).toBe(false);
  });
});

describe("hasParamControls", () => {
  it("is true for skills with a presentation overlay, false otherwise", () => {
    expect(hasParamControls("selom.integration")).toBe(true);
    expect(hasParamControls("umap_scrna")).toBe(true);
    // The false case is an id with no overlay — deliberately an UNKNOWN one rather than a real
    // skill that happens to lack controls today. This assertion used to name `go_graph`, and
    // giving that skill its overlay (working down `API_ONLY_KNOBS`) failed a test whose subject
    // is this function, not the backlog. The backlog has its own guard, exact in both directions.
    expect(hasParamControls("selom.not_a_skill")).toBe(false);
  });
});

/**
 * The `pairs=` vocabulary is REACHABLE (selom-shipped-not-reachable). A backend param with no
 * overlay entry renders no control and can only be reached via the API — which is how
 * `assemble-scrna` shipped with no surface. These prove the merge actually yields the controls,
 * not merely that the keys line up (registry-completeness.test.ts already checks that).
 */
describe("distribution-comparison controls (boxplot · violin)", () => {
  const VOCAB = ["order", "add_count", "pairs", "sig_test", "correction"];

  it.each(["boxplot", "violin"])("%s surfaces the whole shared vocabulary", (id) => {
    const keys = paramFieldsFromSpec(id, SKILL_PARAM_SPECS[id]).map((f) => f.key);
    for (const k of VOCAB) expect(keys).toContain(k);
  });

  it.each(["boxplot", "violin"])("%s offers every backend test + correction option", (id) => {
    const fields = paramFieldsFromSpec(id, SKILL_PARAM_SPECS[id]);
    const opts = (k: string) => fields.find((f) => f.key === k)!.options!.map((o) => o.value);
    expect(opts("sig_test")).toEqual(["welch", "student", "mannwhitney"]);
    expect(opts("correction")).toEqual(["none", "bonferroni", "bh"]);
  });

  it("boxplot's pre-existing knobs are reachable too (it had NO overlay before)", () => {
    const keys = paramFieldsFromSpec("boxplot", SKILL_PARAM_SPECS.boxplot).map((f) => f.key);
    for (const k of ["group", "value", "points", "orientation", "notched"]) {
      expect(keys).toContain(k);
    }
  });

  it("both skills present the shared vocabulary in the SAME order", () => {
    const order = (id: string) =>
      paramFieldsFromSpec(id, SKILL_PARAM_SPECS[id])
        .map((f) => f.key)
        .filter((k) => VOCAB.includes(k));
    expect(order("boxplot")).toEqual(order("violin"));
  });

  it("composition takes the ordering half only — no pairs (one value per cell, nothing to test)", () => {
    const keys = paramFieldsFromSpec("composition", SKILL_PARAM_SPECS.composition).map((f) => f.key);
    expect(keys).toContain("order");
    expect(keys).not.toContain("pairs");
    expect(keys).not.toContain("add_count");
  });

  it("defaults still come from the spec, never the overlay", () => {
    const fields = paramFieldsFromSpec("boxplot", SKILL_PARAM_SPECS.boxplot);
    expect(fields.find((f) => f.key === "correction")!.default).toBe("none");
    expect(fields.find((f) => f.key === "add_count")!.default).toBe(false);
  });
});

/**
 * The column / pair pickers (NEXT#1). The whole feature is a THIRD, OPTIONAL input to the merge —
 * the loaded dataset's own schema, already fetched by `/data/inspect` and already persisted on the
 * dataset. These prove the two halves that matter: with no context nothing whatsoever changes
 * (`dataFit`/`design` are legitimately null for demo data, a failed inspect, and every h5ad — where
 * `columns` is empty by construction), and with a context the fields offer what the data actually has.
 */
describe("data-aware param fields — no context means no change", () => {
  const OLD_TYPES = ["range", "number", "text", "switch", "select"];

  it("a context perturbs ONLY the fields that name a column — every other knob is untouched", () => {
    // The real invariant: threading the dataset in must not move a label, a default, a range, a
    // select's options or a showWhen gate anywhere. If it does, the context is not additive.
    const ctx: ParamDataContext = { columns: ["condition", "value"], groups: [] };
    for (const id of Object.keys(overlayParamKeys())) {
      const spec = SKILL_PARAM_SPECS[id];
      if (!spec) continue;
      const bare = paramFieldsFromSpec(id, spec);
      const rich = paramFieldsFromSpec(id, spec, ctx);
      expect(rich.map((f) => f.key)).toEqual(bare.map((f) => f.key)); // same fields, same order
      for (const [i, before] of bare.entries()) {
        const after = rich[i];
        // Strip what the picker is ALLOWED to change; the rest must match exactly.
        const { type: _t, columns: _c, levelsByGroup: _l, levelsFrom: _lf, ...restBefore } = before;
        const { type: _t2, columns: _c2, levelsByGroup: _l2, levelsFrom: _lf2, ...restAfter } = after;
        expect(restAfter).toEqual(restBefore);
        // And the widget only ever changes text → column/pairs, never anything else.
        if (after.type !== before.type) {
          expect(before.type).toBe("text");
          expect(["column", "pairs"]).toContain(after.type);
        }
      }
    }
  });

  it("no skill renders a picker widget without a context — every field stays one of the original five", () => {
    // The guard against a half-wired picker shipping as an empty select: `column`/`pairs` are
    // RESOLVED widgets, emitted only when the vocabulary to fill them exists.
    for (const id of Object.keys(overlayParamKeys())) {
      const spec = SKILL_PARAM_SPECS[id];
      if (!spec) continue;
      for (const f of paramFieldsFromSpec(id, spec)) expect(OLD_TYPES).toContain(f.type);
    }
  });

  it("an empty column list is the same as no context (an h5ad has no columns by construction)", () => {
    const empty: ParamDataContext = { columns: [], groups: [] };
    expect(paramFieldsFromSpec("slope", SKILL_PARAM_SPECS.slope, empty)).toEqual(
      paramFieldsFromSpec("slope", SKILL_PARAM_SPECS.slope),
    );
  });
});

describe("column picker", () => {
  // The real erg_metrics_long.csv shape (verified against the live engine 2026-08-04).
  const ctx: ParamDataContext = {
    columns: ["sample_id", "condition", "eye", "intensity_group", "b_wave_uv", "a_wave_uv"],
    groups: [
      { key: "condition", label: "condition", n_levels: 6, reference_guess: "Control", levels:
        ["AAV8-CMV-GFP", "AAV8-RK-GFP-polyA-stuffer", "AAV8-RK-PDE6B", "AAV8-RK-PDE6B-3UTR", "Control", "Untreated"]
          .map((name) => ({ name, n_replicates: 5, replicate_unit: "rows" })) },
      { key: "eye", label: "eye", n_levels: 2, reference_guess: null, levels:
        ["LE", "RE"].map((name) => ({ name, n_replicates: 105, replicate_unit: "rows" })) },
    ],
  };

  it("offers the dataset's real columns on the fields that name a column", () => {
    const fields = paramFieldsFromSpec("slope", SKILL_PARAM_SPECS.slope, ctx);
    const subject = fields.find((f) => f.key === "subject")!;
    expect(subject.type).toBe("column");
    expect(subject.columns?.map((c) => c.value)).toEqual(ctx.columns);
  });

  it("annotates the categorical columns with their level count, and leaves the rest bare", () => {
    // The honest form of the type glyph mature builders show (Snowflake `A`, Glide `123`): the
    // inspect payload carries no per-column dtype, but it does carry level counts for the
    // categorical ones — which is the distinction that decides group-column vs value-column.
    const cols = paramFieldsFromSpec("slope", SKILL_PARAM_SPECS.slope, ctx)
      .find((f) => f.key === "condition")!.columns!;
    expect(cols.find((c) => c.value === "condition")!.label).toBe("condition — 6 levels");
    expect(cols.find((c) => c.value === "b_wave_uv")!.label).toBe("b_wave_uv");
  });

  it("leaves a NON-column field alone (order stays free text — it is a list, not one column)", () => {
    const fields = paramFieldsFromSpec("boxplot", SKILL_PARAM_SPECS.boxplot, ctx);
    expect(fields.find((f) => f.key === "order")!.type).toBe("text");
    expect(fields.find((f) => f.key === "group")!.type).toBe("column");
  });
});

describe("pair picker", () => {
  const ctx: ParamDataContext = {
    columns: ["condition", "eye", "b_wave_uv"],
    groups: [
      { key: "condition", label: "condition", n_levels: 3, reference_guess: "Control", levels:
        ["Control", "Treated", "Rescue"].map((name) => ({ name, n_replicates: 4, replicate_unit: "rows" })) },
      { key: "eye", label: "eye", n_levels: 2, reference_guess: null, levels:
        ["LE", "RE"].map((name) => ({ name, n_replicates: 6, replicate_unit: "rows" })) },
    ],
  };
  const fields = paramFieldsFromSpec("boxplot", SKILL_PARAM_SPECS.boxplot, ctx);
  const pairsWith = (params: Record<string, string>) =>
    visibleParamFields(fields, params).find((f) => f.key === "pairs")!;

  it("stays a text field while the group column is on auto-detect", () => {
    // Blank = the backend's auto-detect (first non-numeric column), a rule the frontend cannot
    // evaluate. Guessing would offer levels from a column the run is not grouping by.
    expect(pairsWith({}).type).toBe("text");
  });

  it("becomes a row-list of the CHOSEN column's levels once a group column is picked", () => {
    const pairs = pairsWith({ group: "condition" });
    expect(pairs.type).toBe("pairs");
    expect(pairs.options?.map((o) => o.value)).toEqual(["Control", "Treated", "Rescue"]);
  });

  it("follows the group column — picking `eye` offers LE/RE, never the condition levels", () => {
    expect(pairsWith({ group: "eye" }).options?.map((o) => o.value)).toEqual(["LE", "RE"]);
  });

  it("falls back to text for a column with no known levels (a value column, or a typo)", () => {
    expect(pairsWith({ group: "b_wave_uv" }).type).toBe("text");
    expect(pairsWith({ group: "nope" }).type).toBe("text");
  });

  it("violin keeps the vocabulary but NOT the widget — its clusters don't exist until the run", () => {
    const violin = paramFieldsFromSpec("violin", SKILL_PARAM_SPECS.violin, ctx);
    expect(violin.find((f) => f.key === "pairs")!.type).toBe("text");
    // …and the shared vocabulary is still all there, in the same order as boxplot.
    const shared = (s: ParamField[]) =>
      s.map((f) => f.key).filter((k) => ["order", "add_count", "pairs", "sig_test", "correction"].includes(k));
    expect(shared(violin)).toEqual(shared(fields));
  });
});

describe("level picker — the single-select sibling of `pairs` (docs/deg-panel/spec.md D2)", () => {
  /** An h5ad: `columns` is [] BY CONSTRUCTION (`engine/compat.py:175`), which is exactly why the
   *  obs knobs read `groups`/`sampleColumns` and not `columns`. */
  const h5ad: ParamDataContext = {
    columns: [],
    sampleColumns: ["orig.ident", "donor"],
    groups: [
      { key: "genotype", label: "genotype", n_levels: 2, reference_guess: "WT", levels:
        ["WT", "KO"].map((name) => ({ name, n_replicates: 3, replicate_unit: "samples" })) },
      { key: "cell_type", label: "cell_type", n_levels: 3, reference_guess: null, levels:
        ["Rod", "Cone", "Muller"].map((name) => ({ name, n_replicates: 6, replicate_unit: "samples" })) },
    ],
  };
  const fieldsFor = (ctx: ParamDataContext, params: Record<string, string> = {}) =>
    visibleParamFields(paramFieldsFromSpec("deg", SKILL_PARAM_SPECS.deg, ctx), {
      mode: "pseudobulk",
      ...params,
    });
  const levelField = (key: string, ctx: ParamDataContext, params: Record<string, string> = {}) =>
    fieldsFor(ctx, params).find((f) => f.key === key)!;

  it("stays text while its column field is blank and several groupings are on offer", () => {
    // Same rule as `pairs`, and for the same reason: blank means the backend's auto-detect, which
    // resolves through alias lists the frontend cannot evaluate.
    expect(levelField("reference", h5ad).type).toBe("text");
  });

  it("offers the CHOSEN column's real levels once that column is picked", () => {
    const ref = levelField("reference", h5ad, { condition_col: "genotype" });
    expect(ref.type).toBe("level");
    expect(ref.options?.map((o) => o.value)).toEqual(["WT", "KO"]);
  });

  it("follows its own column field — `label` reads label_col, not condition_col", () => {
    // The two level fields on this panel point at DIFFERENT columns. A shared resolver that read
    // one sibling for both would put cell types in the contrast box.
    const params = { condition_col: "genotype", label_col: "cell_type" };
    expect(levelField("reference", h5ad, params).options?.map((o) => o.value)).toEqual(["WT", "KO"]);
    expect(levelField("label", h5ad, params).options?.map((o) => o.value)).toEqual([
      "Rod", "Cone", "Muller",
    ]);
  });

  it("annotates the engine's reference guess on `reference` ONLY, and never pre-selects it", () => {
    const params = { condition_col: "genotype" };
    const ref = levelField("reference", h5ad, params);
    expect(ref.options?.find((o) => o.value === "WT")!.label).toBe("WT — likely control");
    // `treatment` carries no hint: "likely control" is advice about the baseline, and repeating it
    // in the treatment box argues against the choice the user is making there.
    expect(levelField("treatment", h5ad, params).options?.find((o) => o.value === "WT")!.label)
      .toBe("WT");
    // The guess annotates; it does not become the value. Writing it in would turn the backend's
    // inferred default into a recorded user choice.
    expect(ref.default).toBe("");
  });

  it("uses the SOLE candidate when the column field is blank — the bulk counts-CSV case", () => {
    // A bulk counts table has no condition COLUMN: the levels come from the sample-column names,
    // which the engine publishes as one candidate under the `__column_names__` sentinel
    // (`engine/questionnaire.py:189`). There is no sibling field that could name it, so without
    // this rule every bulk user would be back on a text box.
    const bulk: ParamDataContext = {
      columns: ["ctrl_1", "ctrl_2", "treat_1", "treat_2"],
      groups: [
        { key: "__column_names__", label: "sample columns", n_levels: 2, reference_guess: "ctrl",
          levels: ["ctrl", "treat"].map((name) => ({ name, n_replicates: 2, replicate_unit: "samples" })) },
      ],
    };
    const ref = visibleParamFields(paramFieldsFromSpec("deg", SKILL_PARAM_SPECS.deg, bulk), {
      mode: "bulk",
    }).find((f) => f.key === "reference")!;
    expect(ref.type).toBe("level");
    expect(ref.options?.map((o) => o.value)).toEqual(["ctrl", "treat"]);
  });

  it("falls back to text with no context at all (byte-identical to life before pickers)", () => {
    const bare = paramFieldsFromSpec("deg", SKILL_PARAM_SPECS.deg);
    expect(bare.find((f) => f.key === "reference")!.type).toBe("text");
    expect(bare.find((f) => f.key === "sample_col")!.type).toBe("text");
    expect(bare.find((f) => f.key === "groupby")!.type).toBe("text");
  });
});

describe("obs-column pickers — `columnsFrom` (docs/deg-panel/spec.md D3)", () => {
  const h5ad: ParamDataContext = {
    columns: [],
    sampleColumns: ["orig.ident", "donor"],
    groups: [
      { key: "genotype", label: "genotype", n_levels: 2, reference_guess: "WT", levels:
        ["WT", "KO"].map((name) => ({ name, n_replicates: 3, replicate_unit: "samples" })) },
    ],
  };
  const deg = (ctx: ParamDataContext) => paramFieldsFromSpec("deg", SKILL_PARAM_SPECS.deg, ctx);

  it("⚑ serves the single-cell knobs, which the DEFAULT source cannot — h5ad `columns` is []", () => {
    // Review finding (f): `resolveColumns` reads ctx.columns, empty by construction for an h5ad,
    // so a `column` widget on an obs knob was a text box on exactly the files it consumes.
    const fields = deg(h5ad);
    expect(fields.find((f) => f.key === "condition_col")!.type).toBe("column");
    expect(fields.find((f) => f.key === "condition_col")!.columns?.map((c) => c.value))
      .toEqual(["genotype"]);
  });

  it("draws the replicate column from `sample_col_candidates`, not from the group candidates", () => {
    // Detected for exactly this (questionnaire `_sample_col_candidates`) and never threaded until
    // now. A sample id is not a grouping factor, so the two lists are deliberately different.
    expect(deg(h5ad).find((f) => f.key === "sample_col")!.columns?.map((c) => c.value))
      .toEqual(["orig.ident", "donor"]);
  });

  it("keeps the level-count annotation on a grouping column (`genotype — 2 levels`)", () => {
    expect(deg(h5ad).find((f) => f.key === "condition_col")!.columns![0].label)
      .toBe("genotype — 2 levels");
  });

  it("`groupby` is a COMBOBOX, because Leiden does not exist until the run", () => {
    // A closed select would make the runner's commonest resolved value unofferable: when the named
    // column is absent, `deg/run_real.py:96-102` clusters the cells itself and groups by `leiden`.
    const groupby = deg(h5ad).find((f) => f.key === "groupby")!;
    expect(groupby.type).toBe("combobox");
    expect(groupby.columns?.map((c) => c.value)).toEqual(["genotype"]);
  });

  it("a design-SHEET column stays text — the context carries no design sheet to pick from", () => {
    expect(deg(h5ad).find((f) => f.key === "time_col")!.type).toBe("text");
    expect(deg(h5ad).find((f) => f.key === "covariate_col")!.type).toBe("text");
  });
});

describe("mode gating — four engines, one panel (docs/deg-panel/spec.md D1)", () => {
  const keys = (params: Record<string, string>) =>
    visibleParamFields(paramFieldsFromSpec("deg", SKILL_PARAM_SPECS.deg), params).map((f) => f.key);

  it("⚑ `auto` shows the scRNA AND bulk knobs — the two engines auto can resolve to", () => {
    // The spec's first draft said "only the shared knobs", which would have HIDDEN the
    // reference/treatment boxes that ship today — a regression dressed as a reachability fix.
    // `run_real.py:31-33`: auto picks scRNA for .h5ad and bulk for everything else, and never
    // picks pseudobulk or time-course.
    const k = keys({});
    expect(k).toEqual(expect.arrayContaining(["reference", "treatment", "groupby", "method",
      "normalize", "group_col", "group_regex", "normalization", "min_count", "top_n"]));
  });

  it("`auto` hides the nine knobs no auto-resolved run can read", () => {
    const k = keys({});
    for (const hidden of ["sample_col", "condition_col", "label_col", "label", "min_cells",
      "time_col", "covariate_col", "group_val"]) {
      expect(k).not.toContain(hidden);
    }
  });

  it("naming a mode narrows the panel to that engine's knobs", () => {
    expect(keys({ mode: "scrna" })).toEqual(["mode", "top_n", "groupby", "method", "normalize"]);
    expect(keys({ mode: "timecourse" })).toEqual(["mode", "top_n", "time_col", "covariate_col",
      "group_val", "group_col", "min_count"]);
  });

  it("`min_count` is hidden on scRNA alone — the one path that never fits a count model", () => {
    // It is read by bulk, pseudobulk AND time-course, which is why it uses `not` rather than
    // listing three modes.
    expect(keys({ mode: "scrna" })).not.toContain("min_count");
    for (const mode of ["bulk", "pseudobulk", "timecourse"]) {
      expect(keys({ mode })).toContain("min_count");
    }
  });

  it("`normalization` reaches the two DESeq2 contrast paths and neither of the others", () => {
    // The `oneOf` case: no single `equals` and no `not` can express "bulk or pseudobulk".
    for (const mode of ["bulk", "pseudobulk"]) expect(keys({ mode })).toContain("normalization");
    for (const mode of ["scrna", "timecourse"]) expect(keys({ mode })).not.toContain("normalization");
  });
});

describe("pairs wire format — the picker authors the SAME string the backend already parses", () => {
  it("round-trips a complete list", () => {
    expect(parsePairs("Control~Treated, Control~Rescue")).toEqual([
      ["Control", "Treated"],
      ["Control", "Rescue"],
    ]);
    expect(serializePairs([["Control", "Treated"], ["Control", "Rescue"]])).toBe(
      "Control~Treated, Control~Rescue",
    );
  });

  it("round-trips an INCOMPLETE row, which is what lets the picker hold no local state", () => {
    // "+ Add" emits an empty row; the user fills it in. `parse_pairs` on the backend requires both
    // sides non-empty and documents that it skips empty chunks, so a half-built row draws no
    // bracket rather than failing the run.
    expect(serializePairs([["Control", ""], ["", ""]])).toBe("Control~, ~");
    expect(parsePairs("Control~, ~")).toEqual([["Control", ""], ["", ""]]);
  });

  it("ignores a chunk that is not a pair at all (a hand-typed stray survives as nothing)", () => {
    expect(parsePairs("Control, ,Treated~Rescue")).toEqual([["Treated", "Rescue"]]);
  });

  it("tolerates the spacing a hand-typed value arrives with", () => {
    expect(parsePairs(" Control ~ Treated ,Control~Rescue ")).toEqual([
      ["Control", "Treated"],
      ["Control", "Rescue"],
    ]);
  });
});

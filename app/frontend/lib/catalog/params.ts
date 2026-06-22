import { runtimeSkillId } from "@/lib/skills-api";
import type { SkillParams } from "@/lib/skills-api";

/**
 * Skill parameter controls — derived from the backend, decorated by the frontend.
 *
 * The contract source of truth is the backend `param_spec` (every
 * `skills/<id>/skill.json`, served verbatim by `GET /skills/{id}`). The set of
 * tunable knobs, their types, defaults, and min/max all come from there — so a
 * knob the runner doesn't have (or a default/range that drifted) can no longer
 * exist in the UI. The frontend keeps only a THIN *presentation overlay*
 * (`PRESENTATION`): friendly labels, help text, the rendered widget, slider step,
 * branded `select` options, and conditional `showWhen` reveals — the polish the
 * spec doesn't carry.
 *
 * `paramFieldsFromSpec(id, spec)` merges the two into the rendered `ParamField[]`.
 * It is pure (no fetch); `useSkillParams` (lib/catalog/use-skill-params) loads the
 * spec and calls it. Skills with no overlay entry simply render no inline controls
 * and run with their backend defaults.
 */

/** One backend `param_spec` entry (skills/<id>/skill.json → SkillSpec.param_spec). */
export interface BackendParam {
  type: "int" | "float" | "str" | "bool";
  default: number | string | boolean;
  min?: number;
  max?: number;
  /** Enum of allowed string values (backend-declared); the overlay may relabel them. */
  options?: string[];
  /** Backend note — used as the help text when the overlay doesn't supply its own. */
  note?: string;
}
export type BackendParamSpec = Record<string, BackendParam>;

/** A rendered parameter control (what `ParamControl` consumes). */
export interface ParamField {
  key: string;
  label: string;
  type: "range" | "number" | "text" | "switch" | "select";
  default: number | string | boolean;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  help?: string;
  /** Choices for a `select` field. */
  options?: { value: string; label: string }[];
  /**
   * Conditional visibility: only render this field when another field in the same
   * schema currently equals `equals`. Lets a "method" select reveal method-specific
   * knobs (e.g. Melody's `alpha` only when the engine is set to Harmony2 mode). The
   * field still carries its default, so it is always sendable — just hidden until
   * relevant. See `visibleParamFields`.
   */
  showWhen?: { key: string; equals: string | number | boolean };
}

/**
 * Per-skill presentation overlay, keyed by backend runtime slug. Lists ONLY the
 * knobs worth surfacing (the rest are advanced and run with backend defaults), in
 * render order, and carries the polish the backend spec lacks. The field's
 * existence + type/default/min/max are read from the spec at merge time, so an
 * overlay entry whose key is absent from the spec is dropped (dead-knob guard).
 */
export interface ParamPresentation {
  key: string;
  label: string;
  /** Rendered widget — the spec only knows int/float/str/bool, so the widget choice
   *  (range vs number, bool→switch, str→select) lives here. */
  type: ParamField["type"];
  step?: number;
  placeholder?: string;
  help?: string;
  options?: { value: string; label: string }[];
  showWhen?: { key: string; equals: string | number | boolean };
}

const PRESENTATION: Record<string, ParamPresentation[]> = {
  // scRNA UMAP — the prep/QC + embedding knobs the runner honours. Resolution lives on
  // `cluster`, not here, so it isn't surfaced (the UMAP runner's Leiden uses the default).
  umap_scrna: [
    { key: "normalize", label: "Normalize input", type: "switch", help: "Log-normalize raw counts. Off for already-normalized data." },
    { key: "n_hvg", label: "Highly variable genes", type: "range", step: 250, help: "Top-N variable genes used for PCA (0 = all genes; ~2000 is the standard choice)." },
    { key: "n_neighbors", label: "Neighbours (kNN)", type: "range", step: 1, help: "Local neighbourhood size for the graph + UMAP." },
    { key: "n_pcs", label: "Principal components", type: "range", step: 1, help: "PCs that build the neighbour graph." },
  ],
  // Leiden clustering — the runner honours resolution + the same graph knobs.
  cluster: [
    { key: "resolution", label: "Cluster resolution", type: "range", step: 0.1, help: "Higher = more, finer clusters." },
    { key: "n_neighbors", label: "Neighbours (kNN)", type: "range", step: 1, help: "Local neighbourhood size for the graph." },
    { key: "n_pcs", label: "Principal components", type: "range", step: 1, help: "PCs that build the neighbour graph." },
    { key: "normalize", label: "Normalize input", type: "switch", help: "Log-normalize raw counts. Off for already-normalized data." },
  ],
  // scRNA batch integration — Selom Melody, our clean-room Harmony-method engine (no GPL; see
  // skills/integration/melody.py). The engine select reveals Harmony2-only knobs (alpha) when in
  // Harmony2 mode — never exposes literal "Harmony" (GPL); the engine is always branded "Melody".
  // `harmony2` is a backend bool; the select carries the to_bool-compatible "true"/"false" strings.
  integration: [
    { key: "batch_key", label: "Batch key", type: "text", placeholder: "e.g. sample, donor, batch", help: "The obs column labelling each library/batch to correct across (falls back to a known alias if absent)." },
    {
      key: "harmony2", label: "Integration engine", type: "select",
      options: [
        { value: "false", label: "Selom Melody — 2019 method" },
        { value: "true", label: "Selom Melody — Harmony2 mode" },
      ],
      help: "Melody is Selom's clean-room batch-correction engine. Harmony2 mode adds the 2026 anti-over-integration improvements for large, heterogeneous data.",
    },
    { key: "theta", label: "Mixing strength (θ)", type: "range", step: 0.5, help: "Higher = stronger batch mixing. Too high can blur real cell-type differences." },
    {
      key: "alpha", label: "Outlier-batch shrinkage (α)", type: "range", step: 0.05,
      help: "Harmony2 only — shrinks the correction of batches that contribute few cells to a cluster, preventing over-integration.",
      showWhen: { key: "harmony2", equals: "true" },
    },
    { key: "n_hvg", label: "Highly variable genes", type: "range", step: 250, help: "Top-N variable genes for PCA before integration (0 = all; ~2000–5000 is standard for multi-batch)." },
    { key: "normalize", label: "Normalize input", type: "switch", help: "Log-normalize raw counts. Off for already-normalized data." },
  ],
  deg: [
    { key: "reference", label: "Reference group", type: "text", placeholder: "e.g. control", help: "Baseline condition for the contrast." },
    { key: "treatment", label: "Treatment group", type: "text", placeholder: "e.g. treated" },
  ],
  violin: [{ key: "gene", label: "Marker gene", type: "text", placeholder: "e.g. MS4A1" }],
  heatmap: [
    { key: "n_genes", label: "Genes shown", type: "range", step: 5, help: "Top genes by variance (bulk) or markers per cluster (scRNA)." },
    {
      key: "dendrogram", label: "Dendrogram", type: "select",
      options: [
        { value: "none", label: "None" },
        { value: "row", label: "Row tree" },
      ],
      help: "Draw the row hierarchical-clustering tree alongside the heatmap.",
    },
  ],
  // Gene-set builder Phase A: apply a corpus source / a highlight panel from "Gene Sets".
  enrichment: [
    {
      key: "gene_sets", label: "Reference library", type: "select",
      options: [
        { value: "go", label: "Gene Ontology" },
        { value: "wikipathways", label: "WikiPathways" },
        { value: "curated", label: "Selom curated" },
        { value: "all", label: "All sources" },
      ],
      help: "The license-clean library the over-representation test scores against.",
    },
    {
      key: "direction", label: "Direction", type: "select",
      options: [
        { value: "combined", label: "Combined" },
        { value: "split", label: "Up / down split" },
      ],
      help: "Split scores up- and down-regulated genes separately (diverging dotplot). Needs a fold-change column.",
    },
  ],
  volcano: [
    {
      key: "highlight", label: "Highlight genes", type: "text",
      placeholder: "e.g. RHO, GNAT1, PDE6B",
      help: "Mark + label a gene-set panel on the plot (comma-separated). Applied from “Gene Sets”.",
    },
  ],
  scorecard: [
    {
      key: "layout", label: "Layout", type: "select",
      options: [
        { value: "radar", label: "Radar (spider)" },
        { value: "heatmap", label: "Heatmap (metrics × conditions)" },
      ],
      help: "Two forms of the same benchmark (paper Fig 6F).",
    },
    {
      key: "invert_metrics", label: "Lower-is-better metrics", type: "text", placeholder: "e.g. off_target, error_rate",
      help: "Comma-separated metrics where lower is better — inverted so higher always reads as better.",
    },
  ],
  proteomics_de: [
    { key: "group_a", label: "Group A", type: "text", placeholder: "e.g. infected", help: "Sample-name substring for the first group." },
    { key: "group_b", label: "Group B", type: "text", placeholder: "e.g. control", help: "Sample-name substring for the second group." },
    {
      key: "stats", label: "Statistics", type: "select",
      options: [
        { value: "welch", label: "Welch t-test" },
        { value: "moderated", label: "Moderated (limma-style)" },
      ],
      help: "Moderated borrows variance across proteins for better power at small N.",
    },
  ],
  // Proprietary ERG module — the few knobs a vision scientist reaches for before publishing:
  // smoothing (filter + low-pass cutoff) and the shared scale-bar size. Colours/labels are then
  // edited directly on the figure (JSON-Patch). The `role` knob is pipeline-level, not surfaced.
  erg_traces: [
    { key: "filter", label: "Clean traces", type: "switch", help: "Notch line-noise + low-pass, keeping oscillatory potentials (“clean flats, keep OPs”)." },
    { key: "lowpass_hz", label: "Low-pass cutoff (Hz)", type: "range", step: 10, help: "Lower = smoother. Default 120 Hz cuts mains/instrument hum while keeping the partial-rescue b-wave; raise toward 300 Hz to retain all oscillatory potentials." },
    { key: "scale_uv", label: "Scale bar — amplitude (µV)", type: "number", step: 10, help: "Vertical scale-bar length." },
    { key: "scale_ms", label: "Scale bar — time (ms)", type: "number", step: 10, help: "Horizontal scale-bar length." },
  ],
  // ERG b-wave bar — one flash intensity, mean ± SEM + every eye as a point (reviewer ask).
  erg_bwave_bar: [
    {
      key: "intensity_group", label: "Flash intensity", type: "select",
      options: [
        { value: "Group1", label: "−1.7 log cd·s/m² (dimmest)" },
        { value: "Group2", label: "−0.8 log cd·s/m²" },
        { value: "Group3", label: "0.1 log cd·s/m²" },
        { value: "Group4", label: "1.0 log cd·s/m²" },
        { value: "Group5", label: "1.9 log cd·s/m²" },
        { value: "Group6", label: "2.8 log cd·s/m²" },
        { value: "Group7", label: "3.1 log cd·s/m² (brightest)" },
      ],
      help: "Which scotopic flash the per-condition b-wave bar is taken at.",
    },
    { key: "points", label: "Show individual eyes", type: "switch", help: "Overlay each eye as a data point (reviewer ask for quantitative graphs)." },
  ],
  // ERG intensity-response — b-wave vs flash energy with the adjustable Naka-Rushton fit.
  erg_intensity_response: [
    { key: "fit", label: "Naka-Rushton fit", type: "switch", help: "Overlay the saturating V = Vmax·Iⁿ/(Iⁿ+Kⁿ) curve per condition." },
    {
      key: "nr_slope", label: "Fit slope (n)", type: "range", step: 0.1,
      help: "0 = auto-fit each condition's slope (falling back to n=1 where under-constrained). Set a value to fix the slope and compare all conditions at one slope.",
    },
    { key: "min_r2", label: "Fit-quality gate (R²)", type: "range", step: 0.05, help: "Minimum R² to report a fit; lower keeps more marginal fits, higher only the cleanest." },
  ],
  annotate: [
    {
      key: "marker_set", label: "Marker panel", type: "select",
      options: [
        { value: "retinal", label: "Retinal (canonical)" },
        { value: "retinal_cepo", label: "Retinal — Cepo (Kim 2023)" },
      ],
      help: "Curated marker panel scored per cluster to assign cell types.",
    },
  ],
};

const _warnedDeadKnobs = new Set<string>();

function warnDeadKnob(id: string, key: string): void {
  if (process.env.NODE_ENV === "production") return;
  const tag = `${id}:${key}`;
  if (_warnedDeadKnobs.has(tag)) return;
  _warnedDeadKnobs.add(tag);
  // Dev signal: the overlay drifted from the backend param_spec.
  console.warn(
    `[params] presentation overlay for "${id}" references param "${key}" that is absent from the backend param_spec — dropping it.`,
  );
}

/** `select` choices: overlay labels (filtered to the spec enum so a stale value can't
 *  survive), else the spec enum verbatim. Non-select fields carry no options. */
function resolveOptions(pres: ParamPresentation, ps: BackendParam): ParamField["options"] {
  if (pres.type !== "select") return undefined;
  if (pres.options) {
    return ps.options ? pres.options.filter((o) => ps.options!.includes(o.value)) : pres.options;
  }
  return ps.options?.map((v) => ({ value: v, label: v }));
}

function mergeField(pres: ParamPresentation, ps: BackendParam): ParamField {
  return {
    key: pres.key,
    label: pres.label,
    type: pres.type,
    default: ps.default, // contract: the default/range come from the backend spec, never the overlay
    min: ps.min,
    max: ps.max,
    step: pres.step,
    placeholder: pres.placeholder,
    help: pres.help ?? ps.note,
    options: resolveOptions(pres, ps),
    showWhen: pres.showWhen,
  };
}

/**
 * Build the rendered fields for a skill by merging its presentation overlay over the
 * backend `param_spec`. Pure + synchronous (the caller supplies the loaded spec). The
 * field SET, types, defaults, and min/max come from `spec`; labels/help/widget/step/
 * options/showWhen from the overlay. An overlay key not in the spec is dropped (logged
 * in dev) so the UI can never offer a knob the runner doesn't accept.
 */
export function paramFieldsFromSpec(catalogOrRuntimeId: string, spec: BackendParamSpec): ParamField[] {
  const overlay = PRESENTATION[runtimeSkillId(catalogOrRuntimeId)] ?? [];
  const out: ParamField[] = [];
  for (const pres of overlay) {
    const ps = spec[pres.key];
    if (!ps) {
      warnDeadKnob(catalogOrRuntimeId, pres.key);
      continue;
    }
    out.push(mergeField(pres, ps));
  }
  return out;
}

/** True when this skill surfaces inline controls (has a presentation overlay). */
export function hasParamControls(catalogOrRuntimeId: string): boolean {
  return (PRESENTATION[runtimeSkillId(catalogOrRuntimeId)] ?? []).length > 0;
}

/**
 * The fields to render right now, given the current param values — drops any `showWhen`
 * field whose gate doesn't match (e.g. Melody's `alpha` while the engine is the 2019
 * method). Shared by both surfaces (Workbench + Figure-data) so the conditional reveal is
 * identical wherever a skill is parameterised. The gate reads the *effective* value (the
 * current param or, if unset, that gate field's default) and compares loosely (a backend
 * bool `false` and the select's string `"false"` are the same gate value).
 */
export function visibleParamFields(schema: ParamField[], params: SkillParams): ParamField[] {
  return schema.filter((f) => {
    if (!f.showWhen) return true;
    const gate = f.showWhen;
    const current = params[gate.key] ?? schema.find((x) => x.key === gate.key)?.default;
    return current === gate.equals || String(current) === String(gate.equals);
  });
}

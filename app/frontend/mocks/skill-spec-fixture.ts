import type { BackendParamSpec } from "@/lib/catalog/params";

/**
 * Offline `param_spec` fixture for `GET /api/skills/:id` (the per-skill describe
 * endpoint, app/backend/main.py → SkillSpec.param_spec). Mirrors the backend
 * `skills/<id>/skill.json` param_specs so `dev:mock` renders the spec-driven param
 * controls exactly like the live backend. Keyed by backend runtime slug. Only the
 * skills that surface inline controls (those with a presentation overlay) are needed;
 * anything else falls through to `{}` (no controls), matching fail-soft behaviour.
 *
 * Dev/test only — the live FE reads the real spec; this is the offline twin.
 */
export const SKILL_PARAM_SPECS: Record<string, BackendParamSpec> = {
  umap_scrna: {
    n_neighbors: { type: "int", default: 15, min: 2, max: 100 },
    n_pcs: { type: "int", default: 50, min: 2, max: 200 },
    n_hvg: { type: "int", default: 0, min: 0, max: 10000, note: "select top-N highly variable genes before PCA (0 = all genes; ~2000 recommended)" },
    color_by: { type: "str", default: "leiden" },
    normalize: { type: "bool", default: true },
    embedding: { type: "str", default: "" },
  },
  cluster: {
    resolution: { type: "float", default: 1.0, min: 0.1, max: 4.0 },
    n_neighbors: { type: "int", default: 15, min: 2, max: 100 },
    n_pcs: { type: "int", default: 50, min: 2, max: 200 },
    normalize: { type: "bool", default: true },
  },
  integration: {
    batch_key: { type: "str", default: "sample" },
    n_neighbors: { type: "int", default: 15, min: 2, max: 100 },
    n_pcs: { type: "int", default: 50, min: 2, max: 200 },
    n_hvg: { type: "int", default: 0, min: 0, max: 10000 },
    color_by: { type: "str", default: "" },
    normalize: { type: "bool", default: true },
    theta: { type: "float", default: 2.0, min: 0.0, max: 10.0 },
    max_iter_harmony: { type: "int", default: 10, min: 1, max: 50 },
    harmony2: { type: "bool", default: false },
    alpha: { type: "float", default: 0.2, min: 0.0, max: 5.0 },
  },
  deg: {
    mode: { type: "str", default: "auto" },
    groupby: { type: "str", default: "leiden" },
    method: { type: "str", default: "wilcoxon" },
    top_n: { type: "int", default: 15, min: 5, max: 50 },
    normalize: { type: "bool", default: true },
    reference: { type: "str", default: "" },
    treatment: { type: "str", default: "" },
  },
  violin: {
    gene: { type: "str", default: "" },
    groupby: { type: "str", default: "leiden" },
    resolution: { type: "float", default: 1.0, min: 0.1, max: 4.0 },
    normalize: { type: "bool", default: true },
  },
  heatmap: {
    n_genes: { type: "int", default: 20, min: 5, max: 100 },
    groupby: { type: "str", default: "leiden" },
    dendrogram: { type: "str", default: "none", options: ["none", "row"] },
  },
  enrichment: {
    top_n: { type: "int", default: 12, min: 3, max: 40 },
    gene_sets: { type: "str", default: "go", options: ["go", "wikipathways", "curated", "all"] },
    direction: { type: "str", default: "combined", options: ["combined", "split"] },
    fdr_threshold: { type: "float", default: 0.05, min: 0.0, max: 1.0 },
    fc_threshold: { type: "float", default: 0.0, min: 0.0, max: 5.0 },
  },
  volcano: {
    fc_threshold: { type: "float", default: 1.0, min: 0.0, max: 5.0 },
    fdr_threshold: { type: "float", default: 0.05, min: 0.0, max: 1.0 },
    top_n: { type: "int", default: 10, min: 0, max: 50 },
    highlight: { type: "str", default: "" },
  },
  scorecard: {
    layout: { type: "str", default: "radar", options: ["radar", "heatmap"] },
    normalize: { type: "bool", default: true },
    fill: { type: "bool", default: true },
    max_rows: { type: "int", default: 8, min: 1, max: 20 },
    invert_metrics: { type: "str", default: "" },
  },
  proteomics_de: {
    group_a: { type: "str", default: "" },
    group_b: { type: "str", default: "" },
    fc_threshold: { type: "float", default: 1.0, min: 0.0, max: 5.0 },
    fdr_threshold: { type: "float", default: 0.05, min: 0.0, max: 1.0 },
    top_n: { type: "int", default: 10, min: 0, max: 50 },
    stats: { type: "str", default: "welch", options: ["welch", "moderated"] },
  },
  erg_traces: {
    role: { type: "str", default: "representative" },
    filter: { type: "bool", default: true },
    lowpass_hz: { type: "float", default: 120.0, min: 30.0, max: 1000.0 },
    scale_uv: { type: "float", default: 200.0, min: 10.0, max: 1000.0 },
    scale_ms: { type: "float", default: 100.0, min: 10.0, max: 500.0 },
  },
  erg_bwave_bar: {
    intensity_group: { type: "str", default: "Group4" },
    value_col: { type: "str", default: "b_wave_uv" },
    points: { type: "bool", default: true },
  },
  erg_intensity_response: {
    value_col: { type: "str", default: "b_wave_uv" },
    fit: { type: "bool", default: true },
    nr_slope: { type: "float", default: 0.0, min: 0.0, max: 4.0 },
    min_r2: { type: "float", default: 0.3, min: 0.0, max: 1.0 },
  },
  annotate: {
    marker_set: { type: "str", default: "retinal", options: ["retinal", "retinal_cepo"] },
    groupby: { type: "str", default: "leiden" },
    embedding: { type: "str", default: "X_umap" },
    normalize: { type: "bool", default: true },
  },
};

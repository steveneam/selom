import { runtimeSkillId } from "@/lib/skills-api";
import type { SkillParams } from "@/lib/skills-api";

/**
 * Inline, tweak-before-run parameters for Verified skills — the few knobs a
 * bench scientist actually reaches for, with smart defaults so a one-click
 * "Apply" still does the right thing. Keyed by the backend runtime slug
 * (`selom.umap_scrna` -> `umap_scrna`). Kept deliberately small and accurate to
 * the real runners; skills without an entry simply run with their defaults.
 */
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
}

const SCHEMAS: Record<string, ParamField[]> = {
  umap_scrna: [
    { key: "resolution", label: "Cluster resolution", type: "range", default: 1.0, min: 0.1, max: 2.0, step: 0.1, help: "Higher = more, finer clusters." },
    { key: "normalize", label: "Normalize input", type: "switch", default: true, help: "Off for already-normalized data." },
  ],
  cluster: [
    { key: "resolution", label: "Cluster resolution", type: "range", default: 1.0, min: 0.1, max: 2.0, step: 0.1, help: "Higher = more, finer clusters." },
    { key: "normalize", label: "Normalize input", type: "switch", default: true },
  ],
  deg: [
    { key: "reference", label: "Reference group", type: "text", default: "", placeholder: "e.g. control", help: "Baseline condition for the contrast." },
    { key: "treatment", label: "Treatment group", type: "text", default: "", placeholder: "e.g. treated" },
  ],
  violin: [{ key: "gene", label: "Marker gene", type: "text", default: "", placeholder: "e.g. MS4A1" }],
  heatmap: [
    { key: "n_genes", label: "Genes shown", type: "range", default: 20, min: 5, max: 100, step: 5, help: "Top genes by variance (bulk) or markers per cluster (scRNA)." },
    {
      key: "dendrogram", label: "Dendrogram", type: "select", default: "none",
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
      key: "gene_sets", label: "Reference library", type: "select", default: "go",
      options: [
        { value: "go", label: "Gene Ontology" },
        { value: "wikipathways", label: "WikiPathways" },
        { value: "curated", label: "Selom curated" },
        { value: "all", label: "All sources" },
      ],
      help: "The license-clean library the over-representation test scores against.",
    },
    {
      key: "direction", label: "Direction", type: "select", default: "combined",
      options: [
        { value: "combined", label: "Combined" },
        { value: "split", label: "Up / down split" },
      ],
      help: "Split scores up- and down-regulated genes separately (diverging dotplot). Needs a fold-change column.",
    },
  ],
  volcano: [
    {
      key: "highlight", label: "Highlight genes", type: "text", default: "",
      placeholder: "e.g. RHO, GNAT1, PDE6B",
      help: "Mark + label a gene-set panel on the plot (comma-separated). Applied from “Gene Sets”.",
    },
  ],
  scorecard: [
    {
      key: "layout", label: "Layout", type: "select", default: "radar",
      options: [
        { value: "radar", label: "Radar (spider)" },
        { value: "heatmap", label: "Heatmap (metrics × conditions)" },
      ],
      help: "Two forms of the same benchmark (paper Fig 6F).",
    },
    {
      key: "invert_metrics", label: "Lower-is-better metrics", type: "text", default: "",
      placeholder: "e.g. off_target, error_rate",
      help: "Comma-separated metrics where lower is better — inverted so higher always reads as better.",
    },
  ],
  proteomics_de: [
    { key: "group_a", label: "Group A", type: "text", default: "", placeholder: "e.g. infected", help: "Sample-name substring for the first group." },
    { key: "group_b", label: "Group B", type: "text", default: "", placeholder: "e.g. control", help: "Sample-name substring for the second group." },
    {
      key: "stats", label: "Statistics", type: "select", default: "welch",
      options: [
        { value: "welch", label: "Welch t-test" },
        { value: "moderated", label: "Moderated (limma-style)" },
      ],
      help: "Moderated borrows variance across proteins for better power at small N.",
    },
  ],
  annotate: [
    {
      key: "marker_set", label: "Marker panel", type: "select", default: "retinal",
      options: [
        { value: "retinal", label: "Retinal (canonical)" },
        { value: "retinal_cepo", label: "Retinal — Cepo (Kim 2023)" },
        { value: "pbmc", label: "PBMC / immune" },
      ],
      help: "Curated marker panel scored per cluster to assign cell types.",
    },
  ],
};

export function skillParamSchema(catalogOrRuntimeId: string): ParamField[] {
  return SCHEMAS[runtimeSkillId(catalogOrRuntimeId)] ?? [];
}

/** Default param values for a skill (what a one-click Apply sends). */
export function defaultParams(catalogOrRuntimeId: string): SkillParams {
  const out: SkillParams = {};
  for (const f of skillParamSchema(catalogOrRuntimeId)) out[f.key] = f.default;
  return out;
}

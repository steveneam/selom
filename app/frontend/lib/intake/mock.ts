import type { Guardrail, Modality, QcReport } from "@/lib/projects/types";

/**
 * Deterministic mock of the guided-intake backend (docs/command-center/design.md
 * §4 / §7). Stands in for `POST /upload` (ingest+QC) and `POST /intake` (the LLM
 * proposal) until phase B2. The LLM proposes; the user approves — nothing here
 * auto-runs an analysis.
 */

export interface IntakeQuestion {
  id: string;
  label: string;
  type: "text" | "textarea" | "select";
  options?: string[];
  placeholder?: string;
  helper?: string;
}

export type IntakeAnswers = Record<string, string>;

export interface ProposedStep {
  skillId: string;
  rationale: string;
  params: Record<string, string | number | boolean>;
  /** 0–1 model confidence; rendered, never hidden. */
  confidence: number;
}

export interface IntakeProposal {
  summary: string;
  cleaning: string[];
  guardrails: Guardrail[];
  steps: ProposedStep[];
  /** Alternative skills the user might prefer (catalog ids). */
  alternatives: string[];
}

/** Heuristic modality detection from a filename (mock of backend sniffing). */
export function detectModality(filename: string): Modality {
  const f = filename.toLowerCase();
  if (f.endsWith(".h5ad")) return "scRNA-seq";
  if (f.endsWith(".mzml") || f.includes("proteom") || f.includes("phospho")) return "proteomics";
  if (f.includes("bulk") || f.includes("counts") || f.includes("deseq")) return "bulk RNA-seq";
  if (f.endsWith(".csv") || f.endsWith(".tsv")) return "bulk RNA-seq";
  return "unknown";
}

const UNIVERSAL: IntakeQuestion[] = [
  {
    id: "organism", label: "Organism / reference", type: "select",
    options: ["Human (GRCh38)", "Mouse (GRCm39)", "Other / not sure"],
    helper: "Used to pick annotation and gene-set references.",
  },
  {
    id: "design", label: "Experimental design", type: "text",
    placeholder: "e.g. 3 treated vs 3 control, two timepoints",
    helper: "Groups, conditions, and replicates if you know them.",
  },
  {
    id: "goal", label: "What do you want to learn?", type: "textarea",
    placeholder: "e.g. which T-cell subsets change after treatment",
    helper: "Your expected findings — Selom proposes a pipeline from this.",
  },
];

const BY_MODALITY: Record<Modality, IntakeQuestion[]> = {
  "scRNA-seq": [
    { id: "tissue", label: "Tissue / sample", type: "text", placeholder: "e.g. PBMC, tumor biopsy" },
    { id: "cell_type", label: "Cell type(s) of interest", type: "text", placeholder: "e.g. CD8+ T cells, monocytes" },
    {
      id: "integration", label: "Multiple samples / batches?", type: "select",
      options: ["Single sample", "Multiple — integrate", "Not sure"],
      helper: "Drives whether batch integration is proposed.",
    },
  ],
  "bulk RNA-seq": [
    { id: "contrast", label: "Contrast of interest", type: "text", placeholder: "e.g. treated vs control" },
    { id: "condition", label: "Condition / disease", type: "text", placeholder: "e.g. IBD, sepsis" },
  ],
  proteomics: [
    {
      id: "labeling", label: "Quantification", type: "select",
      options: ["Label-free (LFQ)", "TMT / iTRAQ", "Not sure"],
    },
    {
      id: "phospho", label: "Phospho-enriched?", type: "select",
      options: ["No (total proteome)", "Yes (phosphoproteomics)"],
    },
    { id: "condition", label: "Condition / disease", type: "text", placeholder: "e.g. drug response" },
  ],
  unknown: [
    { id: "modality_hint", label: "What kind of data is this?", type: "text", placeholder: "e.g. single-cell, bulk RNA-seq, proteomics" },
  ],
};

export function questionsFor(modality: Modality): IntakeQuestion[] {
  return [...(BY_MODALITY[modality] ?? []), ...UNIVERSAL];
}

/** Mock ingest + QC report (design §7). */
export function mockQcReport(modality: Modality): QcReport {
  switch (modality) {
    case "scRNA-seq":
      return {
        detectedModality: modality, nObs: 2700, nVar: 13714,
        cleaning: ["filter cells (<200 genes)", "filter genes (<3 cells)", "normalize (log1p)", "HVG (2000)", "scale"],
        guardrails: [
          { level: "warn", msg: "2 samples detected — batch effect likely; consider integration before clustering." },
          { level: "info", msg: "Mitochondrial fraction within normal range (median 4.1%)." },
        ],
      };
    case "bulk RNA-seq":
      return {
        detectedModality: modality, nObs: 24, nVar: 18102,
        cleaning: ["drop low-count genes (<10 reads)", "design-aware size-factor normalization"],
        guardrails: [
          { level: "warn", msg: "n=4 per group — modest power; treat marginal genes cautiously." },
          { level: "info", msg: "No obvious library-size outliers." },
        ],
      };
    case "proteomics":
      return {
        detectedModality: modality, nObs: 16, nVar: 6421,
        cleaning: ["remove contaminants/reverse hits", "log2 transform", "median normalization", "impute (MinProb)"],
        guardrails: [
          { level: "warn", msg: "31% missing values — imputation choice affects volcano tails." },
        ],
      };
    default:
      return {
        detectedModality: "unknown", nObs: 0, nVar: 0,
        cleaning: ["modality not detected — confirm data type to enable cleaning"],
        guardrails: [{ level: "error", msg: "Could not detect modality from the file; please confirm the data type." }],
      };
  }
}

/** Mock LLM proposal (design §4.3) — deterministic by modality. */
export function proposeForModality(modality: Modality, answers: IntakeAnswers): IntakeProposal {
  const qc = mockQcReport(modality);
  const want = answers.goal || answers.cell_type || answers.contrast || "your question";

  switch (modality) {
    case "scRNA-seq":
      return {
        summary: `Single-cell dataset (${qc.nObs.toLocaleString()} cells). You want: ${want}.`,
        cleaning: qc.cleaning, guardrails: qc.guardrails,
        steps: [
          { skillId: "selom.umap_scrna", rationale: "Embed + cluster to reveal cell-type structure.",
            params: { n_neighbors: 15, resolution: 1.0, color_by: "leiden" }, confidence: 0.86 },
          { skillId: "selom.deg", rationale: "Rank markers to label the clusters you care about.",
            params: { group: "leiden", method: "wilcoxon" }, confidence: 0.71 },
        ],
        alternatives: ["clawbio.scrna-orchestrator"],
      };
    case "bulk RNA-seq":
      return {
        summary: `Bulk RNA-seq (${qc.nObs} samples). You want: ${want}.`,
        cleaning: qc.cleaning, guardrails: qc.guardrails,
        steps: [
          { skillId: "selom.deg", rationale: "Differential expression for the contrast of interest.",
            params: { method: "pydeseq2", contrast: answers.contrast || "treated_vs_control" }, confidence: 0.83 },
          { skillId: "selom.volcano", rationale: "Visualize DE with FDR/log2FC thresholds + top labels.",
            params: { fdr: 0.05, lfc: 1.0, label_top: 15 }, confidence: 0.8 },
          { skillId: "selom.enrichment", rationale: "Interpret the hit list against GO / Reactome.",
            params: { gene_sets: "GO_Biological_Process,Reactome" }, confidence: 0.62 },
        ],
        alternatives: ["selom.heatmap"],
      };
    case "proteomics":
      return {
        summary: `Mass-spec proteomics (${qc.nObs} samples). You want: ${want}.`,
        cleaning: qc.cleaning, guardrails: qc.guardrails,
        steps: [
          { skillId: "selom.proteomics_volcano", rationale: "Differential abundance across your condition.",
            params: { fdr: 0.05, lfc: 1.0, imputation: "MinProb" }, confidence: 0.74 },
          { skillId: "selom.enrichment", rationale: "Pathway context for the changed proteins.",
            params: { gene_sets: "Reactome" }, confidence: 0.58 },
        ],
        alternatives: [],
      };
    default:
      return {
        summary: "Couldn't detect the data type — confirm the modality to get a proposal.",
        cleaning: qc.cleaning, guardrails: qc.guardrails, steps: [], alternatives: [],
      };
  }
}

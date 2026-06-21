import type { DataCheck, FigureLegend, SkillGuardrail, SkillMethods, SkillProvenance, StatsTable } from "@/lib/skills-api";

/**
 * A representative publish-confidence bundle for the MSW mock (B4), so the panel
 * renders in offline dev (`npm run dev:mock`). The real bundle is produced by the
 * backend (provenance.py / methods.py); this just mirrors the shape with plausible
 * content keyed off the skill + its params.
 */
const MOCK_PKGS = {
  scanpy: "1.10.3",
  anndata: "0.11.1",
  "scikit-learn": "1.5.2",
  plotly: "6.1.1",
  numpy: "2.1.3",
  pandas: "2.2.3",
};

const METHODS: Record<string, string> = {
  umap_scrna:
    "Single-cell RNA-seq data were processed with Scanpy. Counts were normalized and log1p-transformed, then embedded in two dimensions with UMAP over the top principal components.",
  cluster:
    "Cells were clustered by Leiden community detection, and cluster-separation quality was quantified by the mean silhouette coefficient on the PCA embedding.",
  deg:
    "Differential expression was assessed by the Wilcoxon rank-sum test (single-cell) or PyDESeq2 (bulk), with Benjamini-Hochberg correction for multiple testing.",
  volcano:
    "Differential-expression results were displayed as a volcano plot of -log10 adjusted p-value against log2 fold change, with significant genes labelled.",
  heatmap:
    "Expression of the top genes was z-scored per gene and displayed as a heatmap with hierarchical row ordering (correlation distance, average linkage).",
  enrichment:
    "Pathway enrichment was computed by hypergeometric over-representation analysis against GO and Reactome gene sets, with Benjamini-Hochberg correction.",
  markers:
    "Marker genes were ranked per cluster with the Wilcoxon rank-sum test (Scanpy rank_genes_groups) and shown as a dotplot — colour = mean log1p expression, dot size = fraction of cells expressing.",
  annotate:
    "Cell types were assigned by scoring curated marker sets per cell (Scanpy score_genes), averaging per cluster, and labelling each cluster with its top-scoring type; the embedding is recoloured by assigned type.",
  trajectory:
    "A diffusion map was computed, the cluster graph abstracted with PAGA, and cells ordered along diffusion pseudotime (DPT); the embedding is coloured by pseudotime with the PAGA graph overlaid.",
  pca:
    "Samples were projected onto their first two principal components (scikit-learn PCA) and coloured by group; variance explained is shown per axis.",
  composition:
    "Category proportions (e.g. cell-type deconvolution) were displayed as grouped bars across conditions.",
  proteomics_de:
    "Protein intensities were log2-transformed and median-normalized across samples; sparse proteins were filtered and residual missing values mean-imputed per group. Differential abundance between groups was tested with a Welch t-test and Benjamini-Hochberg correction, displayed as a volcano plot.",
  gsea:
    "Genes were ranked by the signed differential statistic and tested for gene-set enrichment with a weighted Kolmogorov-Smirnov running enrichment score (Subramanian et al. 2005); a normalized enrichment score and empirical p-value were estimated by permutation.",
  corr_heatmap:
    "Pairwise Pearson correlation coefficients were computed between samples and displayed as a heatmap on a diverging colour scale centred at zero, with rows and columns reordered by hierarchical clustering (1−r distance, average linkage).",
  upset:
    "Set membership was summarized as an UpSet plot: intersection sizes are shown as bars above a dot-matrix of set membership, with the largest intersections displayed.",
  scorecard:
    "Conditions were compared across multiple metrics on a radar (spider) chart, one filled polygon per condition; each metric was min–max normalized to [0,1] for comparability.",
  normalization_qc:
    "Per-cell quality-control metrics — total counts, genes per cell, and mitochondrial-read percentage — were computed with Scanpy and shown as violin distributions split by sample.",
  sankey:
    "Quantities flowing between categories were displayed as a Sankey (alluvial) diagram; node and link thickness are proportional to the flow value summed over the input edge list.",
  string_network:
    "Protein-protein interactions among the input genes were retrieved from the STRING database and displayed as an editable network; nodes are coloured by log2 fold change (or degree) and edges are STRING interactions above a confidence cutoff.",
};

// Mirrors backend guardrails.py for the canned demo input (a clean raw-count h5ad):
// FDR skills always report multiple-testing; a lax fdr_threshold query adds a warning.
const FDR_SKILLS = new Set(["deg", "volcano", "enrichment", "proteomics_de"]);

function mockGuardrails(skillId: string, params: Record<string, string>): SkillGuardrail[] {
  const out: SkillGuardrail[] = [];
  if (FDR_SKILLS.has(skillId)) {
    out.push({
      level: "info",
      code: "multiple-testing",
      title: "Multiple-testing correction applied",
      detail: "p-values are corrected across genes/sets by the Benjamini–Hochberg FDR procedure.",
    });
  }
  const fdr = Number(params.fdr_threshold);
  if (Number.isFinite(fdr) && fdr > 0.1) {
    out.push({
      level: "warn",
      code: "fdr-threshold",
      title: fdr >= 1 ? "No FDR filtering" : "Lax FDR threshold",
      detail: `fdr_threshold = ${fdr}: thresholds above 0.1 inflate false positives; 0.05 is conventional.`,
    });
  }
  return out;
}

export function mockBundle(
  skillId: string,
  params: Record<string, string>,
): { provenance: SkillProvenance; methods: SkillMethods; guardrails: SkillGuardrail[] } {
  const base = METHODS[skillId] ?? `Figure generated by the Selom '${skillId}' skill.`;
  return {
    guardrails: mockGuardrails(skillId, params),
    provenance: {
      skill: { id: skillId, version: "0.1.0", title: titleize(skillId), engine: "python" },
      params,
      input: {
        filename: "demo.h5ad",
        sha256: "0a0b722d98d5e91b4ba94d52f0e3c7a18b6c4d2e9f10a3b5c6d7e8f90a1b2c3d4",
        n_bytes: 21_233_664,
      },
      environment: {
        python: "3.12.13",
        platform: "mock-offline",
        engine_policy: "stub",
        packages: MOCK_PKGS,
      },
    },
    methods: {
      text: `${base} Analysis was performed using Selom (skill '${skillId}' v0.1.0).`,
      citations: [
        "Wolf, F.A., Angerer, P. & Theis, F.J. SCANPY: large-scale single-cell gene expression data analysis. Genome Biology 19, 15 (2018).",
      ],
    },
  };
}

function titleize(slug: string): string {
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * A representative is-my-data-clean verdict for the mock (P1c/P3a) — a clean raw-count
 * scRNA matrix with the standard scRNA pipeline — so the Data check panel renders offline
 * (`npm run dev:mock`). The real verdict comes from the backend engine (engine/qc.py +
 * engine/route.py). The block + override affordance is exercised against the live backend.
 */
export function mockDataCheck(): DataCheck {
  return {
    kind: "sc_counts",
    qc: {
      ran: true,
      ok: true,
      blocked: false,
      flags: [],
      stats: { n_cells: 2700, n_genes: 13_714, median_pct_mito: 2.1 },
    },
    routing: {
      kind: "sc_counts",
      confident: true,
      note: "Single-cell matrix detected — the standard scRNA path.",
      steps: [
        { skill_id: "normalization_qc", role: "qc", reason: "QC + normalize before clustering" },
        { skill_id: "umap_scrna", role: "analyze", reason: "cluster the cells + embed (UMAP)" },
        { skill_id: "markers", role: "analyze", reason: "find each cluster's marker genes" },
        { skill_id: "composition", role: "visualize", reason: "cell-type composition across conditions" },
      ],
    },
  };
}

/** A representative figure legend for the mock (legends.py — the Methods+legend layer). */
export function mockLegend(skillId: string): FigureLegend {
  return { text: `${titleize(skillId)} of the demo single-cell dataset.` };
}

// Skills whose figure carries a tabular DE result (Pillar 1 Statistics node).
const DE_SKILLS = new Set(["deg", "volcano", "proteomics_de"]);

/**
 * A representative Statistics `table` for the mock (Pillar 1, Decision D7), so the
 * Statistics node renders offline (`npm run dev:mock`). Purely-visual skills get null.
 * The real table comes from the backend runner (skills/_table.py).
 *
 * The clustering table scales its cluster count with the `resolution` query param
 * (more clusters at higher resolution — the real Leiden behaviour), so a parameter
 * sweep produces genuinely different tables and the S3 compare view shows a real
 * row-level diff offline. Mock-only; the production umap/cluster table is a backend
 * concern (markers/cluster-summary not yet wired into the S2.1 contract).
 */
export function mockTable(skillId: string, query: Record<string, string> = {}): StatsTable | null {
  if (skillId === "umap_scrna" || skillId === "cluster") {
    const res = Number(query.resolution ?? 1.0);
    const n = Math.max(2, Math.min(18, Math.round(3 + (Number.isFinite(res) ? res : 1) * 6)));
    const total = 2700;
    const weights = Array.from({ length: n }, (_, i) => 1 / (i + 1.4));
    const sum = weights.reduce((a, b) => a + b, 0);
    let acc = 0;
    const rows = weights.map((w, i): (string | number)[] => {
      const cells = i === n - 1 ? total - acc : Math.round((total * w) / sum);
      acc += cells;
      return [`cluster ${i}`, cells, Number(((cells / total) * 100).toFixed(1))];
    });
    return { columns: ["cluster", "cells", "% of total"], rows, title: "Cluster summary" };
  }
  if (DE_SKILLS.has(skillId)) {
    const genes = ["RHO", "PDE6B", "GNAT1", "NRL", "CRX", "RCVRN", "SAG", "GUCA1A", "RBP3", "OPN1SW", "NR2E3", "ROM1"];
    const rows = genes.map((g, i): (string | number)[] => {
      const lfc = Number(((i % 2 ? 1 : -1) * (3.4 - i * 0.22)).toFixed(3));
      const padj = Number(Math.min(0.5, 1e-6 * 10 ** (i * 0.5)).toPrecision(2));
      const direction = lfc >= 1 ? "up" : lfc <= -1 ? "down" : "n.s.";
      return [g, lfc, padj, direction];
    });
    return { columns: ["gene", "log2FC", "padj", "direction"], rows, title: "Differential expression" };
  }
  // L3 synthesized tables (table-synthesis spec): tableless skills whose figure Selom re-shapes
  // into a Statistics table on the run path — mocked here so the "computed by Selom" label renders
  // offline. Shapes mirror extract/synthesize.py (pca → [component, %]; composition → bar arrays).
  if (skillId === "pca") {
    return {
      columns: ["component", "variance %"],
      rows: [["PC1", 61.2], ["PC2", 12.7]],
      title: "PCA variance explained",
      synthesized: true,
      source: "figure",
    };
  }
  if (skillId === "composition") {
    return {
      columns: ["category", "DR %", "PD %"],
      rows: [
        ["Rods", 21.8, 4.5],
        ["Müller glia", 2.6, 22.2],
        ["Microglia", 9.5, 15.2],
        ["Bipolar", 10.4, 14.3],
      ],
      title: "Composition",
      synthesized: true,
      source: "figure",
    };
  }
  if (skillId === "enrichment") {
    return {
      columns: ["pathway", "-log10 padj", "overlap genes"],
      rows: [
        ["Reactome: Phototransduction", 6.2, 18],
        ["GO: Visual perception", 5.4, 22],
        ["Reactome: Cilium assembly", 4.8, 14],
        ["GO: Photoreceptor outer segment", 4.1, 11],
        ["Reactome: Retinoid metabolism", 3.3, 9],
      ],
      title: "Enrichment results",
    };
  }
  return null;
}

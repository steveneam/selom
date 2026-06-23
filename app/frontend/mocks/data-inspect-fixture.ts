/**
 * Offline mock of `POST /api/data/inspect` (backend engine/cleaning.py + main.py).
 *
 * A light stand-in for the layered detector so `dev:mock` shows the SAME dynamic behaviour as the
 * live engine for the common cases — an ERG / generic table gets an empty cleaning plan (no
 * gene-subset cleaning), a count matrix gets the steps. It reads only the CSV header (not a full
 * parse), so matrix deltas are omitted here; verify real figure/cleaning content against the live
 * backend, never dev:mock ([[verify-on-real-data-not-mock]]).
 */

interface MockStep {
  id: string;
  label: string;
  detail?: string;
  kind: "filter" | "transform" | "selection";
  obs_delta?: number | null;
  var_delta?: number | null;
}

const ERG_WAVE = ["a_wave", "b_wave", "a-wave", "b-wave", "awave", "bwave"];
const ERG_INTENSITY = ["intensity", "cd_s_m2", "cd.s.m"];
const LOGFC = ["log2foldchange", "logfoldchange", "logfc", "log2fc", "avg_log2fc"];
const PVAL = ["padj", "pvalue", "p_val", "pval", "fdr", "qvalue", "adj.p.val"];

const LABEL: Record<string, string> = {
  erg: "ERG / electrophysiology",
  sc_counts: "Single-cell RNA-seq",
  bulk_counts: "Bulk RNA-seq counts",
  de_results: "Differential-expression results",
  proteomics: "Proteomics intensities",
  generic_table: "Data table",
  unknown: "Unrecognized data",
};

function has(cols: string[], needles: string[]): boolean {
  return cols.some((c) => needles.some((n) => c.includes(n)));
}

function classify(cols: string[], filename: string): string {
  if (filename.toLowerCase().endsWith(".iwxdata")) return "erg";
  if (has(cols, ERG_WAVE) && has(cols, ERG_INTENSITY)) return "erg";
  if (has(cols, LOGFC) && has(cols, PVAL)) return "de_results";
  if (filename.toLowerCase().endsWith(".h5ad")) return "sc_counts";
  return "generic_table";
}

function cleaningSteps(code: string): MockStep[] {
  switch (code) {
    case "sc_counts":
      return [
        { id: "filter_genes", label: "Filter rarely-detected genes", detail: "Drop genes seen in fewer than 3 cells.", kind: "filter" },
        { id: "normalize", label: "Normalize + log1p", detail: "Library-size normalize, then log1p.", kind: "transform" },
      ];
    case "bulk_counts":
      return [
        { id: "drop_low", label: "Drop low-count genes", detail: "Remove genes with fewer than 10 reads across all samples.", kind: "filter" },
        { id: "size_factor", label: "Size-factor normalization", kind: "transform" },
      ];
    case "proteomics":
      return [
        { id: "drop_undetected", label: "Drop never-detected proteins", kind: "filter" },
        { id: "log2", label: "Log2 transform", kind: "transform" },
        { id: "median_norm", label: "Median normalization", kind: "transform" },
        { id: "impute", label: "Impute missing (MNAR-aware)", kind: "transform" },
      ];
    default:
      return [];
  }
}

const AXES: Record<string, [string, string]> = {
  sc_counts: ["cells", "genes"],
  bulk_counts: ["samples", "genes"],
  proteomics: ["samples", "proteins"],
};

const NOTE: Record<string, string> = {
  erg: "ERG measurements table — used as-is. No matrix cleaning (gene filtering / normalization) applies.",
  de_results: "Pre-computed results table — used as-is. No cleaning needed.",
  generic_table: "Used as-is. No matrix cleaning applies to this table.",
};

/** Build the inspect response for a dropped file (header read by the caller). `override` is the
 *  query `profile` (erg) or `hint` (a Kind). */
export function mockInspect(filename: string, header: string, override?: string): Record<string, unknown> {
  const cols = header.split(/[,\t]/).map((c) => c.trim().toLowerCase());
  const code = override || classify(cols, filename);
  const kind = code === "erg" ? "generic_table" : code;
  const steps = cleaningSteps(code);
  const applies = steps.length > 0;
  const [obsLabel, varLabel] = AXES[code] ?? ["rows", "columns"];
  const confidence = override ? "certain" : code === "erg" ? "likely" : code === "generic_table" ? "unsure" : "likely";
  const reason = override
    ? "You set the data type."
    : code === "erg"
      ? "a-/b-wave amplitude and flash-intensity columns recognized."
      : code === "generic_table"
        ? "Modality not recognized — usable as a plain table."
        : "Recognized from the data's columns/shape.";

  const erg = code === "erg";
  const ergSteps = ["erg_traces", "erg_bwave_bar", "erg_intensity_response"];
  const byKind: Record<string, string[]> = {
    de_results: ["volcano", "enrichment", "gsea"],
    bulk_counts: ["deg", "volcano", "enrichment"],
    sc_counts: ["normalization_qc", "umap_scrna", "markers"],
    generic_table: ["pca", "corr_heatmap"],
  };
  const routeIds = erg ? ergSteps : byKind[code] ?? [];

  return {
    filename,
    kind,
    profile: { code, label: LABEL[code] ?? code, confidence, reason, overridden: !!override },
    cleaning_plan: {
      kind,
      profile: code,
      applies,
      obs_label: obsLabel,
      var_label: varLabel,
      n_obs: 0,
      n_var: 0,
      steps,
      note: applies ? "Standard cleaning before analysis." : NOTE[code] ?? "Used as-is.",
    },
    qc: { ran: true, ok: true, blocked: false, flags: [], stats: {} },
    routing: {
      kind,
      steps: routeIds.map((id) => ({ skill_id: id, role: "analyze", reason: "" })),
      confident: routeIds.length > 0 && !erg ? true : erg,
      note: erg ? "ERG / electrophysiology data — the electrophysiology figure skills." : "",
    },
  };
}

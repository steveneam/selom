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

// The weakest layer — a light mirror of engine/cleaning.py _FILENAME_HINTS (whole-token match for
// short keys). Returns the hinted code, or null. dev:mock parity only; verify on the live engine.
const FILENAME_HINTS: [string[], string][] = [
  [["erg", "electroretin", "scotopic", "photopic", "iwx"], "erg"],
  [["scrna", "scrnaseq", "singlecell", "cellranger", "scanpy", "10x"], "sc_counts"],
  [["bulk", "rnaseq", "featurecounts", "salmon"], "bulk_counts"],
  [["deg", "degs", "deseq", "edger", "limma", "volcano", "differential"], "de_results"],
  [["proteom", "maxquant", "diann", "tmt", "lfq"], "proteomics"],
];

function filenameHint(filename: string): string | null {
  const stem = filename.toLowerCase().replace(/\.[^.]+$/, "");
  const tokens = new Set(stem.split(/[^a-z0-9]+/).filter(Boolean));
  const norm = stem.replace(/[^a-z0-9]+/g, "");
  for (const [keywords, code] of FILENAME_HINTS) {
    for (const kw of keywords) {
      if (kw.length < 5 ? tokens.has(kw) : norm.includes(kw)) return code;
    }
  }
  return null;
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

// Design-hint mock (Layer A ingest): mirrors engine.questionnaire for the ONE case a header-only
// mock can infer — bulk condition labels from the sample column names. scRNA design needs the obs
// table (not in the header), so dev:mock returns no design for it; verify scRNA design on the live
// backend ([[selom-mock-is-wire-only-verify-real]]).
//
// The same limit now covers `generic_table`: the engine's `_table_hints` reads the column VALUES to
// find the categorical factors and their levels, and a header-only mock has no values to read. So
// dev:mock deliberately returns NO group candidates for a plain table — a fail-soft mock degrades
// structure, never fabricates data ([[mock-fallback-never-fabricates-data]]). Consequence to know
// before debugging: in `dev:mock` the inline COLUMN picker works (its columns come from the real
// header) but the PAIR picker stays a text field. That is the mock being honest, not a regression —
// verify pairs against a live backend.
const COLUMN_NAMES_KEY = "__column_names__";
const REP_RE = /_\d+$/;
const CONTROL_RE = /\b(wt|ctrl|control|wild[\s_-]?type|vehicle|dmso|untreated|naive|baseline|mock|sham|0h|day0|d0)\b/i;

function mockDesign(kind: string, rawCols: string[]): Record<string, unknown> {
  const empty = {
    needs_design: false, source: "none", modality: kind,
    group_candidates: [], best_group: null, sample_col: null, note: "",
  };
  if (kind !== "bulk_counts") return empty;
  const sampleCols = rawCols.slice(1); // header-only: assume the first column is the gene label
  const order: string[] = [];
  const counts: Record<string, number> = {};
  for (const c of sampleCols) {
    const label = c.replace(REP_RE, "");
    if (!(label in counts)) order.push(label);
    counts[label] = (counts[label] ?? 0) + 1;
  }
  if (order.length < 2) return empty;
  const reference =
    order.find((n) => CONTROL_RE.test(n) || CONTROL_RE.test(n.replace(/[\s_-]*\d+$/, ""))) ?? null;
  const levels = order.map((name) => ({ name, n_replicates: counts[name], replicate_unit: "samples" }));
  return {
    needs_design: true,
    source: "column_names",
    modality: kind,
    group_candidates: [
      { key: COLUMN_NAMES_KEY, label: "sample columns", levels, n_levels: order.length, reference_guess: reference },
    ],
    best_group: COLUMN_NAMES_KEY,
    sample_col: null,
    note: `inferred ${order.length} condition(s) from the sample column names`,
  };
}

const NOTE: Record<string, string> = {
  erg: "ERG measurements table — used as-is. No matrix cleaning (gene filtering / normalization) applies.",
  de_results: "Pre-computed results table — used as-is. No cleaning needed.",
  generic_table: "Used as-is. No matrix cleaning applies to this table.",
};

/** Build the inspect response for a dropped file (header read by the caller). `override` is the
 *  query `profile` (erg) or `hint` (a Kind). */
export function mockInspect(filename: string, header: string, override?: string): Record<string, unknown> {
  const cols = header.split(/[,\t]/).map((c) => c.trim().toLowerCase());
  const contentCode = classify(cols, filename);
  const hintCode = override ? null : filenameHint(filename);
  // Content wins; a filename hint only fills the neutral gap (content couldn't type it).
  const code = override
    || (contentCode !== "generic_table" ? contentCode : (hintCode ?? "generic_table"));
  const kind = code === "erg" ? "generic_table" : code;
  const steps = cleaningSteps(code);
  const applies = steps.length > 0;
  const [obsLabel, varLabel] = AXES[code] ?? ["rows", "columns"];
  const fromFilename = !override && contentCode === "generic_table" && hintCode != null;
  const isFormat = !override && code === "erg" && filename.toLowerCase().endsWith(".iwxdata");
  const source = override ? "user" : isFormat ? "format" : fromFilename ? "filename" : "content";
  const confidence = override ? "certain"
    : fromFilename ? "unsure"
      : code === "erg" ? (isFormat ? "certain" : "likely")
        : code === "generic_table" ? "unsure" : "likely";
  const reason = override
    ? "You set the data type."
    : fromFilename
      ? `The filename mentions “${hintCode}”.`
      : code === "erg"
        ? (isFormat ? ".iwxdata is a native electrophysiology format." : "a-/b-wave amplitude and flash-intensity columns recognized.")
        : code === "generic_table"
          ? "Modality not recognized — usable as a plain table."
          : "Recognized from the data's columns/shape.";
  // Ranked candidates + the mismatch nudge (content typed it, but the name says otherwise).
  const candidates: Record<string, unknown>[] = [{ code, label: LABEL[code] ?? code, confidence, source, reason }];
  if (!override && hintCode && hintCode !== code) {
    candidates.push({ code: hintCode, label: LABEL[hintCode] ?? hintCode, confidence: "unsure",
      source: "filename", reason: `The filename mentions “${hintCode}”.` });
  }
  const mismatch = (!override && hintCode && hintCode !== code && contentCode !== "generic_table")
    ? `The filename suggests ${LABEL[hintCode] ?? hintCode}, but the data looks like ${LABEL[code] ?? code}. The data content wins — override if the name is right.`
    : "";

  const erg = code === "erg";
  const ergSteps = ["erg_traces", "erg_bwave_bar", "erg_intensity_response"];
  const byKind: Record<string, string[]> = {
    de_results: ["volcano", "enrichment", "gsea"],
    bulk_counts: ["deg", "volcano", "enrichment"],
    sc_counts: ["normalization_qc", "umap_scrna", "markers"],
    generic_table: ["pca", "corr_heatmap"],
  };
  const routeIds = erg ? ergSteps : byKind[code] ?? [];

  // data_fit (Slice 2): the per-skill fit + the table shape the FE forwards to /ai/propose as the
  // data context. Header-only mock — columns are real, the numeric count is approximated (verify
  // real fit content against the live backend, not here). Every routed skill is shown as a fit.
  const rawCols = header.split(/[,\t]/).map((c) => c.trim()).filter(Boolean);
  const nNumeric = Math.max(0, rawCols.length - 1); // assume the first column is the gene/sample label
  const fits = routeIds.map((id) => ({
    filename, skill_id: id, kind, score: 90, compatible: true,
    verdict: "fit", qc_ok: true, reason: `fits ${id}`,
    confidence: "confident", confidence_label: "",
  }));

  return {
    filename,
    kind,
    profile: { code, label: LABEL[code] ?? code, confidence, reason, overridden: !!override, candidates, mismatch },
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
    data_fit: {
      quality: 100,
      confidence: fits.length ? "confident" : "uncertain",
      columns: rawCols,
      n_numeric_cols: nNumeric,
      fits,
    },
    design: mockDesign(kind, rawCols),
  };
}

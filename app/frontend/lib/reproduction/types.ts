/**
 * Reproduction view types — mirror the backend Reproduction-engine models
 * (app/backend/reproduction.py) served by GET /papers and GET /papers/{slug}.
 *
 * The view renders the Reproducibility Score: two axes kept SEPARATE —
 * `reproducibility` ("can the figure be regenerated?", a paper+data property → the
 * heatmap headline) vs `selom_confidence` ("is Selom's reconstruction trustworthy?",
 * an our-tool property). A paper-irreproducible figure scores LOW reproducibility but
 * HIGH confidence — a discovery, never a Selom failure.
 */

/** Who a residual is on — keeps a low score from ever reading as accusatory. */
export type Attribution = "selom" | "engine" | "paper" | "data";

/** The weighted paper rollup (the big number on each card). */
export interface PaperScore {
  paper_id: string;
  reproducibility: number | null;
  selom_confidence: number | null;
  tier: string;
  color: string;
  n_scored: number;
  n_in_scope: number;
  n_out_of_scope: number;
  n_form_only: number;
  coverage: string;
}

/** One per-panel heatmap cell on the index card's mini strip. */
export interface PaperCell {
  panel_key: string;
  reproducibility: number | null;
  tier: string;
  color: string;
  attribution_icon: string;
  in_scope: boolean;
}

/** One paper in the index "reproducibility spectrum". Carries the shared Paper-anchor metadata
 *  (the same shape Skill Match uses) so cards render the author/citation row via the shared
 *  `authorSummary`/`citationLine` formatters (spec §10). */
export interface PaperSummary {
  slug: string;
  title: string;
  doi: string;
  pmid: string;
  authors: string[];
  venue: string;
  year: number | null;
  volume: string;
  issue: string;
  pages: string;
  geo: string[];
  score: PaperScore | null;
  n_panels: number;
  n_in_scope: number;
  findings: Record<string, number>;
  provenance_divergences: string[];
  cells: PaperCell[];
}

/** A graded per-panel cell (the detail heatmap). */
export interface PanelScore {
  panel_key: string;
  reproducibility: number | null;
  selom_confidence: number | null;
  tier: string;
  color: string;
  attribution: Attribution;
  /** The DEPOSITED-SOURCE badge (e.g. "ST6+ Fig4e−") — which deposits backed this panel. */
  provenance: string;
  /**
   * How Selom READ the numbers back — a different question from `provenance` above, which is why
   * it is a different field. `""` for a value read off a table the skill emitted; `"synthesized"`
   * when any metric on the panel came from an L3-synthesized table, which also caps
   * `selom_confidence` at 75 backend-side (DECISIONS #16).
   */
  reading_provenance: string;
  in_scope: boolean;
  weight: number;
  note: string;
}

/** A printed target value, sourced only from the PDF. */
export interface Golden {
  metric: string;
  value: number | string;
  unit: string;
  source: string;
  confidence: number;
  note: string;
}

/**
 * A staged X3-lifted panel thumbnail (★D bridge). Purely presentational — it NEVER influences
 * the Reproducibility Score (digitize ≠ reproduce). `digitizable` gates the "Digitize this panel"
 * entry to traceable chart forms (bar/line/scatter).
 */
export interface PanelLift {
  page_index: number;
  bbox: [number, number, number, number] | null;
  kind: string; // "vector" | "raster"
  thumbnail_url: string;
  digitizable: boolean;
}

export interface Panel {
  paper_id: string;
  figure: string;
  panel: string;
  chart_form: string;
  scope: string;
  data_source: string;
  skill_id: string | null;
  golden: Golden[];
  weight: number;
  note: string;
  lift?: PanelLift | null;
  status: string;
}

/** One golden-vs-computed metric row (the detail table). */
export interface ValidationResult {
  metric: string;
  golden: number | string;
  computed: number | string | null;
  oracle: number | string | null;
  delta: number | null;
  verdict: "exact" | "close" | "fail" | string;
  blame: string | null;
  note: string;
}

export interface Validation {
  run_id: string;
  panel_key: string;
  results: ValidationResult[];
  panel_verdict: string;
  guards_fired: string[];
}

export interface Scorecard {
  paper_id: string;
  n_panels: number;
  n_in_scope: number;
  totals_by_verdict: Record<string, number>;
  totals_by_blame: Record<string, number>;
  findings: Record<string, number>;
  provenance_divergences: string[];
  panel_scores: PanelScore[];
  score: PaperScore | null;
  generated_at: string;
}

export interface Paper {
  id: string;
  slug: string;
  title: string;
  doi: string;
  pmid: string;
  authors: string[];
  venue: string;
  year: number | null;
  volume: string;
  issue: string;
  pages: string;
  geo: string[];
}

/** The full driven ledger — one fetch feeds the whole detail view. */
export interface Ledger {
  paper: Paper;
  panels: Panel[];
  validations: Validation[];
  scorecard: Scorecard | null;
}

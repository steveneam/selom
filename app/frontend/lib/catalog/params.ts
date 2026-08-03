import { runtimeSkillId } from "@/lib/skills/api";
import type { SkillParams } from "@/lib/skills/api";

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
  /**
   * Conditional *enablement* (vs `showWhen`'s conditional visibility): the field always
   * RENDERS, but is shown disabled (greyed, non-interactive) until another field equals
   * `equals`. Use for a capability-signaling control that should stay DISCOVERABLE even when
   * inert — e.g. the ERG trace grid's Spread / Error-metric knobs, which only act when
   * "Trace shows" is Mean of replicates but should advertise that the SEM/SD/band options
   * exist. Cosmetic fine-tuning that would only clutter the panel stays on `showWhen` (hidden).
   * See `isFieldDisabled`.
   */
  enabledWhen?: { key: string; equals: string | number | boolean };
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
  /** Show-but-disable gate (see `ParamField.enabledWhen`): the control always renders, greyed
   *  until the named field matches `equals`. For discoverable-but-inert capability controls. */
  enabledWhen?: { key: string; equals: string | number | boolean };
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
  // Distribution comparisons (boxplot · violin) share ONE vocabulary, because they share one
  // engine (skills/_stats.py): order → add_count → pairs → the test behind the stars. Keep the two
  // lists in the same order and wording — a user who learns the knobs on a box plot should not
  // have to relearn them on a violin.
  //
  // `pairs` is a TEXT field and that is a known compromise, not the intended affordance. Mobbin
  // (Rows / Glide / Databricks / Hex chart builders) is unanimous that "add another structural
  // thing" is a repeatable row-list of typed selects with an explicit "+ Add" — nobody asks the
  // user to type a mini-DSL. Selom cannot render that yet for two concrete reasons: ParamField has
  // no repeatable-list widget, and a param control has no access to the dataset's category values
  // at render time (the spec is static; the group names only exist after the data is loaded). So
  // the help text carries the syntax and names the failure mode instead. Captured as a gap.
  boxplot: [
    { key: "group", label: "Group column", type: "text", placeholder: "auto-detect", help: "Column holding the category. Blank = first non-numeric column." },
    { key: "value", label: "Value column", type: "text", placeholder: "auto-detect", help: "Column holding the measurement. Blank = first numeric column." },
    { key: "order", label: "Category order", type: "text", placeholder: "e.g. Control, Low, High", help: "Comma-separated. Named categories lead, in this order; the rest follow unchanged." },
    { key: "add_count", label: "Show n per group", type: "switch", help: "Append n= to each category label." },
    { key: "pairs", label: "Compare groups", type: "text", placeholder: "e.g. Control~Treated, Control~Rescue", help: "Comma-separated pairs joined by ~. Each draws a bracket with significance stars, and the p-values appear in the Statistics table. A name that doesn't match a group is skipped." },
    { key: "sig_test", label: "Significance test", type: "select", help: "Applied to every pair above.", options: [
      { value: "welch", label: "Welch t-test (unequal variance)" },
      { value: "student", label: "Student t-test (equal variance)" },
      { value: "mannwhitney", label: "Mann-Whitney U (rank)" },
    ] },
    { key: "correction", label: "Multiple-comparison correction", type: "select", help: "Several brackets means several shots at p<0.05. Correcting adjusts BOTH the stars and the table.", options: [
      { value: "none", label: "None (raw p)" },
      { value: "bonferroni", label: "Bonferroni" },
      { value: "bh", label: "Benjamini-Hochberg (FDR)" },
    ] },
    { key: "points", label: "Show points", type: "select", options: [
      { value: "outliers", label: "Outliers only" },
      { value: "all", label: "All points" },
      { value: "suspectedoutliers", label: "Suspected outliers" },
      { value: "none", label: "None" },
    ] },
    { key: "orientation", label: "Orientation", type: "select", options: [
      { value: "v", label: "Vertical" },
      { value: "h", label: "Horizontal" },
    ] },
    { key: "notched", label: "Notched boxes", type: "switch", help: "Notch marks the median's confidence interval." },
  ],
  violin: [
    { key: "gene", label: "Marker gene", type: "text", placeholder: "e.g. MS4A1" },
    { key: "order", label: "Category order", type: "text", placeholder: "e.g. cluster 2, cluster 0", help: "Comma-separated. Named categories lead, in this order; the rest follow unchanged." },
    { key: "add_count", label: "Show n per group", type: "switch", help: "Append n= to each category label." },
    { key: "pairs", label: "Compare groups", type: "text", placeholder: "e.g. cluster 0~cluster 1", help: "Comma-separated pairs joined by ~. Each draws a bracket with significance stars, and the p-values appear in the Statistics table. A name that doesn't match a group is skipped." },
    { key: "sig_test", label: "Significance test", type: "select", help: "Applied to every pair above.", options: [
      { value: "welch", label: "Welch t-test (unequal variance)" },
      { value: "student", label: "Student t-test (equal variance)" },
      { value: "mannwhitney", label: "Mann-Whitney U (rank)" },
    ] },
    { key: "correction", label: "Multiple-comparison correction", type: "select", help: "Several brackets means several shots at p<0.05. Correcting adjusts BOTH the stars and the table.", options: [
      { value: "none", label: "None (raw p)" },
      { value: "bonferroni", label: "Bonferroni" },
      { value: "bh", label: "Benjamini-Hochberg (FDR)" },
    ] },
  ],
  // Composition takes the ordering half of the vocabulary only — it holds one value per
  // category x condition cell, so there is no distribution to test. See the note at the top of
  // app/backend/skills/composition/run.py.
  composition: [
    { key: "order", label: "Category order", type: "text", placeholder: "e.g. Rods, Bipolar", help: "Comma-separated. Named categories lead, in this order; the rest follow unchanged." },
    { key: "sort_by", label: "Sort by series", type: "text", placeholder: "a value column", help: "Sort categories by one series' values. Applied before Category order." },
    { key: "mode", label: "Bar mode", type: "select", options: [
      { value: "grouped", label: "Grouped" },
      { value: "stacked", label: "Stacked" },
    ] },
    { key: "orientation", label: "Orientation", type: "select", options: [
      { value: "h", label: "Horizontal" },
      { value: "v", label: "Vertical" },
    ] },
  ],
  heatmap: [
    { key: "n_genes", label: "Genes shown", type: "range", step: 5, help: "Top genes by variance (bulk) or markers per cluster (scRNA)." },
    {
      key: "cluster", label: "Clustering", type: "select",
      options: [
        { value: "none", label: "None" },
        { value: "row", label: "Rows (genes)" },
        { value: "column", label: "Columns (samples)" },
        { value: "both", label: "Both" },
      ],
      help: "Draw the hierarchical-clustering dendrogram for rows, columns, or both. Rows are always clustered for ordering; this controls which trees show and whether samples are reordered.",
    },
    {
      key: "cut_k", label: "Colour branches (clusters)", type: "range", step: 1,
      help: "Cut the clustering tree into k groups and colour each cluster's branches a distinct hue (0 = one grey tree). Needs a tree drawn (Clustering ≠ None).",
    },
    {
      key: "annotations", label: "Annotation tracks", type: "text",
      placeholder: "e.g. condition, genotype",
      help: "Comma-separated sample-sheet columns to paint as categorical colour strips above the columns. Needs a design / sample sheet (add one in the Data tab).",
    },
    {
      key: "quant_track", label: "Row side bar", type: "select",
      options: [
        { value: "none", label: "None" },
        { value: "variance", label: "Variance (per gene)" },
        { value: "mean", label: "Mean expression" },
        { value: "logfc", label: "log₂ fold-change (groups)" },
      ],
      help: "A quantitative bar aligned to the rows, left of the heatmap. Variance / mean come from the data; log₂FC needs a design sheet with a two-group condition column.",
    },
    {
      key: "split_by", label: "Split columns by", type: "text",
      placeholder: "e.g. condition",
      help: "A sample-sheet column to block-split the columns into groups (gap + header per block). Column clustering is dropped in favour of the group order. Needs a design / sample sheet.",
    },
    {
      key: "split_by_cut", label: "Split columns by cut", type: "switch",
      help: "Block-split the columns into the colour-branch clusters (gap + header per block) — unsupervised, no sample sheet. Needs Colour branches ≥ 2; ignored when Split columns by is set.",
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
    {
      key: "central", label: "Trace shows", type: "select",
      options: [
        { value: "representative", label: "Representative (one exemplar)" },
        { value: "mean", label: "Mean of replicates" },
        { value: "none", label: "Individual traces only (no mean)" },
      ],
      help: "Representative draws one exemplar recording per cell (the back-compatible default). Mean averages the n eye/animal recordings at each time — and unlocks the Spread / Error options below (shaded band, SEM vs SD). Individual draws every replicate at equal weight with no averaged line — combine several files first (multi-file) for a real cohort n.",
    },
    {
      // Always visible (enabledWhen, not showWhen) so the band/SEM/SD capability is discoverable
      // even on a single representative trace; greyed until "Trace shows" = Mean of replicates.
      key: "spread", label: "Spread", type: "select",
      options: [
        { value: "band", label: "Shaded band" },
        { value: "error_bars", label: "Error bars" },
        { value: "individual", label: "Individual traces (behind mean)" },
        { value: "both", label: "Band + error bars" },
        { value: "none", label: "None (mean only)" },
      ],
      help: "How the variability across replicates is drawn behind/around the mean trace. Needs Trace shows = Mean of replicates.",
      enabledWhen: { key: "central", equals: "mean" },
    },
    {
      // Always visible (enabledWhen) — the SEM-vs-SD toggle is a headline capability; greyed until Mean.
      key: "error", label: "Error metric", type: "select",
      options: [
        { value: "sem", label: "SEM (standard error)" },
        { value: "sd", label: "SD (standard deviation)" },
        { value: "ci95", label: "95% CI" },
        { value: "minmax", label: "Range (min–max)" },
      ],
      help: "What the band/error bars span. SEM is the default; SD shows biological spread; 95% CI is the most defensible. Needs Trace shows = Mean of replicates.",
      enabledWhen: { key: "central", equals: "mean" },
    },
    {
      key: "boundary_lines", label: "Band edges", type: "select",
      options: [
        { value: "none", label: "None (fill only)" },
        { value: "solid", label: "Solid lines" },
        { value: "dashed", label: "Dashed lines" },
      ],
      help: "Draw the band's upper/lower edges as lines (off by default — the fill alone).",
      showWhen: { key: "central", equals: "mean" },
    },
    {
      key: "band_alpha", label: "Band opacity", type: "range", step: 0.05,
      help: "Opacity of the shaded ± band.",
      showWhen: { key: "central", equals: "mean" },
    },
    {
      key: "band_color", label: "Band colour", type: "text",
      placeholder: "match the trace",
      help: "Leave blank to match each trace's colour (default); or set a hex like #0072B2 to recolour every band.",
      showWhen: { key: "central", equals: "mean" },
    },
    {
      key: "error_every", label: "Error bar every Nth point", type: "range", step: 1,
      help: "Draw an error bar only every Nth time sample, to de-clutter a dense trace (Origin's 'skip each group of N').",
      showWhen: { key: "central", equals: "mean" },
    },
    {
      key: "adaptation", label: "Adaptation", type: "select",
      options: [
        { value: "auto", label: "Auto (scotopic first)" },
        { value: "scotopic", label: "Scotopic (dark-adapted)" },
        { value: "photopic", label: "Photopic (light-adapted)" },
      ],
      help: "Which flash family to render from a multi-mode export. Auto shows the dark-adapted (scotopic) series; switch to photopic for the light-adapted flashes. No-op for a single-mode recording.",
    },
    { key: "filter", label: "Clean traces", type: "switch", help: "Notch line-noise + low-pass, keeping oscillatory potentials (“clean flats, keep OPs”)." },
    { key: "lowpass_hz", label: "Low-pass cutoff (Hz)", type: "range", step: 10, help: "Lower = smoother. Default 120 Hz cuts mains/instrument hum while keeping the partial-rescue b-wave; raise toward 300 Hz to retain all oscillatory potentials." },
    {
      key: "display_unit", label: "Display unit", type: "select",
      options: [
        { value: "auto", label: "Auto (suggest)" },
        { value: "nV", label: "nV" },
        { value: "uV", label: "µV" },
        { value: "mV", label: "mV" },
        { value: "V", label: "V" },
      ],
      help: "Amplitude unit for the traces, scale bar, and a/b table — a pure rescale (nothing re-measured). Auto picks the unit that reads cleanest for the signal size.",
    },
    { key: "scale_uv", label: "Scale bar — amplitude (µV)", type: "number", step: 10, help: "Vertical scale-bar length, set in µV (shown in the chosen display unit)." },
    { key: "scale_ms", label: "Scale bar — time (ms)", type: "number", step: 10, help: "Horizontal scale-bar length." },
  ],
  // ERG a/b-wave bar — one flash intensity, mean ± SEM + every eye as a point (reviewer ask).
  erg_bwave_bar: [
    {
      key: "wave", label: "Wave", type: "select",
      options: [
        { value: "b", label: "b-wave (inner retina)" },
        { value: "a", label: "a-wave (photoreceptor)" },
      ],
      help: "Which ERG component to bar. The peak comes from the device markers when present, else it is measured from the same traces the grid draws.",
    },
    {
      key: "adaptation", label: "Adaptation", type: "select",
      options: [
        { value: "auto", label: "Auto (scotopic first)" },
        { value: "scotopic", label: "Scotopic (dark-adapted)" },
        { value: "photopic", label: "Photopic (light-adapted)" },
      ],
      help: "Which flash family the bar is taken from in a multi-mode export. No-op for a single-mode recording.",
    },
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
      help: "Which flash the per-condition a/b-wave bar is taken at — the intensity you set yourself.",
    },
    { key: "points", label: "Show individual eyes", type: "switch", help: "Overlay each eye as a data point (reviewer ask for quantitative graphs)." },
    { key: "show_error", label: "Show error bars", type: "switch", help: "Show or hide the error bars on each bar." },
    {
      key: "error", label: "Error metric", type: "select",
      options: [
        { value: "sem", label: "SEM (standard error)" },
        { value: "sd", label: "SD (standard deviation)" },
        { value: "ci95", label: "95% CI" },
        { value: "minmax", label: "Range (min–max)" },
      ],
      help: "What the error bars show. SEM is the default; SD shows biological spread; 95% CI is the most defensible for 'is the difference real'.",
    },
    {
      key: "bar_fill", label: "Bar style", type: "select",
      options: [
        { value: "pattern", label: "Hatch patterns (per condition)" },
        { value: "filled", label: "Solid colour" },
        { value: "open", label: "Open (outline)" },
      ],
      help: "Per-condition hatch patterns match the GraphPad Fig 1E look (good for B&W print); solid uses the condition colours; open is white-fill outlined bars.",
    },
    { key: "legend", label: "Show legend", type: "switch", help: "A per-condition legend with the pattern/colour swatches (the bars are also labelled on the x-axis)." },
    {
      key: "comparisons", label: "Significance brackets", type: "text",
      help: "Pairs to bracket, e.g. 'Untreated~AAV8-RK-PDE6B, AAV8-RK-GFP-polyA-stuffer~AAV8-RK-PDE6B-3UTR'. Selom computes the stars; override per pair with ':**' or a p-value (':0.003').",
    },
    {
      key: "sig_test", label: "Significance test", type: "select",
      options: [
        { value: "welch", label: "Welch t-test (unequal variance)" },
        { value: "student", label: "Student t-test (equal variance)" },
        { value: "mannwhitney", label: "Mann–Whitney U (rank)" },
      ],
      help: "The test used to compute bracket p-values (when you don't override the stars).",
    },
    { key: "hline", label: "Reference line (µV)", type: "text", help: "Draw a dashed horizontal line at this amplitude (leave blank for none) — e.g. a threshold or a group reference." },
    { key: "hline_label", label: "Reference line label", type: "text", help: "Optional caption for the reference line." },
    {
      key: "display_unit", label: "Display unit", type: "select",
      options: [
        { value: "auto", label: "Auto (suggest)" },
        { value: "nV", label: "nV" },
        { value: "uV", label: "µV" },
        { value: "mV", label: "mV" },
        { value: "V", label: "V" },
      ],
      help: "Amplitude unit for the y-axis and table — a pure rescale (nothing re-measured). Auto picks the unit that reads cleanest.",
    },
  ],
  // ERG intensity-response — b-wave vs flash energy with the adjustable Naka-Rushton fit.
  erg_intensity_response: [
    {
      key: "adaptation", label: "Adaptation", type: "select",
      options: [
        { value: "auto", label: "Auto (scotopic first)" },
        { value: "scotopic", label: "Scotopic (dark-adapted)" },
        { value: "photopic", label: "Photopic (light-adapted)" },
      ],
      help: "Which flash family the intensity series uses in a multi-mode export. No-op for a single-mode recording.",
    },
    { key: "fit", label: "Naka-Rushton fit", type: "switch", help: "Overlay the saturating V = Vmax·Iⁿ/(Iⁿ+Kⁿ) curve per condition." },
    {
      key: "nr_slope", label: "Fit slope (n)", type: "range", step: 0.1,
      help: "0 = auto-fit each condition's slope (falling back to n=1 where under-constrained). Set a value to fix the slope and compare all conditions at one slope.",
    },
    { key: "min_r2", label: "Fit-quality gate (R²)", type: "range", step: 0.05, help: "Minimum R² to report a fit; lower keeps more marginal fits, higher only the cleanest." },
    {
      key: "display_unit", label: "Display unit", type: "select",
      options: [
        { value: "auto", label: "Auto (suggest)" },
        { value: "nV", label: "nV" },
        { value: "uV", label: "µV" },
        { value: "mV", label: "mV" },
        { value: "V", label: "V" },
      ],
      help: "Amplitude unit for the y-axis, fit, and Vmax table — a pure rescale (nothing re-measured). Auto picks the unit that reads cleanest.",
    },
  ],
  // ERG flicker — steady-state waveform grid OR N1→P1-vs-frequency summary.
  erg_flicker: [
    {
      key: "view", label: "View", type: "select",
      options: [
        { value: "waveform", label: "Waveform grid (frequency × condition)" },
        { value: "summary", label: "N1→P1 vs frequency" },
      ],
      help: "The steady-state flicker waveforms as floating small-multiples, or the N1→P1 amplitude plotted against flicker frequency (needs ≥2 frequencies to read as a curve).",
    },
    { key: "filter", label: "Clean traces", type: "switch", help: "Notch line-noise + low-pass; the flicker fundamental (10–30 Hz) is well below the cutoff, so it is preserved." },
    { key: "marks", label: "Mark N1 / P1", type: "switch", help: "Dot the N1 (trough) and P1 (peak) on each waveform panel — a visual locator on the first cycle. The reported N1→P1 amplitude itself comes from the device markers when present (else the phase-folded cycle)." },
    { key: "lowpass_hz", label: "Low-pass cutoff (Hz)", type: "range", step: 10, help: "Lower = smoother. The 10–30 Hz flicker response sits well below the default 120 Hz." },
    {
      key: "display_unit", label: "Display unit", type: "select",
      options: [
        { value: "auto", label: "Auto (suggest)" },
        { value: "nV", label: "nV" },
        { value: "uV", label: "µV" },
        { value: "mV", label: "mV" },
        { value: "V", label: "V" },
      ],
      help: "Amplitude unit for the waveforms, scale bar, and N1/P1 table — a pure rescale (nothing re-measured). Auto picks the unit that reads cleanest for the (small) flicker signal.",
    },
    { key: "scale_uv", label: "Scale bar — amplitude (µV)", type: "number", step: 5, help: "Vertical scale-bar length, set in µV (flicker amplitudes are small — ~20 µV is a good default)." },
    { key: "scale_ms", label: "Scale bar — time (ms)", type: "number", step: 10, help: "Horizontal scale-bar length (a 10 Hz cycle is 100 ms, a 30 Hz cycle ~33 ms)." },
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
    enabledWhen: pres.enabledWhen,
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
 * Every presentation-overlay key, per backend runtime slug — the surface the
 * registry-completeness gate (B5) validates against the backend `param_spec`. Each
 * key here MUST back to a `skills/<slug>/skill.json` param_spec entry, or the merge
 * in `paramFieldsFromSpec` silently drops it (`warnDeadKnob`); the gate promotes that
 * drift from a dev console warning to a failing test. Keyed by the runtime slug used
 * to look up the spec, so the test compares like-for-like.
 */
export function overlayParamKeys(): Record<string, string[]> {
  return Object.fromEntries(
    Object.entries(PRESENTATION).map(([id, fields]) => [id, fields.map((f) => f.key)]),
  );
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
  return schema.filter((f) => !f.showWhen || gateMatches(f.showWhen, schema, params));
}

/**
 * Whether a rendered field should be shown DISABLED right now — true when it declares an
 * `enabledWhen` gate that the current params don't satisfy (the field still renders; the control
 * is greyed + non-interactive). The companion to `visibleParamFields`: `showWhen` hides, `enabledWhen`
 * disables. Reads the gate field's effective value (current param or its default) with the same
 * loose comparison, so a backend bool and a select's string are the same gate value.
 */
export function isFieldDisabled(schema: ParamField[], field: ParamField, params: SkillParams): boolean {
  return field.enabledWhen ? !gateMatches(field.enabledWhen, schema, params) : false;
}

/** Does the current (or default) value of the gate's field match its `equals`? Loose compare. */
function gateMatches(
  gate: { key: string; equals: string | number | boolean },
  schema: ParamField[],
  params: SkillParams,
): boolean {
  const current = params[gate.key] ?? schema.find((x) => x.key === gate.key)?.default;
  return current === gate.equals || String(current) === String(gate.equals);
}

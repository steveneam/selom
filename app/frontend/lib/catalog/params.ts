import { runtimeSkillId } from "@/lib/skills/api";
import type { SkillParams } from "@/lib/skills/api";
import type { GroupCandidate } from "@/lib/intake/design";

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
 * `paramFieldsFromSpec(id, spec, ctx?)` merges the two into the rendered `ParamField[]`.
 * It is pure (no fetch); `useSkillParams` (lib/catalog/use-skill-params) loads the
 * spec and calls it. Skills with no overlay entry simply render no inline controls
 * and run with their backend defaults.
 *
 * `ctx` (a {@link ParamDataContext}) is the OPTIONAL third input: the loaded dataset's own
 * schema — its columns and its categorical levels, both already fetched by `/data/inspect` and
 * persisted on the dataset. It is what turns a "type the column name" text box into a picker
 * over the columns that actually exist. It is the ONE place dataset knowledge enters this
 * module: `visibleParamFields` / `isFieldDisabled` stay pure over (schema, params), because the
 * merge has already baked the vocabulary onto the field.
 *
 * **Fail-soft is the contract, not a nicety.** `ctx` is legitimately absent — demo/sample data, a
 * dataset whose inspect failed, a matrix (h5ad) where `columns` is empty by construction, the
 * Figure-data panel on a figure whose dataset was deleted. With no usable context a `column` /
 * `pairs` field renders as the plain text field it always was, and the merge is byte-identical to
 * a context-free one. `params.test.ts` pins that.
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

/**
 * The loaded dataset's own schema, threaded into the merge so a column knob can be PICKED rather
 * than typed. Every field maps 1:1 onto something `/data/inspect` already returns and the FE
 * already persists on the `Dataset` (`lib/projects/types.ts`), so this costs no request:
 *
 *   - `columns`      ← `data_fit.columns`          (every column in the table)
 *   - `groups`       ← `design.group_candidates[]` (categorical columns + their level names)
 *
 * Both optional: a matrix (h5ad) has no `columns` by construction, and a dataset whose inspect
 * failed has neither. Absent → the fields render exactly as they did before any of this existed.
 *
 * `design.best_group` is deliberately NOT threaded. It is the engine's pick for a *deg contrast*,
 * and a chart skill's auto-detect is a different rule (boxplot's blank `group` takes the first
 * non-numeric column — `sample_id` on the real ERG table, where `best_group` is `condition`). Using
 * it as the pair picker's fallback would offer levels from a column the run is not grouping by:
 * confident, wrong, and indistinguishable from correct on screen.
 */
export interface ParamDataContext {
  columns?: string[] | null;
  groups?: GroupCandidate[] | null;
}

/**
 * A conditional gate on another field's current value, shared by `showWhen` and `enabledWhen`.
 *
 * `not` inverts the match, and exists for one shape the plain `equals` cannot express: a knob that
 * is inert until a free-text field is NON-empty. `equals: ""` already reads "that field is blank"
 * (an unset param falls back to its default, and these default to `""`), so the inverse is the only
 * missing half. Kept as a flag on the same gate rather than a second gate type, so both consumers
 * — `visibleParamFields` and `isFieldDisabled` — keep one comparison between them.
 */
export interface FieldGate {
  key: string;
  equals: string | number | boolean;
  not?: boolean;
}

/** A rendered parameter control (what `ParamControl` consumes). */
export interface ParamField {
  key: string;
  label: string;
  /**
   * `column` — a picker over the dataset's real columns (falls back to `text` with no context).
   * `pairs`  — the repeatable "compare A vs B" row-list (falls back to `text` with no levels).
   * Both are *resolved* widgets: they are only emitted when the vocabulary to fill them exists,
   * so `ParamControl` never has to render an empty picker.
   */
  type: "range" | "number" | "text" | "switch" | "select" | "column" | "pairs";
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
  showWhen?: FieldGate;
  /**
   * Conditional *enablement* (vs `showWhen`'s conditional visibility): the field always
   * RENDERS, but is shown disabled (greyed, non-interactive) until another field equals
   * `equals`. Use for a capability-signaling control that should stay DISCOVERABLE even when
   * inert — e.g. the ERG trace grid's Spread / Error-metric knobs, which only act when
   * "Trace shows" is Mean of replicates but should advertise that the SEM/SD/band options
   * exist. Cosmetic fine-tuning that would only clutter the panel stays on `showWhen` (hidden).
   * See `isFieldDisabled`.
   */
  enabledWhen?: FieldGate;
  /**
   * `column` fields only — the dataset's columns, annotated where the engine also told us the
   * column is categorical (`condition — 6 levels`). That annotation is the honest Selom form of the
   * type glyph mature builders show beside a field (Snowflake's `A`, Glide's `123`): the inspect
   * payload carries no per-column dtype, but it DOES carry level counts for the categorical ones,
   * which is the distinction that actually matters when choosing a group vs a value column.
   */
  columns?: { value: string; label: string }[];
  /**
   * `pairs` fields only — level names per candidate group column, and which sibling field names
   * the group column in play. The pair vocabulary depends on a param the user picks at RUN time,
   * so the options can't be frozen at merge time; `visibleParamFields` resolves them per render
   * (and drops the field back to `text` when the chosen column has no known levels).
   */
  levelsByGroup?: Record<string, string[]>;
  levelsFrom?: string;
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
  showWhen?: FieldGate;
  /** Show-but-disable gate (see `ParamField.enabledWhen`): the control always renders, greyed
   *  until the named field matches `equals`. For discoverable-but-inert capability controls. */
  enabledWhen?: FieldGate;
  /** `pairs` only — the sibling field naming the group column whose levels this picker offers
   *  (e.g. boxplot's `group`). Omitted → the engine's `best_group` is the only source. */
  levelsFrom?: string;
}

/**
 * The two gene-list cutoffs shared by every over-representation skill (`enrichment` · `pathway` ·
 * `go_graph`). Declared ONCE because the semantics are easy to misread and easier to let drift
 * across three panels: these do **not** filter the terms the figure draws — each term carries its
 * own enrichment p — they decide which rows of the input DE table become the QUERY gene list that
 * gets tested. Both are inert on a bare gene list (there is no adjusted-p column to filter on), so
 * the help says that rather than leaving a control that silently does nothing on half the inputs.
 *
 * Contrast `volcano`/`proteomics_de`, where the SAME two keys are the significance test itself and
 * are drawn on the canvas as dashed lines. Same names, different jobs — which is exactly why the
 * wording lives here instead of being retyped per skill.
 */
/**
 * The gene-list adjusted-p cutoff, as its own factory because FOUR skills take it and only three of
 * them draw terms. `string_network` draws EDGES, each carrying a STRING confidence score rather than
 * an enrichment p — so the "not a cutoff on the X drawn" clause is the one part that varies, and it
 * is the part most worth saying. It was hand-copied here once and had already drifted (the clause
 * was simply dropped), which is the failure this file's shared blocks exist to prevent.
 */
const geneListFdr = (notACutoffOn: string): ParamPresentation => ({
  key: "fdr_threshold", label: "Gene-list cutoff (adjusted p)", type: "number", step: 0.001,
  help: `Which rows of your DE table become the query gene list. ${notACutoffOn} Ignored for a bare gene list.`,
});

/**
 * The pairwise-comparison block — the test and the correction applied to `pairs`.
 *
 * THREE skills declare these (`boxplot` · `violin` · `lollipop`) and they mean exactly one thing.
 * Confirmed the KNOBS-2 way, by reading each runner's BODY rather than matching the key name: all
 * three call `test_pairs(parse_pairs(params["pairs"]), values_of, test=…, correction=…)` from the
 * same `skills/_stats.py`, with the same `welch`/`none` defaults — byte-identical calls
 * (`boxplot/run.py:111` · `violin/run.py:126` · `lollipop/run.py:203`).
 *
 * `pairs` itself is NOT in this block, and that is the point: it is the same knob by meaning but a
 * different WIDGET per skill. `boxplot`/`lollipop` resolve a row-list over the group column's real
 * levels; `violin` stays a text box on purpose, because its clusters do not exist until the run.
 * Sharing the two that are genuinely identical and letting the third vary is the honest split —
 * folding `pairs` in would force one widget onto a skill whose vocabulary is not knowable yet.
 */
const COMPARISON_STATS: ParamPresentation[] = [
  {
    key: "sig_test", label: "Significance test", type: "select", help: "Applied to every pair above.",
    options: [
      { value: "welch", label: "Welch t-test (unequal variance)" },
      { value: "student", label: "Student t-test (equal variance)" },
      { value: "mannwhitney", label: "Mann-Whitney U (rank)" },
    ],
  },
  {
    key: "correction", label: "Multiple-comparison correction", type: "select",
    help: "Several brackets means several shots at p<0.05. Correcting adjusts BOTH the stars and the table.",
    options: [
      { value: "none", label: "None (raw p)" },
      { value: "bonferroni", label: "Bonferroni" },
      { value: "bh", label: "Benjamini-Hochberg (FDR)" },
    ],
  },
];

const GENE_LIST_CUTOFFS: ParamPresentation[] = [
  geneListFdr("Not a cutoff on the terms drawn — each of those carries its own p."),
  {
    key: "fc_threshold", label: "Gene-list fold-change cutoff (log₂)", type: "range", step: 0.1,
    help: "Require |log₂FC| ≥ this as well, narrowing the query list by effect size. 0 = no fold-change filter, so the adjusted p alone decides it.",
  },
];

/**
 * `normalize` — the scRNA preparation switch. ELEVEN skills declare it and mean exactly one thing:
 * `to_bool(params.get("normalize", True))` gating `sc.pp.normalize_total(target_sum=1e4)` +
 * `sc.pp.log1p`. That was confirmed by reading each runner's BODY, not by matching the key name —
 * which is the whole reason this block exists, because **three other skills declare a param called
 * `normalize` that is a different knob**:
 *
 *   - `pvca.normalize`      — divides each feature by its SD (unit variance before PCA). It is the
 *                             twin of `pca.scale`, not of this. (`skills/pvca/run_real.py:40`)
 *   - `scorecard.normalize` — min–max scales each METRIC COLUMN so radar axes are comparable.
 *   - `confusion.normalize` — a `str` enum (none/row/column/all): which matrix reading to show.
 *
 * Same name, different job — the collision `fc_threshold` already has between `volcano` (where it
 * IS the significance test, drawn as a dashed line) and the over-representation trio (where it
 * selects the query gene list). A shared block is only correct where the MEANING is shared, so
 * those three are deliberately absent below and keep their own wording.
 *
 * `deg` belongs to this block by meaning (`skills/deg/run_real.py:92`, same call, same comment) and
 * is left out only because its panel is specced as a whole (board NEXT#1(d)) — spread it in there.
 */
/** The shared sentence itself, exported so the guard can assert membership rather than trust prose. */
export const SCRNA_NORMALIZE_HELP =
  "Log-normalize raw counts (counts-per-10k, then log1p) before the analysis. Turn this OFF only " +
  "if your file is already normalized — doing it twice compresses the differences you are looking for.";

const scrnaNormalize = (extra = ""): ParamPresentation => ({
  key: "normalize", label: "Normalize input", type: "switch",
  help: SCRNA_NORMALIZE_HELP + (extra ? ` ${extra}` : ""),
});

/**
 * `groupby` — the cell-grouping column, for the skills where it names the levels the figure is
 * DRAWN over: `markers` (dotplot rows) · `violin` (categories) · `annotate` (the unit scored) ·
 * `trajectory` (PAGA nodes) · `heatmap` (marker genes per group). All five resolve it identically —
 * the named obs column if the file carries one, else Leiden clusters computed on the spot — and the
 * fallback sentence is `heatmap`'s, which had the clearest wording of the five and is now its one home.
 *
 * **`pseudotime_genes.groupby` is NOT in this block**, and that exclusion is the point of having
 * one: there the column never reaches the figure at all. `compute_pseudotime(adata, root, groupby)`
 * uses it ONLY to pick the cell the trajectory is rooted at (`skills/_scrna.py:28`) while the axis
 * is pseudotime bins, and its own `note` in `skill.json` says so. Same key, different job — as with
 * `normalize` above, three times over.
 */
const scrnaGroupby = (purpose: string): ParamPresentation => ({
  key: "groupby", label: "Group cells by", type: "text", placeholder: "leiden",
  help: `${purpose} If your file has no such column, Selom clusters the cells itself (Leiden) and groups by that.`,
});

/**
 * The gene-set library pair — `gene_sets` (which collection to score) and `gene_set` (paste your
 * own instead). Shared by `enrichment` · `gsea` · `ssgsea`, whose runners resolve them through
 * byte-identical code: the same `_SOURCE_ALIASES` map into `gene_sets.library.load_collection`,
 * and the same `_parse_panel` split on commas/whitespace. Confirmed by reading each runner's BODY
 * (`skills/gsea/run_real.py:104` · `skills/ssgsea/run_real.py:55`), the `normalize`/`pvca` rule.
 *
 * The METHOD is not shared and the wording must not pretend otherwise: `enrichment` is an
 * over-representation test on a gene LIST, `gsea` walks a whole ranked contrast, `ssgsea` scores
 * each sample independently. So the shared part is the library and the override; the clause naming
 * what scores against it is passed in.
 *
 * ⚑ THE OVERRIDE IS THE REASON THESE TRAVEL TOGETHER. A non-empty `gene_set` switches the run into
 * single-set mode and the library selection stops mattering entirely — silently, today, because the
 * two were independent controls. Mobbin was unanimous that mature products make an override an
 * EXPLICIT mode rather than an emergent one: Google AI Studio puts "Write my own instructions" in
 * the same dropdown as the presets (https://mobbin.com/screens/675981da-f3cf-42a5-b10f-0655500284f9),
 * and WRITER uses a segmented `Upload new file | Paste URL | Paste text`
 * (https://mobbin.com/screens/90363e8d-d9ab-466d-8953-abd6a2c11920) — one decision, one control.
 * Selom cannot adopt either shape without inventing a backend `mode` param the runners do not have,
 * which is a contract change, not a reachability fix. So the honest half is taken: the library
 * control GREYS OUT the moment a set is pasted (`enabledWhen`), which makes the override visible at
 * the instant it takes effect. Recorded as ruled-out-with-reason, not as a pattern to copy later.
 */
const geneSetLibrary = (scoredBy: string, overridable = false): ParamPresentation => ({
  key: "gene_sets", label: "Reference library", type: "select",
  options: [
    { value: "go", label: "Gene Ontology" },
    { value: "wikipathways", label: "WikiPathways" },
    { value: "curated", label: "Selom curated" },
    { value: "reference", label: "Reference panels" },
    { value: "all", label: "All sources" },
  ],
  // `resolveOptions` intersects these with the skill's own declared options, so `enrichment` —
  // whose skill.json omits `reference` — renders its four and no dead choice appears.
  //
  // `overridable` is NOT cosmetic and defaults to off: `enrichment` declares no `gene_set` param at
  // all, and a gate naming a key absent from the schema reads `undefined`, never matches `""`, and
  // would leave its library select PERMANENTLY DISABLED. The sentence would be false there too —
  // there is no paste field to override it. Sharing the vocabulary means sharing what is actually
  // shared; the override belongs to the two skills that have one.
  help: overridable
    ? `The license-clean library ${scoredBy}. Ignored while you have pasted your own gene set below.`
    : `The license-clean library ${scoredBy}.`,
  enabledWhen: overridable ? { key: "gene_set", equals: "" } : undefined,
});

const pastedGeneSet = (instead: string): ParamPresentation => ({
  key: "gene_set", label: "Or paste your own gene set", type: "text",
  placeholder: "TP53, BRCA1, EGFR",
  help: `Gene symbols separated by commas or spaces. Leave blank to use the reference library above; fill it in and ${instead}`,
});

const PRESENTATION: Record<string, ParamPresentation[]> = {
  // scRNA UMAP — the prep/QC + embedding knobs the runner honours. Resolution lives on
  // `cluster`, not here, so it isn't surfaced (the UMAP runner's Leiden uses the default).
  umap_scrna: [
    scrnaNormalize(),
    { key: "n_hvg", label: "Highly variable genes", type: "range", step: 250, help: "Top-N variable genes used for PCA (0 = all genes; ~2000 is the standard choice)." },
    { key: "n_neighbors", label: "Neighbours (kNN)", type: "range", step: 1, help: "Local neighbourhood size for the graph + UMAP." },
    { key: "n_pcs", label: "Principal components", type: "range", step: 1, help: "PCs that build the neighbour graph." },
  ],
  // Leiden clustering — the runner honours resolution + the same graph knobs.
  cluster: [
    { key: "resolution", label: "Cluster resolution", type: "range", step: 0.1, help: "Higher = more, finer clusters." },
    { key: "n_neighbors", label: "Neighbours (kNN)", type: "range", step: 1, help: "Local neighbourhood size for the graph." },
    { key: "n_pcs", label: "Principal components", type: "range", step: 1, help: "PCs that build the neighbour graph." },
    scrnaNormalize(),
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
    scrnaNormalize(),
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
  // `pairs` is the repeatable row-list Mobbin is unanimous about (beehiiv "+ Condition" · Braintrust
  // / Confluence / ClickUp / AutoSend "+ Add filter" · Glide's numbered ITEM blocks with "+ Add item"
  // — every one a row of typed selects with a per-row delete and an explicit "+ Add" beneath). It
  // renders as that row-list once the group column is chosen, and as the old text field until then,
  // because the levels come from the CHOSEN column and blank means backend auto-detect.
  //
  // The vocabulary needed one backend change to exist at all: `design.group_candidates` was empty
  // for `generic_table` — the exact kind a long-form CSV lands in, i.e. the only kind that uses
  // `pairs=`. `engine/questionnaire._table_hints` now fills it WITHOUT claiming a design
  // (`needs_design` stays false, so no intake confirm-card appears for a dropped CSV).
  boxplot: [
    { key: "style", label: "Chart style", type: "select", help: "Strip hides the box and shows every individual value — honest when n is small, where a box implies more data than you have.", options: [
      { value: "box", label: "Box plot (quartiles + whiskers)" },
      { value: "strip", label: "Strip plot (individual points only)" },
    ] },
    { key: "group", label: "Group column", type: "column", placeholder: "auto-detect", help: "Column holding the category. Blank = first non-numeric column." },
    { key: "value", label: "Value column", type: "column", placeholder: "auto-detect", help: "Column holding the measurement. Blank = first numeric column." },
    { key: "order", label: "Category order", type: "text", placeholder: "e.g. Control, Low, High", help: "Comma-separated. Named categories lead, in this order; the rest follow unchanged." },
    { key: "add_count", label: "Show n per group", type: "switch", help: "Append n= to each category label." },
    { key: "pairs", label: "Compare groups", type: "pairs", levelsFrom: "group", placeholder: "e.g. Control~Treated, Control~Rescue", help: "Each pair draws a bracket with significance stars, and its p-value appears in the Statistics table. Pick the group column above to choose from its real levels." },
    ...COMPARISON_STATS,
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
  // Scatter (backend slug `regression`, kept for provenance). It had NO overlay at all, so x/y/
  // group/label were API-only — the same gap boxplot had. `fit` is last because the fit is the
  // default reading of this figure; turning it off is the deliberate act, not the common one.
  regression: [
    { key: "x", label: "X column", type: "column", placeholder: "auto-detect", help: "Blank = the first numeric column." },
    { key: "y", label: "Y column", type: "column", placeholder: "auto-detect", help: "Blank = the second numeric column." },
    { key: "group", label: "Colour by", type: "column", placeholder: "e.g. condition, genotype", help: "A category column. Each value becomes its own colour and legend entry." },
    { key: "label", label: "Label points with", type: "column", placeholder: "e.g. sample_id", help: "Annotates every point — best on small tables." },
    { key: "fit", label: "Show trend line", type: "switch", help: "Ordinary-least-squares fit with R², slope and p. Off draws a plain scatter and computes no fit." },
  ],
  // Lollipop — a ranked value per category. The estimator/CI wording says what the interval IS,
  // because a bootstrap interval and a mean±SEM are different claims and the figure draws one bar
  // for either.
  lollipop: [
    { key: "group", label: "Category column", type: "column", placeholder: "auto-detect", help: "Blank = the first non-numeric column." },
    { key: "value", label: "Value column", type: "column", placeholder: "auto-detect", help: "Blank = the first numeric column." },
    { key: "estimator", label: "Dot shows", type: "select", options: [
      { value: "median", label: "Median" },
      { value: "mean", label: "Mean" },
    ], help: "Median is the default — a ranking is usually read off the median." },
    { key: "sort", label: "Rank by", type: "select", options: [
      { value: "desc", label: "Highest first" },
      { value: "asc", label: "Lowest first" },
      { value: "none", label: "Order in the file" },
    ] },
    { key: "orientation", label: "Direction", type: "select", options: [
      { value: "h", label: "Horizontal (ranked list)" },
      { value: "v", label: "Vertical" },
    ], help: "Horizontal gives long category names room instead of a tick rotation." },
    { key: "error_bars", label: "95% confidence interval", type: "switch", help: "A seeded percentile bootstrap. Needs 3+ values per category — an already-aggregated table gets no interval rather than a fabricated one." },
    { key: "add_tip", label: "Label each value", type: "switch", help: "Print the number beside its dot." },
    { key: "add_count", label: "Show n per category", type: "switch" },
    // ⚑ `pairs` is what MAKES lollipop's second Statistics table exist — without a control, the
    // multi-table result shipped in the same change would have been unreachable from the UI, which
    // is [[selom-shipped-not-reachable]] one layer further in than a knob: an unreachable contract
    // capability. The help carries the one thing lollipop's `pairs` must say and boxplot's need
    // not: an already-aggregated table is n=1 per category, so every test would be n=1 vs n=1 and
    // the runner drops the comparison rather than printing "ns" whatever the data says.
    { key: "pairs", label: "Compare groups", type: "pairs", levelsFrom: "group", placeholder: "e.g. Control~Treated, Control~Rescue", help: "Each pair draws a bracket with significance stars, and the p-values arrive as a second Statistics table beside the ranked values. Ignored on an already-aggregated table (one row per category), where every test would compare a single value with a single value." },
    ...COMPARISON_STATS,
  ],
  // Ridge — the honesty knob is `scale`, so it is surfaced rather than left to the API. Peak
  // normalization is the ridgeline convention AND the thing that makes a 5-point group look like
  // a 5000-point one, so the control has to state that trade rather than just name the modes.
  ridge: [
    { key: "group", label: "Category column", type: "column", placeholder: "auto-detect", help: "One ridge per level. Blank = the first non-numeric column." },
    { key: "value", label: "Value column", type: "column", placeholder: "auto-detect", help: "Blank = the first numeric column." },
    { key: "order", label: "Ridge order", type: "text", placeholder: "e.g. Control, Treated", help: "Comma-separated. Named groups lead, in this order; the rest follow by descending median, which is the default for all of them." },
    { key: "scale", label: "Ridge height", type: "select", options: [
      { value: "peak", label: "Normalized per group (compare shapes)" },
      { value: "common", label: "Shared density scale (compare heights)" },
    ], help: "Normalized makes every ridge the same height, so a group of 5 looks as tall as one of 5000 — the n= label is then the only size cue." },
    { key: "overlap", label: "Overlap", type: "range", step: 0.05, help: "How far each ridge rides over the one below. 0 separates them completely." },
    { key: "median_line", label: "Mark the median", type: "switch" },
    { key: "add_count", label: "Show n per ridge", type: "switch" },
  ],
  // Confusion — two labellings of the same rows. `normalize` leads because it changes what the
  // reader is looking at (counts vs per-class recall), not merely how it looks.
  confusion: [
    { key: "true", label: "Reference labels (rows)", type: "column", placeholder: "auto-detect", help: "The ground-truth or reference annotation. Blank = the first categorical column." },
    { key: "predicted", label: "Compared labels (columns)", type: "column", placeholder: "auto-detect", help: "The predicted or second annotation. Blank = the next categorical column." },
    { key: "normalize", label: "Cells show", type: "select", options: [
      { value: "none", label: "Counts" },
      { value: "row", label: "% of each reference label (recall)" },
      { value: "column", label: "% of each compared label" },
      { value: "all", label: "% of all rows" },
    ], help: "The raw count stays in the hover, so a 100% row of one observation cannot pass for a hundred." },
    { key: "annotate", label: "Print values in cells", type: "switch", help: "Dropped automatically above 400 cells." },
  ],
  // Slope — the ONLY skill here that refuses to auto-detect its key columns, because pairing the
  // wrong rows produces a confident and completely wrong figure. That refusal is exactly why it
  // gains the most from the picker: the required columns are now chosen from the ones the dataset
  // actually has, instead of typed and silently failing at run time.
  //
  // The "(required)" marking is GitHub Insights' explicit "(optional)" convention INVERTED, and it
  // stays useful after the picker: a picker makes the value valid, not necessarily the one meant.
  slope: [
    { key: "subject", label: "Subject column (required)", type: "column", placeholder: "e.g. sample_id, animal, patient", help: "What makes two rows the same individual. Never guessed — the wrong choice pairs the wrong rows and the figure still looks right." },
    { key: "condition", label: "Condition column (required)", type: "column", placeholder: "e.g. timepoint, intensity_group", help: "The column holding the two states being compared." },
    { key: "levels", label: "Which two, in order", type: "text", placeholder: "e.g. before, after", help: "Required when the condition column has more than two levels — picking two silently would decide the whole result." },
    { key: "value", label: "Value column", type: "column", placeholder: "auto-detect", help: "Blank = the first numeric column." },
    { key: "group", label: "Cluster by", type: "column", placeholder: "optional", help: "Draws one before/after pair per group along the x-axis." },
    { key: "order", label: "Group order", type: "text", placeholder: "e.g. Control, Treated", help: "Comma-separated. Named groups lead along the x-axis, in this order; the rest follow unchanged. Needs Cluster by." },
    { key: "summary", label: "Summary line", type: "select", options: [
      { value: "mean", label: "Mean" },
      { value: "median", label: "Median" },
      { value: "none", label: "None" },
    ] },
    { key: "sig_test", label: "Significance test", type: "select", options: [
      { value: "paired_t", label: "Paired t-test" },
      { value: "wilcoxon", label: "Wilcoxon signed-rank" },
    ], help: "Both are paired by design — an unpaired test would discard the pairing this figure is built on." },
    { key: "points", label: "Mark each value", type: "switch" },
  ],
  // Line — the spread vocabulary here is the SAME one the bar chart and the ERG trace grid use
  // (skills/_charts.py), because it is the same code. Keep the wording identical to those so a
  // user who learns "Spread shows" once does not relearn it per chart type.
  line: [
    { key: "x", label: "X column", type: "column", placeholder: "auto-detect", help: "Blank = the first numeric column." },
    { key: "y", label: "Y column", type: "column", placeholder: "auto-detect", help: "Blank = the second numeric column." },
    { key: "series", label: "One line per", type: "column", placeholder: "e.g. condition, genotype", help: "A category column. Never auto-detected — guessing it would silently change what the figure means." },
    { key: "spread", label: "Spread shows", type: "select", options: [
      { value: "band", label: "Shaded band" },
      { value: "error_bars", label: "Error bars" },
      { value: "individual", label: "Individual replicates" },
      { value: "both", label: "Band + individual replicates" },
      { value: "none", label: "No spread" },
    ] },
    { key: "error", label: "Error metric", type: "select", help: "What the band or bars measure.", options: [
      { value: "sem", label: "SEM (standard error)" },
      { value: "sd", label: "SD (standard deviation)" },
      { value: "ci95", label: "95% confidence interval" },
      { value: "minmax", label: "Min-max range" },
    ] },
    { key: "central", label: "Line shows", type: "select", options: [
      { value: "mean", label: "Mean of replicates" },
      { value: "representative", label: "A representative replicate" },
      { value: "none", label: "No central line" },
    ] },
    { key: "markers", label: "Mark each point", type: "switch", help: "Show a marker at every measured x." },
    { key: "points", label: "Show replicates", type: "switch", help: "Plot every individual value behind the line." },
    { key: "log_x", label: "Log x-axis", type: "switch", help: "For dose or intensity ladders." },
  ],
  // Set overlap (venn · upset) — one input shape, two views. venn's `sets` is the choice the
  // figure cannot make for you above three columns: the engine falls back to the largest three
  // and SAYS so in the title, but naming them is what makes the figure the one you meant.
  venn: [
    { key: "sets", label: "Sets to draw", type: "text", placeholder: "e.g. Rod, Cone, Bipolar", help: "Comma-separated column names, 2 or 3. Blank = the three largest, and the title says so. For more sets, use the UpSet plot." },
    { key: "show_percent", label: "Show % of union", type: "switch", help: "Print each region's share of the union under its count." },
  ],
  // Forest — effect + interval. `conf_level` only acts when the interval is DERIVED (from a
  // standard error or t-statistic); a table carrying explicit CI columns is used as-is, which is
  // why the control says so rather than implying it always applies.
  forest: [
    { key: "top_n", label: "Features shown", type: "range", step: 1, help: "A forest plot is read row by row; past ~30 rows it stops being legible." },
    { key: "sort_by", label: "Order rows by", type: "select", options: [
      { value: "significance", label: "Significance (most significant first)" },
      { value: "effect", label: "Effect size (largest magnitude first)" },
      { value: "label", label: "Feature name (A-Z)" },
      { value: "none", label: "Table order" },
    ] },
    { key: "conf_level", label: "Confidence level", type: "range", step: 0.01, help: "Used when the interval is derived from a standard error or t-statistic. Explicit CI columns in your table are used as they are." },
    { key: "ref_line", label: "Null line", type: "number", step: 0.5, help: "0 for a log fold-change or coefficient; 1 for an unlogged ratio." },
  ],
  // Q-Q — a calibration check. `p_col` is surfaced first because auto-detect deliberately
  // REFUSES adjusted columns (an adjusted p is monotone-transformed, so λ and the quantiles
  // would be meaningless), and a table whose only p-column is adjusted needs the user to say so.
  qq: [
    { key: "p_col", label: "P-value column", type: "column", placeholder: "auto-detect", help: "Must be RAW p-values. Adjusted/FDR columns are skipped by auto-detect on purpose — their quantiles and λ are not interpretable." },
    { key: "band", label: "Show 95% null band", type: "switch", help: "The pointwise interval a calibrated test should stay inside." },
    { key: "top_n", label: "Points in the table", type: "range", step: 1, help: "How many of the most extreme features to list in the Statistics table." },
    // step 100, not 500: a range input snaps to `min + k*step`, and with min 200 the 500-step
    // lattice does not contain the spec's own 6000 default — the thumb sat at 5700 while the
    // readout beside it said 6000. Caught by the slider-step guard in registry-completeness.
    { key: "max_points", label: "Plotted-point budget", type: "range", step: 100, help: "Large tables are thinned to keep the figure editable. The significant tail is always kept whole; λ and n always use every p-value." },
  ],
  // Violin keeps the SAME vocabulary, order and wording as boxplot — but its `pairs` stays a text
  // field, and that asymmetry is deliberate. A violin's categories are Leiden clusters, which do not
  // exist until the run produces them, so there is no pre-run level list to offer; `/data/inspect`
  // reads an h5ad's obs, never its future clustering. A picker here would have to source levels from
  // some other factor, which is the "confident and wrong" failure the whole design refuses. The
  // widget differs because the data does; the vocabulary is identical.
  violin: [
    { key: "gene", label: "Marker gene", type: "text", placeholder: "e.g. MS4A1" },
    scrnaGroupby("The cell-annotation column whose levels become one violin each — e.g. cell_type."),
    // Immediately after `groupby`, because it only does anything in that knob's FALLBACK case.
    // Parked at the end of the panel it sat a full scroll away from the control that triggers it.
    { key: "resolution", label: "Cluster resolution", type: "range", step: 0.1,
      help: "Only used when Selom has to cluster the cells itself — i.e. when “Group cells by” names no column your file has. Higher = more, finer clusters." },
    { key: "order", label: "Category order", type: "text", placeholder: "e.g. cluster 2, cluster 0", help: "Comma-separated. Named categories lead, in this order; the rest follow unchanged." },
    { key: "add_count", label: "Show n per group", type: "switch", help: "Append n= to each category label." },
    { key: "pairs", label: "Compare groups", type: "text", placeholder: "e.g. cluster 0~cluster 1", help: "Comma-separated pairs joined by ~. Each draws a bracket with significance stars, and the p-values appear in the Statistics table. A name that doesn't match a group is skipped." },
    ...COMPARISON_STATS,
    // The PubMed annotation block. `context` and `known_min` do nothing unless the annotation is on,
    // so they are gated on it rather than left as two controls that silently no-op.
    { key: "annotate", label: "Annotate with literature", type: "select", options: [
      { value: "none", label: "None" },
      { value: "pubmed", label: "PubMed hit count" },
    ], help: "Look the gene up in PubMed and note how well studied it is. Best-effort — an unreachable lookup leaves the figure unannotated rather than failing the run." },
    { key: "context", label: "Literature context", type: "text", placeholder: "e.g. retina, macrophage", showWhen: { key: "annotate", equals: "pubmed" },
      help: "Narrows the PubMed query to this field, so a gene famous elsewhere is not counted as well studied here." },
    // step 1, not 5: a `number` input snaps to `min + k*step` exactly as a range does, and min 1 /
    // step 5 would make the default 5 an INVALID value the browser rejects.
    { key: "known_min", label: "“Well studied” threshold (papers)", type: "number", step: 1, showWhen: { key: "annotate", equals: "pubmed" },
      help: "At or above this many hits, the gene is called well studied. Below it, novel. The count is a LIVE PubMed lookup made when the figure runs, so re-running later can move it." },
    scrnaNormalize(),
  ],
  // Composition takes the ordering half of the vocabulary only — it holds one value per
  // category x condition cell, so there is no distribution to test. See the note at the top of
  // app/backend/skills/composition/run.py.
  composition: [
    { key: "order", label: "Category order", type: "text", placeholder: "e.g. Rods, Bipolar", help: "Comma-separated. Named categories lead, in this order; the rest follow unchanged." },
    { key: "sort_by", label: "Sort by series", type: "column", placeholder: "a value column", help: "Sort categories by one series' values. Applied before Category order." },
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
    scrnaGroupby("The cell-annotation column to take marker genes per group from — e.g. cell_type if your file carries one."),
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
    geneSetLibrary("the over-representation test scores against"),
    {
      key: "direction", label: "Direction", type: "select",
      options: [
        { value: "combined", label: "Combined" },
        { value: "split", label: "Up / down split" },
      ],
      help: "Split scores up- and down-regulated genes separately (diverging dotplot). Needs a fold-change column.",
    },
    {
      key: "top_n", label: "Terms shown", type: "range", step: 1,
      help: "How many of the most enriched terms to draw. Under a split, this many per direction.",
    },
    ...GENE_LIST_CUTOFFS,
  ],
  // Pathway map — a live Reactome over-representation drawn as a parent→child node-link, so
  // `top_n` sets how many pathway nodes the map holds, not just how many rows a list shows.
  pathway: [
    {
      key: "top_n", label: "Pathways shown", type: "range", step: 1,
      help: "How many of the most enriched Reactome pathways become nodes. The parent→child edges are drawn among these.",
    },
    ...GENE_LIST_CUTOFFS,
  ],
  // GO enrichment graph — same query-set contract as `enrichment`, plus the one knob that is
  // specific to GO: which of the three ontologies to keep. The backend declares `namespace` as a
  // free string, but the DAG only ever holds BP / MF / CC, so the control offers those and names
  // blank as "all three" instead of leaving a text box the user has to guess the tokens for.
  go_graph: [
    {
      key: "top_n", label: "GO terms shown", type: "range", step: 1,
      help: "How many of the most enriched terms become nodes, before the parent→child edges are wired.",
    },
    {
      key: "namespace", label: "Ontology", type: "select",
      options: [
        { value: "", label: "All three" },
        { value: "BP", label: "Biological process" },
        { value: "MF", label: "Molecular function" },
        { value: "CC", label: "Cellular component" },
      ],
      help: "GO's three branches answer different questions. Mixing them in one graph is usually why it reads as unrelated clusters.",
    },
    ...GENE_LIST_CUTOFFS,
  ],
  // GSEA — every knob was API-only until 2026-08-05. The ranking is derived from the file, so what
  // is left to choose is WHAT is tested (library or a pasted set), HOW hard the metric is weighted,
  // and how much permutation resolution the p-value gets. Ordered library → override → statistics.
  gsea: [
    geneSetLibrary("the ranked list is scored against", true),
    pastedGeneSet("only that set is tested, as a single pre-ranked GSEA."),
    {
      key: "set_name", label: "Name for your gene set", type: "text", placeholder: "Gene set",
      // Greyed rather than hidden: it names the pasted set in the figure TITLE, so it is worth
      // advertising, but in library mode the label comes from the winning term and this is inert.
      // `not` inverts the blank test — the one gate shape `equals` alone cannot express.
      enabledWhen: { key: "gene_set", equals: "", not: true },
      help: "Labels your pasted set on the figure. Unused with the reference library, where each term carries its own name.",
    },
    {
      key: "weight", label: "Metric weighting exponent", type: "range", step: 0.05,
      help: "How hard the ranking metric weights the running score. 1 is the classic weighted GSEA; 0 ignores the magnitudes and tests rank order alone.",
    },
    {
      // NOT a slider, for `fdr_threshold`'s reason: the useful values (100 / 1000 / 10000) are
      // log-spaced across a 0-10000 track, so a linear thumb makes the two smaller ones
      // indistinguishable. The floor is stated because it is real — `_perm_count` raises anything
      // under 100 to 100, so a control that silently accepted 50 would misreport its own run.
      key: "n_perm", label: "Permutations", type: "number", step: 100,
      help: "More permutations resolve smaller p-values, and cost run time proportionally. The gseapy and blitzGSEA engines use 100 as a floor.",
    },
    {
      key: "engine", label: "GSEA engine", type: "select",
      options: [
        { value: "auto", label: "Automatic (recommended)" },
        { value: "gseapy", label: "gseapy.prerank" },
        { value: "blitzgsea", label: "blitzGSEA (gamma-fit p-values)" },
        { value: "inhouse", label: "In-house weighted KS (single set only)" },
      ],
      help: "Automatic picks gseapy, the validated default. blitzGSEA resolves smaller p-values and scales to large libraries, but its first run pays a JIT compile. The in-house engine needs no extra dependency and scores only a pasted set.",
    },
  ],
  // ssGSEA — scores every sample independently, so there is no contrast to choose: the knobs decide
  // which sets qualify, how many of them are drawn, and whether the heatmap shows raw NES or z.
  ssgsea: [
    geneSetLibrary("every sample is scored against", true),
    pastedGeneSet("every sample is scored against that set alone."),
    {
      // The selection rule is the part a reader cannot guess and the one that differs from
      // `enrichment.top_n` (most ENRICHED): these are the most VARIABLE across samples, which is
      // what makes a heatmap worth looking at. Same key, different meaning — not shared.
      key: "top_n", label: "Gene sets shown", type: "range", step: 1,
      help: "How many gene sets the heatmap draws, taken in order of variance ACROSS samples — the ones that separate your samples, not the most enriched overall.",
    },
    {
      key: "min_size", label: "Smallest gene set", type: "number", step: 1,
      help: "Sets with fewer detected members than this are dropped. Very small sets score erratically because one gene moves the whole result.",
    },
    {
      key: "max_size", label: "Largest gene set", type: "number", step: 1,
      help: "Sets with more detected members than this are dropped. Very broad sets score near-identically in every sample and crowd out the informative ones.",
    },
    {
      key: "weight", label: "Rank weighting exponent", type: "range", step: 0.05,
      help: "How hard a gene's rank within the sample weights its contribution. 0.25 is the value the ssGSEA method was published with.",
    },
    {
      key: "zscore", label: "Z-score rows for display", type: "switch",
      help: "Centres each pathway across samples so the diverging colours read as relative activity. Off shows the raw enrichment scores, where a uniformly high pathway stays high. The exported table always carries the raw scores.",
    },
  ],
  // Sankey — one knob, and it was API-only, so this skill rendered an EMPTY parameter panel.
  sankey: [
    {
      key: "max_links", label: "Flows drawn", type: "range", step: 1,
      help: "Keeps this many of the largest flows. A Sankey with every small link drawn is unreadable; the dropped ones are the smallest by value.",
    },
  ],
  // Volcano — the first three knobs ARE the figure's claim: which points read as up or down, where
  // the dashed lines sit, and which genes get named. They were API-only until 2026-08-04, so the
  // panel invited the user to "tune the options" and then rendered one text box for a gene panel
  // (`API_ONLY_KNOBS`, registry-completeness.test.ts). Ordered by what each DECIDES, so `highlight`
  // — an overlay applied on top of an already-decided figure — comes last.
  //
  // `fdr_threshold` is the one number here that is NOT a slider, and deliberately: its range is
  // 0–1 while every value anyone uses (0.05 · 0.01 · 0.001) sits inside the first tenth of that
  // track, so a linear slider would make the conventional cutoffs fiddly and 0.001 unreachable at
  // any usable step. A typed field reaches all of them exactly.
  volcano: [
    {
      key: "fc_threshold", label: "Fold-change cutoff (log₂)", type: "range", step: 0.1,
      help: "A point counts as changed at |log₂FC| ≥ this — 1 is a doubling. Drawn as the two vertical dashed lines.",
    },
    {
      key: "fdr_threshold", label: "Significance cutoff (adjusted p)", type: "number", step: 0.001,
      help: "The horizontal dashed line, and the other half of the up/down test. 0.05 by convention; 0.01 or 0.001 for a stricter call.",
    },
    {
      key: "top_n", label: "Genes labelled", type: "range", step: 1,
      help: "The most significant genes that clear BOTH cutoffs get a label. 0 labels none — any point can still be clicked to label it.",
    },
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
    // `normalize` here is NOT the scRNA switch — see the scrnaNormalize block. It rescales each
    // metric COLUMN so metrics in different units share one axis.
    {
      key: "normalize", label: "Rescale each metric", type: "switch",
      help: "Min–max scale every metric to 0–1 across the conditions, so metrics in different units share one axis. Off plots the raw values, which only reads well when they already share a scale.",
    },
    { key: "fill", label: "Fill the radar area", type: "switch", help: "Shade the area inside each condition's outline. Off leaves outlines only, which is easier to read once several conditions overlap.", showWhen: { key: "layout", equals: "radar" } },
    { key: "max_rows", label: "Conditions shown", type: "range", step: 1, help: "How many rows of the input to draw, from the top." },
  ],
  // Proteomics DE — ordered along the pipeline the runner actually walks: which samples → how the
  // matrix is prepared → which test → where the volcano's lines fall. The preparation knobs are not
  // cosmetic: `missing` picks between an impute that shrinks real MNAR fold-changes and the
  // left-censored treatment that preserves them, which changes the result more than the test does.
  proteomics_de: [
    { key: "group_a", label: "Group A", type: "text", placeholder: "e.g. infected", help: "Sample-name substring for the first group." },
    { key: "group_b", label: "Group B", type: "text", placeholder: "e.g. control", help: "Sample-name substring for the second group." },
    {
      key: "log_input", label: "Intensities are already log₂", type: "switch",
      help: "Off log₂-transforms and median-normalizes the matrix first. Turn on only if your export is already logged — doing it twice flattens every fold-change.",
    },
    {
      key: "min_valid", label: "Measured in at least", type: "range", step: 0.05,
      help: "A protein must be present in this fraction of the samples in EACH group, or it is dropped before testing. 0.5 = half.",
    },
    {
      key: "missing", label: "Fill missing values with", type: "select",
      options: [
        { value: "mean", label: "Per-protein mean (simple)" },
        { value: "mindet", label: "Detection limit (left-censored)" },
        { value: "minprob", label: "Downshifted normal (Perseus)" },
      ],
      help: "Proteomics dropouts are mostly below the run's detection limit, so the mean fill biases real fold-changes toward zero. The two left-censored modes fill from each sample's low tail instead. Mean is the default so existing outputs are unchanged.",
    },
    {
      key: "stats", label: "Statistics", type: "select",
      options: [
        { value: "welch", label: "Welch t-test" },
        { value: "moderated", label: "Moderated (limma-style)" },
      ],
      help: "Moderated borrows variance across proteins for better power at small N.",
    },
    {
      key: "fc_threshold", label: "Fold-change cutoff (log₂)", type: "range", step: 0.1,
      help: "A protein counts as changed at |log₂FC| ≥ this — 1 is a doubling. Drawn as the two vertical dashed lines.",
    },
    {
      key: "fdr_threshold", label: "Significance cutoff (adjusted p)", type: "number", step: 0.001,
      help: "The horizontal dashed line, and the other half of the up/down test. 0.05 by convention; 0.01 or 0.001 for a stricter call.",
    },
    {
      key: "top_n", label: "Proteins labelled", type: "range", step: 1,
      help: "The most significant proteins that clear BOTH cutoffs get a label. 0 labels none.",
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
    {
      key: "correction", label: "Multiple-comparison correction", type: "select",
      options: [
        { value: "none", label: "None (raw p)" },
        { value: "bonferroni", label: "Bonferroni" },
        { value: "bh", label: "Benjamini–Hochberg (FDR)" },
      ],
      help: "Several brackets means several shots at p<0.05. Correcting adjusts BOTH the stars and the reported p-values. A star you overrode by hand is never re-corrected.",
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
    // Steps divide (default − min), or the default is a value the input itself rejects: min 1 /
    // default 20 admits only step 1, and min 5 / default 50 admits 5 but not 10. Both shipped
    // off-lattice under a step guard that looked at sliders only.
    { key: "scale_uv", label: "Scale bar — amplitude (µV)", type: "number", step: 1, help: "Vertical scale-bar length, set in µV (flicker amplitudes are small — ~20 µV is a good default)." },
    { key: "scale_ms", label: "Scale bar — time (ms)", type: "number", step: 5, help: "Horizontal scale-bar length (a 10 Hz cycle is 100 ms, a 30 Hz cycle ~33 ms)." },
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
    scrnaGroupby("The cell-annotation column whose levels each get a cell-type call — e.g. leiden."),
    { key: "embedding", label: "Embedding", type: "text", placeholder: "X_umap",
      help: "The obsm key holding the 2-D coordinates to draw the labelled cells on." },
    scrnaNormalize(),
  ],
  // Marker dotplot. `rank_by` decides HOW markers are chosen and `method` only applies to the
  // p-value route — an effect-size ranking never calls a test, so the test select is hidden there
  // rather than left visible and inert (`skills/markers/run_real.py:46`).
  markers: [
    scrnaGroupby("The cell-annotation column whose levels become the dotplot's rows — e.g. cell_type."),
    { key: "n_genes", label: "Genes per group", type: "range", step: 1,
      help: "Top markers drawn for each group. A gene that ranks in two groups is drawn once." },
    { key: "rank_by", label: "Rank markers by", type: "select", options: [
      { value: "wilcoxon", label: "Wilcoxon p-value (classic)" },
      { value: "cohens_d", label: "Cohen's d (effect size)" },
      { value: "auc", label: "AUC (effect size)" },
    ], help: "An effect size ranks by how separated the groups actually are. The Wilcoxon p-value is the classic choice, but it is circular when the groups came from clustering this same data — so it flatters itself." },
    { key: "method", label: "Statistical test", type: "select", options: [
      { value: "wilcoxon", label: "Wilcoxon rank-sum" },
      { value: "t-test", label: "t-test" },
      { value: "t-test_overestim_var", label: "t-test (overestimated variance)" },
      { value: "logreg", label: "Logistic regression" },
    ], showWhen: { key: "rank_by", equals: "wilcoxon" },
      help: "The test behind the ranking. Not used by the effect-size rankings." },
    { key: "standard_scale", label: "Scale colour per gene", type: "switch",
      help: "Scale each gene to 0–1 across the groups, so colour shows WHERE a gene is highest rather than how abundant it is. Off = mean log1p expression, where one loud gene can wash out the rest." },
    scrnaNormalize(),
  ],
  trajectory: [
    scrnaGroupby("The cell-annotation column whose levels become the trajectory's nodes — e.g. cell_type."),
    { key: "root", label: "Start from", type: "text", placeholder: "auto",
      help: "The group the trajectory is rooted at. Blank = the cell furthest along the first diffusion component, which is a guess about direction, not a finding." },
    { key: "embedding", label: "Embedding", type: "text", placeholder: "X_umap",
      help: "The obsm key holding the 2-D coordinates the nodes are positioned on." },
    { key: "threshold", label: "Edge threshold (connectivity)", type: "range", step: 0.01,
      help: "PAGA connectivity below this is not drawn. Higher = a sparser, more confident skeleton; low values connect almost everything to everything." },
    scrnaNormalize(),
  ],
  // `groupby` here is deliberately NOT the shared one — see the scrnaGroupby block: this column
  // never reaches the figure, it only chooses where the trajectory starts.
  pseudotime_genes: [
    { key: "top_n", label: "Genes shown", type: "range", step: 1,
      help: "How many of the most pseudotime-varying genes to draw." },
    // No positional words in the help — the grid is 2-column, so these two render side by side on
    // the Workbench and stacked in the 360px dock. Each names the other by LABEL instead.
    { key: "groupby", label: "Root cluster column", type: "text", placeholder: "leiden",
      help: "Used ONLY to place the start of the trajectory — the figure's x-axis is pseudotime, not this column. Pair it with “Start from”." },
    { key: "root", label: "Start from", type: "text", placeholder: "auto",
      help: "Which level of “Root cluster column” the trajectory begins at. Blank = the extreme of the first diffusion component." },
    { key: "n_bins", label: "Pseudotime bins", type: "range", step: 5,
      help: "Cells are averaged into this many bins along pseudotime before smoothing. Fewer = smoother curves and less visible noise." },
    scrnaNormalize(),
  ],
  mixing_metrics: [
    { key: "batch_key", label: "Batch column", type: "text", placeholder: "e.g. sample, donor, batch",
      help: "The obs column naming each library/batch — the thing integration is supposed to mix. Falls back to a known alias when absent." },
    { key: "label_key", label: "Cell-type column", type: "text", placeholder: "e.g. cell_type",
      help: "The obs column with biological labels. Without it the label-aware metrics (cLISI, ARI, NMI, ASW-label) are reported N/A rather than guessed." },
    { key: "embedding_key", label: "Embedding", type: "text", placeholder: "auto",
      help: "The obsm key to score. Blank resolves the corrected embedding first (Melody → Harmony → X_emb → X_pca), and computes a PCA only if none exists." },
    { key: "n_neighbors", label: "Neighbours (kBET)", type: "range", step: 5,
      help: "Neighbourhood size for the kBET test. Larger = a coarser, more forgiving verdict on local mixing." },
    { key: "perplexity", label: "LISI perplexity", type: "range", step: 5,
      help: "Kernel width for the LISI scores (uses roughly 3× this many neighbours)." },
    { key: "n_pcs", label: "Principal components", type: "range", step: 1,
      help: "PCs used when an embedding has to be computed. Ignored when your file already has one." },
    scrnaNormalize("Only applies when no embedding is present and one must be computed from counts."),
  ],
  cepo: [
    { key: "group_key", label: "Cell-type column", type: "text", placeholder: "auto",
      help: "The obs column holding the cell-type labels to find stable markers for. Blank = resolved from the usual names." },
    { key: "n_genes", label: "Genes per cell type", type: "range", step: 1,
      help: "Top stable markers drawn for each cell type." },
    // step 2, not 5: min 2 / step 5 would put the default 20 off the lattice (see `known_min`).
    { key: "min_cells", label: "Minimum cells per type", type: "number", step: 2,
      help: "Cell types with fewer cells than this are dropped — a stability score from a handful of cells is noise wearing a number." },
    { key: "exprs_pct", label: "Minimum detection rate", type: "number", step: 0.01,
      help: "Genes detected in a smaller fraction of cells than this are excluded before scoring (0.05 = 5%)." },
    scrnaNormalize(),
  ],
  // `normalize` here is NOT the scRNA switch — see the scrnaNormalize block. It scales each feature
  // to unit variance before the PCA, which is `pca.scale` under a different name.
  pvca: [
    { key: "factors", label: "Factors", type: "text", placeholder: "e.g. batch, condition, sex",
      help: "Comma-separated categorical columns to apportion the variance across. Blank = every non-numeric column in the file." },
    { key: "pct_threshold", label: "Variance retained", type: "range", step: 0.05,
      help: "How much of the total variance the kept principal components must cover before the apportionment is computed." },
    { key: "normalize", label: "Scale features", type: "switch",
      help: "Divide each feature by its standard deviation before the PCA, so a high-variance feature cannot dominate purely because of its units. This is a scaling choice, not the count normalization of the scRNA skills." },
  ],
  upset: [
    { key: "mode", label: "Intersection mode", type: "select", options: [
      { value: "distinct", label: "Distinct (in these sets and no others)" },
      { value: "inclusive", label: "Inclusive (in at least these sets)" },
    ], help: "Distinct partitions the items so every one is counted exactly once — the standard UpSet reading. Inclusive lets an item count towards several bars." },
    { key: "min_size", label: "Minimum intersection size", type: "number", step: 1,
      help: "Intersections smaller than this are dropped before sorting." },
    { key: "max_intersections", label: "Bars shown", type: "range", step: 1,
      help: "How many intersections to draw, after sorting." },
    { key: "sort_by", label: "Sort bars by", type: "select", options: [
      { value: "size", label: "Size (largest first)" },
      { value: "degree", label: "Degree (most sets first)" },
    ], help: "Size answers “what overlaps most”; degree groups the bars by how many sets each intersection spans." },
  ],
  string_network: [
    { key: "species", label: "Species", type: "select", options: [
      { value: "9606", label: "Human (9606)" },
      { value: "10090", label: "Mouse (10090)" },
      { value: "10116", label: "Rat (10116)" },
      { value: "7955", label: "Zebrafish (7955)" },
      { value: "7227", label: "Fly (7227)" },
      { value: "6239", label: "C. elegans (6239)" },
      { value: "4932", label: "Yeast (4932)" },
    ], help: "NCBI taxon the gene symbols are looked up against. The wrong species returns few edges rather than an error." },
    { key: "required_score", label: "Minimum confidence", type: "range", step: 50,
      help: "STRING's combined score, 0–1000. The published bands are 150 low · 400 medium · 700 high · 900 highest — below 400 the network fills with weak, mostly text-mined links." },
    { key: "max_genes", label: "Genes requested", type: "range", step: 1,
      help: "How many of your genes to send. A larger network is denser, not clearer." },
    geneListFdr("Not a cutoff on the edges drawn — each of those carries its own STRING confidence score."),
  ],
  corr_heatmap: [
    { key: "axis", label: "Correlate", type: "select", options: [
      { value: "samples", label: "Samples (columns)" },
      { value: "features", label: "Features (rows)" },
    ], help: "Samples answers “do my replicates agree”; features answers “which genes move together”." },
    { key: "method", label: "Correlation", type: "select", options: [
      { value: "pearson", label: "Pearson (linear)" },
      { value: "spearman", label: "Spearman (rank)" },
    ], help: "Spearman is the safer default on skewed expression data — it judges monotone agreement, so one outlier cannot manufacture a correlation." },
    { key: "cluster", label: "Cluster the matrix", type: "switch",
      help: "Reorder rows and columns by hierarchical clustering, so blocks of similar samples sit together. Off keeps the file's own order." },
  ],
  pca: [
    { key: "group_regex", label: "Group name pattern", type: "text", placeholder: "\\d+$",
      help: "A regex REMOVED from each sample name; what remains is the group. The default strips trailing digits, so ctrl1/ctrl2/ctrl3 all become ctrl." },
    { key: "scale", label: "Scale features", type: "switch",
      help: "Divide each feature by its standard deviation first, so a high-variance feature cannot dominate the components purely because of its units." },
    { key: "label_points", label: "Label points", type: "switch",
      help: "Print each sample's name beside its point. Best on small sets — it collides on large ones." },
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

/**
 * The column choices for a `column` field: every column the table has, with the categorical ones
 * annotated by their level count. Returns undefined when there is nothing to pick from — which is
 * how the field falls back to a plain text box.
 */
function resolveColumns(ctx: ParamDataContext | undefined): ParamField["columns"] {
  const cols = ctx?.columns;
  if (!cols || cols.length === 0) return undefined;
  const levels = new Map((ctx?.groups ?? []).map((g) => [g.key, g.n_levels]));
  return cols.map((c) => {
    const n = levels.get(c);
    return { value: c, label: n ? `${c} — ${n} levels` : c };
  });
}

/** Level names per candidate group column — the pair picker's vocabulary. */
function resolveLevels(ctx: ParamDataContext | undefined): Record<string, string[]> | undefined {
  const groups = (ctx?.groups ?? []).filter((g) => g.levels.length > 0);
  if (groups.length === 0) return undefined;
  return Object.fromEntries(groups.map((g) => [g.key, g.levels.map((l) => l.name)]));
}

function mergeField(pres: ParamPresentation, ps: BackendParam, ctx?: ParamDataContext): ParamField {
  // A `column`/`pairs` widget is only emitted when its vocabulary exists; otherwise the field
  // degrades to the text box it has always been. That keeps a context-free merge byte-identical
  // to today's and spares `ParamControl` an empty-picker branch.
  const columns = pres.type === "column" ? resolveColumns(ctx) : undefined;
  const levelsByGroup = pres.type === "pairs" ? resolveLevels(ctx) : undefined;
  const type: ParamField["type"] =
    (pres.type === "column" && !columns) || (pres.type === "pairs" && !levelsByGroup)
      ? "text"
      : pres.type;
  return {
    key: pres.key,
    label: pres.label,
    type,
    default: ps.default, // contract: the default/range come from the backend spec, never the overlay
    min: ps.min,
    max: ps.max,
    step: pres.step,
    placeholder: pres.placeholder,
    help: pres.help ?? ps.note,
    options: resolveOptions(pres, ps),
    showWhen: pres.showWhen,
    enabledWhen: pres.enabledWhen,
    columns,
    levelsByGroup,
    levelsFrom: levelsByGroup ? pres.levelsFrom : undefined,
  };
}

/**
 * Build the rendered fields for a skill by merging its presentation overlay over the
 * backend `param_spec`. Pure + synchronous (the caller supplies the loaded spec). The
 * field SET, types, defaults, and min/max come from `spec`; labels/help/widget/step/
 * options/showWhen from the overlay. An overlay key not in the spec is dropped (logged
 * in dev) so the UI can never offer a knob the runner doesn't accept.
 *
 * `ctx` is the loaded dataset's schema (see {@link ParamDataContext}) — optional, and omitting it
 * yields exactly the field list this function returned before pickers existed.
 */
export function paramFieldsFromSpec(
  catalogOrRuntimeId: string,
  spec: BackendParamSpec,
  ctx?: ParamDataContext,
): ParamField[] {
  const overlay = PRESENTATION[runtimeSkillId(catalogOrRuntimeId)] ?? [];
  const out: ParamField[] = [];
  for (const pres of overlay) {
    const ps = spec[pres.key];
    if (!ps) {
      warnDeadKnob(catalogOrRuntimeId, pres.key);
      continue;
    }
    out.push(mergeField(pres, ps, ctx));
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
  return schema
    .filter((f) => !f.showWhen || gateMatches(f.showWhen, schema, params))
    .map((f) => (f.type === "pairs" ? resolvePairsField(f, schema, params) : f));
}

/**
 * A `pairs` field's options depend on ANOTHER param — the group column the user picked this render
 * (boxplot's `group`) — so they resolve here, not at merge time.
 *
 * There is deliberately NO fallback when that field is blank. Blank means "auto-detect", and the
 * detection is a backend rule over the table's dtypes that the frontend cannot evaluate; guessing
 * would offer level names from a column the run is not grouping by. So the picker appears once the
 * group column is chosen, and until then the field is the free-text box it always was. Same drop
 * back to text when the chosen column has no known levels — a column the design layer didn't
 * classify, or a skill whose categories only exist after the run (violin's Leiden clusters).
 */
function resolvePairsField(field: ParamField, schema: ParamField[], params: SkillParams): ParamField {
  const byGroup = field.levelsByGroup ?? {};
  const chosen = field.levelsFrom
    ? String(params[field.levelsFrom] ?? schema.find((x) => x.key === field.levelsFrom)?.default ?? "")
    : "";
  const levels = byGroup[chosen];
  if (!levels || levels.length < 2) return { ...field, type: "text" };
  return { ...field, options: levels.map((l) => ({ value: l, label: l })) };
}

/**
 * Parse / serialize the `pairs` wire format — the SAME `"A~B, C~D"` string the backend already
 * reads (`skills/_stats.parse_pairs`). The picker is a nicer way to author that string, not a new
 * contract: a figure saved from the text field opens in the picker and vice versa, nothing on the
 * backend changed, and no provenance moved.
 *
 * These round-trip an INCOMPLETE row (`"~"`, `"A~"`) instead of dropping it. That is what lets the
 * picker be fully controlled with no local draft state: "+ Add" emits an empty row, the user fills
 * it in, and nothing has to reconcile a local list against the parent's string. It is safe on the
 * wire because `parse_pairs` requires both sides to be non-empty and documents that it skips
 * empty/malformed chunks — a half-built row draws no bracket rather than failing the run.
 */
export function parsePairs(value: string): [string, string][] {
  return value
    .split(",")
    .map((chunk) => chunk.trim())
    .filter((chunk) => chunk.includes("~"))
    .map((chunk) => {
      const [a = "", b = ""] = chunk.split("~").map((s) => s.trim());
      return [a, b] as [string, string];
    });
}

export function serializePairs(pairs: [string, string][]): string {
  return pairs.map(([a, b]) => `${a}~${b}`).join(", ");
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
function gateMatches(gate: FieldGate, schema: ParamField[], params: SkillParams): boolean {
  const current = params[gate.key] ?? schema.find((x) => x.key === gate.key)?.default;
  const hit = current === gate.equals || String(current) === String(gate.equals);
  return gate.not ? !hit : hit;
}

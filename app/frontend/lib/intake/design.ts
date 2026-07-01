/**
 * The intake questionnaire's DESIGN layer (Layer A ingest, deterministic) — the FE mirror of the
 * engine's `engine.questionnaire.DesignHints` (backend `/data/inspect` → `design`) plus the
 * confirmed-choice → run-param mapping.
 *
 * The engine pre-fills the design deterministically (candidate group columns, levels, replicate
 * counts, a control guess); the confirm-card lets the user correct it; `designRunParams` turns the
 * confirmed choice into the exact `deg` run params the runner ALREADY reads + records in provenance
 * (`reference`/`treatment`/`condition_col`/`sample_col`/`group_col`). So the design "compiles away":
 * a gateway-off re-run from those params reproduces. See docs/intake-questionnaire/build-spec.md §3b.
 */

/** One condition level + how many replicates carry it (engine LevelHint). */
export interface LevelHint {
  name: string;
  n_replicates: number;
  /** "samples" (biological replicates) | "cells" (scRNA with no sample column found). */
  replicate_unit: string;
  /** time_course only: this level's numeric timepoint (the axis value driving order + the Wald trend).
   *  The confirm-card shows it and lets the user correct a misparse; null/absent for a categorical level. */
  time?: number | null;
}

/** One synthesized design-sheet row for a time-course run: a sample column → its numeric timepoint.
 *  The engine parses the time once (via the deg runner's `_numeric_time`); the FE serializes these
 *  verbatim into the design CSV the runner re-consumes, so DETECTED == CONSUMED (no FE re-parse). */
export interface TimeRow {
  sample: string;
  time: number;
}

/** A candidate design factor: a column (or the bulk header-inferred pseudo-column) + its levels. */
export interface GroupCandidate {
  /** An obs / design-sheet column name, or the sentinel `__column_names__` for bulk headers. */
  key: string;
  label: string;
  /** "time_course" when the levels form an ordered timepoint axis (0h/24h/48h) — the confirm-card
   *  renders a timeline (a trend across time), not a 2-group contrast. "categorical"/absent otherwise. */
  kind?: "categorical" | "time_course";
  levels: LevelHint[];
  n_levels: number;
  /** A control/reference level among `levels` (null when no keyword matched). For a time-course this
   *  is the baseline (earliest) timepoint. */
  reference_guess: string | null;
  /** time_course only: one row per sample column (id → numeric time) → the synthesized design sheet. */
  time_rows?: TimeRow[];
}

/** The deterministic design prefill the engine returns for a dropped file (engine DesignHints). */
export interface DesignHints {
  needs_design: boolean;
  source: "column_names" | "obs" | "design_sheet" | "none";
  modality: string;
  group_candidates: GroupCandidate[];
  best_group: string | null;
  /** scRNA: the detected biological-replicate column (the deg `sample_col`). */
  sample_col?: string | null;
  /** scRNA: obs id-like columns the user can pick as the sample/replicate column when detection missed
   *  it (followups #6). Empty for bulk (no obs). Pseudobulk aggregates by this column, not by cells. */
  sample_col_candidates?: string[];
  note: string;
}

/** The bulk sentinel: condition labels inferred from the sample column names (no real column). */
export const COLUMN_NAMES_KEY = "__column_names__";

/**
 * A partial design the ingest AI refiner (Layer A 2b) proposes, to PRE-FILL the editable
 * questionnaire — never applied silently; the user confirms/edits it. Only fields the AI actually
 * proposed AND that survive the honesty check are set: `reference`/`treatment` must be levels PRESENT
 * in the detected design (an absent level is dropped — a coherent-but-unfulfillable intent becomes a
 * gap, never an invented level); `groupKey` is set only when the AI named a real candidate column.
 */
export interface DesignPatch {
  groupKey?: string;
  reference?: string;
  treatment?: string;
}

/** The user's confirmed design (the confirm-card output) — staged into the run. */
export interface DesignChoice {
  /** The chosen group factor: an obs/sheet column, or `__column_names__` for bulk headers. */
  groupKey: string;
  source: DesignHints["source"];
  /** "time_course" runs go through the deg time-course mode with a synthesized design sheet; the
   *  reference/treatment contrast doesn't apply. "categorical"/absent = a normal 2-group contrast. */
  kind?: "categorical" | "time_course";
  /** The reference (control) level — logFC is computed treatment-vs-reference. */
  reference: string;
  /** The treatment level — the other side of the 2-group contrast. */
  treatment: string;
  /** The confirmed condition levels (after any rename/remove/add). */
  levels: string[];
  /** scRNA: the detected sample column, threaded so pseudobulk aggregates by replicate. */
  sampleCol?: string | null;
  /** time_course only: the design-sheet rows serialized as the run's designFile. */
  timeRows?: TimeRow[];
}

/** Look up a candidate by key (the active group factor). */
export function candidateFor(hints: DesignHints | null | undefined, key: string): GroupCandidate | null {
  return hints?.group_candidates.find((c) => c.key === key) ?? null;
}

/** Build the default {@link DesignChoice} from the engine prefill — the best group, its control
 *  guess as reference, the next level as treatment. Returns null when there is no usable contrast. */
export function defaultDesignChoice(hints: DesignHints | null | undefined): DesignChoice | null {
  if (!hints?.needs_design || !hints.best_group) return null;
  const cand = candidateFor(hints, hints.best_group);
  if (!cand || cand.levels.length < 2) return null;
  const levels = cand.levels.map((l) => l.name);
  if (cand.kind === "time_course") {
    // A time-course has no control/treatment contrast — the baseline is the earliest timepoint. Keep
    // reference/treatment populated (first/last) so the shape stays valid, but they don't drive the run.
    return {
      groupKey: cand.key,
      source: hints.source,
      kind: "time_course",
      reference: levels[0],
      treatment: levels[levels.length - 1],
      levels,
      sampleCol: hints.sample_col ?? null,
      timeRows: cand.time_rows ?? [],
    };
  }
  const reference = cand.reference_guess ?? levels[0];
  const treatment = levels.find((l) => l !== reference) ?? levels[1];
  return {
    groupKey: cand.key,
    source: hints.source,
    reference,
    treatment,
    levels,
    sampleCol: hints.sample_col ?? null,
  };
}

/**
 * Map a confirmed {@link DesignChoice} → the `deg` run params the runner already reads (build-spec
 * §3b). Bulk infers groups from headers (no `group_col`); scRNA aggregates per replicate
 * (`mode=pseudobulk` + `condition_col`/`sample_col`); a design sheet keys on `group_col`.
 */
export function designRunParams(choice: DesignChoice): Record<string, string> {
  if (choice.kind === "time_course") {
    // The deg time-course mode fits time as a continuous covariate (Wald-tested) — no reference/treatment
    // contrast. It reads the synthesized design sheet (id + `time`); `time_col=time` matches its column.
    return { mode: "timecourse", time_col: "time" };
  }
  const params: Record<string, string> = { reference: choice.reference, treatment: choice.treatment };
  if (choice.source === "obs") {
    params.mode = "pseudobulk";
    params.condition_col = choice.groupKey;
    if (choice.sampleCol) params.sample_col = choice.sampleCol;
  } else if (choice.source === "column_names") {
    params.mode = "bulk";
  } else if (choice.source === "design_sheet") {
    params.group_col = choice.groupKey;
  }
  return params;
}

/** Escape a value for a CSV cell (quote when it contains a comma, quote, or newline). */
function csvCell(v: string): string {
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

/**
 * Serialize a time-course choice into the design-sheet CSV the deg time-course runner reads: an id
 * column (`sample_id`, one of the runner's id aliases) + a numeric `time` column, one row per sample.
 * The engine already parsed the numeric times (DETECTED == CONSUMED), so this is a verbatim
 * serialization — a gateway-off re-run from the recorded params + this sheet reproduces. Returns null
 * for a non-time-course choice or when there are no rows (the caller then keeps any attached sheet).
 */
export function timeCourseDesignFile(choice: DesignChoice): File | null {
  const rows = choice.timeRows ?? [];
  if (choice.kind !== "time_course" || rows.length === 0) return null;
  const body = rows.map((r) => `${csvCell(r.sample)},${r.time}`).join("\n");
  return new File([`sample_id,time\n${body}\n`], "timecourse-design.csv", { type: "text/csv" });
}

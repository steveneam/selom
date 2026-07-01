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
}

/** A candidate design factor: a column (or the bulk header-inferred pseudo-column) + its levels. */
export interface GroupCandidate {
  /** An obs / design-sheet column name, or the sentinel `__column_names__` for bulk headers. */
  key: string;
  label: string;
  levels: LevelHint[];
  n_levels: number;
  /** A control/reference level among `levels` (null when no keyword matched). */
  reference_guess: string | null;
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

/** The user's confirmed design (the confirm-card output) — staged into the run. */
export interface DesignChoice {
  /** The chosen group factor: an obs/sheet column, or `__column_names__` for bulk headers. */
  groupKey: string;
  source: DesignHints["source"];
  /** The reference (control) level — logFC is computed treatment-vs-reference. */
  reference: string;
  /** The treatment level — the other side of the 2-group contrast. */
  treatment: string;
  /** The confirmed condition levels (after any rename/remove/add). */
  levels: string[];
  /** scRNA: the detected sample column, threaded so pseudobulk aggregates by replicate. */
  sampleCol?: string | null;
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

"use client";

/**
 * Loading the write-up sections for one source (docs/paper-outputs/spec.md §2).
 *
 * Section-independent by design: Methods, legends and the scorecard resolve separately and a
 * failure in one never blanks the others. A ledger whose panels name an unbuilt skill 400s on
 * `/methods/compose` while its legends and scorecard are perfectly good — the user should still
 * get those.
 */

import * as React from "react";

import type { Ledger, Scorecard } from "@/lib/reproduction/types";
import {
  composeMethods,
  getPaperLegends,
  getPaperMethods,
  getPaperScorecard,
  type FigureLegend,
  type MethodsSection,
} from "./api";
import { datasetDescriptor, runsFromLedger, type WriteUpSource } from "./source";

/** Why run-sourced legends are missing — stated in the UI rather than rendered as an empty box. */
export const RUN_LEGENDS_UNAVAILABLE =
  "Figure legends are numbered from a paper's reproduction ledger, and the route that composes " +
  "them is scoped to published reproductions today — so your own run's legends aren't available yet.";

export interface WriteUpState {
  methods: MethodsSection | null;
  legends: FigureLegend[];
  scorecard: Scorecard | null;
  loading: boolean;
  /** Per-section failure messages — a section that failed says so where it would have rendered. */
  errors: { methods?: string; legends?: string; scorecard?: string };
  /** Sections this source structurally cannot fill. Not a failure — a stated limit. */
  unavailable: { legends?: string };
}

const EMPTY: WriteUpState = {
  methods: null,
  legends: [],
  scorecard: null,
  loading: false,
  errors: {},
  unavailable: {},
};

function message(e: unknown): string {
  return e instanceof Error && e.message ? e.message : "couldn't load this section";
}

/**
 * A published reproduction's write-up: every section straight from the paper-level routes.
 * `slug` empty -> idle (hooks can't be conditional, so both sources are always mounted).
 */
function useReferenceWriteUp(slug: string): WriteUpState {
  const [state, setState] = React.useState<WriteUpState>(EMPTY);

  React.useEffect(() => {
    if (!slug) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when the slug clears
      setState(EMPTY);
      return;
    }
    let on = true;
    setState({ ...EMPTY, loading: true });
    const patch = (next: Partial<WriteUpState>) => {
      if (!on) return;
      setState((s) => ({ ...s, ...next, errors: { ...s.errors, ...next.errors } }));
    };

    const settled = Promise.all([
      getPaperMethods(slug).then(
        (methods) => patch({ methods }),
        (e) => patch({ errors: { methods: message(e) } }),
      ),
      getPaperLegends(slug).then(
        (legends) => patch({ legends }),
        (e) => patch({ errors: { legends: message(e) } }),
      ),
      getPaperScorecard(slug).then(
        (scorecard) => patch({ scorecard }),
        (e) => patch({ errors: { scorecard: message(e) } }),
      ),
    ]);
    void settled.then(() => patch({ loading: false }));

    return () => {
      on = false;
    };
  }, [slug]);

  return state;
}

/**
 * The user's own driven run: Methods composed from the ledger's in-scope analysis panels, the score
 * read off the run's own scorecard. Legends are structurally unavailable (see the constant above).
 * A null ledger -> idle.
 */
function useRunWriteUp(ledger: Ledger | null): WriteUpState {
  const [methods, setMethods] = React.useState<MethodsSection | null>(null);
  const [error, setError] = React.useState<string | undefined>(undefined);
  const [composing, setComposing] = React.useState(false);

  const runs = React.useMemo(() => runsFromLedger(ledger), [ledger]);
  // The ledger's declared `paper.modality` isn't carried on the shared view type, so the intro is
  // framed by the dataset descriptor alone and the per-skill paragraphs supply the data-type detail
  // — which is exactly what the backend does for an empty modality.
  const dataset = React.useMemo(
    () => datasetDescriptor(ledger?.paper?.geo, ledger?.paper?.title),
    [ledger],
  );

  React.useEffect(() => {
    if (runs.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when the ledger clears
      setMethods(null);
      return;
    }
    let on = true;
    setComposing(true);
    setError(undefined);
    composeMethods(runs, { dataset })
      .then(
        (section) => on && setMethods(section),
        (e) => on && setError(message(e)),
      )
      .finally(() => {
        if (on) setComposing(false);
      });
    return () => {
      on = false;
    };
  }, [runs, dataset]);

  return {
    methods,
    legends: [],
    scorecard: ledger?.scorecard ?? null,
    loading: composing,
    errors: error ? { methods: error } : {},
    unavailable: { legends: RUN_LEGENDS_UNAVAILABLE },
  };
}

/** The write-up for whichever source the stage is showing. */
export function useWriteUp(source: WriteUpSource | null): WriteUpState {
  const reference = useReferenceWriteUp(source?.kind === "reference" ? source.slug : "");
  const run = useRunWriteUp(source?.kind === "run" ? source.ledger : null);
  if (!source) return EMPTY;
  return source.kind === "reference" ? reference : run;
}

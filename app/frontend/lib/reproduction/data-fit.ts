"use client";

/**
 * Dropped-data fit client (Slice 2). The engine scores each supplement the user drops against what
 * the paper's analyses actually need — modality + columns + cleanliness — into a 0-100 score and a
 * confidence BAND ("Confident / Usable / Uncertain / Not a fit / Unreadable"). This module fetches
 * that ranking so the Reproduce stage can show it BEFORE Run (swap a wrong file) and the Score stage
 * AFTER (what the run actually fed). Wire shape mirrors `engine.compat.FileFitReport`.
 */

import * as React from "react";

import { paperFiles, usePaperFiles } from "@/lib/paper/run-files";

export type ConfidenceBand =
  | "confident"
  | "usable"
  | "uncertain"
  | "not_a_fit"
  | "unreadable";

/** One file scored against one skill. */
export interface DataFit {
  filename: string;
  skill_id: string;
  kind: string;
  score: number;
  compatible: boolean | null;
  verdict: string;
  qc_ok: boolean;
  reason: string;
  confidence: ConfidenceBand;
  confidence_label: string;
}

/** One dropped file ranked against the run's analyses + its headline band. */
export interface FileFitReport {
  filename: string;
  kind: string;
  quality: number;
  qc_ok: boolean;
  loadable: boolean;
  note: string;
  score: number;
  best_skill: string;
  best_verdict: string;
  fits: DataFit[];
  confidence: ConfidenceBand;
  confidence_label: string;
}

/** Per-band display metadata — one source for the chip color/tone across both stages. */
export const CONFIDENCE_META: Record<
  ConfidenceBand,
  { label: string; color: string; short: string }
> = {
  confident: { label: "Confident", short: "good data for this analysis", color: "#10b981" },
  usable: { label: "Usable", short: "fits, with minor data caveats", color: "#f59e0b" },
  uncertain: { label: "Uncertain", short: "can't confirm this fits — check it", color: "#64748b" },
  not_a_fit: { label: "Not a fit", short: "wrong data for this analysis", color: "#ef4444" },
  unreadable: { label: "Unreadable", short: "couldn't open this file", color: "#6b7280" },
};

/** POST the paper PDF + supplements → the per-file fit ranking (no skills run; cheap). */
export async function assessData(
  paperId: string,
  main: File | undefined,
  supplements: File[],
): Promise<FileFitReport[]> {
  if (supplements.length === 0) return [];
  const body = new FormData();
  if (main) body.append("main", main);
  for (const s of supplements) body.append("supplements", s);
  const url = `/api/papers/${encodeURIComponent(paperId)}/assess-data`;
  const res = await fetch(url, { method: "POST", body });
  if (!res.ok) {
    let detail = res.status === 413 ? "those files exceed the upload limit" : `failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = String(j.detail);
    } catch {
      /* non-JSON body */
    }
    throw new Error(`Couldn't check the data — ${detail}.`);
  }
  const json = (await res.json()) as { data_fits?: FileFitReport[] };
  return json.data_fits ?? [];
}

export interface DataFitState {
  fits: FileFitReport[];
  loading: boolean;
  error: string | null;
}

/**
 * Auto-assess a paper's attached supplements whenever the attached set changes (the bytes are in the
 * session cache). Needs the main PDF present so the engine can route the paper to its analyses; with
 * no PDF it stays idle (the run gate already requires the PDF). Debounced so a burst of drops fires
 * one request.
 */
export function useDataFit(paperId: string): DataFitState {
  const fv = usePaperFiles(paperId);
  const sig = `${fv.hasMain ? "m" : ""}|${[...fv.attached].sort().join(",")}`;
  const [state, setState] = React.useState<DataFitState>({ fits: [], loading: false, error: null });

  React.useEffect(() => {
    if (!fv.hasMain || fv.supplementCount === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when files clear
      setState({ fits: [], loading: false, error: null });
      return;
    }
    let on = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    const t = setTimeout(() => {
      void (async () => {
        try {
          const fits = await assessData(
            paperId,
            paperFiles.getMain(paperId),
            paperFiles.getSupplementFiles(paperId),
          );
          if (on) setState({ fits, loading: false, error: null });
        } catch (e) {
          if (on) {
            setState({
              fits: [],
              loading: false,
              error: e instanceof Error ? e.message : "Couldn't check the data.",
            });
          }
        }
      })();
    }, 400);
    return () => {
      on = false;
      clearTimeout(t);
    };
    // re-assess only when the attached file set changes (sig), not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId, sig]);

  return state;
}

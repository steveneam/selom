"use client";

/**
 * Live-reproduction run client + React controllers (live-reproduction-spec §5 / §7).
 *
 * Two backend calls via the /api proxy: POST /papers/{id}/reproduce (the paper PDF + supplements →
 * an inline reproduce run) and GET /reproduction-runs/{id} (the driven Ledger once succeeded —
 * same shape as GET /papers/{slug}, so the Score stage reuses every showcase component). v1 runs
 * INLINE (spec §6, L5): the POST returns already-terminal, so there's no SSE/poll to babysit; the
 * poll loop below is a forward-compatible no-op that only engages if a future arq path returns a
 * non-terminal status. The bytes come from the session File cache (`@/lib/paper/run-files`, I5).
 */

import * as React from "react";
import { useRouter } from "next/navigation";

import { paperFiles, usePaperFiles } from "@/lib/paper/run-files";
import { workspaceStore } from "@/lib/workspace/store";
import type { Ledger } from "./types";

export type RunStatus = "queued" | "running" | "succeeded" | "failed";

/** The wire shape of a run (GET full; POST returns the light subset). */
export interface RunPayload {
  run_id: string;
  status: RunStatus;
  progress?: string;
  error?: string;
  ledger?: Ledger;
  drive_summary?: Record<string, number>;
}

const TERMINAL: readonly RunStatus[] = ["succeeded", "failed"];

/** POST the paper PDF + supplements → start a reproduce run. Returns the light payload. */
export async function startReproduction(
  paperId: string,
  main: File,
  supplements: File[],
): Promise<RunPayload> {
  const body = new FormData();
  body.append("main", main);
  for (const s of supplements) body.append("supplements", s);
  const url = `/api/papers/${encodeURIComponent(paperId)}/reproduce`;
  const res = await fetch(url, { method: "POST", body });
  if (!res.ok) {
    // Mirror the house convention (skills-api.ts): surface the backend's `detail` when present.
    let detail = res.status === 413 ? "those files exceed the upload limit" : `rejected (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = String(j.detail);
    } catch {
      /* non-JSON body */
    }
    throw new Error(`Couldn't start reproduction — ${detail}.`);
  }
  return (await res.json()) as RunPayload;
}

/** GET a run's state — the full payload (driven Ledger + scorecard once succeeded). */
export async function fetchRun(runId: string): Promise<RunPayload> {
  const url = `/api/reproduction-runs/${encodeURIComponent(runId)}`;
  const res = await fetch(url, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return (await res.json()) as RunPayload;
}

export type RunPhase = "idle" | "running" | "succeeded" | "failed";

/** The Reproduce-stage run controller — owns the POST lifecycle + the readiness gate. */
export interface PaperRun {
  phase: RunPhase;
  error: string | null;
  hasMain: boolean;
  supplementCount: number;
  /** Both the paper PDF and ≥1 supplement have bytes this session, and no run is in flight. */
  canRun: boolean;
  start: () => void;
}

/**
 * Drive one paper's reproduction. Reads the session File bytes, POSTs them, and on success stamps
 * `reproductionRunId` on the saved paper + navigates to the Score stage (which fetches the driven
 * ledger by that id). A single instance lives in the Paper shell so the forward button and the
 * Reproduce stage share one lifecycle.
 */
export function usePaperRun(paperId: string): PaperRun {
  const router = useRouter();
  const fv = usePaperFiles(paperId);
  const [phase, setPhase] = React.useState<RunPhase>("idle");
  const [error, setError] = React.useState<string | null>(null);

  const canRun = fv.hasMain && fv.supplementCount >= 1 && phase !== "running";

  const start = React.useCallback(() => {
    const main = paperFiles.getMain(paperId);
    const supps = paperFiles.getSupplementFiles(paperId);
    if (!main || supps.length === 0) return;
    setPhase("running");
    setError(null);
    void (async () => {
      try {
        let payload = await startReproduction(paperId, main, supps);
        // Inline → already terminal. Poll only if a future async path hands back a running run.
        for (let i = 0; i < 600 && !TERMINAL.includes(payload.status); i += 1) {
          await new Promise((r) => setTimeout(r, 500));
          payload = await fetchRun(payload.run_id);
        }
        if (payload.status === "failed") {
          setPhase("failed");
          setError(payload.error ?? "The reproduction run failed.");
          return;
        }
        workspaceStore.setPaperReproductionRun(paperId, payload.run_id);
        setPhase("succeeded");
        router.push(`/paper/${paperId}?stage=score`);
      } catch (e) {
        setPhase("failed");
        // `startReproduction` throws a user-friendly message; a bare network failure is a fetch
        // TypeError → fall back to the "is the backend up?" hint.
        setError(
          e instanceof Error && e.message.startsWith("Couldn't start reproduction")
            ? e.message
            : "Couldn't reach the reproduction service. Is the backend running on :8000?",
        );
      }
    })();
  }, [paperId, router]);

  return { phase, error, hasMain: fv.hasMain, supplementCount: fv.supplementCount, canRun, start };
}

/** The Score-stage loader — GET the driven ledger by run id (the run is already terminal). */
export interface LoadedRun {
  status: RunStatus | null;
  ledger: Ledger | null;
  /** "expired" when the run is gone (the in-process store cleared / a reload outlived it). */
  error: string | null;
  loading: boolean;
}

export function useReproductionRun(runId: string | undefined): LoadedRun {
  const [state, setState] = React.useState<LoadedRun>({
    status: null,
    ledger: null,
    error: null,
    loading: !!runId,
  });

  React.useEffect(() => {
    if (!runId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when the run id clears
      setState({ status: null, ledger: null, error: null, loading: false });
      return;
    }
    let on = true;
    setState({ status: null, ledger: null, error: null, loading: true });
    fetchRun(runId)
      .then((p) => {
        if (!on) return;
        setState({ status: p.status, ledger: p.ledger ?? null, error: p.error ?? null, loading: false });
      })
      .catch(() => {
        if (on) setState({ status: null, ledger: null, error: "expired", loading: false });
      });
    return () => {
      on = false;
    };
  }, [runId]);

  return state;
}

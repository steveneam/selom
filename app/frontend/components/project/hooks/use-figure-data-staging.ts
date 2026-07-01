"use client";

import * as React from "react";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { deriveFigureModel } from "@/lib/figure/figure-model";
import {
  applyStagedMarks,
  hideDotLabels,
  parseManualMarks,
  serializeManualMarks,
  setManualMark,
  type MarkRole,
} from "@/lib/erg/marks";
import { applyStagedThresholds, readThresholds, type VolcanoThresholds } from "@/lib/volcano/thresholds";
import { applyAcceptedProposals } from "@/lib/ai/proposals";
import type { SkillParams } from "@/lib/skills/api";
import { recommendParams, runtimeSkillId, stageableRecommendations } from "@/lib/skills/api";
import type { Dataset, Figure } from "@/lib/projects/types";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { AutoTuneOutcome } from "@/components/ai/ask-ai";

/** Coerce a staged param value (number | numeric string | undefined) to a number, else the fallback. */
function numOr(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : typeof v === "string" ? parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

interface UseFigureDataStagingArgs {
  /** The open figure — its provenance.params seed the staged base; its aiProposals re-hydrate on scope change. */
  activeFigure: Figure | undefined;
  activeFigureId: string | null;
  /** The open figure's source dataset — its persisted route/fit/design feed the deterministic Auto-tune. */
  activeDataset: Dataset | undefined;
  /** The shared figure store — the live preview reads its spec. */
  figure: FigureStore;
}

export interface FigureDataStaging {
  /** The staged Figure-data inputs (lifted from the panel so a drag + the numeric editor write one place). */
  fdParams: SkillParams;
  setFdParams: React.Dispatch<React.SetStateAction<SkillParams>>;
  /** The open figure's committed run params — the base the staged inputs diff against. */
  fdBaseParams: SkillParams;
  /** The (dataset · skill · figure) scope key — remounts the bespoke inputs on any switch. */
  fdScope: string;
  /** Are there staged input changes pending a re-run? */
  fdDirty: boolean;
  /** The live preview spec: staged marks + label toggle + staged volcano thresholds, all pure + instant. */
  previewSpec: FigureSpec | null | undefined;
  /** Live "show a/b labels" toggle for the preview (cosmetic — an instant client-side restyle). */
  markLabelsShown: boolean;
  setMarkLabelsShown: React.Dispatch<React.SetStateAction<boolean>>;
  /** Drag an ERG landmark dot → stage the new time (the dot moves live; re-measures on re-run). */
  onMarkMove: (segment: string, role: MarkRole, tMs: number) => void;
  /** Drag a volcano FC/p threshold → stage the new cut (points re-colour live; recompute on re-run). */
  onThresholdChange: (t: VolcanoThresholds) => void;
  /** The deterministic one-click Auto-tune (best-practice defaults; no gateway, no ✨). */
  autoTune: () => Promise<AutoTuneOutcome>;
}

/**
 * The Figure-data staging concern for ProjectWorkspace — extracted from the composition root
 * ([[contract-frozen-refactor]]: lift a cohesive orchestration cluster into a `useX` hook, leave
 * rendering in the view). Owns the STAGED figure-data inputs (a dot drag + the numeric Marks/Threshold
 * editors all write the same `fdParams`, a live preview reflects them, ONE explicit re-run applies them)
 * plus the deterministic Auto-tune handler (`docs/auto-tune/spec.md`). Behaviour is the root's verbatim.
 *
 * The staged inputs are scoped to the (dataset · skill · figure) the open figure was produced by — not
 * just its id: switching skill/dataset, or opening another figure, restarts from THAT figure's own
 * params. Derive-don't-sync: the reset happens DURING render when the scope key changes (React's "store
 * information from previous renders" pattern), not in an effect that lags a paint.
 */
export function useFigureDataStaging({
  activeFigure,
  activeFigureId,
  activeDataset,
  figure,
}: UseFigureDataStagingArgs): FigureDataStaging {
  // Live "show a/b labels" toggle for the Figure-data preview (figure-data-capabilities §6). Labels
  // are cosmetic on already-drawn dots, so hiding them is an INSTANT client-side restyle.
  const [markLabelsShown, setMarkLabelsShown] = React.useState(true);
  // The Figure-data inputs are STAGED here (lifted from the panel) so a dot drag and the numeric Marks
  // editor write to the same params, the preview reflects them live, and ONE explicit re-run applies
  // them. Reset from the open figure's own params when the scope changes (derive-during-render below).
  const [fdParams, setFdParams] = React.useState<SkillParams>({});
  // The open figure's committed run params — the base the staged inputs diff against. Memoized so the
  // `?? {}` fallback doesn't mint a fresh object each render (which would churn fdDirty's memo).
  const fdBaseParams = React.useMemo(
    () => (activeFigure?.provenance?.params ?? {}) as SkillParams,
    [activeFigure],
  );
  // The staged Figure-data inputs are scoped to the (dataset · skill · figure) the open figure was
  // produced by — not just its figure id (inventory §5.4 / gate Spine 3). Switching skill/dataset, or
  // opening another figure, must restart from THAT figure's own params; a stale fc from skill A must
  // never carry into a skill-B run, and a failed re-run must not strand another skill's staged value.
  // Derive-don't-sync: reset the staged state DURING render when the scope key changes (React's
  // "store information from previous renders" pattern) instead of in an effect — the old effect lagged
  // a paint (a one-frame flash of the prior staged marks/thresholds on the new figure) and keyed only
  // on the figure id. The label toggle re-derives from the same base params.
  const fdScope = `${activeFigure?.datasetId ?? "_"}:${activeFigure?.skillId ?? "_"}:${activeFigureId ?? "_"}`;
  const [fdScopeKey, setFdScopeKey] = React.useState(fdScope);
  if (fdScopeKey !== fdScope) {
    setFdScopeKey(fdScope);
    // Seed from the figure's base params, then re-hydrate any ACCEPTED AI proposals' staged values
    // (S5) so an accepted-but-not-yet-re-run suggestion survives a reload coherently — the banner's
    // "staged" row, the counter, and the ✨ control marker stay in agreement.
    setFdParams(applyAcceptedProposals({ ...fdBaseParams }, activeFigure?.aiProposals ?? []));
    setMarkLabelsShown(fdBaseParams.mark_labels === undefined ? true : String(fdBaseParams.mark_labels) === "true");
  }
  // Are there staged input changes pending a re-run? (drag / time edit / dots toggle / any input.)
  const fdDirty = React.useMemo(() => {
    const keys = new Set([...Object.keys(fdBaseParams), ...Object.keys(fdParams)]);
    return [...keys].some((k) => fdParams[k] !== fdBaseParams[k]);
  }, [fdParams, fdBaseParams]);
  // The preview reflects the staged marks (dots move live) + the label toggle + staged volcano
  // thresholds (points re-colour live) — all pure + instant, no re-run.
  const previewSpec = React.useMemo(() => {
    let base = figure.spec ?? activeFigure?.spec;
    if (!base) return base;
    const manual = parseManualMarks(fdParams.manual_marks);
    if (Object.keys(manual).length) base = applyStagedMarks(base, manual);
    if (!markLabelsShown) base = hideDotLabels(base);
    // Volcano: live re-bucket to the staged FC/p cuts. Idempotent, so applying the figure's own
    // thresholds is a no-op — only re-bucket when a staged value actually differs.
    if (deriveFigureModel(base).capabilities.thresholds) {
      const t = readThresholds(base);
      if (t) {
        const fc = numOr(fdParams.fc_threshold, t.fc);
        const fdr = numOr(fdParams.fdr_threshold, t.fdr);
        if (fc !== t.fc || fdr !== t.fdr) base = applyStagedThresholds(base, { fc, fdr }).spec;
      }
    }
    return base;
  }, [
    figure.spec,
    activeFigure?.spec,
    fdParams.manual_marks,
    fdParams.fc_threshold,
    fdParams.fdr_threshold,
    markLabelsShown,
  ]);

  // Drag an ERG landmark dot on the canvas (erg-manual-marks R5) → STAGE the new time into the shared
  // figure-data params (same place the numeric Marks editor writes). The dot moves live (the preview
  // applies the staged marks); the amplitude re-measures server-side on the next explicit re-run — so
  // you can drag freely without a re-run per drop. The pending-changes banner prompts the re-run.
  const onMarkMove = React.useCallback((segment: string, role: MarkRole, tMs: number) => {
    setFdParams((p) => ({
      ...p,
      marks: true,
      manual_marks: serializeManualMarks(setManualMark(parseManualMarks(p.manual_marks), segment, role, tMs)),
    }));
  }, [setFdParams]);

  // Drag a volcano FC/p-value threshold line (generalization-spec §E) → STAGE the new cut into the
  // shared figure-data params (same place the numeric Threshold editor writes). The points re-colour
  // live (the preview re-buckets); the DE table + labels recompute on the next explicit re-run.
  const onThresholdChange = React.useCallback((t: VolcanoThresholds) => {
    setFdParams((p) => ({ ...p, fc_threshold: t.fc, fdr_threshold: t.fdr }));
  }, [setFdParams]);

  // The DETERMINISTIC one-click default (Layer A Auto-tune, docs/auto-tune/spec.md): fetch the
  // engine's best-practice params for this skill + data, stage the diff into the SAME pending queue as
  // human-authored changes (no ✨, no gateway) — one re-run commits them. Design params stay ingest's
  // job, so they never appear here. A plain closure (like the prior inline handler), not memoized.
  const autoTune = async (): Promise<AutoTuneOutcome> => {
    if (!activeFigure?.skillId) {
      return { ok: false, note: "No skill to tune yet — run a skill first." };
    }
    const recs = await recommendParams(runtimeSkillId(activeFigure.skillId), {
      data_columns: activeDataset?.dataFit?.columns ?? null,
      data_kind: activeDataset?.routing?.kind ?? null,
      data_n_numeric_cols: activeDataset?.dataFit?.n_numeric_cols ?? null,
      design: activeDataset?.design ?? null,
    });
    // Diff against the committed base (fdBaseParams) AND leave any input the user has already
    // hand-staged untouched — so the note matches the visible amber cue and Auto-tune never silently
    // overwrites an in-progress edit.
    const { changes, applied, skipped } = stageableRecommendations(recs.recs, fdParams, fdBaseParams);
    const skipMsg = skipped.length
      ? ` Left your ${skipped.length} edited input${skipped.length === 1 ? "" : "s"} (${skipped.join(", ")}) as-is.`
      : "";
    if (applied.length === 0) {
      return { ok: true, note: `Already at the best-practice settings — nothing to change.${skipMsg}` };
    }
    setFdParams((prev) => ({ ...prev, ...changes }));
    // The reviewable, no-black-box diff: each changed input as OLD→NEW + why (spec §What / R9).
    const diff = applied.map((a) => `${a.key} ${a.from}→${a.to} (${a.why})`).join(" · ");
    return {
      ok: true,
      note: `Set ${applied.length} best-practice input${applied.length === 1 ? "" : "s"}: ${diff}.${skipMsg} Review the changed inputs below, then re-run.`,
    };
  };

  return {
    fdParams,
    setFdParams,
    fdBaseParams,
    fdScope,
    fdDirty,
    previewSpec,
    markLabelsShown,
    setMarkLabelsShown,
    onMarkMove,
    onThresholdChange,
    autoTune,
  };
}

"use client";

import * as React from "react";
import type { FigureStore } from "@/hooks/use-figure-store";
import { projectStore } from "@/lib/projects/store";
import { pushUndo } from "@/lib/workspace/undo";
import { datasetDisplayName } from "@/lib/lineage/family";
import type { Dataset, Figure } from "@/lib/projects/types";
import type { RailView } from "../workrail";

interface UseFigureCrudArgs {
  /** The live figure-edit store — seeded/reset as figures open + close. */
  figure: FigureStore;
  /** Routing state read by the delete handlers (extracted in useWorkspaceView). */
  view: RailView;
  activeFigureId: string | null;
  activeDatasetId: string | null;
  /** Injected routing setters — open/delete navigate by writing these. */
  setView: React.Dispatch<React.SetStateAction<RailView>>;
  setActiveFigureId: React.Dispatch<React.SetStateAction<string | null>>;
  setActiveDatasetId: React.Dispatch<React.SetStateAction<string | null>>;
  setCompareIds: React.Dispatch<React.SetStateAction<string[]>>;
}

export interface FigureCrud {
  openFigure: (f: Figure) => void;
  openStats: (f: Figure) => void;
  openCompare: (ids: string[]) => void;
  deleteFigure: (f: Figure) => void;
  deleteDataset: (d: Dataset) => void;
}

/**
 * Open + delete handlers for figures and datasets (§3C). Each navigates by writing the
 * injected useWorkspaceView setters and seeds/resets the shared figure store; deletes
 * are Undo-backed (never a confirm) since the removal is reversible from the returned
 * record. Behaviour is identical to the inline handlers it replaced — these stay plain
 * per-render closures over the current routing state.
 */
export function useFigureCrud({
  figure,
  view,
  activeFigureId,
  activeDatasetId,
  setView,
  setActiveFigureId,
  setActiveDatasetId,
  setCompareIds,
}: UseFigureCrudArgs): FigureCrud {
  // Open a persisted figure in the editor: seed the live store from its stored spec
  // (durable now — Pillar 1). A legacy figure with no stored spec opens to a notice
  // rather than crashing (see the Figure view's empty states).
  function openFigure(f: Figure) {
    setActiveFigureId(f.id);
    if (f.spec) figure.init(f.spec);
    else figure.reset();
    setView("figure");
  }

  // Select a figure's Statistics node: focus it (drives the table read-out). Load its spec into the
  // editor store too, so the gene-label Label toggle in the table edits the SAME spec the canvas does
  // (one shared, undoable label set). A legacy figure with no stored spec is left as-is.
  function openStats(f: Figure) {
    setActiveFigureId(f.id);
    if (f.spec) figure.init(f.spec);
    setView("stats");
  }

  // Open the compare view for a version family (from the rail's family group or the
  // version bar). Needs ≥2 versions; focuses the newest so the lineage reads cleanly.
  function openCompare(ids: string[]) {
    if (ids.length < 2) return;
    setCompareIds(ids);
    setActiveFigureId(ids[ids.length - 1]);
    setView("compare");
  }

  // Delete ONE figure (only that figure — never the project). Offers an Undo rather
  // than a confirm, since the removal is reversible from the returned record. If the
  // deleted figure was open, drop back to the project home.
  function deleteFigure(f: Figure) {
    const removed = projectStore.removeFigure(f.id);
    if (!removed) return;
    pushUndo(`Deleted figure “${f.title}”`, () => projectStore.restoreFigure(removed));
    if (activeFigureId === f.id) {
      setActiveFigureId(null);
      figure.reset();
      if (view === "figure" || view === "stats") setView("home");
    }
  }

  // Delete ONE dataset (only the dataset — its figures stay, just without a live data
  // link). Undo-backed, like figure delete.
  function deleteDataset(d: Dataset) {
    const removed = projectStore.removeDataset(d.id);
    if (!removed) return;
    pushUndo(`Deleted dataset “${datasetDisplayName(removed)}”`, () => projectStore.restoreDataset(removed));
    if (activeDatasetId === d.id) setActiveDatasetId(null);
  }

  return { openFigure, openStats, openCompare, deleteFigure, deleteDataset };
}

"use client";

import * as React from "react";
import type { RailView } from "../workrail";

/**
 * The workrail's routing state (Pillar 1, S2.3) — the four slots that drive which
 * pane the orchestrator shows and which figure/dataset is in focus. The run + CRUD
 * hooks write these through the injected setters; this hook owns nothing but state,
 * so it stays the single home for "where are we / what's open" in ProjectWorkspace.
 */
export interface WorkspaceView {
  /** home (pipeline) / data / skill (run) / stats / figure / figuredata / compare. */
  view: RailView;
  setView: React.Dispatch<React.SetStateAction<RailView>>;
  /**
   * The persisted figure in focus (Pillar 1) — drives the editor (figure view), the
   * Statistics table (stats view), and the staleness/bundle read-out. null = nothing
   * open / a fresh run.
   */
  activeFigureId: string | null;
  setActiveFigureId: React.Dispatch<React.SetStateAction<string | null>>;
  /**
   * The dataset in focus in the Data view (picked from the rail) — drives the
   * context-scoped header delete ("Delete dataset").
   */
  activeDatasetId: string | null;
  setActiveDatasetId: React.Dispatch<React.SetStateAction<string | null>>;
  /** The version family (figure ids) shown in the compare view (S3.2). */
  compareIds: string[];
  setCompareIds: React.Dispatch<React.SetStateAction<string[]>>;
}

export function useWorkspaceView(): WorkspaceView {
  // The workrail view (Pillar 1, S2.3) — replaces the old four tabs. The lineage rail
  // navigates: home (pipeline) / data / skill (run) / stats (a result table) / figure.
  const [view, setView] = React.useState<RailView>("home");
  const [activeFigureId, setActiveFigureId] = React.useState<string | null>(null);
  const [activeDatasetId, setActiveDatasetId] = React.useState<string | null>(null);
  const [compareIds, setCompareIds] = React.useState<string[]>([]);

  return {
    view,
    setView,
    activeFigureId,
    setActiveFigureId,
    activeDatasetId,
    setActiveDatasetId,
    compareIds,
    setCompareIds,
  };
}

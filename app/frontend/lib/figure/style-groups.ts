/**
 * Which Style-panel groups render, for a given figure — the SINGLE SOURCE OF TRUTH.
 *
 * The adaptive Style panel shows control groups conditionally from the derived FigureModel (a line
 * grid never shows point size; a heatmap never shows markers; a sankey/radar shows no axis
 * gridlines). This module computes that group list once so (a) the panel renders from it and (b) a
 * node-env golden test can assert the exact set per archetype without rendering React — the two can
 * never drift. See docs/figure-editor-contract/spec.md §3.2 + docs/pillar-2-direct-manipulation
 * spec §5.1 (the new "gridlines" group).
 *
 * Pure; only reads the model + the (already-validated) spec. `palette` + `background` are universal;
 * every other group is capability/spec gated to match the panel's JSX exactly.
 */
import type { FigureModel } from "./figure-model";
import { findColorbarTrace, type FigureSpec } from "./figure-spec";
import { heatmapColorscaleState } from "./contract";
import { hasDendrogram } from "@/lib/heatmap/dendrogram";
import { mainHeatmapIndex } from "@/lib/heatmap/labels";

export type StyleGroupId =
  | "markers"
  | "lines"
  | "colorscale"
  | "colorscaleEmpty"
  | "dendrogram"
  | "labels"
  | "palette"
  | "background"
  | "gridlines"
  | "colorbar";

/**
 * The ordered list of Style groups that render for this figure. Order mirrors the panel's JSX so a
 * snapshot reads top-to-bottom. `colorscale`/`colorscaleEmpty` are mutually exclusive (a heatmap
 * trace → the live re-tone controls; a declared-heatmap-but-traceless spec → an explicit note;
 * neither for a plain continuous-colour scatter). `colorbar` also requires an actual colour-bar
 * trace (the panel's inner guard), so a declared-but-absent colour bar doesn't leave an empty group.
 */
export function styleGroups(model: FigureModel, spec: FigureSpec): StyleGroupId[] {
  const cap = model.capabilities;
  const heatmapCount = model.heatmapTraceIndices.length;
  const colorscaleState = heatmapColorscaleState({
    heatmapTones: cap.heatmapTones,
    heatmapLabels: cap.heatmapLabels,
    heatmapTraceCount: heatmapCount,
  });

  const groups: StyleGroupId[] = [];
  if (cap.markers) groups.push("markers");
  if (cap.lines) groups.push("lines");
  if (colorscaleState === "ready") groups.push("colorscale");
  else if (colorscaleState === "empty") groups.push("colorscaleEmpty");
  if (heatmapCount > 0 && hasDendrogram(spec)) groups.push("dendrogram");
  if (cap.heatmapLabels && heatmapCount > 0 && mainHeatmapIndex(spec) >= 0) groups.push("labels");
  groups.push("palette");
  groups.push("background");
  if (cap.cartesianAxes) groups.push("gridlines");
  if (cap.colorbar && findColorbarTrace(spec) != null) groups.push("colorbar");
  return groups;
}

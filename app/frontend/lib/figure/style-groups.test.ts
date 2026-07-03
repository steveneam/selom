import { describe, expect, it } from "vitest";

import { deriveFigureModel } from "./figure-model";
import { styleGroups } from "./style-groups";
import type { FigureSpec } from "./figure-spec";

/**
 * Golden: which Style-panel groups render per figure archetype. `styleGroups` is the single source of
 * truth the panel renders from, so this snapshot IS what the user sees — no React render needed. The
 * headline for Pillar-2 slice 1: the new "gridlines" group shows for Cartesian figures (scatter /
 * line / bar / box) and is HIDDEN for heatmap / sankey / radar (docs/pillar-2-direct-manipulation
 * spec §5.1). `palette` + `background` are universal.
 */

function groupsFor(data: unknown[], layout: Record<string, unknown> = {}): string[] {
  const spec = { data, layout } as unknown as FigureSpec;
  return styleGroups(deriveFigureModel(spec), spec);
}

describe("Style groups per archetype (the golden)", () => {
  it("marker scatter (umap/pca) → markers + gridlines", () => {
    expect(groupsFor([{ type: "scatter", mode: "markers", marker: { color: "#1f77b4" } }])).toEqual([
      "markers",
      "palette",
      "background",
      "gridlines",
    ]);
  });

  it("line scatter (ERG / trajectory) → lines + gridlines, no markers", () => {
    expect(groupsFor([{ type: "scatter", mode: "lines", line: { color: "#111" } }])).toEqual([
      "lines",
      "palette",
      "background",
      "gridlines",
    ]);
  });

  it("bar (deg) → gridlines, no markers/lines group (colour via Palette/Data)", () => {
    expect(groupsFor([{ type: "bar", marker: { color: "#0072B2" } }])).toEqual([
      "palette",
      "background",
      "gridlines",
    ]);
  });

  it("box / violin → gridlines", () => {
    expect(groupsFor([{ type: "box", marker: { color: "#0072B2" } }])).toContain("gridlines");
    expect(groupsFor([{ type: "violin", marker: { color: "#0072B2" } }])).toContain("gridlines");
  });

  it("heatmap → colorscale + colorbar, NO gridlines", () => {
    const g = groupsFor([{ type: "heatmap", z: [[1, 2], [3, 4]], colorscale: "Viridis" }]);
    expect(g).toEqual(["colorscale", "palette", "background", "colorbar"]);
    expect(g).not.toContain("gridlines");
  });

  it("sankey → no gridlines (universal groups only)", () => {
    const g = groupsFor([{ type: "sankey", node: {}, link: {} }]);
    expect(g).toEqual(["palette", "background"]);
    expect(g).not.toContain("gridlines");
  });

  it("radar (scatterpolar) → no gridlines", () => {
    const g = groupsFor([{ type: "scatterpolar", r: [1, 2], theta: ["a", "b"] }]);
    expect(g).toEqual(["palette", "background"]);
    expect(g).not.toContain("gridlines");
  });

  it("a heatmap+scatter overlay still gets gridlines (any Cartesian trace → the group)", () => {
    const g = groupsFor([
      { type: "heatmap", z: [[1, 2], [3, 4]] },
      { type: "scatter", mode: "markers", marker: { color: "#f00" } },
    ]);
    expect(g).toContain("gridlines");
    expect(g).toContain("colorscale");
  });

  it("declared-but-traceless heatmap → the empty colour-scale note, still no gridlines", () => {
    const g = groupsFor([{ type: "scatter", mode: "lines", line: { color: "#111" } }], {
      meta: { selom: { capabilities: { tools: { heatmapTones: true } } } },
    });
    // lines figure (Cartesian) declaring a heatmap tone but shipping no heatmap trace:
    expect(g).toContain("colorscaleEmpty");
    expect(g).toContain("gridlines"); // the line trace is still Cartesian
  });
});

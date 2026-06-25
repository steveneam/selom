import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure-spec";
import { applyPatches } from "@/lib/patch";

import {
  HIGHLIGHT_COLOR,
  categoryLabels,
  currentTicktext,
  formatTick,
  hasRowDendrogram,
  highlightedGenes,
  labelRows,
  labelSideOps,
  mainHeatmapIndex,
  originalLabels,
  parseTick,
  renameLabelOps,
  setHighlightOps,
  setHighlightedGenesOps,
} from "./labels";

/** A heatmap spec in the skills/heatmap/run.py shape (canonical originals in meta.selom). */
function heatmapSpec(opts: { withRowTree?: boolean; extraTrace?: boolean } = {}): FigureSpec {
  const data: Record<string, unknown>[] = [
    {
      type: "heatmap",
      z: [
        [0, 1, -2],
        [3, -1.5, 0.5],
        [0.2, -0.3, 0.7],
      ],
      x: ["S1", "S2", "S3"],
      y: ["STRIP2", "CALD1", "ENPP2"],
      colorscale: "RdBu",
    },
  ];
  if (opts.extraTrace) {
    // a 1-row annotation strip (fewer rows than the main map) + a dendrogram scatter
    data.push({ type: "heatmap", z: [[1, 2, 3]], x: ["S1", "S2", "S3"], y: ["track"] });
    data.push({ type: "scatter", mode: "lines", x: [0, 1], y: [0, 1], xaxis: "x2", yaxis: "y2" });
  }
  const layout: Record<string, unknown> = {
    // the real backend always emits the axis objects (fast-json-patch `add` needs the parent)
    xaxis: { title: { text: "sample" } },
    yaxis: { title: { text: "gene" } },
    meta: {
      selom: {
        heatmapLabels: {
          x: ["S1", "S2", "S3"],
          y: ["ENSG1~STRIP2", "ENSG2~CALD1", "ENSG3~ENPP2"],
        },
      },
    },
  };
  if (opts.withRowTree) layout.xaxis2 = { domain: [0, 0.14] };
  return { data, layout } as unknown as FigureSpec;
}

describe("heatmap labels — read helpers", () => {
  it("mainHeatmapIndex picks the largest heatmap (skips 1-row strips + scatters)", () => {
    expect(mainHeatmapIndex(heatmapSpec())).toBe(0);
    expect(mainHeatmapIndex(heatmapSpec({ extraTrace: true }))).toBe(0); // the 3-row map, not the strip
    expect(mainHeatmapIndex({ data: [], layout: {} } as unknown as FigureSpec)).toBe(-1);
  });

  it("categoryLabels reads the data array; originalLabels prefers the canonical meta", () => {
    expect(categoryLabels(heatmapSpec(), "y")).toEqual(["STRIP2", "CALD1", "ENPP2"]);
    expect(originalLabels(heatmapSpec(), "y")).toEqual(["ENSG1~STRIP2", "ENSG2~CALD1", "ENSG3~ENPP2"]);
    // no meta → falls back to the category labels
    const noMeta = { data: heatmapSpec().data, layout: {} } as unknown as FigureSpec;
    expect(originalLabels(noMeta, "y")).toEqual(["STRIP2", "CALD1", "ENPP2"]);
  });

  it("currentTicktext seeds from the category labels until a rename pins it", () => {
    expect(currentTicktext(heatmapSpec(), "x")).toEqual(["S1", "S2", "S3"]);
  });

  it("hasRowDendrogram detects the left gutter axis", () => {
    expect(hasRowDendrogram(heatmapSpec())).toBe(false);
    expect(hasRowDendrogram(heatmapSpec({ withRowTree: true }))).toBe(true);
  });
});

describe("heatmap labels — span parse/format", () => {
  it("round-trips plain and highlighted ticks", () => {
    expect(parseTick("STRIP2")).toEqual({ text: "STRIP2", highlighted: false });
    const wrapped = formatTick("STRIP2", true);
    expect(wrapped).toBe(`<span style="color:${HIGHLIGHT_COLOR}">STRIP2</span>`);
    expect(parseTick(wrapped)).toEqual({ text: "STRIP2", highlighted: true });
  });
});

describe("heatmap labels — rename", () => {
  it("renames one label (display-only) leaving the data + meta untouched", () => {
    const spec = heatmapSpec();
    const next = applyPatches(spec, renameLabelOps(spec, "y", 0, "My Gene"));
    // axis ticktext shows the rename; the data y + canonical meta are unchanged → hover/provenance intact
    expect((next.layout as Record<string, { ticktext?: string[] }>).yaxis.ticktext).toEqual([
      "My Gene",
      "CALD1",
      "ENPP2",
    ]);
    expect((next.data[0] as { y: string[] }).y).toEqual(["STRIP2", "CALD1", "ENPP2"]);
    expect(labelRows(next, "y")[0]).toMatchObject({ text: "My Gene", original: "ENSG1~STRIP2" });
  });

  it("uses positional tickvals so the categorical axis maps cleanly", () => {
    const spec = heatmapSpec();
    const next = applyPatches(spec, renameLabelOps(spec, "x", 1, "Treated"));
    const xaxis = (next.layout as Record<string, { tickmode?: string; tickvals?: number[] }>).xaxis;
    expect(xaxis.tickmode).toBe("array");
    expect(xaxis.tickvals).toEqual([0, 1, 2]);
  });

  it("a blank rename resets to the category base label", () => {
    let spec = heatmapSpec();
    spec = applyPatches(spec, renameLabelOps(spec, "y", 0, "Foo"));
    spec = applyPatches(spec, renameLabelOps(spec, "y", 0, "   "));
    expect(labelRows(spec, "y")[0].text).toBe("STRIP2");
  });
});

describe("heatmap labels — highlight + side", () => {
  it("highlights a gene as a red span and reports it, preserving a rename", () => {
    let spec = heatmapSpec();
    spec = applyPatches(spec, renameLabelOps(spec, "y", 1, "CALD1*"));
    spec = applyPatches(spec, setHighlightOps(spec, "y", 1, true));
    const tt = (spec.layout as Record<string, { ticktext?: string[] }>).yaxis.ticktext!;
    expect(tt[1]).toBe(`<span style="color:${HIGHLIGHT_COLOR}">CALD1*</span>`);
    expect(highlightedGenes(spec)).toEqual(["CALD1*"]);
    // un-highlight keeps the renamed text
    spec = applyPatches(spec, setHighlightOps(spec, "y", 1, false));
    expect(highlightedGenes(spec)).toEqual([]);
    expect(labelRows(spec, "y")[1].text).toBe("CALD1*");
  });

  it("setHighlightedGenesOps highlights exactly the requested set by display text", () => {
    const spec = heatmapSpec();
    const next = applyPatches(spec, setHighlightedGenesOps(spec, ["STRIP2", "ENPP2"]));
    expect(highlightedGenes(next).sort()).toEqual(["ENPP2", "STRIP2"]);
  });

  it("labelSideOps moves the gene labels to a side", () => {
    const spec = heatmapSpec();
    const next = applyPatches(spec, labelSideOps("y", "right"));
    expect((next.layout as Record<string, { side?: string }>).yaxis.side).toBe("right");
  });
});

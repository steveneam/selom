import { describe, expect, it } from "vitest";

import {
  annotationItems,
  annotationTextOp,
  annotationVisibilityOp,
  deriveFigureModel,
  inferTraceKind,
  scalebarResizeOps,
  scalebarVisibilityOps,
  seriesColorOps,
  seriesForTrace,
} from "./figure-model";
import type { FigureSpec as SpecType } from "./figure-spec";

/**
 * The agnostic floor is INFERENCE — these fixtures carry NO `meta.selom` hints, so they
 * prove the editor derives a correct model from a raw Plotly spec for every archetype.
 * The headline case is the ERG trace grid: 42 line traces must collapse to 6 condition
 * series, each editing `line.color` (not the historical `marker.color` no-op), with the
 * two grey arms (PDE6B / stuffer) kept apart despite sharing a colour.
 */

function spec(data: unknown[], layout: Record<string, unknown> = {}): SpecType {
  return { data, layout } as unknown as SpecType;
}

// Mirror the real ERG colours from skills/_erg.py::COLORS (PDE6B + stuffer share grey).
const ERG = {
  Control: "#111111",
  Untreated: "#0072B2",
  "AAV8-RK-PDE6B": "#9aa3ad",
  "AAV8-RK-GFP-polyA-stuffer": "#9aa3ad",
  "AAV8-CMV-GFP": "#E69F00",
  "AAV8-RK-PDE6B-3UTR": "#c0392b",
} as const;

function ergGrid(): SpecType {
  const data: unknown[] = [];
  const layout: Record<string, unknown> = { shapes: [], annotations: [] };
  let k = 1;
  for (const cond of Object.keys(ERG)) {
    for (let g = 1; g <= 7; g++) {
      const sfx = k === 1 ? "" : String(k);
      data.push({
        type: "scatter",
        mode: "lines",
        x: [0, 1, 2],
        y: [0, 1, 0],
        line: { width: 1.2, color: ERG[cond as keyof typeof ERG] },
        xaxis: `x${sfx}`,
        yaxis: `y${sfx}`,
        name: `${cond} g${g}`,
      });
      if (k > 1) {
        layout[`xaxis${sfx}`] = { visible: false };
        layout[`yaxis${sfx}`] = { visible: false };
      }
      k++;
    }
  }
  // Two paper-referenced scale-bar lines (as _tracegrid emits).
  (layout.shapes as unknown[]).push(
    { type: "line", xref: "paper", yref: "paper", x0: 0.03, x1: 0.03, y0: 0.02, y1: 0.1 },
    { type: "line", xref: "paper", yref: "paper", x0: 0.03, x1: 0.1, y0: 0.02, y1: 0.02 },
  );
  return spec(data, layout);
}

describe("inferTraceKind", () => {
  it("classifies by type + mode", () => {
    expect(inferTraceKind({ type: "scatter", mode: "lines" })).toBe("lineScatter");
    expect(inferTraceKind({ type: "scatter", mode: "markers" })).toBe("markerScatter");
    expect(inferTraceKind({ type: "scatter", mode: "lines+markers" })).toBe("lineMarkerScatter");
    expect(inferTraceKind({ type: "scattergl", mode: "markers" })).toBe("markerScatter");
    expect(inferTraceKind({ type: "heatmap" })).toBe("heatmap");
    expect(inferTraceKind({ type: "bar" })).toBe("bar");
    expect(inferTraceKind({ type: "box" })).toBe("box");
    expect(inferTraceKind({ type: "violin" })).toBe("violin");
    expect(inferTraceKind({ type: "sankey" })).toBe("sankey");
    expect(inferTraceKind({ type: "scatterpolar" })).toBe("polar");
  });

  it("defaults a mode-less scatter from its sub-objects (markers unless only line)", () => {
    expect(inferTraceKind({ type: "scatter", line: { color: "#000" } })).toBe("lineScatter");
    expect(inferTraceKind({ type: "scatter", marker: { color: "#000" } })).toBe("markerScatter");
    expect(inferTraceKind({})).toBe("markerScatter");
  });
});

describe("ERG trace grid (the headline agnostic win)", () => {
  const model = deriveFigureModel(ergGrid());

  it("groups 42 line traces into the 6 conditions", () => {
    expect(model.series).toHaveLength(6);
    expect(model.series.every((s) => s.traceIndices.length === 7)).toBe(true);
    expect(model.series.map((s) => s.label)).toEqual([
      "Control",
      "Untreated",
      "AAV8-RK-PDE6B",
      "AAV8-RK-GFP-polyA-stuffer",
      "AAV8-CMV-GFP",
      "AAV8-RK-PDE6B-3UTR",
    ]);
  });

  it("keeps the two grey arms separate despite the shared colour", () => {
    const grey = model.series.filter((s) => s.color?.toLowerCase() === "#9aa3ad");
    expect(grey).toHaveLength(2);
    expect(grey.map((s) => s.label).sort()).toEqual([
      "AAV8-RK-GFP-polyA-stuffer",
      "AAV8-RK-PDE6B",
    ]);
  });

  it("edits the LINE colour channel, not marker (the no-op bug)", () => {
    const control = model.series[0];
    expect(control.colorChannels).toEqual(["line"]);
    expect(control.colorPath).toBe("/data/0/line/color");
    const ops = seriesColorOps(control, "#ff0000");
    expect(ops).toHaveLength(7);
    expect(ops[0]).toEqual({ op: "add", path: "/data/0/line/color", value: "#ff0000" });
    expect(ops.every((o) => o.path.endsWith("/line/color"))).toBe(true);
  });

  it("exposes line + scalebar + subplot capabilities, NOT markers", () => {
    expect(model.capabilities.lines).toBe(true);
    expect(model.capabilities.markers).toBe(false);
    expect(model.capabilities.scalebar).toBe(true);
    expect(model.capabilities.subplotRanges).toBe(true);
    expect(model.primitives.map((p) => p.kind)).toContain("scalebar");
  });

  it("resolves a clicked curve back to its condition series", () => {
    const s = seriesForTrace(model, 9); // 2nd condition (Untreated), 3rd panel
    expect(s?.label).toBe("Untreated");
    expect(s?.traceIndices).toContain(9);
  });
});

describe("marker scatter (umap / pca) is unchanged", () => {
  const umap = spec([
    { type: "scatter", mode: "markers", marker: { color: "#1f77b4" }, name: "Cluster 1" },
    { type: "scatter", mode: "markers", marker: { color: "#ff7f0e" }, name: "Cluster 2" },
    { type: "scatter", mode: "markers", marker: { color: "#2ca02c" }, name: "Cluster 3" },
  ]);
  const model = deriveFigureModel(umap);

  it("keeps distinctly-coloured clusters as separate series (no wrong prefix-merge)", () => {
    expect(model.series).toHaveLength(3);
    expect(model.series.map((s) => s.label)).toEqual(["Cluster 1", "Cluster 2", "Cluster 3"]);
  });

  it("edits the marker colour channel", () => {
    expect(model.series[0].colorChannels).toEqual(["marker"]);
    expect(model.series[0].colorPath).toBe("/data/0/marker/color");
    expect(model.capabilities.markers).toBe(true);
    expect(model.capabilities.lines).toBe(false);
    expect(model.markerTraceIndices).toEqual([0, 1, 2]);
  });
});

describe("other archetypes", () => {
  it("heatmap → colorscale + colorbar, no markers/lines", () => {
    const m = deriveFigureModel(
      spec([{ type: "heatmap", z: [[1, 2], [3, 4]], colorscale: "Viridis" }]),
    );
    expect(m.capabilities.colorscale).toBe(true);
    expect(m.capabilities.colorbar).toBe(true);
    expect(m.capabilities.markers).toBe(false);
    expect(m.capabilities.lines).toBe(false);
    expect(m.heatmapTraceIndices).toEqual([0]);
  });

  it("bar → marker colour channel, no point/line controls", () => {
    const m = deriveFigureModel(
      spec([
        { type: "bar", marker: { color: "#0072B2" }, name: "Up" },
        { type: "bar", marker: { color: "#D55E00" }, name: "Down" },
      ]),
    );
    expect(m.series).toHaveLength(2);
    expect(m.series[0].colorChannels).toEqual(["marker"]);
    expect(m.capabilities.markers).toBe(false);
    expect(m.capabilities.lines).toBe(false);
  });

  it("sankey / radar → no per-trace solid colour series", () => {
    const sankey = deriveFigureModel(spec([{ type: "sankey", node: {}, link: {} }]));
    expect(sankey.series[0].colorChannels).toEqual([]);
    expect(sankey.series[0].colorPath).toBeNull();

    const radar = deriveFigureModel(spec([{ type: "scatterpolar", r: [1, 2], theta: ["a", "b"] }]));
    expect(radar.traceKinds).toEqual(["polar"]);
  });

  it("volcano (per-point colour array) shows no single swatch", () => {
    const m = deriveFigureModel(
      spec([{ type: "scatter", mode: "markers", marker: { color: ["#aaa", "#bbb", "#ccc"] } }]),
    );
    expect(m.series[0].perPoint).toBe(true);
    expect(m.series[0].color).toBeNull();
  });
});

describe("layout.meta.selom hints override inference", () => {
  it("uses the stamped series grouping when present", () => {
    const s = spec(
      [
        { type: "scatter", mode: "lines", line: { color: "#111" }, name: "a" },
        { type: "scatter", mode: "lines", line: { color: "#222" }, name: "b" },
      ],
      {
        meta: {
          selom: {
            figureKind: "trace_grid",
            series: [{ label: "Both", traceIndices: [0, 1] }],
          },
        },
      },
    );
    const m = deriveFigureModel(s);
    expect(m.series).toHaveLength(1);
    expect(m.series[0].label).toBe("Both");
    expect(m.series[0].traceIndices).toEqual([0, 1]);
  });

  it("groups by legendgroup when traces carry it", () => {
    const s = spec([
      { type: "scatter", mode: "lines", line: { color: "#111" }, name: "x1", legendgroup: "G" },
      { type: "scatter", mode: "lines", line: { color: "#111" }, name: "x2", legendgroup: "G" },
      { type: "scatter", mode: "lines", line: { color: "#222" }, name: "y1", legendgroup: "H" },
    ]);
    const m = deriveFigureModel(s);
    expect(m.series).toHaveLength(2);
    expect(m.series[0].traceIndices).toEqual([0, 1]);
  });
});

// --- P3 primitives: scale bar + annotations --------------------------------------------

/** A spec carrying the trace-grid scale bar: vertical (amplitude) shape, horizontal (time)
 *  shape, two unit-label annotations, and the meta.selom hint pointing at their indices. */
function scalebarSpec(): SpecType {
  return spec(
    [{ type: "scatter", mode: "lines", line: { color: "#111" }, name: "t" }],
    {
      shapes: [
        { type: "line", xref: "paper", yref: "paper", x0: 0.05, x1: 0.05, y0: 0.02, y1: 0.12 }, // vertical
        { type: "line", xref: "paper", yref: "paper", x0: 0.05, x1: 0.15, y0: 0.02, y1: 0.02 }, // horizontal
      ],
      annotations: [
        { xref: "paper", yref: "paper", text: "200 µV", x: 0.044, y: 0.07 },
        { xref: "paper", yref: "paper", text: "100 ms", x: 0.1, y: 0.006 },
      ],
      meta: {
        selom: {
          figureKind: "trace_grid",
          primitives: [
            { kind: "scalebar", shapeIdx: [0, 1], annoIdx: [0, 1], xLen: 100, xUnit: "ms", yLen: 200, yUnit: "µV" },
          ],
        },
      },
    },
  );
}

describe("scale-bar primitive (P3 §3.5)", () => {
  it("derives an editable scale bar from the meta.selom hint", () => {
    const m = deriveFigureModel(scalebarSpec());
    expect(m.scalebar).not.toBeNull();
    expect(m.scalebar!.shapeIdx).toEqual([0, 1]);
    expect(m.scalebar!.yLen).toBe(200);
    expect(m.scalebar!.yUnit).toBe("µV");
    expect(m.scalebar!.visible).toBe(true);
    expect(m.capabilities.scalebar).toBe(true);
  });

  it("no scale bar without the hint (not index-editable)", () => {
    const m = deriveFigureModel(spec([{ type: "scatter", mode: "lines", line: { color: "#111" } }]));
    expect(m.scalebar).toBeNull();
  });

  it("show/hide toggles both shapes and both labels", () => {
    const m = deriveFigureModel(scalebarSpec());
    const ops = scalebarVisibilityOps(m.scalebar!, false);
    expect(ops).toContainEqual({ op: "add", path: "/layout/shapes/0/visible", value: false });
    expect(ops).toContainEqual({ op: "add", path: "/layout/shapes/1/visible", value: false });
    expect(ops).toContainEqual({ op: "add", path: "/layout/annotations/0/visible", value: false });
    expect(ops).toContainEqual({ op: "add", path: "/layout/annotations/1/visible", value: false });
  });

  it("resize rescales the bar proportionally, relabels it, and syncs meta", () => {
    const s = scalebarSpec();
    const m = deriveFigureModel(s);
    // Halve the amplitude: 200 → 100 µV. The vertical bar (paper length 0.10) halves to 0.05.
    const ops = scalebarResizeOps(s, m.scalebar!, "y", 100);
    expect(ops).toContainEqual({ op: "add", path: "/layout/shapes/0/y1", value: 0.07 }); // 0.02 + 0.05
    expect(ops).toContainEqual({ op: "add", path: "/layout/annotations/0/text", value: "100 µV" });
    expect(ops).toContainEqual({ op: "add", path: "/layout/meta/selom/primitives/0/yLen", value: 100 });
  });

  it("ignores a non-positive resize", () => {
    const s = scalebarSpec();
    const m = deriveFigureModel(s);
    expect(scalebarResizeOps(s, m.scalebar!, "y", 0)).toEqual([]);
  });
});

describe("annotations (P3 §3.5)", () => {
  it("lists annotations with text + visibility, and builds edit ops", () => {
    const items = annotationItems(scalebarSpec());
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ index: 0, text: "200 µV", visible: true });
    expect(annotationVisibilityOp(1, false)).toEqual({ op: "add", path: "/layout/annotations/1/visible", value: false });
    expect(annotationTextOp(0, "x")).toEqual({ op: "add", path: "/layout/annotations/0/text", value: "x" });
  });
});

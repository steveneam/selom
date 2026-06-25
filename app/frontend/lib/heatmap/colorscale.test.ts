import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure-spec";
import { applyPatches } from "@/lib/patch";

import {
  clampToExtent,
  heatmapTraceIndices,
  readTones,
  toneOps,
  zExtent,
} from "./colorscale";

/** A minimal heatmap spec (the skills/heatmap/run.py shape), optionally among other traces. */
function heatmapSpec(extra: Record<string, unknown> = {}): FigureSpec {
  return {
    data: [
      {
        type: "heatmap",
        z: [
          [0, 1, -2],
          [3, -1.5, 0.5],
        ],
        x: ["c0", "c1", "c2"],
        y: ["G1", "G2"],
        colorscale: "RdBu",
        reversescale: true,
        zmid: 0,
        ...extra,
      },
    ],
    layout: {},
  } as unknown as FigureSpec;
}

describe("heatmap colour-scale transforms", () => {
  it("zExtent finds the min/max over every finite z cell", () => {
    expect(zExtent(heatmapSpec())).toEqual({ min: -2, max: 3 });
    expect(zExtent({ data: [], layout: {} } as unknown as FigureSpec)).toBeNull(); // no heatmap → null
  });

  it("heatmapTraceIndices identifies heatmap traces by TYPE, not order", () => {
    const spec: FigureSpec = {
      data: [
        { type: "scatter", mode: "lines", x: [1], y: [1] }, // a dendrogram line trace, index 0
        { type: "heatmap", z: [[0, 1]] }, // index 1
      ],
      layout: {},
    } as unknown as FigureSpec;
    expect(heatmapTraceIndices(spec)).toEqual([1]);
    expect(heatmapTraceIndices(heatmapSpec())).toEqual([0]);
  });

  it("readTones falls back to the data extent for zmin/zmax and 0 for zmid", () => {
    expect(readTones(heatmapSpec())).toEqual({
      colorscale: "RdBu",
      reversed: true,
      zmid: 0,
      zmin: -2, // no zmin on the trace → data extent
      zmax: 3, // no zmax on the trace → data extent
    });
  });

  it("readTones reads explicit zmin/zmax/zmid when the trace pins them", () => {
    const t = readTones(heatmapSpec({ zmid: 0.5, zmin: -1, zmax: 1, reversescale: false }))!;
    expect(t).toMatchObject({ zmid: 0.5, zmin: -1, zmax: 1, reversed: false });
  });

  it("readTones is null-safe at the seam (null/undefined/garbage/heatmap-less → null, never throws)", () => {
    // Task B2: a pane reading tones off an unexpected spec must degrade to null, not crash.
    expect(readTones(null)).toBeNull();
    expect(readTones(undefined)).toBeNull();
    expect(readTones({} as unknown as FigureSpec)).toBeNull();
    expect(readTones({ data: "nope" } as unknown as FigureSpec)).toBeNull();
    expect(readTones({ data: [{ type: "scatter", x: [1], y: [1] }], layout: {} } as unknown as FigureSpec)).toBeNull();
  });

  it("toneOps writes the right leafs on every heatmap trace and round-trips", () => {
    const ops = toneOps([0], { zmid: 0.5, zmin: -1.5, zmax: 1.5 });
    expect(ops).toEqual([
      { op: "add", path: "/data/0/zmid", value: 0.5 },
      { op: "add", path: "/data/0/zmin", value: -1.5 },
      { op: "add", path: "/data/0/zmax", value: 1.5 },
    ]);
    const next = applyPatches(heatmapSpec(), ops);
    expect(readTones(next)).toMatchObject({ zmid: 0.5, zmin: -1.5, zmax: 1.5 });
  });

  it("toneOps maps `reversed` → reversescale and `colorscale` → colorscale, across two heatmaps", () => {
    const ops = toneOps([0, 2], { reversed: false, colorscale: "Viridis" });
    expect(ops).toEqual([
      { op: "add", path: "/data/0/colorscale", value: "Viridis" },
      { op: "add", path: "/data/0/reversescale", value: false },
      { op: "add", path: "/data/2/colorscale", value: "Viridis" },
      { op: "add", path: "/data/2/reversescale", value: false },
    ]);
  });

  it("re-applying the figure's own tones is idempotent (no visual change)", () => {
    const spec = heatmapSpec();
    const cur = readTones(spec)!;
    const next = applyPatches(spec, toneOps([0], { zmid: cur.zmid, zmin: cur.zmin, zmax: cur.zmax }));
    expect(readTones(next)).toEqual(cur);
  });

  it("clampToExtent keeps a value inside a slightly-padded extent", () => {
    const ext = { min: -2, max: 3 };
    expect(clampToExtent(0, ext)).toBe(0);
    expect(clampToExtent(99, ext)).toBeCloseTo(3.25, 5); // max + 5% pad
    expect(clampToExtent(-99, ext)).toBeCloseTo(-2.25, 5); // min − 5% pad
  });
});

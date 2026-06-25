import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure-spec";
import { applyPatches } from "@/lib/patch";

import {
  applyDendrogramTips,
  colTreeFraction,
  dendroLayoutOps,
  hasColTree,
  hasDendrogram,
  hasRowTree,
  leafKeyOf,
  leafStubs,
  maxDistance,
  rowTreeFraction,
  setColTreeOps,
  setLeafTipOps,
  setRowTreeOps,
  tipGap,
  tipLengthOps,
} from "./dendrogram";

/** A clustermap spec in the skills/heatmap shape — `cluster` selects which gutter axes exist. */
function clustermap(cluster: "none" | "row" | "column" | "both"): FigureSpec {
  const layout: Record<string, unknown> = {
    xaxis: { domain: cluster === "row" || cluster === "both" ? [0.16, 1] : [0, 1] },
    yaxis: { domain: cluster === "column" || cluster === "both" ? [0, 0.84] : [0, 1] },
  };
  if (cluster === "row" || cluster === "both") {
    layout.xaxis2 = { domain: [0, 0.14] };
    layout.yaxis2 = { domain: cluster === "both" ? [0, 0.84] : [0, 1] };
  }
  if (cluster === "column" || cluster === "both") {
    layout.xaxis3 = { domain: cluster === "both" ? [0.16, 1] : [0, 1] };
    layout.yaxis3 = { domain: [0.86, 1] };
  }
  return { data: [{ type: "heatmap", z: [[1]] }], layout } as unknown as FigureSpec;
}

describe("dendrogram presence + current fractions", () => {
  it("detects which trees are present", () => {
    expect(hasDendrogram(clustermap("none"))).toBe(false);
    expect(hasRowTree(clustermap("row"))).toBe(true);
    expect(hasColTree(clustermap("row"))).toBe(false);
    expect(hasColTree(clustermap("both"))).toBe(true);
  });

  it("reads the current gutter fractions from the domains (defaults to 0.16 when absent)", () => {
    expect(rowTreeFraction(clustermap("row"))).toBeCloseTo(0.16);
    expect(colTreeFraction(clustermap("column"))).toBeCloseTo(0.16);
    // no axis domain at all → the default
    const bare = { data: [], layout: {} } as unknown as FigureSpec;
    expect(rowTreeFraction(bare)).toBeCloseTo(0.16);
  });
});

describe("dendrogram resize is a coordinated, instant layout edit", () => {
  it("no-ops when there is no dendrogram", () => {
    expect(dendroLayoutOps(clustermap("none"), 0.3, 0.3)).toEqual([]);
  });

  it("widening the row tree re-flows the heatmap + the left gutter", () => {
    const spec = clustermap("row");
    const next = applyPatches(spec, setRowTreeOps(spec, 0.3));
    const L = next.layout as Record<string, { domain?: number[] }>;
    expect(L.xaxis.domain).toEqual([0.3, 1]); // heatmap starts later
    expect(L.xaxis2.domain).toEqual([0, 0.28]); // tree gutter grows (minus the 0.02 gap)
    expect(rowTreeFraction(next)).toBeCloseTo(0.3);
  });

  it("taller column tree re-flows the heatmap + the top gutter, keeping cross-domains aligned", () => {
    const spec = clustermap("both");
    const next = applyPatches(spec, setColTreeOps(spec, 0.25));
    const L = next.layout as Record<string, { domain?: number[] }>;
    expect(L.yaxis.domain).toEqual([0, 0.75]); // heatmap caps lower
    expect(L.yaxis3.domain).toEqual([0.77, 1]); // top gutter grows (plus the 0.02 gap)
    // the row tree's vertical span follows the heatmap, and the column tree's horizontal span the x
    expect(L.yaxis2.domain).toEqual([0, 0.75]);
    expect(L.xaxis3.domain).toEqual([0.16, 1]);
    // the OTHER tree's size is preserved
    expect(rowTreeFraction(next)).toBeCloseTo(0.16);
  });

  it("clamps out-of-range fractions into a sane band", () => {
    const spec = clustermap("row");
    const tiny = applyPatches(spec, setRowTreeOps(spec, 0.01));
    expect((tiny.layout as Record<string, { domain?: number[] }>).xaxis.domain![0]).toBeCloseTo(0.08);
    const huge = applyPatches(spec, setRowTreeOps(spec, 0.9));
    expect((huge.layout as Record<string, { domain?: number[] }>).xaxis.domain![0]).toBeCloseTo(0.45);
  });
});

// --- Leaf-tip length: meta-pref + render-time projection (dendrogram-tips-spec.md) -----------------

/**
 * A clustermap WITH dendrogram polyline traces, in the `skills/heatmap/run.py::_dendro_trace` shape.
 * Two leaves per tree, one merge. Col (top) tree: x = leaf positions, y = distances, leaves at y=0.
 * Row (left) tree: x = distances (axis reversed), y = leaf positions, leaves at x=0.
 */
function clustermapTrees(): FigureSpec {
  return {
    data: [
      { type: "heatmap", z: [[1, 2]] },
      // row tree (x2/y2): distance on x (reversed), position on y; leaves at x=0
      { type: "scatter", mode: "lines", x: [0, 2, 2, 0, null], y: [5, 5, 15, 15, null], xaxis: "x2", yaxis: "y2" },
      // col tree (x3/y3): position on x, distance on y; leaves at y=0
      { type: "scatter", mode: "lines", x: [5, 5, 15, 15, null], y: [0, 1, 1, 0, null], xaxis: "x3", yaxis: "y3" },
    ],
    layout: {
      xaxis: { domain: [0.16, 1] },
      yaxis: { domain: [0, 0.84] },
      xaxis2: { domain: [0, 0.14], range: [2.1, 0] },
      yaxis2: { domain: [0, 0.84] },
      xaxis3: { domain: [0.16, 1] },
      yaxis3: { domain: [0.86, 1], range: [0, 1.05] },
      meta: { selom: {} },
    },
  } as unknown as FigureSpec;
}

describe("leaf-tip detection", () => {
  it("rounds a position to a stable key", () => {
    expect(leafKeyOf(5)).toBe("5.00");
    expect(leafKeyOf(15.004)).toBe("15.00");
  });

  it("finds each tree's leaf stubs (position + first-merge distance)", () => {
    const spec = clustermapTrees();
    expect(leafStubs(spec, "col")).toEqual([
      { pos: 5, leafKey: "5.00", merge: 1 },
      { pos: 15, leafKey: "15.00", merge: 1 },
    ]);
    expect(leafStubs(spec, "row")).toEqual([
      { pos: 5, leafKey: "5.00", merge: 2 },
      { pos: 15, leafKey: "15.00", merge: 2 },
    ]);
    expect(maxDistance(spec, "col")).toBeCloseTo(1);
    expect(maxDistance(spec, "row")).toBeCloseTo(2);
  });
});

describe("applyDendrogramTips projection", () => {
  it("is identity (same object) when there is no pref", () => {
    const spec = clustermapTrees();
    expect(applyDendrogramTips(spec)).toBe(spec);
  });

  it("the uniform lever moves every leaf base out and widens the gutter range (col)", () => {
    const spec = applyPatches(clustermapTrees(), tipLengthOps(clustermapTrees(), "col", 0.4));
    const out = applyDendrogramTips(spec);
    const col = (out.data as Record<string, unknown[]>[])[2];
    expect(col.y).toEqual([-0.4, 1, 1, -0.4, null]); // leaf bases out to -gap; merge bar (1) untouched
    expect(col.x).toEqual([5, 5, 15, 15, null]); // positions untouched → shape preserved
    const L = out.layout as Record<string, { range?: number[] }>;
    expect(L.yaxis3.range).toEqual([-0.4, 1.05]); // gutter widened to fit, root top kept
    // the OTHER tree (row) has no pref → untouched
    expect((out.data as Record<string, unknown[]>[])[1].x).toEqual([0, 2, 2, 0, null]);
  });

  it("a per-leaf override adds on top of the lever and drives the widened range", () => {
    let spec = clustermapTrees();
    spec = applyPatches(spec, tipLengthOps(spec, "col", 0.4));
    spec = applyPatches(spec, setLeafTipOps(spec, "col", "5.00", 0.6));
    const out = applyDendrogramTips(spec);
    const col = (out.data as Record<string, unknown[]>[])[2];
    expect(col.y).toEqual([-1, 1, 1, -0.4, null]); // leaf 5 → -(0.4+0.6); leaf 15 → -0.4
    expect((out.layout as Record<string, { range?: number[] }>).yaxis3.range).toEqual([-1, 1.05]);
  });

  it("the row tree extends along its reversed distance axis", () => {
    const spec = applyPatches(clustermapTrees(), tipLengthOps(clustermapTrees(), "row", 0.5));
    const out = applyDendrogramTips(spec);
    const row = (out.data as Record<string, unknown[]>[])[1];
    expect(row.x).toEqual([-0.5, 2, 2, -0.5, null]); // leaf bases (x=0) out to -gap
    expect(row.y).toEqual([5, 5, 15, 15, null]); // positions untouched
    expect((out.layout as Record<string, { range?: number[] }>).xaxis2.range).toEqual([2.1, -0.5]);
  });

  it("gap=0 with no per-leaf tips is identity", () => {
    const spec = applyPatches(clustermapTrees(), tipLengthOps(clustermapTrees(), "col", 0));
    expect(applyDendrogramTips(spec)).toBe(spec);
  });
});

describe("tip ops write the right meta paths", () => {
  it("the lever sets the uniform gap and is read back", () => {
    const spec = applyPatches(clustermapTrees(), tipLengthOps(clustermapTrees(), "col", 0.4));
    expect(tipGap(spec, "col")).toBeCloseTo(0.4);
    expect(tipGap(spec, "row")).toBe(0);
  });

  it("setLeafTipOps adds an override, then clears it when extra <= 0", () => {
    let spec = clustermapTrees();
    spec = applyPatches(spec, setLeafTipOps(spec, "col", "5.00", 0.6));
    expect(
      (spec.layout as { meta: { selom: { dendrogramTips: { col: { tips: Record<string, number> } } } } })
        .meta.selom.dendrogramTips.col.tips["5.00"],
    ).toBeCloseTo(0.6);
    spec = applyPatches(spec, setLeafTipOps(spec, "col", "5.00", 0));
    expect(
      (spec.layout as { meta: { selom: { dendrogramTips: { col: { tips: Record<string, number> } } } } })
        .meta.selom.dendrogramTips.col.tips["5.00"],
    ).toBeUndefined();
  });

  it("setting a leaf override preserves an existing gap", () => {
    let spec = clustermapTrees();
    spec = applyPatches(spec, tipLengthOps(spec, "col", 0.4));
    spec = applyPatches(spec, setLeafTipOps(spec, "col", "15.00", 0.3));
    expect(tipGap(spec, "col")).toBeCloseTo(0.4);
  });
});

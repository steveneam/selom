import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure-spec";
import { applyPatches } from "@/lib/patch";

import {
  colTreeFraction,
  dendroLayoutOps,
  hasColTree,
  hasDendrogram,
  hasRowTree,
  rowTreeFraction,
  setColTreeOps,
  setRowTreeOps,
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

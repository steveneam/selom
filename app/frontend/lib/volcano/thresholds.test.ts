import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure-spec";

import {
  applyStagedThresholds,
  clampThresholds,
  gatherPoints,
  readThresholds,
  yCut,
} from "./thresholds";

/** A minimal volcano spec (the `_assemble` shape): 3 bucket traces + a labels trace + 3 lines. */
function volcanoSpec(): FigureSpec {
  const yc = yCut(0.05); // 1.30103…
  return {
    data: [
      { type: "scattergl", mode: "markers", name: "n.s.", x: [0.5, 2], y: [3, 0.5] },
      { type: "scattergl", mode: "markers", name: "up", x: [2], y: [3] },
      { type: "scattergl", mode: "markers", name: "down", x: [-2], y: [3] },
      { type: "scatter", mode: "text", name: "labels", x: [2], y: [3], text: ["GENEX"] },
    ],
    layout: {
      shapes: [
        { type: "line", x0: 1, x1: 1, yref: "paper", y0: 0, y1: 1 },
        { type: "line", x0: -1, x1: -1, yref: "paper", y0: 0, y1: 1 },
        { type: "line", xref: "paper", x0: 0, x1: 1, y0: yc, y1: yc },
      ],
    },
  };
}

const byName = (spec: FigureSpec, name: string) => spec.data.find((t) => t.name === name)!;

describe("volcano thresholds", () => {
  it("readThresholds round-trips fc + fdr from the line shapes", () => {
    const t = readThresholds(volcanoSpec());
    expect(t).not.toBeNull();
    expect(t!.fc).toBe(1);
    expect(t!.fdr).toBeCloseTo(0.05, 6);
  });

  it("gatherPoints returns the union of up/down/n.s. (labels excluded)", () => {
    const pts = gatherPoints(volcanoSpec());
    expect(pts).toHaveLength(4); // 2 ns + 1 up + 1 down, never the labels trace
  });

  it("re-buckets points by a looser FC + moves the FC lines, leaving labels untouched", () => {
    const { spec, readout } = applyStagedThresholds(volcanoSpec(), { fc: 0.4, fdr: 0.05 });
    // (0.5,3) now clears |0.4| and y_cut → up; (2,3) up; (-2,3) down; (2,0.5) below y_cut → ns.
    expect(readout).toEqual({ up: 2, down: 1, ns: 1 });
    expect([...(byName(spec, "up").x as number[])].sort((a, b) => a - b)).toEqual([0.5, 2]);
    expect(byName(spec, "down").x).toEqual([-2]);
    expect(byName(spec, "n.s.").x).toEqual([2]);
    // FC lines moved symmetrically to ±0.4; the labels trace is untouched (refreshes on re-run).
    const verticals = (spec.layout.shapes as { x0: number }[])
      .filter((s) => s.x0 === Math.abs(s.x0) || s.x0 < 0)
      .map((s) => s.x0)
      .filter((x) => x === 0.4 || x === -0.4);
    expect(verticals.sort()).toEqual([-0.4, 0.4]);
    expect(byName(spec, "labels").text).toEqual(["GENEX"]);
  });

  it("re-buckets by a tighter FDR (raises the y-cut)", () => {
    const { readout } = applyStagedThresholds(volcanoSpec(), { fc: 1, fdr: 0.001 }); // y_cut = 3
    // y≥3: (0.5,3),(2,3),(-2,3). up = x≥1&y≥3 → (2,3); down → (-2,3); ns = (0.5,3),(2,0.5).
    expect(readout).toEqual({ up: 1, down: 1, ns: 2 });
  });

  it("carries per-point customdata through a re-bucket (the gene-label substrate stays aligned)", () => {
    const spec: FigureSpec = {
      data: [
        { type: "scattergl", mode: "markers", name: "n.s.", x: [0.5], y: [3], customdata: [["NS1", 0.4]] },
        { type: "scattergl", mode: "markers", name: "up", x: [2], y: [3], customdata: [["UP1", 1e-5]] },
        { type: "scattergl", mode: "markers", name: "down", x: [-2], y: [3], customdata: [["DN1", 1e-4]] },
      ],
      layout: { shapes: volcanoSpec().layout.shapes },
    };
    // Loosen FC so the (0.5,3) n.s. point moves into "up": its customdata must move with it. Points
    // are re-gathered in up→down→n.s. order, so "up" ends up [UP1 (already up), NS1 (moved in)].
    const { spec: out } = applyStagedThresholds(spec, { fc: 0.4, fdr: 0.05 });
    const up = byName(out, "up");
    expect(up.x).toEqual([2, 0.5]);
    expect(up.customdata).toEqual([["UP1", 1e-5], ["NS1", 0.4]]); // re-partitioned alongside x/y
    expect((byName(out, "n.s.").customdata as unknown[])).toEqual([]); // emptied bucket, no stale rows
  });

  it("is idempotent — applying the same thresholds twice yields the same spec", () => {
    const once = applyStagedThresholds(volcanoSpec(), { fc: 0.4, fdr: 0.05 }).spec;
    const twice = applyStagedThresholds(once, { fc: 0.4, fdr: 0.05 }).spec;
    expect(twice.data).toEqual(once.data);
    expect(twice.layout.shapes).toEqual(once.layout.shapes);
  });

  it("clampThresholds enforces the param-spec bounds", () => {
    expect(clampThresholds({ fc: 10, fdr: 2 })).toEqual({ fc: 5, fdr: 1 });
    expect(clampThresholds({ fc: -3, fdr: 0.05 }).fc).toBe(3); // |fc| then clamp
    expect(clampThresholds({ fc: 1, fdr: 0 }).fdr).toBeGreaterThan(0); // never log10(0)
  });

  it("is a tolerant no-op on a non-volcano figure", () => {
    const umap: FigureSpec = {
      data: [{ type: "scattergl", mode: "markers", name: "cluster 1", x: [1], y: [2] }],
      layout: {},
    };
    expect(readThresholds(umap)).toBeNull();
    expect(gatherPoints(umap)).toHaveLength(0);
    const { spec, readout } = applyStagedThresholds(umap, { fc: 1, fdr: 0.05 });
    expect(spec).toBe(umap); // unchanged reference
    expect(readout).toEqual({ up: 0, down: 0, ns: 0 });
  });
});

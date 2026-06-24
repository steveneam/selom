import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure-spec";
import { applyPatches } from "@/lib/patch";

import {
  findPoint,
  gatherLabelablePoints,
  isLabeled,
  labelableGenes,
  labeledGenes,
  pointFromClick,
  toggleGeneLabelOps,
  toggleLabelOps,
} from "./labels";

/** A minimal volcano spec with per-point gene `customdata` (the volcano/run.py shape). */
function volcanoSpec(): FigureSpec {
  return {
    data: [
      { type: "scattergl", mode: "markers", name: "n.s.", x: [0.2], y: [0.5], customdata: [["NSG", 0.4]] },
      { type: "scattergl", mode: "markers", name: "up", x: [2, 3], y: [3, 4], customdata: [["FOO", 1e-5], ["BAR", 1e-8]] },
      { type: "scattergl", mode: "markers", name: "down", x: [-2], y: [3], customdata: [["BAZ", 1e-4]] },
      { type: "scatter", mode: "text", name: "labels", x: [3], y: [4], text: ["BAR"] },
    ],
    layout: {},
  };
}

describe("volcano gene labels", () => {
  it("gathers the union of up/down/n.s. points with their gene (labels trace excluded)", () => {
    const pts = gatherLabelablePoints(volcanoSpec());
    expect(pts).toHaveLength(4);
    expect(new Set(pts.map((p) => p.gene))).toEqual(new Set(["NSG", "FOO", "BAR", "BAZ"]));
  });

  it("labelableGenes is every gene with a plotted point", () => {
    expect(labelableGenes(volcanoSpec())).toEqual(new Set(["NSG", "FOO", "BAR", "BAZ"]));
  });

  it("findPoint resolves a gene's coordinates by symbol, or null", () => {
    expect(findPoint(volcanoSpec(), "FOO")).toEqual({ x: 2, y: 3, gene: "FOO" });
    expect(findPoint(volcanoSpec(), "NOPE")).toBeNull();
  });

  it("labeledGenes reads the currently-pinned genes from the annotations", () => {
    expect(labeledGenes(volcanoSpec())).toEqual(new Set()); // no annotations yet
    const withAnno: FigureSpec = {
      ...volcanoSpec(),
      layout: { annotations: [{ x: 2, y: 3, text: "FOO" }] },
    };
    expect(labeledGenes(withAnno)).toEqual(new Set(["FOO"]));
    expect(isLabeled(withAnno, "FOO")).toBe(true);
    expect(isLabeled(withAnno, "BAR")).toBe(false);
  });

  it("toggleLabelOps adds a label on the first point (sets the whole array), then removes it", () => {
    const spec = volcanoSpec();
    const point = findPoint(spec, "FOO")!;
    const addOps = toggleLabelOps(spec, point);
    expect(addOps).toEqual([expect.objectContaining({ op: "add", path: "/layout/annotations" })]);
    const added = applyPatches(spec, addOps);
    expect(labeledGenes(added)).toEqual(new Set(["FOO"]));
    // Toggling the same gene again removes its annotation.
    const removeOps = toggleLabelOps(added, point);
    expect(removeOps).toEqual([{ op: "remove", path: "/layout/annotations/0" }]);
    const removed = applyPatches(added, removeOps);
    expect(labeledGenes(removed)).toEqual(new Set());
  });

  it("appends a second label with `/-` (keeps the first)", () => {
    let spec = volcanoSpec();
    spec = applyPatches(spec, toggleLabelOps(spec, findPoint(spec, "FOO")!));
    const ops = toggleLabelOps(spec, findPoint(spec, "BAR")!);
    expect(ops).toEqual([expect.objectContaining({ op: "add", path: "/layout/annotations/-" })]);
    const both = applyPatches(spec, ops);
    expect(labeledGenes(both)).toEqual(new Set(["FOO", "BAR"]));
  });

  it("toggleGeneLabelOps (by name) round-trips, and is a no-op for an unplotted gene", () => {
    let spec = volcanoSpec();
    spec = applyPatches(spec, toggleGeneLabelOps(spec, "BAZ"));
    expect(labeledGenes(spec)).toEqual(new Set(["BAZ"]));
    spec = applyPatches(spec, toggleGeneLabelOps(spec, "BAZ"));
    expect(labeledGenes(spec)).toEqual(new Set());
    expect(toggleGeneLabelOps(spec, "GHOST")).toEqual([]); // not plotted → nothing to anchor
  });

  it("pointFromClick extracts the gene + coords from a Plotly click point", () => {
    expect(pointFromClick({ x: 2, y: 3, customdata: ["FOO", 1e-5] })).toEqual({ x: 2, y: 3, gene: "FOO" });
    expect(pointFromClick({ x: 1, y: 1 })).toBeNull(); // no customdata → not labellable
    expect(pointFromClick(undefined)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";

import type { FigureSpec } from "@/lib/figure/figure-spec";
import { applyPatches } from "@/lib/figure/patch";

import {
  captureLabels,
  carryLabels,
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

  describe("persistence across a re-run (captureLabels + carryLabels)", () => {
    it("captureLabels returns the user's gene-label annotations (full objects), skipping non-gene ones", () => {
      const spec: FigureSpec = {
        ...volcanoSpec(),
        layout: { annotations: [{ x: 2, y: 3, text: "FOO", ay: -40 }, { x: 0, y: 0, text: "" }, { x: 1, y: 1 }] },
      };
      const captured = captureLabels(spec);
      expect(captured).toEqual([{ x: 2, y: 3, text: "FOO", ay: -40 }]); // drops the empty + text-less entries
    });

    it("carryLabels re-anchors a labelled gene onto a fresh re-run spec, keeping its drag offset + text", () => {
      const prev = captureLabels({ ...volcanoSpec(), layout: { annotations: [{ x: 2, y: 3, text: "FOO", ay: -40 }] } });
      // The re-run produced a fresh spec (no annotations) where FOO sits at slightly new coords.
      const fresh: FigureSpec = {
        data: [{ type: "scattergl", mode: "markers", name: "up", x: [2.5], y: [3.5], customdata: [["FOO", 1e-6]] }],
        layout: {},
      };
      const carried = carryLabels(fresh, prev);
      expect(labeledGenes(carried)).toEqual(new Set(["FOO"]));
      expect((carried.layout!.annotations as Record<string, unknown>[])[0]).toEqual({
        x: 2.5, // re-anchored to the gene's current point
        y: 3.5,
        text: "FOO",
        ay: -40, // user's drag offset preserved
      });
    });

    it("carryLabels drops a label whose gene is no longer plotted, and is a no-op on a non-volcano spec", () => {
      const prev = captureLabels({ ...volcanoSpec(), layout: { annotations: [{ x: 9, y: 9, text: "GONE" }] } });
      expect(carryLabels(volcanoSpec(), prev)).toEqual(volcanoSpec()); // GONE not plotted → nothing carried
      // No gene customdata anywhere → no labellable points → carry is a no-op.
      const plain: FigureSpec = { data: [{ type: "heatmap", z: [[1]] }], layout: {} };
      expect(carryLabels(plain, prev)).toBe(plain);
      expect(carryLabels(volcanoSpec(), [])).toEqual(volcanoSpec()); // empty prev → unchanged
    });

    it("carryLabels skips a gene the fresh spec already labels (no duplicate annotation)", () => {
      const prev = captureLabels({ ...volcanoSpec(), layout: { annotations: [{ x: 2, y: 3, text: "FOO" }] } });
      const fresh: FigureSpec = { ...volcanoSpec(), layout: { annotations: [{ x: 2, y: 3, text: "FOO" }] } };
      const carried = carryLabels(fresh, prev);
      expect((carried.layout!.annotations as unknown[]).length).toBe(1); // not doubled
    });
  });
});

describe("gene labels vs the Selom annotation layer (milestone review blocker A3)", () => {
  const point = { x: 1.2, y: 4.5, gene: "RPGRIP1" };
  const selomTextLabel = {
    text: "RPGRIP1",
    x: 0.02,
    y: 0.98,
    xref: "paper",
    yref: "paper",
    selom: { kind: "textLabel", id: "sel-1" },
  };

  it("does not report a gene as labelled because a hand-placed annotation shares its text", () => {
    const spec = { data: [], layout: { annotations: [selomTextLabel] } } as unknown as FigureSpec;
    expect(isLabeled(spec, "RPGRIP1")).toBe(false);
    expect(labeledGenes(spec).has("RPGRIP1")).toBe(false);
  });

  it("ADDS a gene label rather than removing the user's annotation of the same text", () => {
    const spec = { data: [], layout: { annotations: [selomTextLabel] } } as unknown as FigureSpec;
    const ops = toggleLabelOps(spec, point);
    expect(ops).toHaveLength(1);
    expect(ops[0].op).toBe("add"); // append, NOT a remove of index 0
    expect(ops[0].path).toBe("/layout/annotations/-");
  });

  it("removes the real gene label at its TRUE index when a Selom item precedes it", () => {
    const geneLabel = { text: "RPGRIP1", x: 1.2, y: 4.5 };
    const spec = {
      data: [],
      layout: { annotations: [selomTextLabel, geneLabel] },
    } as unknown as FigureSpec;
    const ops = toggleLabelOps(spec, point);
    expect(ops).toEqual([{ op: "remove", path: "/layout/annotations/1" }]);
  });

  it("does not carry a Selom annotation across a re-run as if it were a gene label", () => {
    const spec = { data: [], layout: { annotations: [selomTextLabel] } } as unknown as FigureSpec;
    expect(captureLabels(spec)).toEqual([]);
  });
});

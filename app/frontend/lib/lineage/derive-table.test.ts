import { describe, expect, it } from "vitest";
import { deriveTable } from "./derive-table";
import type { FigureSpec } from "@/lib/figure/figure-spec";

describe("deriveTable (FE fallback, D3)", () => {
  it("derives [label, value] from a labelled bar trace, using the axis titles as headers", () => {
    const spec: FigureSpec = {
      data: [{ type: "bar", orientation: "h", x: [2, -1, 3], y: ["CD3D", "LYZ", "NKG7"] }],
      layout: { xaxis: { title: { text: "log2 fold-change" } }, yaxis: { title: { text: "gene" } } },
    };
    const t = deriveTable(spec)!;
    expect(t.columns).toEqual(["gene", "log2 fold-change"]);
    expect(t.rows).toEqual([
      ["CD3D", 2],
      ["LYZ", -1],
      ["NKG7", 3],
    ]);
  });

  it("returns null for a purely-numeric scatter (no tabular shape → node omitted)", () => {
    const spec: FigureSpec = { data: [{ type: "scattergl", x: [1, 2], y: [3, 4] }], layout: {} };
    expect(deriveTable(spec)).toBeNull();
  });

  it("returns null for an empty or missing spec", () => {
    expect(deriveTable(null)).toBeNull();
    expect(deriveTable(undefined)).toBeNull();
    expect(deriveTable({ data: [], layout: {} })).toBeNull();
  });

  it("falls back to generic headers when axis titles are absent", () => {
    const spec: FigureSpec = { data: [{ x: [1], y: ["A"] }], layout: {} };
    expect(deriveTable(spec)!.columns).toEqual(["label", "value"]);
  });
});

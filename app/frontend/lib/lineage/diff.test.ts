import { describe, expect, it } from "vitest";
import { changedParams, diffParams, diffTables } from "./diff";
import type { StatsTable } from "@/lib/skills-api";

describe("diffParams", () => {
  it("reports same / changed / added / removed per key, sorted + order-independent", () => {
    const a = { resolution: 0.5, normalize: true, only_a: "x" };
    const b = { normalize: true, resolution: 1.0, only_b: 9 };
    const d = diffParams(a, b);
    expect(d.map((x) => x.key)).toEqual(["normalize", "only_a", "only_b", "resolution"]); // sorted
    const by = Object.fromEntries(d.map((x) => [x.key, x.status]));
    expect(by).toEqual({ normalize: "same", only_a: "removed", only_b: "added", resolution: "changed" });
    const res = d.find((x) => x.key === "resolution")!;
    expect(res.a).toBe(0.5);
    expect(res.b).toBe(1.0);
  });

  it("treats undefined maps as empty", () => {
    expect(diffParams(undefined, { a: 1 })).toEqual([{ key: "a", a: undefined, b: 1, status: "added" }]);
    expect(diffParams({ a: 1 }, undefined)).toEqual([{ key: "a", a: 1, b: undefined, status: "removed" }]);
    expect(diffParams(undefined, undefined)).toEqual([]);
  });

  it("changedParams drops the unchanged keys", () => {
    const d = diffParams({ a: 1, b: 2 }, { a: 1, b: 3 });
    expect(changedParams(d).map((x) => x.key)).toEqual(["b"]);
  });
});

const TA: StatsTable = {
  columns: ["gene", "log2FC", "padj"],
  rows: [
    ["RHO", 3.2, 0.001],
    ["PDE6B", -2.1, 0.01],
    ["NRL", 1.0, 0.2],
  ],
  title: "DE",
};

describe("diffTables", () => {
  it("aligns rows on the first column and classifies them", () => {
    const TB: StatsTable = {
      columns: ["gene", "log2FC", "padj"],
      rows: [
        ["RHO", 3.2, 0.001], // same
        ["PDE6B", -2.6, 0.005], // changed (both cells differ)
        ["GNAT1", 2.4, 0.02], // added (only in B)
        // NRL dropped → removed
      ],
      title: "DE",
    };
    const diff = diffTables(TA, TB)!;
    expect(diff.keyColumn).toBe("gene");
    const by = Object.fromEntries(diff.rows.map((r) => [r.key, r.status]));
    expect(by).toEqual({ RHO: "same", PDE6B: "changed", GNAT1: "added", NRL: "removed" });
    expect(diff.added).toBe(1);
    expect(diff.removed).toBe(1);
    expect(diff.changed).toBe(1);
    // The changed row marks which cells diverged.
    const pde = diff.rows.find((r) => r.key === "PDE6B")!;
    const cellStatus = Object.fromEntries(pde.cells.map((c) => [c.column, c.status]));
    expect(cellStatus).toEqual({ gene: "same", log2FC: "changed", padj: "changed" });
  });

  it("unions columns B-major, appending A-only columns", () => {
    const A: StatsTable = { columns: ["k", "x"], rows: [["a", 1]] };
    const B: StatsTable = { columns: ["k", "y"], rows: [["a", 2]] };
    const diff = diffTables(A, B)!;
    expect(diff.columns).toEqual(["k", "y", "x"]);
  });

  it("models cluster-count growth as added rows (the sweep demo)", () => {
    // resolution 0.5 → 3 clusters; 1.0 → 5 clusters.
    const lo: StatsTable = { columns: ["cluster", "cells"], rows: [["0", 900], ["1", 600], ["2", 300]] };
    const hi: StatsTable = {
      columns: ["cluster", "cells"],
      rows: [["0", 700], ["1", 500], ["2", 300], ["3", 250], ["4", 150]],
    };
    const diff = diffTables(lo, hi)!;
    expect(diff.added).toBe(2); // clusters 3 + 4 are new
    expect(diff.removed).toBe(0);
    expect(diff.changed).toBe(2); // clusters 0 + 1 lost cells to the new ones
  });

  it("returns null only when neither table exists; one-sided = all added/removed", () => {
    expect(diffTables(null, undefined)).toBeNull();
    expect(diffTables(null, TA)!.added).toBe(3);
    expect(diffTables(TA, null)!.removed).toBe(3);
  });
});

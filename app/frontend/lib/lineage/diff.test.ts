import { describe, expect, it } from "vitest";
import { changedParams, diffParams, diffTables, pairTableDiffs } from "./diff";
import type { StatsTable } from "@/lib/skills/api";

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

describe("pairTableDiffs", () => {
  // The two-table shape this milestone made real: a ranked/detail table plus a scalar or pairwise
  // one. `lollipop`, `boxplot`, `confusion` and `qq` all ship it.
  const ranked: StatsTable = {
    columns: ["rank", "arm", "median"],
    rows: [[1, "WT", 412.5], [2, "KO", 268.9]],
    title: "Ranked values",
  };
  const pairsA: StatsTable = {
    columns: ["group A", "group B", "p"],
    rows: [["WT", "KO", 0.031]],
    title: "Pairwise comparisons",
  };
  const pairsB: StatsTable = { ...pairsA, rows: [["WT", "KO", 0.0093]] };

  it("⚑ diffs the SECOND table — the regression that shipped for a whole milestone", () => {
    // Compare read `figureTables(x)[0]`, so a re-run that changed only the p-values (correction
    // none → BH) reported "The results tables are identical". Table 0 is byte-identical here; every
    // difference between these two versions lives in table 1.
    const paired = pairTableDiffs([ranked, pairsA], [ranked, pairsB]);
    expect(paired).toHaveLength(2);
    expect(paired[0].diff.changed, "the ranked table really is unchanged").toBe(0);
    expect(paired[1].diff.changed, "the p-value change must survive into the diff").toBeGreaterThan(0);
  });

  it("labels each pair with the table's own title, so a stack of cards is readable", () => {
    expect(pairTableDiffs([ranked, pairsA], [ranked, pairsB]).map((p) => p.title)).toEqual([
      "Ranked values",
      "Pairwise comparisons",
    ]);
  });

  it("falls back to a generic title only when neither side named the table", () => {
    const untitled: StatsTable = { columns: ["a"], rows: [["x"]] };
    expect(pairTableDiffs([untitled], [untitled])[0].title).toBe("Results table");
  });

  it("keeps a table that exists on ONE side — an added or removed table is a real difference", () => {
    // A parameter change can make a second table appear (setting `pairs=`). Dropping it because the
    // baseline has no counterpart would hide exactly the change the user is comparing to find.
    const added = pairTableDiffs([ranked], [ranked, pairsB]);
    expect(added).toHaveLength(2);
    expect(added[1].title).toBe("Pairwise comparisons");
    expect(added[1].diff.added).toBeGreaterThan(0);

    const removed = pairTableDiffs([ranked, pairsA], [ranked]);
    expect(removed).toHaveLength(2);
    expect(removed[1].diff.removed).toBeGreaterThan(0);
  });

  it("is empty when neither version has a table — the view says so rather than rendering a shell", () => {
    expect(pairTableDiffs([], [])).toEqual([]);
  });
});

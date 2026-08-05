import { describe, expect, it } from "vitest";

import { asTables } from "./stats-tables";
import { figureTables } from "@/lib/lineage/figure-table";
import type { Figure } from "@/lib/projects/types";
import type { StatsTable } from "@/lib/skills/api";
import { mockTable } from "@/mocks/stub-bundle";

/**
 * The frontend half of the multi-table contract (docs/stats-tables/spec.md D1) — the ONE place the
 * `StatsTable | StatsTable[] | null` union is narrowed. Its backend twin is `skills/_table.py`
 * `as_tables`; the "only one narrowing site" ratchet lives in `lib/structure.guard.test.ts`.
 */
const T1: StatsTable = { columns: ["arm", "median"], rows: [["WT", 12]], title: "Ranked values" };
const T2: StatsTable = { columns: ["pair", "p"], rows: [["WT vs KO", 0.004]], title: "Pairwise p-values" };

describe("asTables", () => {
  it("maps the three wire cases onto an array", () => {
    expect(asTables(null)).toEqual([]);
    expect(asTables(undefined)).toEqual([]);
    expect(asTables(T1)).toEqual([T1]);
    expect(asTables([T1, T2])).toEqual([T1, T2]);
  });

  it("treats an empty list exactly as null — no table is no table", () => {
    // The FE twin of the backend's L3-gate hazard: `[]` must never read as "a table exists".
    expect(asTables([])).toEqual([]);
    expect(asTables([]).length).toBe(asTables(null).length);
  });

  it("returns the same array instance for a list (no defensive copy to drift from)", () => {
    const list = [T1, T2];
    expect(asTables(list)).toBe(list);
  });
});

describe("figureTables", () => {
  const fig = (over: Partial<Figure>): Figure =>
    ({ id: "f1", projectId: "p1", title: "F", createdAt: 0, ...over }) as Figure;

  it("G3 — a single stored table yields exactly one, unchanged", () => {
    expect(figureTables(fig({ table: T1 }))).toEqual([T1]);
  });

  it("yields every stored table, in array order", () => {
    expect(figureTables(fig({ table: [T1, T2] }))).toEqual([T1, T2]);
  });

  it("falls back to the spec-derived table only when none is stored (D3)", () => {
    const spec = { data: [{ y: ["a", "b"], x: [1, 2] }], layout: {} } as Figure["spec"];
    expect(figureTables(fig({ spec }))).toHaveLength(1);
    // A stored table wins over the fallback — the fallback is fill-when-absent, not an addition.
    expect(figureTables(fig({ table: [T1, T2], spec }))).toEqual([T1, T2]);
  });

  it("is empty when there is nothing substantive — the Statistics node is omitted, not shown empty", () => {
    expect(figureTables(fig({}))).toEqual([]);
    expect(figureTables(fig({ table: [] }))).toEqual([]);
    expect(figureTables(fig({ spec: { data: [], layout: {} } }))).toEqual([]);
  });
});

describe("the dev:mock fixture mirrors the multi-table contract", () => {
  // A mock that only ever returns one table proves the shape that already worked
  // [[mock-must-mirror-backend-contract]]. `lollipop` is D4's rank 1 — it computes ranked values
  // AND, when `pairs=` is set, the p-values behind the stars it draws, and today discards one.
  it("returns two titled tables for lollipop with pairs= set, one without", () => {
    const single = asTables(mockTable("lollipop", {}));
    expect(single).toHaveLength(1);
    expect(single[0].title).toBe("Ranked values");

    const both = asTables(mockTable("lollipop", { pairs: "WT Control,CMV-GFP" }));
    expect(both).toHaveLength(2);
    // G4's frontend mirror: stacked panels are told apart by their titles, so every one must have
    // a real title — the backend twin is `validate_result_table`'s `untitled_table`.
    expect(both.every((t) => (t.title ?? "").trim().length > 0)).toBe(true);
    expect(both.map((t) => t.title)).toEqual(["Ranked values", "Pairwise p-values"]);
    // Array order is the runner's and carries meaning (D4): the ranked values are primary, and the
    // pairwise table is the provenance of marks already drawn on the figure.
    expect(both[1].columns).toContain("adjusted p");
  });

  it("every mocked table is well-formed — rectangular rows under real columns", () => {
    for (const id of ["umap_scrna", "deg", "volcano", "pca", "composition", "enrichment", "lollipop"]) {
      for (const t of asTables(mockTable(id, { pairs: "a,b" }))) {
        expect(t.columns.length, `${id} has columns`).toBeGreaterThan(0);
        for (const row of t.rows) expect(row, `${id} row width`).toHaveLength(t.columns.length);
      }
    }
  });
});

import { describe, expect, it } from "vitest";

import { asTables } from "./stats-tables";
import { figureTables } from "@/lib/lineage/figure-table";
import type { Figure } from "@/lib/projects/types";
import type { StatsTable } from "@/lib/skills/api";

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

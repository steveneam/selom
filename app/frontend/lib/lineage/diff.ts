/**
 * Version diff (Pillar 1 — liveness & lineage, S3). Pure functions that power the
 * compare view: a per-key **params diff** and a row-aligned **Statistics-table diff**.
 * No React, no storage — just data in, deltas out, so the logic is unit-testable and
 * the compare surface is a thin renderer over it.
 */
import type { StatsTable } from "@/lib/skills/api";

export type ParamValue = string | number | boolean;

/** added = only in B · removed = only in A · changed = both but differ · same = equal. */
export type DeltaStatus = "added" | "removed" | "changed" | "same";

export interface ParamDelta {
  key: string;
  a?: ParamValue;
  b?: ParamValue;
  status: DeltaStatus;
}

/**
 * Diff two param maps key-by-key (keys sorted for a stable, order-independent result).
 * `a` is the baseline (version A), `b` the comparison (version B).
 */
export function diffParams(
  a: Record<string, ParamValue> | undefined,
  b: Record<string, ParamValue> | undefined,
): ParamDelta[] {
  const av = a ?? {};
  const bv = b ?? {};
  const keys = Array.from(new Set([...Object.keys(av), ...Object.keys(bv)])).sort();
  return keys.map((key) => {
    const inA = Object.prototype.hasOwnProperty.call(av, key);
    const inB = Object.prototype.hasOwnProperty.call(bv, key);
    let status: DeltaStatus;
    if (inA && !inB) status = "removed";
    else if (!inA && inB) status = "added";
    else status = av[key] === bv[key] ? "same" : "changed";
    return { key, a: inA ? av[key] : undefined, b: inB ? bv[key] : undefined, status };
  });
}

/** Only the params that actually differ (the compare view's headline). */
export function changedParams(deltas: ParamDelta[]): ParamDelta[] {
  return deltas.filter((d) => d.status !== "same");
}

export type Cell = string | number;

export interface CellDelta {
  column: string;
  a?: Cell;
  b?: Cell;
  /** same · changed · added (column only in B) · removed (column only in A). */
  status: DeltaStatus;
}

export interface RowDelta {
  /** The first-column value the two tables are aligned on. */
  key: string;
  status: DeltaStatus;
  cells: CellDelta[];
}

export interface TableDiff {
  /** The column the rows are aligned on (B's first column, else A's). */
  keyColumn: string;
  /** Union of columns, B-major then any A-only columns appended. */
  columns: string[];
  rows: RowDelta[];
  added: number;
  removed: number;
  changed: number;
}

function emptyLike(t: StatsTable): StatsTable {
  return { columns: t.columns, rows: [], title: t.title };
}

/** Index a table's rows by their first-column value (last wins on a duplicate key). */
function indexRows(t: StatsTable): Map<string, Cell[]> {
  const m = new Map<string, Cell[]>();
  for (const r of t.rows) m.set(String(r[0]), r);
  return m;
}

function cellOf(t: StatsTable, row: Cell[], col: string): Cell | undefined {
  const i = t.columns.indexOf(col);
  return i >= 0 ? row[i] : undefined;
}

/**
 * Diff two Statistics tables by aligning rows on the first column (the key/label).
 * Reports per-row status (added/removed/changed/same) and, for changed rows, which
 * cells diverged. Columns are unioned (B-major). Returns null when neither table
 * exists; a one-sided table is diffed against an empty one (all added / all removed).
 */
export function diffTables(
  a: StatsTable | null | undefined,
  b: StatsTable | null | undefined,
): TableDiff | null {
  if (!a && !b) return null;
  const A = a ?? emptyLike(b!);
  const B = b ?? emptyLike(a!);

  const keyColumn = B.columns[0] ?? A.columns[0] ?? "key";
  const columns = [...B.columns];
  for (const c of A.columns) if (!columns.includes(c)) columns.push(c);

  const aRows = indexRows(A);
  const bRows = indexRows(B);
  // Keys in B order first (the "current" version), then A-only keys in A order.
  const keys: string[] = [];
  const seen = new Set<string>();
  for (const r of B.rows) {
    const k = String(r[0]);
    if (!seen.has(k)) { seen.add(k); keys.push(k); }
  }
  for (const r of A.rows) {
    const k = String(r[0]);
    if (!seen.has(k)) { seen.add(k); keys.push(k); }
  }

  let added = 0, removed = 0, changed = 0;
  const rows: RowDelta[] = keys.map((key) => {
    const ar = aRows.get(key);
    const br = bRows.get(key);
    const inA = ar !== undefined;
    const inB = br !== undefined;
    const cells: CellDelta[] = columns.map((col) => {
      const av = inA ? cellOf(A, ar!, col) : undefined;
      const bv = inB ? cellOf(B, br!, col) : undefined;
      let status: DeltaStatus;
      if (!inA && inB) status = "added";
      else if (inA && !inB) status = "removed";
      else status = av === bv ? "same" : "changed";
      return { column: col, a: av, b: bv, status };
    });
    let status: DeltaStatus;
    if (!inA && inB) { status = "added"; added++; }
    else if (inA && !inB) { status = "removed"; removed++; }
    else if (cells.some((c) => c.status === "changed")) { status = "changed"; changed++; }
    else status = "same";
    return { key, status, cells };
  });

  return { keyColumn, columns, rows, added, removed, changed };
}

/** One table's diff, plus the title the compare surface labels it with. */
export interface PairedTableDiff {
  /** Index in both runners' arrays — the pairing key (D4: array order carries meaning). */
  index: number;
  title: string;
  diff: TableDiff;
}

/**
 * Pair two runs' table arrays BY INDEX and diff every pair — the multi-table half of compare.
 *
 * `diffTables` compares one table against one table, so someone has to decide which goes with
 * which. That decision is spec D4's: array order is the runner's and carries meaning, so index i on
 * one side is the same result as index i on the other (`lollipop`'s ranked values against its
 * ranked values, its pairwise p-values against its pairwise p-values).
 *
 * ⚑ It lives here, not inline in the view, because the version that lived inline read `[0]` and
 * nobody could test it. Compare diffed one table for a whole milestone while its card announced
 * "The results tables are identical" — so two versions differing only in Cohen's κ, or only in the
 * p-values behind their drawn stars, reported themselves identical. A pure function is the home
 * where that claim can be pinned.
 */
export function pairTableDiffs(a: StatsTable[], b: StatsTable[]): PairedTableDiff[] {
  const out: PairedTableDiff[] = [];
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const diff = diffTables(a[i], b[i]);
    // `diffTables` returns null only when NEITHER side has a table at this index, which cannot
    // happen inside the loop bound — but a table added or removed between versions is a real
    // asymmetry, and it must yield a diff rather than be dropped.
    if (diff) out.push({ index: i, title: a[i]?.title ?? b[i]?.title ?? "Results table", diff });
  }
  return out;
}

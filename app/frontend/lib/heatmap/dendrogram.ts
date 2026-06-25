/**
 * Heatmap dendrogram layout sizing (owner request 2026-06-25) — adjust how much room the row /
 * column clustering trees get, so the branch connections read as clearly as the scientist likes.
 *
 * Pure + framework-free (node-env unit-tested). Every edit here is INSTANT + COSMETIC: it only
 * re-proportions the tree-gutter vs heatmap axis DOMAINS — a layout edit, so the patch classifier
 * treats it as client-side and it rides the figure store's undo. No data / clustering change, no
 * re-run. The dendrogram polylines live on their own gutter axes (`x2`/`y2` row, `x3`/`y3` column),
 * so a larger domain simply draws the same tree bigger / more spread — clearer connections.
 *
 * The geometry mirrors the backend (`skills/heatmap/run.py::heatmap_spec`): a row tree owns a LEFT
 * gutter `[0, rowFrac - GAP]` and pushes the heatmap to start at x=`rowFrac`; a column tree owns a
 * TOP gutter `[1 - colFrac + GAP, 1]` and caps the heatmap at y=`1 - colFrac`. Resizing one tree
 * re-flows the shared cross-domain of the other, so both stay aligned to the heatmap.
 */

import type { FigureSpec, PlotlyTrace } from "@/lib/figure-spec";
import { getAt, set, type Operation } from "@/lib/patch";

/** Breathing room between a tree gutter and the heatmap (matches the backend's 0.16 vs 0.14). */
const GAP = 0.02;
/** The default gutter fraction the backend ships (heatmap starts at 0.16 / ends at 0.84). */
export const DEFAULT_FRACTION = 0.16;
const MIN_FRACTION = 0.08;
const MAX_FRACTION = 0.45;

function layoutObj(spec: FigureSpec | null | undefined): Record<string, unknown> {
  const l = spec?.layout;
  return l && typeof l === "object" ? (l as Record<string, unknown>) : {};
}

function domainOf(spec: FigureSpec | null | undefined, axis: string): number[] | null {
  const d = (layoutObj(spec)[axis] as { domain?: unknown } | undefined)?.domain;
  return Array.isArray(d) && d.length === 2 && d.every((v) => typeof v === "number")
    ? (d as number[])
    : null;
}

/** A row dendrogram is present (it owns the left gutter, `xaxis2`). */
export function hasRowTree(spec: FigureSpec | null | undefined): boolean {
  return !!layoutObj(spec).xaxis2;
}

/** A column dendrogram is present (it owns the top gutter, `yaxis3`). */
export function hasColTree(spec: FigureSpec | null | undefined): boolean {
  return !!layoutObj(spec).yaxis3;
}

/** Either tree present → the Dendrogram styling controls apply. */
export function hasDendrogram(spec: FigureSpec | null | undefined): boolean {
  return hasRowTree(spec) || hasColTree(spec);
}

/** Current row-tree width fraction (the heatmap's x-domain start), or the default. */
export function rowTreeFraction(spec: FigureSpec | null | undefined): number {
  const d = domainOf(spec, "xaxis");
  return d ? d[0] : DEFAULT_FRACTION;
}

/** Current column-tree height fraction (1 − the heatmap's y-domain end), or the default. */
export function colTreeFraction(spec: FigureSpec | null | undefined): number {
  const d = domainOf(spec, "yaxis");
  return d ? 1 - d[1] : DEFAULT_FRACTION;
}

function clampFrac(v: number): number {
  if (!Number.isFinite(v)) return DEFAULT_FRACTION;
  return Math.min(MAX_FRACTION, Math.max(MIN_FRACTION, v));
}

function round4(v: number): number {
  return Math.round(v * 1e4) / 1e4;
}

/**
 * Recompute every coordinated axis domain from the two gutter fractions + which trees are present.
 * Pure → the caller commits the ops to the figure store (instant, undoable). Returns `[]` when no
 * dendrogram is present (nothing to size).
 */
export function dendroLayoutOps(
  spec: FigureSpec,
  rowFrac: number,
  colFrac: number,
): Operation[] {
  const hasRow = hasRowTree(spec);
  const hasCol = hasColTree(spec);
  if (!hasRow && !hasCol) return [];
  const rf = clampFrac(rowFrac);
  const cf = clampFrac(colFrac);
  const xStart = hasRow ? rf : 0;
  const yEnd = hasCol ? 1 - cf : 1;
  const ops: Operation[] = [
    set("/layout/xaxis/domain", [round4(xStart), 1]),
    set("/layout/yaxis/domain", [0, round4(yEnd)]),
  ];
  if (hasRow) {
    ops.push(set("/layout/xaxis2/domain", [0, round4(rf - GAP)]));
    ops.push(set("/layout/yaxis2/domain", [0, round4(yEnd)]));
  }
  if (hasCol) {
    ops.push(set("/layout/yaxis3/domain", [round4(yEnd + GAP), 1]));
    ops.push(set("/layout/xaxis3/domain", [round4(xStart), 1]));
  }
  return ops;
}

/** Resize just the row tree (keeping the current column-tree size). */
export function setRowTreeOps(spec: FigureSpec, fraction: number): Operation[] {
  return dendroLayoutOps(spec, fraction, colTreeFraction(spec));
}

/** Resize just the column tree (keeping the current row-tree size). */
export function setColTreeOps(spec: FigureSpec, fraction: number): Operation[] {
  return dendroLayoutOps(spec, rowTreeFraction(spec), fraction);
}

// --- Leaf-tip length (dendrogram-tips-spec.md) -----------------------------------------------------
//
// The dendrogram's leaf END-STUBS (the short segment between a merge bar and the heatmap, at distance
// 0) are too short to read. Lengthen them — uniformly via a "Leaf tip length" lever, or one stub at a
// time by dragging it. Editing the trace's coordinate arrays is OFF-LIMITS: `lib/patch.ts` classifies
// `/data/<i>/(x|y)` as a SERVER re-run AND it's insert-not-replace under JSON-Patch (the same wall the
// rename hit). So tip length lives as a `meta.selom.dendrogramTips` pref (a layout/meta path → the
// patch classifier treats it as client/instant, and it rides undo) and is applied to the trace at
// RENDER time by `applyDendrogramTips` — a pure, reversible projection (mirrors `figure-model.ts::
// projectOverlay`): the canonical trace stays leaves-at-0, the view grows the stubs. No backend change.

/** Which tree a tip edit targets — `col` = top tree (x3/y3), `row` = left tree (x2/y2). */
export type TipAxis = "row" | "col";

/** `gap` = the uniform lever (added to EVERY leaf stub on that tree); `tips[leafKey]` = a per-leaf
 *  override from a drag (added on TOP of `gap`). Distances are in the tree's own distance-axis units. */
export interface TipPref {
  gap?: number;
  tips?: Record<string, number>;
}
export interface DendrogramTips {
  col?: TipPref;
  row?: TipPref;
}

/** A leaf stub = its position coordinate, a stable key, and the distance of its first merge (stub top). */
export interface LeafStub {
  leafKey: string;
  pos: number;
  merge: number;
}

/** A leaf base sits at distance 0 (only leaves touch distance 0 → unambiguous detection). */
const TIP_EPS = 1e-6;

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** A stable string key for a leaf, from its position coordinate (col → its x, row → its y). Rounded
 *  so it survives a re-render without index bookkeeping. Plotly leaf positions are integers (5,15,…). */
export function leafKeyOf(pos: number): string {
  return (Math.round(pos * 100) / 100).toFixed(2);
}

/** The stored tip pref (`{}` when none). */
export function readDendrogramTips(spec: FigureSpec | null | undefined): DendrogramTips {
  return getAt<DendrogramTips>(spec, "/layout/meta/selom/dendrogramTips", {}) ?? {};
}

/** The current uniform lever (`gap`) for a tree, or 0. */
export function tipGap(spec: FigureSpec | null | undefined, axis: TipAxis): number {
  const g = readDendrogramTips(spec)[axis]?.gap;
  return isNum(g) && g > 0 ? g : 0;
}

const distAxisKey = (axis: TipAxis) => (axis === "col" ? "yaxis3" : "xaxis2");

/** Index of each dendrogram polyline trace + which tree it is (row → x2/y2, col → x3/y3). */
function dendroTraces(spec: FigureSpec | null | undefined): Array<{ index: number; axis: TipAxis }> {
  const data = Array.isArray(spec?.data) ? (spec!.data as PlotlyTrace[]) : [];
  const out: Array<{ index: number; axis: TipAxis }> = [];
  data.forEach((t, i) => {
    if (t?.type !== "scatter") return;
    if (t.xaxis === "x3" && t.yaxis === "y3") out.push({ index: i, axis: "col" });
    else if (t.xaxis === "x2" && t.yaxis === "y2") out.push({ index: i, axis: "row" });
  });
  return out;
}

/** The distance (col → y, row → x) and position (col → x, row → y) coordinate arrays of a tree's trace. */
function traceCoords(
  spec: FigureSpec,
  axis: TipAxis,
): { index: number; dist: unknown[]; pos: unknown[] } | null {
  const hit = dendroTraces(spec).find((t) => t.axis === axis);
  if (!hit) return null;
  const t = (spec.data as PlotlyTrace[])[hit.index];
  const dist = axis === "col" ? t.y : t.x;
  const pos = axis === "col" ? t.x : t.y;
  if (!Array.isArray(dist) || !Array.isArray(pos)) return null;
  return { index: hit.index, dist: dist as unknown[], pos: pos as unknown[] };
}

/** The tree's max merge distance (the root) — for the lever's range + the projected gutter top. */
export function maxDistance(spec: FigureSpec, axis: TipAxis): number {
  const c = traceCoords(spec, axis);
  if (!c) return 0;
  let m = 0;
  for (const v of c.dist) if (isNum(v) && v > m) m = v;
  return m;
}

/**
 * Every leaf stub of a tree: its position, key, and first-merge distance (the stub's far end). The
 * SciPy polyline is links of 4 points (a ⊓: left arm, merge bar, right arm) + a `null` separator;
 * an arm whose base sits at distance 0 is a leaf. Reused by the drag for hit-testing + highlight.
 */
export function leafStubs(spec: FigureSpec, axis: TipAxis): LeafStub[] {
  const c = traceCoords(spec, axis);
  if (!c) return [];
  const { dist, pos } = c;
  const out: LeafStub[] = [];
  for (let k = 0; k + 3 < dist.length; ) {
    if (!isNum(dist[k])) {
      k++;
      continue;
    }
    const d = [dist[k], dist[k + 1], dist[k + 2], dist[k + 3]];
    const p = [pos[k], pos[k + 1], pos[k + 2], pos[k + 3]];
    if (d.every(isNum) && p.every(isNum)) {
      // left arm base (p0,d0)→merge (p1=p0,d1); right arm base (p3,d3)→merge (p2=p3,d2)
      if (Math.abs(d[0] as number) <= TIP_EPS) {
        out.push({ pos: p[0] as number, leafKey: leafKeyOf(p[0] as number), merge: d[1] as number });
      }
      if (Math.abs(d[3] as number) <= TIP_EPS) {
        out.push({ pos: p[3] as number, leafKey: leafKeyOf(p[3] as number), merge: d[2] as number });
      }
    }
    k += 4;
    while (k < dist.length && !isNum(dist[k])) k++; // skip the null separator(s)
  }
  return out;
}

/** The current extension `e = gap + tips[leafKey]` applied to a single leaf (≥ 0). */
export function leafTipLength(spec: FigureSpec, axis: TipAxis, leafKey: string): number {
  const pref = readDendrogramTips(spec)[axis];
  const e = (pref?.gap ?? 0) + (pref?.tips?.[leafKey] ?? 0);
  return e > 0 ? e : 0;
}

/**
 * Render-time PROJECTION: grow each tree's leaf stubs per `meta.selom.dendrogramTips`, returning a NEW
 * spec (the canonical one is untouched). Each leaf-base point (distance ≈ 0) moves out to `-e` where
 * `e = gap + (tips[leafKey] ?? 0)`; the merge bars + internal segments are untouched, so the tree SHAPE
 * is preserved and only the stubs lengthen. The gutter's distance-axis range widens to `[-E, top]`
 * (col) / `[top, -E]` (row, reversed) so the longer stubs stay inside the gutter without overlapping
 * the heatmap. Identity (today's render) when no pref / no tree / `gap=0` and no per-leaf tips.
 */
export function applyDendrogramTips(spec: FigureSpec): FigureSpec {
  const prefs = readDendrogramTips(spec);
  if (!prefs.col && !prefs.row) return spec; // fast path: no pref → today's render
  const traces = dendroTraces(spec);
  if (!traces.length) return spec;

  let newData: PlotlyTrace[] | null = null;
  const newLayout: Record<string, unknown> = { ...(spec.layout as Record<string, unknown>) };
  let changed = false;

  for (const { index, axis } of traces) {
    const pref = prefs[axis];
    const hasTips = pref?.tips && Object.keys(pref.tips).some((k) => (pref.tips![k] ?? 0) > 0);
    if (!pref || (!(pref.gap && pref.gap > 0) && !hasTips)) continue;
    const c = traceCoords(spec, axis);
    if (!c) continue;
    const { dist, pos } = c;
    const nextDist = dist.slice();
    let maxE = 0;
    for (let k = 0; k < nextDist.length; k++) {
      const d = nextDist[k];
      const p = pos[k];
      if (!isNum(d) || !isNum(p) || Math.abs(d) > TIP_EPS) continue; // leaf bases only
      const e = (pref.gap ?? 0) + (pref.tips?.[leafKeyOf(p)] ?? 0);
      if (e > 0) {
        nextDist[k] = -e;
        if (e > maxE) maxE = e;
      }
    }
    if (maxE <= 0) continue;

    newData = newData ?? (spec.data as PlotlyTrace[]).slice();
    const t = newData[index];
    newData[index] = axis === "col" ? { ...t, y: nextDist } : { ...t, x: nextDist };

    // Widen the gutter's distance axis so the extended stubs fit (keeping the root's `top`).
    const key = distAxisKey(axis);
    const ax = { ...((newLayout[key] as Record<string, unknown>) ?? {}) };
    const r = ax.range as unknown[] | undefined;
    const top =
      Array.isArray(r) && r.length === 2 && r.every(isNum)
        ? Math.max(Math.abs(r[0] as number), Math.abs(r[1] as number))
        : maxDistance(spec, axis) * 1.05;
    ax.range = axis === "col" ? [-maxE, top] : [top, -maxE]; // row distance axis is reversed
    newLayout[key] = ax;
    changed = true;
  }

  if (!changed || !newData) return spec;
  return { ...spec, data: newData, layout: newLayout };
}

/** Set the uniform leaf-tip lever for a tree. Rewrites the whole `dendrogramTips` object (one `add`
 *  on the always-present `/layout/meta/selom`), so no intermediate-object bookkeeping. Instant/undoable. */
export function tipLengthOps(spec: FigureSpec, axis: TipAxis, gap: number): Operation[] {
  const tips: DendrogramTips = { ...readDendrogramTips(spec) };
  tips[axis] = { ...(tips[axis] ?? {}), gap: round4(Math.max(0, gap)) };
  return [set("/layout/meta/selom/dendrogramTips", tips)];
}

/** Set (or clear, when `extra <= 0`) a single leaf's tip override — the drag handler's commit. */
export function setLeafTipOps(
  spec: FigureSpec,
  axis: TipAxis,
  leafKey: string,
  extra: number,
): Operation[] {
  const tips: DendrogramTips = { ...readDendrogramTips(spec) };
  const cur: TipPref = { ...(tips[axis] ?? {}) };
  const leaf: Record<string, number> = { ...(cur.tips ?? {}) };
  if (extra > 0) leaf[leafKey] = round4(extra);
  else delete leaf[leafKey];
  cur.tips = leaf;
  tips[axis] = cur;
  return [set("/layout/meta/selom/dendrogramTips", tips)];
}

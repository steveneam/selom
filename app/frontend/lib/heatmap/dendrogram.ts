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

import type { FigureSpec } from "@/lib/figure-spec";
import { set, type Operation } from "@/lib/patch";

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

/**
 * Volcano FC / p-value threshold direct-manipulation (docs/figure-data-capabilities/generalization-spec.md
 * §D) — the shared, framework-free front-end logic for the draggable threshold lines + the numeric
 * threshold editor. Pure so it unit-tests in node-env vitest; the React + canvas pieces consume it.
 *
 * A volcano carries every plotted point (x=log2FC, y=−log10 padj) across three marker traces named
 * "up" / "down" / "n.s." — their UNION is all the data. So changing a threshold re-buckets the points
 * LIVE, client-side, with no DE table and no re-run: exactly the staged-edit model the ERG dots use
 * (`lib/erg/marks.ts::applyStagedMarks`). The numbers that need the server — the exact stats table, the
 * labelled genes, the methods text — refresh on the ONE explicit re-run; this is just the live preview.
 *
 * The skill draws three dashed threshold `shapes`: two vertical lines at x=±fc (FC) and one horizontal
 * line at y=−log10(fdr) (the p-value cut). We identify the bucket traces by NAME and the lines by
 * ORIENTATION, so neither couples to trace/shape order.
 */

import type { FigureSpec, PlotlyLayout, PlotlyTrace } from "@/lib/figure/figure-spec";

/** The volcano's two thresholds in their natural units (NOT y_cut). */
export interface VolcanoThresholds {
  /** |log2 fold-change| cut — the symmetric vertical lines sit at ±fc. */
  fc: number;
  /** Adjusted-p cut — the horizontal line sits at y = −log10(fdr). */
  fdr: number;
}

/** Live up / down / n.s. counts after a re-bucket. */
export interface ThresholdReadout {
  up: number;
  down: number;
  ns: number;
}

/** Param-spec bounds (skills/volcano/skill.json): fc ∈ [0,5], fdr ∈ (0,1]. */
const FC_MIN = 0;
const FC_MAX = 5;
const FDR_MIN = 1e-300;
const FDR_MAX = 1;

const BUCKET_NAMES = { up: "up", down: "down", ns: "n.s." } as const;

/** Clamp staged thresholds to the skill's accepted ranges. */
export function clampThresholds(t: VolcanoThresholds): VolcanoThresholds {
  const fc = Number.isFinite(t.fc) ? Math.min(FC_MAX, Math.max(FC_MIN, Math.abs(t.fc))) : 1;
  const fdr = Number.isFinite(t.fdr) ? Math.min(FDR_MAX, Math.max(FDR_MIN, t.fdr)) : 0.05;
  return { fc, fdr };
}

/** The −log10(p) y-cut for an FDR p-value (0 when fdr ≤ 0). Mirrors run_real.py. */
export function yCut(fdr: number): number {
  return fdr > 0 ? -Math.log10(fdr) : 0;
}

/** Recover the FDR p-value from a y-cut (inverse of `yCut`). */
function fdrFromYCut(y: number): number {
  return Math.min(FDR_MAX, Math.max(FDR_MIN, 10 ** -y));
}

function asNumberArray(v: unknown): number[] | null {
  return Array.isArray(v) ? (v as number[]) : null;
}

/** Index of a bucket trace by its exact name, or -1. */
function bucketIndex(data: PlotlyTrace[], name: string): number {
  return data.findIndex((t) => t?.name === name && Array.isArray(t?.x) && Array.isArray(t?.y));
}

/** A point gathered from the bucket traces. `cd` is its `customdata` row (`[gene, padj]`), carried
 *  through a re-bucket so the gene-labelling substrate stays aligned with the point after a drag. */
export interface Point {
  x: number;
  y: number;
  cd?: unknown;
}

/** Pure up/down/n.s. counts for a set of points at the given thresholds — the editor's live readout
 *  (cheaper than rebuilding the spec via applyStagedThresholds). Same rule as the bucketing below. */
export function bucketCounts(points: Point[], thresholds: VolcanoThresholds): ThresholdReadout {
  const { fc, fdr } = clampThresholds(thresholds);
  const yc = yCut(fdr);
  let up = 0;
  let down = 0;
  let ns = 0;
  for (const { x, y } of points) {
    if (x >= fc && y >= yc) up++;
    else if (x <= -fc && y >= yc) down++;
    else ns++;
  }
  return { up, down, ns };
}

/**
 * Every plotted point, from the UNION of the up/down/n.s. traces. Always re-gather the union — never
 * assume the current partition — so re-bucketing is idempotent. The label/highlight traces are excluded.
 */
export function gatherPoints(spec: FigureSpec | null | undefined): Point[] {
  const data = Array.isArray(spec?.data) ? spec!.data : [];
  const out: Point[] = [];
  for (const name of Object.values(BUCKET_NAMES)) {
    const i = bucketIndex(data, name);
    if (i < 0) continue;
    const xs = asNumberArray(data[i].x);
    const ys = asNumberArray(data[i].y);
    if (!xs || !ys) continue;
    const cds = Array.isArray(data[i].customdata) ? (data[i].customdata as unknown[]) : null;
    const n = Math.min(xs.length, ys.length);
    for (let k = 0; k < n; k++) {
      const x = xs[k];
      const y = ys[k];
      if (Number.isFinite(x) && Number.isFinite(y)) out.push({ x, y, cd: cds ? cds[k] : undefined });
    }
  }
  return out;
}

/** Classify the threshold line shapes: the two vertical FC lines + the one horizontal FDR line. */
function classifyShapes(shapes: unknown): { fcLines: number[]; fdrLine: number | null } {
  const fcLines: number[] = [];
  let fdrLine: number | null = null;
  if (!Array.isArray(shapes)) return { fcLines, fdrLine };
  shapes.forEach((s, i) => {
    if (!s || s.type !== "line") return;
    const vertical = typeof s.x0 === "number" && s.x0 === s.x1; // ±fc lines (yref:"paper")
    const horizontal = typeof s.y0 === "number" && s.y0 === s.y1; // the y_cut line (xref:"paper")
    if (vertical) fcLines.push(i);
    else if (horizontal && fdrLine === null) fdrLine = i;
  });
  return { fcLines, fdrLine };
}

/** Read the figure's current thresholds from its line shapes, or null if they can't be found. */
export function readThresholds(spec: FigureSpec | null | undefined): VolcanoThresholds | null {
  const shapes = (spec?.layout as PlotlyLayout | undefined)?.shapes;
  const { fcLines, fdrLine } = classifyShapes(shapes);
  if (!fcLines.length || fdrLine === null) return null;
  const fc = Math.max(...fcLines.map((i) => Math.abs((shapes as PlotlyTrace[])[i].x0 as number)));
  const fdr = fdrFromYCut((shapes as PlotlyTrace[])[fdrLine].y0 as number);
  return { fc, fdr };
}

/**
 * Re-bucket every point by the staged thresholds and move the three lines — a pure, instant
 * client-side preview of a threshold drag / numeric edit (no re-run). The label + highlight traces are
 * left as-is (they refresh on the re-run). Returns the new spec + the live up/down/ns counts. When the
 * figure isn't a recognisable volcano (no bucket traces / no lines) the spec is returned unchanged.
 */
export function applyStagedThresholds(
  spec: FigureSpec,
  thresholds: VolcanoThresholds,
): { spec: FigureSpec; readout: ThresholdReadout } {
  const { fc, fdr } = clampThresholds(thresholds);
  const yc = yCut(fdr);
  const points = gatherPoints(spec);

  // Each bucket carries x, y, AND the per-point customdata row (so the gene-labelling substrate
  // re-partitions WITH the points — a stale full-length customdata array would misalign with the new,
  // shorter x/y). Customdata is emitted only when the source traces had it (else proteomics-style
  // volcanos / the unit fixtures stay customdata-free).
  const up: [number[], number[], unknown[]] = [[], [], []];
  const down: [number[], number[], unknown[]] = [[], [], []];
  const ns: [number[], number[], unknown[]] = [[], [], []];
  let hasCd = false;
  for (const { x, y, cd } of points) {
    const bucket = x >= fc && y >= yc ? up : x <= -fc && y >= yc ? down : ns;
    bucket[0].push(x);
    bucket[1].push(y);
    bucket[2].push(cd);
    if (cd !== undefined) hasCd = true;
  }
  const readout: ThresholdReadout = { up: up[0].length, down: down[0].length, ns: ns[0].length };

  const data = Array.isArray(spec?.data) ? [...spec.data] : [];
  const idxUp = bucketIndex(data, BUCKET_NAMES.up);
  const idxDown = bucketIndex(data, BUCKET_NAMES.down);
  const idxNs = bucketIndex(data, BUCKET_NAMES.ns);
  if (idxUp < 0 || idxDown < 0 || idxNs < 0) return { spec, readout };
  const rebucket = (trace: PlotlyTrace, b: [number[], number[], unknown[]]): PlotlyTrace =>
    hasCd ? { ...trace, x: b[0], y: b[1], customdata: b[2] } : { ...trace, x: b[0], y: b[1] };
  data[idxUp] = rebucket(data[idxUp], up);
  data[idxDown] = rebucket(data[idxDown], down);
  data[idxNs] = rebucket(data[idxNs], ns);

  // Move the threshold lines: the two verticals to ±fc (larger x → +fc, smaller → −fc), the
  // horizontal to y_cut. Identify by orientation so it survives any shape ordering.
  const shapes = Array.isArray(spec?.layout?.shapes) ? [...spec.layout.shapes] : [];
  const { fcLines, fdrLine } = classifyShapes(shapes);
  if (fcLines.length >= 2) {
    const sorted = [...fcLines].sort((a, b) => (shapes[a].x0 as number) - (shapes[b].x0 as number));
    const neg = sorted[0];
    const pos = sorted[sorted.length - 1];
    shapes[neg] = { ...shapes[neg], x0: -fc, x1: -fc };
    shapes[pos] = { ...shapes[pos], x0: fc, x1: fc };
  }
  if (fdrLine !== null) shapes[fdrLine] = { ...shapes[fdrLine], y0: yc, y1: yc };

  return {
    spec: { ...spec, data, layout: { ...spec.layout, shapes } },
    readout,
  };
}

/**
 * Volcano gene labelling (docs/figure-data-capabilities/generalization-spec.md §H) — the shared,
 * framework-free logic for pinning a gene's symbol as a text annotation on its plotted point. Pure so
 * it unit-tests in node-env vitest; the canvas click-handler + the Statistics-table toggle consume it.
 *
 * A label is an INSTANT cosmetic edit (a `layout.annotations` entry on an already-plotted point) — no
 * re-run, and it rides the figure store's undo/JSON-Patch history. Two surfaces write ONE shared set:
 * clicking a point on the canvas, and a Label toggle in the Statistics table. Both resolve a gene's
 * coordinates from the per-point `customdata` the volcano stamps (`[gene, padj]`), so the table toggle
 * can place a label for a gene it only knows by name.
 *
 * The volcano draws no layout annotations of its own (its auto top-N labels are a `text` TRACE), so on
 * a volcano every `layout.annotations` entry IS a gene label and is identified by its `text` (the gene
 * symbol). `top_n` stays the auto-suggest seed; the amber `highlight` gene-set panel stays separate.
 */

import type { FigureSpec, PlotlyLayout, PlotlyTrace } from "@/lib/figure-spec";
import { remove, set, type Operation } from "@/lib/patch";

/** A plotted point that can carry a gene label: its data coordinates + the gene symbol. */
export interface GeneLabelPoint {
  x: number;
  y: number;
  gene: string;
}

/** The bucket traces whose points carry a gene `customdata` (mirrors volcano/run.py). */
const BUCKET_NAMES = ["up", "down", "n.s."] as const;

function asArray(v: unknown): unknown[] | null {
  return Array.isArray(v) ? v : null;
}

/** The gene symbol stored in a point's `customdata` row (`[gene, padj]`), or null. */
function geneOf(cd: unknown): string | null {
  const row = asArray(cd);
  const g = row?.[0];
  return typeof g === "string" && g ? g : null;
}

/** Every labellable point — the union of the up/down/n.s. traces that carry gene `customdata`. */
export function gatherLabelablePoints(spec: FigureSpec | null | undefined): GeneLabelPoint[] {
  const data = Array.isArray(spec?.data) ? (spec!.data as PlotlyTrace[]) : [];
  const out: GeneLabelPoint[] = [];
  for (const name of BUCKET_NAMES) {
    const t = data.find(
      (d) => d?.name === name && Array.isArray(d?.x) && Array.isArray(d?.y) && Array.isArray(d?.customdata),
    );
    if (!t) continue;
    const xs = t.x as number[];
    const ys = t.y as number[];
    const cds = t.customdata as unknown[];
    const n = Math.min(xs.length, ys.length, cds.length);
    for (let k = 0; k < n; k++) {
      const gene = geneOf(cds[k]);
      if (gene && Number.isFinite(xs[k]) && Number.isFinite(ys[k])) out.push({ x: xs[k], y: ys[k], gene });
    }
  }
  return out;
}

/** Every gene that has a plotted point (so the Statistics-table Label toggle knows what's labellable). */
export function labelableGenes(spec: FigureSpec | null | undefined): Set<string> {
  return new Set(gatherLabelablePoints(spec).map((p) => p.gene));
}

/** Locate a gene's plotted point by symbol (the table toggle only knows the name), or null. */
export function findPoint(spec: FigureSpec | null | undefined, gene: string): GeneLabelPoint | null {
  return gatherLabelablePoints(spec).find((p) => p.gene === gene) ?? null;
}

/** Read the current label annotations (on a volcano, every annotation is a gene label). */
function readAnnotations(spec: FigureSpec | null | undefined): { text?: unknown }[] {
  const a = (spec?.layout as PlotlyLayout | undefined)?.annotations;
  return Array.isArray(a) ? (a as { text?: unknown }[]) : [];
}

/** The set of currently-labelled gene symbols (the shared `label_genes` set), read from the annotations. */
export function labeledGenes(spec: FigureSpec | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const a of readAnnotations(spec)) if (typeof a?.text === "string" && a.text) out.add(a.text);
  return out;
}

/** Is this gene currently labelled? */
export function isLabeled(spec: FigureSpec | null | undefined, gene: string): boolean {
  return readAnnotations(spec).some((a) => a?.text === gene);
}

/** Build the gene-label annotation: a small text tag with a short leader arrow to the point. */
function labelAnnotation(p: GeneLabelPoint): Record<string, unknown> {
  return {
    x: p.x,
    y: p.y,
    text: p.gene,
    showarrow: true,
    arrowhead: 0,
    arrowsize: 1,
    arrowwidth: 1,
    arrowcolor: "#94a3b8",
    ax: 0,
    ay: -18,
    font: { size: 10, color: "#0f172a" },
    bgcolor: "rgba(255,255,255,0.72)",
    bordercolor: "rgba(148,163,184,0.5)",
    borderpad: 1,
    captureevents: false,
  };
}

/**
 * Toggle a gene's label: REMOVE its annotation if present, else ADD one at the gene's point. Pure —
 * returns the JSON-Patch ops the caller commits to the figure store (instant, undoable, no re-run).
 * Returns `[]` when adding but the gene has no plotted point (nothing to anchor a label to).
 */
export function toggleLabelOps(spec: FigureSpec, point: GeneLabelPoint): Operation[] {
  const annos = readAnnotations(spec);
  const idx = annos.findIndex((a) => a?.text === point.gene);
  if (idx >= 0) return [remove(`/layout/annotations/${idx}`)];
  const anno = labelAnnotation(point);
  // `set` = JSON-Patch add: on a missing/empty array, set the whole array; else append with `/-`.
  return annos.length === 0 ? [set("/layout/annotations", [anno])] : [set("/layout/annotations/-", anno)];
}

/** Toggle a gene known only by symbol (the Statistics-table path): resolve its point, then toggle. */
export function toggleGeneLabelOps(spec: FigureSpec, gene: string): Operation[] {
  if (isLabeled(spec, gene)) {
    const idx = readAnnotations(spec).findIndex((a) => a?.text === gene);
    return idx >= 0 ? [remove(`/layout/annotations/${idx}`)] : [];
  }
  const point = findPoint(spec, gene);
  return point ? toggleLabelOps(spec, point) : [];
}

/** Extract a labellable point from a Plotly click event point (`customdata` = `[gene, padj]`), or null. */
export function pointFromClick(pt: unknown): GeneLabelPoint | null {
  const p = pt as { x?: unknown; y?: unknown; customdata?: unknown } | null | undefined;
  const gene = geneOf(p?.customdata);
  if (gene && typeof p?.x === "number" && typeof p?.y === "number") return { x: p.x, y: p.y, gene };
  return null;
}

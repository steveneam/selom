/**
 * Heatmap label editing — rename · highlight · side (docs/figure-data-capabilities/heatmap-clustermap-spec.md
 * §6–8). The shared, framework-free logic for the provenance-safe label affordances; pure so it
 * unit-tests in node-env vitest. The Figure-Styling "Labels" panel builds its edits here.
 *
 * Every edit here is INSTANT + COSMETIC: it writes the axis `ticktext` (a LAYOUT edit, so the patch
 * classifier treats it as client-side/instant and it rides the figure store's undo/JSON-Patch
 * history — NOT a data `x`/`y` edit, which would be a server re-run). The data `x`/`y` arrays stay
 * the CANONICAL category labels, so hover keeps showing the original and the dataset / run params /
 * methods are never touched — the figure merely *shows* the chosen label. The true source-of-truth
 * IDs (pre symbol-strip) ride `meta.selom.heatmapLabels`, surfaced in the panel.
 *
 * A highlighted gene-of-interest (035617: red labels) is the SAME ticktext wrapped in an inline
 * colour span — Plotly renders a per-tick `<span style="color:…">`, where a uniform `tickfont.color`
 * could not. So rename + highlight compose on one `ticktext` array.
 */

import type { FigureSpec, PlotlyTrace } from "@/lib/figure/figure-spec";
import { set, type Operation } from "@/lib/figure/patch";

/** Which axis a label set lives on: `x` = samples (columns), `y` = genes (rows). */
export type LabelAxis = "x" | "y";
const AXIS_KEY: Record<LabelAxis, string> = { x: "xaxis", y: "yaxis" };

/** Gene-of-interest highlight colour (red, matching the publication references). */
export const HIGHLIGHT_COLOR = "#dc2626";

const HEATMAP_TYPES = new Set(["heatmap", "heatmapgl", "contour"]);

function isHeatmap(t: PlotlyTrace | undefined | null): boolean {
  return !!t && HEATMAP_TYPES.has(String(t?.type ?? "").toLowerCase());
}

function layoutObj(spec: FigureSpec | null | undefined): Record<string, unknown> {
  const l = spec?.layout;
  return l && typeof l === "object" ? (l as Record<string, unknown>) : {};
}

/**
 * Index of the MAIN heatmap trace — the gene×sample map (the most rows), distinguished from the
 * 1-row categorical annotation strips a later slice adds. -1 when there's no heatmap trace.
 */
export function mainHeatmapIndex(spec: FigureSpec | null | undefined): number {
  const data = Array.isArray(spec?.data) ? (spec!.data as PlotlyTrace[]) : [];
  let best = -1;
  let bestRows = -1;
  data.forEach((t, i) => {
    if (!isHeatmap(t)) return;
    const z = (t as { z?: unknown }).z;
    const rows = Array.isArray(z) ? z.length : 0;
    if (rows > bestRows) {
      bestRows = rows;
      best = i;
    }
  });
  return best;
}

/** The category (data) labels for an axis of the main heatmap — the canonical tick positions. */
export function categoryLabels(spec: FigureSpec | null | undefined, axis: LabelAxis): string[] {
  const i = mainHeatmapIndex(spec);
  if (i < 0) return [];
  const arr = (spec!.data[i] as Record<string, unknown>)[axis];
  return Array.isArray(arr) ? arr.map(String) : [];
}

/** The canonical source-of-truth labels (backend `meta.selom.heatmapLabels`), or the category labels. */
export function originalLabels(spec: FigureSpec | null | undefined, axis: LabelAxis): string[] {
  const meta = layoutObj(spec).meta as { selom?: { heatmapLabels?: Record<string, unknown> } } | undefined;
  const ol = meta?.selom?.heatmapLabels?.[axis];
  if (Array.isArray(ol) && ol.length) return ol.map(String);
  return categoryLabels(spec, axis);
}

const SPAN_RE = /^<span style="color:[^"]*">([\s\S]*)<\/span>$/;

/** Parse a ticktext entry → its editable plain text + whether it's highlight-wrapped. */
export function parseTick(s: string): { text: string; highlighted: boolean } {
  const m = SPAN_RE.exec(s);
  return m ? { text: m[1], highlighted: true } : { text: s, highlighted: false };
}

/** Render a label's display text, wrapping it in a colour span when highlighted. */
export function formatTick(text: string, highlighted: boolean): string {
  return highlighted ? `<span style="color:${HIGHLIGHT_COLOR}">${text}</span>` : text;
}

/** The current rendered ticktext for an axis, seeded from the category labels when unset. */
export function currentTicktext(spec: FigureSpec | null | undefined, axis: LabelAxis): string[] {
  const ax = layoutObj(spec)[AXIS_KEY[axis]] as { ticktext?: unknown } | undefined;
  const tt = ax?.ticktext;
  if (Array.isArray(tt) && tt.length) return tt.map(String);
  return categoryLabels(spec, axis);
}

/** One editable label row for the panel: position, canonical original, current display text, highlight. */
export interface LabelRow {
  index: number;
  original: string;
  text: string;
  highlighted: boolean;
}

/** Every label on an axis, parsed for the panel (rename input + highlight toggle). */
export function labelRows(spec: FigureSpec | null | undefined, axis: LabelAxis): LabelRow[] {
  const orig = originalLabels(spec, axis);
  return currentTicktext(spec, axis).map((t, i) => {
    const p = parseTick(t);
    return { index: i, original: orig[i] ?? p.text, text: p.text, highlighted: p.highlighted };
  });
}

/** The genes (y-axis labels) currently highlighted — their plain display text. */
export function highlightedGenes(spec: FigureSpec | null | undefined, axis: LabelAxis = "y"): string[] {
  return labelRows(spec, axis).filter((r) => r.highlighted).map((r) => r.text);
}

/** JSON-Patch ops to pin an axis to an explicit ticktext array (positions = the categorical indices). */
function ticktextOps(axis: LabelAxis, ticks: string[]): Operation[] {
  const key = AXIS_KEY[axis];
  return [
    set(`/layout/${key}/tickmode`, "array"),
    set(`/layout/${key}/tickvals`, ticks.map((_, i) => i)),
    set(`/layout/${key}/ticktext`, ticks),
  ];
}

/** Rebuild the whole ticktext array from the current rows with one row transformed. */
function rebuild(
  spec: FigureSpec,
  axis: LabelAxis,
  transform: (row: LabelRow, i: number) => { text: string; highlighted: boolean },
): Operation[] {
  const rows = labelRows(spec, axis);
  if (!rows.length) return [];
  const ticks = rows.map((r, i) => {
    const next = transform(r, i);
    return formatTick(next.text, next.highlighted);
  });
  return ticktextOps(axis, ticks);
}

/**
 * Rename one label (keeping its highlight state). A blank/whitespace name resets that label to its
 * category (display) base. Pure → the caller commits the ops to the figure store (instant, undoable).
 */
export function renameLabelOps(spec: FigureSpec, axis: LabelAxis, index: number, text: string): Operation[] {
  const base = categoryLabels(spec, axis);
  const clean = text.trim();
  return rebuild(spec, axis, (r, i) =>
    i === index ? { text: clean || base[i] || r.text, highlighted: r.highlighted } : r,
  );
}

/** Set the highlight state of one label (red gene-of-interest span), keeping its renamed text. */
export function setHighlightOps(
  spec: FigureSpec,
  axis: LabelAxis,
  index: number,
  highlighted: boolean,
): Operation[] {
  return rebuild(spec, axis, (r, i) => (i === index ? { text: r.text, highlighted } : r));
}

/**
 * Set the highlighted gene set wholesale (the panel's gene-of-interest multiselect). Matches by the
 * label's current DISPLAY text; everything not in the set is un-highlighted. `axis` defaults to genes.
 */
export function setHighlightedGenesOps(
  spec: FigureSpec,
  genes: Iterable<string>,
  axis: LabelAxis = "y",
): Operation[] {
  const want = new Set(genes);
  return rebuild(spec, axis, (r) => ({ text: r.text, highlighted: want.has(r.text) }));
}

/** Move the gene (y) / sample (x) tick labels to a side. Pure layout edit (instant, undoable). */
export function labelSideOps(axis: LabelAxis, side: "left" | "right" | "top" | "bottom"): Operation[] {
  return [set(`/layout/${AXIS_KEY[axis]}/side`, side)];
}

/** Is a row dendrogram present? (It owns the left gutter, so the gene labels are pinned right.) */
export function hasRowDendrogram(spec: FigureSpec | null | undefined): boolean {
  const xa = layoutObj(spec).xaxis2;
  return !!xa;
}

// --- Colour tick labels by annotation group (heatmap-clustermap-spec §8 / refs 035617/035636) -----
//
// The publication clustermaps colour the SAMPLE tick labels by their group (DR teal / PD red). When a
// categorical annotation track is present (slice 4), each sample already has a group + a colour — so
// colouring its label is a cosmetic reuse of the SAME span mechanism the gene highlight uses (a uniform
// tickfont.color can't colour one tick). Reads the group→colour map straight off the track's legend
// proxies + the per-column category off the strip's customdata, so the labels match the strips exactly.
// Instant + undoable (writes the axis ticktext); the chosen track rides meta.selom.labelColorBy.{axis}
// so the control knows the active selection (committed in the same op set → reverts together on undo).

/** Wrap a label in an arbitrary colour span (the shape `parseTick` understands), or plain when null. */
export function formatColorTick(text: string, color: string | null): string {
  return color ? `<span style="color:${color}">${text}</span>` : text;
}

/** The annotation strips' legend proxies give each (track → category → colour). Built from the
 *  showlegend scatter proxies the backend emits beside the strips. */
function trackColorMap(spec: FigureSpec | null | undefined): Record<string, Record<string, string>> {
  const data = Array.isArray(spec?.data) ? (spec!.data as PlotlyTrace[]) : [];
  const out: Record<string, Record<string, string>> = {};
  for (const t of data) {
    const tt = t as { type?: string; showlegend?: boolean; legendgroup?: unknown; name?: unknown; marker?: { color?: unknown } };
    if (tt.type !== "scatter" || tt.showlegend !== true) continue;
    const group = typeof tt.legendgroup === "string" ? tt.legendgroup : null;
    const name = tt.name == null ? null : String(tt.name);
    const color = typeof tt.marker?.color === "string" ? tt.marker.color : null;
    if (!group || name == null || !color) continue;
    (out[group] ??= {})[name] = color;
  }
  return out;
}

/** The annotation-track names present on the figure (the column strips), in render order. */
export function annotationTrackNames(spec: FigureSpec | null | undefined): string[] {
  return Object.keys(trackColorMap(spec));
}

/** A track strip's per-column category list (from its customdata), aligned to the heatmap columns. */
function trackCategories(spec: FigureSpec | null | undefined, trackName: string): string[] | null {
  const data = Array.isArray(spec?.data) ? (spec!.data as PlotlyTrace[]) : [];
  for (const t of data) {
    const tt = t as { type?: string; y?: unknown; customdata?: unknown };
    if (tt.type !== "heatmap" || !Array.isArray(tt.y) || tt.y.length !== 1) continue;
    if (String(tt.y[0]) !== trackName) continue;
    const cd = tt.customdata;
    if (Array.isArray(cd) && Array.isArray(cd[0])) return (cd[0] as unknown[]).map(String);
  }
  return null;
}

/** Which track currently colours an axis's labels (meta.selom.labelColorBy.{axis}), or null. */
export function labelColorBy(spec: FigureSpec | null | undefined, axis: LabelAxis): string | null {
  const meta = layoutObj(spec).meta as { selom?: { labelColorBy?: Record<string, unknown> } } | undefined;
  const v = meta?.selom?.labelColorBy?.[axis];
  return typeof v === "string" && v ? v : null;
}

/**
 * Colour an axis's tick labels by an annotation track's group (or clear, when `trackName` is null).
 * Each label is wrapped in its group's colour — the SAME colour as the strip — preserving any rename.
 * Writes the axis ticktext + stamps the chosen track at `meta.selom.labelColorBy.{axis}` in one
 * commit (instant, undoable together). A label whose group has no colour falls back to plain.
 */
export function colorLabelsByGroupOps(
  spec: FigureSpec,
  axis: LabelAxis,
  trackName: string | null,
): Operation[] {
  const rows = labelRows(spec, axis);
  if (!rows.length) return [];
  const colors = trackName ? trackColorMap(spec)[trackName] : null;
  const cats = trackName ? trackCategories(spec, trackName) : null;
  const ticks = rows.map((r, i) => {
    const cat = cats?.[i];
    const color = trackName && colors && cat ? (colors[cat] ?? null) : null;
    return formatColorTick(r.text, color);
  });
  const prior = layoutObj(spec).meta as { selom?: { labelColorBy?: Record<string, unknown> } } | undefined;
  const next = { ...(prior?.selom?.labelColorBy ?? {}), [axis]: trackName ?? "" };
  return [...ticktextOps(axis, ticks), set("/layout/meta/selom/labelColorBy", next)];
}

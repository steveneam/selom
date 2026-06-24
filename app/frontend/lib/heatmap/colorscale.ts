/**
 * Heatmap colour-scale direct-manipulation (docs/figure-data-capabilities/heatmap-spec.md §C) — the
 * shared, framework-free logic for re-toning an expression heatmap. Pure so it unit-tests in node-env
 * vitest; the Style "Colour scale" sliders and the canvas colour-bar drag both build their edits here.
 *
 * Re-toning is an INSTANT cosmetic edit: shifting the diverging midpoint (`zmid`) and the saturation
 * clip (`zmin`/`zmax`) only changes how the existing z-matrix maps to colour — no data changes, no
 * re-run. So these become JSON-Patch ops committed to the figure store (undoable), exactly like the
 * volcano gene labels. The genes/clustering change (which DOES change the data) stays a staged re-run.
 *
 * Heatmap traces are identified by TYPE (`heatmap`/`heatmapgl`/`contour`), never by index order, and a
 * patch is applied to EVERY heatmap trace so a multi-heatmap figure stays consistent (mirrors the Style
 * panel's `apply` and `figure-model`'s `seriesColorOps`).
 */

import type { FigureSpec, PlotlyTrace } from "@/lib/figure-spec";
import { set, type Operation } from "@/lib/patch";

/** A heatmap's current colour-mapping state (the diverging tones, not the z data). */
export interface HeatmapTones {
  /** Named Plotly colour scale (e.g. "RdBu"), or null when a custom stop array is used. */
  colorscale: string | null;
  reversed: boolean;
  /** The diverging centre (white point of RdBu). */
  zmid: number;
  /** Low clip — cells at/below map to the full low colour. */
  zmin: number;
  /** High clip — cells at/above map to the full high colour. */
  zmax: number;
}

/** The data extent of the z-matrix (the natural bounds for the midpoint / saturation sliders). */
export interface ZExtent {
  min: number;
  max: number;
}

const HEATMAP_TYPES = new Set(["heatmap", "heatmapgl", "contour"]);

function isHeatmap(t: PlotlyTrace | undefined | null): boolean {
  return !!t && HEATMAP_TYPES.has(String(t.type ?? "").toLowerCase());
}

function num(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

/** Indices of every heatmap trace (by TYPE, never order) — the set a re-tone patch writes to. */
export function heatmapTraceIndices(spec: FigureSpec | null | undefined): number[] {
  const data = Array.isArray(spec?.data) ? spec!.data : [];
  const out: number[] = [];
  data.forEach((t, i) => {
    if (isHeatmap(t)) out.push(i);
  });
  return out;
}

/** The first heatmap trace, or null. */
function firstHeatmap(spec: FigureSpec | null | undefined): PlotlyTrace | null {
  const idx = heatmapTraceIndices(spec);
  return idx.length ? ((spec!.data as PlotlyTrace[])[idx[0]] ?? null) : null;
}

/** Min/max over every finite z cell across all heatmap traces, or null when there's no finite z. */
export function zExtent(spec: FigureSpec | null | undefined): ZExtent | null {
  const data = Array.isArray(spec?.data) ? spec!.data : [];
  let min = Infinity;
  let max = -Infinity;
  for (const t of data) {
    if (!isHeatmap(t)) continue;
    const z = (t as { z?: unknown }).z;
    if (!Array.isArray(z)) continue;
    for (const row of z) {
      if (!Array.isArray(row)) continue;
      for (const v of row) {
        if (typeof v === "number" && Number.isFinite(v)) {
          if (v < min) min = v;
          if (v > max) max = v;
        }
      }
    }
  }
  return Number.isFinite(min) && Number.isFinite(max) ? { min, max } : null;
}

/**
 * Read a heatmap's current tones. `zmid` defaults to 0 (the diverging centre); `zmin`/`zmax` fall back
 * to the z data extent when the trace hasn't pinned them (so the saturation slider starts at full range).
 * Returns null when there's no heatmap trace.
 */
export function readTones(spec: FigureSpec | null | undefined): HeatmapTones | null {
  const t = firstHeatmap(spec);
  if (!t) return null;
  const ext = zExtent(spec) ?? { min: -1, max: 1 };
  const tt = t as { colorscale?: unknown; reversescale?: unknown; zmid?: unknown; zmin?: unknown; zmax?: unknown };
  return {
    colorscale: typeof tt.colorscale === "string" ? tt.colorscale : null,
    reversed: tt.reversescale === true,
    zmid: num(tt.zmid, 0),
    zmin: num(tt.zmin, ext.min),
    zmax: num(tt.zmax, ext.max),
  };
}

/** Clamp a z value into a slightly-padded data extent (so a slider/drag can reach the edges). */
export function clampToExtent(v: number, ext: ZExtent): number {
  const pad = (ext.max - ext.min) * 0.05 || 0.5;
  return Math.min(ext.max + pad, Math.max(ext.min - pad, v));
}

/** A partial re-tone (only the fields present are written). */
export interface TonePatch {
  colorscale?: string;
  reversed?: boolean;
  zmid?: number;
  zmin?: number;
  zmax?: number;
}

/**
 * JSON-Patch ops to apply a tone patch to EVERY heatmap trace (`indices` from `heatmapTraceIndices`).
 * Pure; the caller commits them to the figure store (`store.commit` / live `store.set` + `store.flush`).
 * Maps `reversed`→`reversescale`; the rest write their same-named leaf.
 */
export function toneOps(indices: number[], patch: TonePatch): Operation[] {
  const ops: Operation[] = [];
  for (const i of indices) {
    if (patch.colorscale !== undefined) ops.push(set(`/data/${i}/colorscale`, patch.colorscale));
    if (patch.reversed !== undefined) ops.push(set(`/data/${i}/reversescale`, patch.reversed));
    if (patch.zmid !== undefined) ops.push(set(`/data/${i}/zmid`, patch.zmid));
    if (patch.zmin !== undefined) ops.push(set(`/data/${i}/zmin`, patch.zmin));
    if (patch.zmax !== undefined) ops.push(set(`/data/${i}/zmax`, patch.zmax));
  }
  return ops;
}

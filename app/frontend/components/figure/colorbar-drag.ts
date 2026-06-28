/**
 * Draggable heatmap colour bar (docs/figure-data-capabilities/heatmap-spec.md §E, the canvas half).
 *
 * Grab the rendered colour bar and drag it to re-tone the heatmap LIVE: the TOP third sets `zmax`, the
 * BOTTOM third sets `zmin` (the saturation clips), the MIDDLE shifts `zmid` (the diverging centre).
 * Each move re-maps the EXISTING z-matrix to colour — an instant, undoable figure-store edit, no re-run
 * (the genes/clustering change stays a staged re-run). Shares state with the Style "Colour scale"
 * sliders — a bar drag and a slider move are the same `toneOps` edit.
 *
 * Imperative wiring (not Plotly `editable`/`colorbarPosition`, which only MOVES the bar). The bar's
 * pixel rect comes from the rendered DOM (`.cbfills`/`.colorbar`) and its value range from Plotly's
 * computed `gd._fullData[i].zmin/zmax`; every access is guarded so a missing bar / range degrades to
 * "the bar just doesn't drag" (the Style sliders are the fallback) — never a throw.
 */

import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { FigureStore } from "@/hooks/use-figure-store";
import {
  clampToExtent,
  heatmapTraceIndices,
  readTones,
  toneOps,
  zExtent,
  type ZExtent,
} from "@/lib/heatmap/colorscale";

interface GraphDiv extends HTMLElement {
  _fullData?: Array<{ zmin?: unknown; zmax?: unknown } | undefined>;
}

/** Magnet band (px): grab the bar within this distance of its rect — no pixel-perfect aiming. */
const GRAB_PX = 18;
/** Keep a minimum gap between zmin and zmax so the colour range never collapses. */
const MIN_GAP = 0.1;

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

type Handle = "zmax" | "zmin" | "zmid";

export interface ColorbarDragDeps {
  /** Latest spec (read fresh each gesture so a re-tone / re-run is reflected). */
  getSpec: () => FigureSpec;
  /** The figure store — a drag is an INSTANT cosmetic edit (set live, flush one undo entry on release). */
  store: FigureStore;
}

/** The colour bar's pixel rect (the gradient fill, falling back to the whole bar group), or null. */
function barRect(gd: GraphDiv): DOMRect | null {
  const el = (gd.querySelector?.(".cbfills") ?? gd.querySelector?.(".colorbar")) as Element | null;
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return rect.height > 4 ? rect : null;
}

/** Plotly's computed effective [zmin, zmax] for the first heatmap trace — the bar's value range. */
function barRange(gd: GraphDiv, spec: FigureSpec): { zmin: number; zmax: number } | null {
  const idx = heatmapTraceIndices(spec)[0];
  if (idx === undefined) return null;
  const full = gd._fullData?.[idx];
  const lo = num(full?.zmin);
  const hi = num(full?.zmax);
  if (lo !== null && hi !== null && hi > lo) return { zmin: lo, zmax: hi };
  // Fallback to the declared/derived tones (e.g. before a full re-render exposes _fullData).
  const t = readTones(spec);
  return t && t.zmax > t.zmin ? { zmin: t.zmin, zmax: t.zmax } : null;
}

/** Which handle (if any) is under a client pixel, given the bar rect + magnet band. */
function hitTest(rect: DOMRect, clientX: number, clientY: number): Handle | null {
  const nearX = clientX >= rect.left - GRAB_PX && clientX <= rect.right + GRAB_PX;
  const nearY = clientY >= rect.top - GRAB_PX && clientY <= rect.bottom + GRAB_PX;
  if (!nearX || !nearY) return null;
  const frac = (clientY - rect.top) / rect.height; // 0 at top (high), 1 at bottom (low)
  if (frac < 0.34) return "zmax";
  if (frac > 0.66) return "zmin";
  return "zmid";
}

/** Map a client-Y inside the bar rect → a z value (top = zmax, bottom = zmin). */
function valueAt(rect: DOMRect, range: { zmin: number; zmax: number }, clientY: number): number {
  const frac = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
  return range.zmax - frac * (range.zmax - range.zmin);
}

/**
 * Wire colour-bar dragging onto a Plotly graph div. Returns a cleanup function. Safe to call
 * repeatedly (the caller disposes the prior binding first).
 */
export function wireColorbarDrag(gd: GraphDiv, deps: ColorbarDragDeps): () => void {
  let armed: Handle | null = null;
  let dragging: Handle | null = null;
  let raf = 0;
  let pending: (() => void) | null = null;

  const flush = () => {
    raf = 0;
    const fn = pending;
    pending = null;
    fn?.();
  };
  const schedule = (fn: () => void) => {
    pending = fn;
    if (!raf) raf = requestAnimationFrame(flush);
  };

  /** Build + apply the re-tone for a handle at a client-Y (clamped so zmin < zmax). Returns true if applied. */
  const applyAt = (handle: Handle, clientY: number, commit: boolean): void => {
    const spec = deps.getSpec();
    const rect = barRect(gd);
    const range = rect ? barRange(gd, spec) : null;
    const tones = readTones(spec);
    const ext: ZExtent = zExtent(spec) ?? { min: -3, max: 3 };
    const idx = heatmapTraceIndices(spec);
    if (!rect || !range || !tones || !idx.length) return;
    const v = clampToExtent(valueAt(rect, range, clientY), ext);
    let patch: { zmid?: number; zmin?: number; zmax?: number };
    if (handle === "zmax") patch = { zmax: Math.max(v, tones.zmin + MIN_GAP) };
    else if (handle === "zmin") patch = { zmin: Math.min(v, tones.zmax - MIN_GAP) };
    else patch = { zmid: Math.min(tones.zmax, Math.max(tones.zmin, v)) };
    deps.store.set(toneOps(idx, patch));
    if (commit) deps.store.flush();
  };

  const onProximityMove = (ev: MouseEvent) => {
    if (dragging) return;
    const rect = barRect(gd);
    armed = rect ? hitTest(rect, ev.clientX, ev.clientY) : null;
    gd.style.cursor = armed ? "ns-resize" : "";
  };

  const onMove = (ev: MouseEvent) => {
    if (!dragging) return;
    const h = dragging;
    const y = ev.clientY;
    schedule(() => applyAt(h, y, false));
  };

  const onUp = (ev: MouseEvent) => {
    const h = dragging;
    dragging = null;
    gd.style.cursor = "";
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (raf) {
      cancelAnimationFrame(raf);
      raf = 0;
      pending = null;
    }
    if (h) applyAt(h, ev.clientY, true); // commit the final value → one undo entry
  };

  const onDown = (ev: MouseEvent) => {
    if (ev.button !== 0) return;
    const rect = barRect(gd);
    const hit = rect ? (armed ?? hitTest(rect, ev.clientX, ev.clientY)) : null;
    if (!hit) return;
    dragging = hit;
    gd.style.cursor = "grabbing";
    // Block Plotly's own gesture for this drag (capture-phase, before Plotly's inner mousedown).
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("mouseup", onUp, true);
  };

  const onLeave = () => {
    if (!dragging) gd.style.cursor = "";
  };

  gd.addEventListener("mousemove", onProximityMove);
  gd.addEventListener("mouseleave", onLeave);
  gd.addEventListener("mousedown", onDown, true);

  return () => {
    gd.removeEventListener("mousemove", onProximityMove);
    gd.removeEventListener("mouseleave", onLeave);
    gd.removeEventListener("mousedown", onDown, true);
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (raf) cancelAnimationFrame(raf);
    gd.style.cursor = "";
  };
}

/**
 * Draggable volcano FC / p-value threshold lines (docs/figure-data-capabilities/generalization-spec.md
 * §E, the canvas half).
 *
 * The dashed threshold lines the skill draws become draggable: grab a vertical FC line (it drags
 * horizontally; both ± lines mirror) or the horizontal p-value line (it drags vertically). Each move
 * stages the new threshold via `onThresholdChange`, and the parent's preview re-buckets every point
 * LIVE (`lib/volcano/thresholds.ts::applyStagedThresholds`) — so the points re-colour and the counts
 * update as you drag, with no re-run. The ONE re-run later recomputes the gene table + labels. Shares
 * state with the numeric Threshold editor — a drag and a typed cut are the same staged edit.
 *
 * Imperative Plotly wiring (we don't use Plotly's `editable`/shape-drag — we need axis-constrained,
 * mirrored, throttled staging). Reads a few axis internals to map pixels↔data; every access is guarded
 * so a version mismatch degrades to "the line just doesn't drag" (the numeric editor is the fallback).
 */

import type { FigureSpec } from "@/lib/figure/figure-spec";
import { clampThresholds, readThresholds, yCut, type VolcanoThresholds } from "@/lib/volcano/thresholds";

interface PlotlyAxis {
  _offset?: number;
  _length?: number;
  p2d?: (p: number) => number;
  d2p?: (d: number) => number;
}
interface GraphDiv extends HTMLElement {
  _fullLayout?: Record<string, PlotlyAxis>;
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Resolve the primary x/y subplot axis (volcano is a single subplot). */
function axisFor(gd: GraphDiv, kind: "x" | "y"): PlotlyAxis | null {
  const ax = gd._fullLayout?.[`${kind}axis`];
  return ax && typeof ax.p2d === "function" && typeof ax.d2p === "function" ? ax : null;
}

/** Magnet band (px): grab a threshold line within this distance of it — no pixel-perfect aiming. */
const GRAB_PX = 18;

export interface ThresholdDragDeps {
  /** Latest spec (read fresh each gesture so a re-run / staged move is reflected). */
  getSpec: () => FigureSpec;
  /** Stage the new thresholds (the parent re-buckets the preview live). Absent → dragging disabled. */
  onThresholdChange?: (t: VolcanoThresholds) => void;
}

type DragKind = "fc" | "fdr";

interface Armed {
  kind: DragKind;
  /** The non-dragged value, captured at grab so the drag only moves one axis. */
  fc0: number;
  fdr0: number;
}

/** Which threshold line (if any) is within the magnet band of a client pixel. */
function hitTest(gd: GraphDiv, spec: FigureSpec, clientX: number, clientY: number): DragKind | null {
  const t = readThresholds(spec);
  if (!t) return null;
  const xaxis = axisFor(gd, "x");
  const yaxis = axisFor(gd, "y");
  const xOff = num(xaxis?._offset);
  const yOff = num(yaxis?._offset);
  const xLen = num(xaxis?._length);
  const yLen = num(yaxis?._length);
  if (!xaxis?.d2p || !yaxis?.d2p || xOff === null || yOff === null || xLen === null || yLen === null) {
    return null;
  }
  const rect = gd.getBoundingClientRect();
  const withinY = clientY >= rect.top + yOff && clientY <= rect.top + yOff + yLen;
  const withinX = clientX >= rect.left + xOff && clientX <= rect.left + xOff + xLen;
  let best: DragKind | null = null;
  let bestD = GRAB_PX;
  if (withinY) {
    for (const fx of [t.fc, -t.fc]) {
      const px = rect.left + xOff + xaxis.d2p(fx);
      const d = Math.abs(clientX - px);
      if (d < bestD) {
        bestD = d;
        best = "fc";
      }
    }
  }
  if (withinX) {
    const py = rect.top + yOff + yaxis.d2p(yCut(t.fdr));
    const d = Math.abs(clientY - py);
    if (d < bestD) {
      bestD = d;
      best = "fdr";
    }
  }
  return best;
}

/**
 * Wire threshold-line dragging onto a Plotly graph div. Returns a cleanup function. Safe to call
 * repeatedly (the caller disposes the prior binding first).
 */
export function wireThresholdDrag(gd: GraphDiv, deps: ThresholdDragDeps): () => void {
  let armed: DragKind | null = null;
  let dragging: Armed | null = null;
  let raf = 0;
  let pending: VolcanoThresholds | null = null;

  // Coalesce moves to one stage per animation frame — the preview re-bucket + Plotly re-render is the
  // heavy step, so we never run it more than ~60×/s no matter how fast the pointer moves.
  const flush = () => {
    raf = 0;
    if (pending && deps.onThresholdChange) deps.onThresholdChange(pending);
    pending = null;
  };
  const stage = (t: VolcanoThresholds) => {
    pending = t;
    if (!raf) raf = requestAnimationFrame(flush);
  };

  const onProximityMove = (ev: MouseEvent) => {
    if (dragging || !deps.onThresholdChange) return;
    const hit = hitTest(gd, deps.getSpec(), ev.clientX, ev.clientY);
    armed = hit;
    gd.style.cursor = hit === "fc" ? "ew-resize" : hit === "fdr" ? "ns-resize" : "";
  };

  const compute = (a: Armed, clientX: number, clientY: number): VolcanoThresholds | null => {
    const rect = gd.getBoundingClientRect();
    if (a.kind === "fc") {
      const xaxis = axisFor(gd, "x");
      const xOff = num(xaxis?._offset);
      if (!xaxis?.p2d || xOff === null) return null;
      return clampThresholds({ fc: Math.abs(xaxis.p2d(clientX - rect.left - xOff)), fdr: a.fdr0 });
    }
    const yaxis = axisFor(gd, "y");
    const yOff = num(yaxis?._offset);
    if (!yaxis?.p2d || yOff === null) return null;
    const dataY = yaxis.p2d(clientY - rect.top - yOff);
    return clampThresholds({ fc: a.fc0, fdr: 10 ** -Math.max(0, dataY) });
  };

  const onMove = (ev: MouseEvent) => {
    if (!dragging) return;
    const t = compute(dragging, ev.clientX, ev.clientY);
    if (t) stage(t);
  };

  const onUp = (ev: MouseEvent) => {
    const a = dragging;
    dragging = null;
    gd.style.cursor = "";
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (!a) return;
    // Commit the final value immediately (don't let the rAF coalescing drop the last move).
    const t = compute(a, ev.clientX, ev.clientY);
    if (t && deps.onThresholdChange) deps.onThresholdChange(t);
  };

  const onDown = (ev: MouseEvent) => {
    if (ev.button !== 0 || !deps.onThresholdChange) return;
    const hit = armed ?? hitTest(gd, deps.getSpec(), ev.clientX, ev.clientY);
    if (!hit) return;
    const cur = readThresholds(deps.getSpec());
    if (!cur) return;
    dragging = { kind: hit, fc0: cur.fc, fdr0: cur.fdr };
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

/**
 * Draggable dendrogram leaf tips (docs/figure-data-capabilities/dendrogram-tips-spec.md, the canvas half).
 *
 * Hover a leaf end-stub → it highlights (a thick accent line drawn as an HTML overlay; restyling the
 * trace can't colour ONE segment of a multi-segment polyline). Drag it out → the stub grows LIVE and
 * the rest of the tree keeps its shape — an instant, undoable figure-store edit, NO re-run. The tip
 * length is a `meta.selom.dendrogramTips` pref the canvas projects at render time (`applyDendrogramTips`);
 * a drag just writes that pref, so it shares state with the Style "Leaf tip length" lever.
 *
 * Why a meta-pref and not the trace coords: editing `data[i].x/y` is classified as a SERVER re-run AND
 * is insert-not-replace under JSON-Patch (`lib/patch.ts`) — the wall the heatmap rename hit. The pref +
 * render-time projection is the instant mechanism (mirrors `figure-model.ts::projectOverlay`).
 *
 * Imperative wiring (not Plotly `editable`, which would let data points move). It reads a few Plotly
 * axis internals (`gd._fullLayout`) to map pixels↔distance; every access is guarded so a version
 * mismatch degrades to "the stub just doesn't drag" (the lever is the fallback) — never a broken canvas.
 */

import type { FigureSpec } from "@/lib/figure-spec";
import type { FigureStore } from "@/hooks/use-figure-store";
import {
  hasColTree,
  hasRowTree,
  leafStubs,
  leafTipLength,
  maxDistance,
  setLeafTipOps,
  tipGap,
  type LeafStub,
  type TipAxis,
} from "@/lib/heatmap/dendrogram";

interface PlotlyAxis {
  _offset?: number;
  _length?: number;
  p2d?: (p: number) => number;
  d2p?: (d: number) => number;
}
interface GraphDiv extends HTMLElement {
  _fullLayout?: Record<string, PlotlyAxis>;
}

export interface DendrogramDragDeps {
  /** Latest spec (read fresh each gesture so a lever change / re-run is reflected). */
  getSpec: () => FigureSpec;
  /** The figure store — a drag is an INSTANT cosmetic edit (set live, flush one undo entry on release). */
  store: FigureStore;
  /** The canvas container, for placing the highlight overlay in its coordinate space. */
  container: HTMLElement | null;
}

/** Pixel proximity to arm/grab a stub (stubs are thin — a soft pull, you needn't land on the line). */
const GRAB_PX = 10;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The position + distance axes of a tree (col → x3/y3, row → x2/y2). */
function axesFor(gd: GraphDiv, axis: TipAxis): { pos: PlotlyAxis; dist: PlotlyAxis } | null {
  const fl = gd._fullLayout;
  const pos = fl?.[axis === "col" ? "xaxis3" : "yaxis2"];
  const dist = fl?.[axis === "col" ? "yaxis3" : "xaxis2"];
  if (!pos?.d2p || !dist?.d2p || num(pos._offset) === null || num(dist._offset) === null) return null;
  return { pos, dist };
}

/** Which trees are present (the drag only applies where a tree is drawn). */
function presentAxes(spec: FigureSpec): TipAxis[] {
  const out: TipAxis[] = [];
  if (hasColTree(spec)) out.push("col");
  if (hasRowTree(spec)) out.push("row");
  return out;
}

/** A stub resolved to container-relative pixels: the fixed position line + the segment's two ends. */
interface StubPx {
  axis: TipAxis;
  stub: LeafStub;
  posPx: number; // the constant coordinate (x for col, y for row)
  basePx: number; // the leaf-base end (its current displayed distance −e)
  mergePx: number; // the first-merge end (stub far end)
}

/** Resolve every present tree's stubs to container pixels (or [] if axes aren't readable). */
function allStubPx(gd: GraphDiv, spec: FigureSpec, container: HTMLElement | null): StubPx[] {
  const crect = container?.getBoundingClientRect();
  const grect = gd.getBoundingClientRect();
  if (!crect) return [];
  const dx = grect.left - crect.left;
  const dy = grect.top - crect.top;
  const out: StubPx[] = [];
  for (const axis of presentAxes(spec)) {
    const ax = axesFor(gd, axis);
    if (!ax) continue;
    const posOff = num(ax.pos._offset)!;
    const distOff = num(ax.dist._offset)!;
    for (const stub of leafStubs(spec, axis)) {
      const e = leafTipLength(spec, axis, stub.leafKey);
      const posPxAxis = ax.pos.d2p!(stub.pos);
      const basePxAxis = ax.dist.d2p!(-e); // current displayed leaf base
      const mergePxAxis = ax.dist.d2p!(stub.merge);
      if (axis === "col") {
        out.push({
          axis,
          stub,
          posPx: dx + posOff + posPxAxis,
          basePx: dy + distOff + basePxAxis,
          mergePx: dy + distOff + mergePxAxis,
        });
      } else {
        out.push({
          axis,
          stub,
          posPx: dy + posOff + posPxAxis,
          basePx: dx + distOff + basePxAxis,
          mergePx: dx + distOff + mergePxAxis,
        });
      }
    }
  }
  return out;
}

/** Distance (container px) from a client point to a stub segment. */
function distToStub(s: StubPx, container: HTMLElement, clientX: number, clientY: number): number {
  const crect = container.getBoundingClientRect();
  const cx = clientX - crect.left;
  const cy = clientY - crect.top;
  const lo = Math.min(s.basePx, s.mergePx);
  const hi = Math.max(s.basePx, s.mergePx);
  if (s.axis === "col") {
    const dyOut = cy < lo ? lo - cy : cy > hi ? cy - hi : 0;
    return Math.hypot(cx - s.posPx, dyOut);
  }
  const dxOut = cx < lo ? lo - cx : cx > hi ? cx - hi : 0;
  return Math.hypot(cy - s.posPx, dxOut);
}

/** Nearest stub within GRAB_PX of a client point, or null. */
function nearest(
  gd: GraphDiv,
  spec: FigureSpec,
  container: HTMLElement,
  clientX: number,
  clientY: number,
): StubPx | null {
  let best: StubPx | null = null;
  let bestD = GRAB_PX;
  for (const s of allStubPx(gd, spec, container)) {
    const d = distToStub(s, container, clientX, clientY);
    if (d < bestD) {
      bestD = d;
      best = s;
    }
  }
  return best;
}

/** A captured (frozen) distance-axis mapping so the drag stays direct even as the gutter range re-flows. */
interface Grab {
  axis: TipAxis;
  leafKey: string;
  /** value(clientPx) = v0 + slope·(clientPx − rectStart − offset). */
  v0: number;
  slope: number;
  offset: number;
  /** The drag client coordinate to read (clientY for col, clientX for row). */
  vertical: boolean;
  cap: number;
}

export function wireDendrogramTipDrag(gd: GraphDiv, deps: DendrogramDragDeps): () => void {
  const { container } = deps;
  let armed: StubPx | null = null;
  let grab: Grab | null = null;
  let raf = 0;
  let pendingExtra: number | null = null;

  // The highlight overlay — a thin accent line drawn over the hovered/dragged stub.
  const hi = document.createElement("div");
  hi.setAttribute("aria-hidden", "true");
  hi.style.cssText =
    "position:absolute;display:none;z-index:10;pointer-events:none;border-radius:2px;background:var(--primary,#6366f1);opacity:.85;box-shadow:0 0 0 1px rgba(255,255,255,.6)";
  container?.appendChild(hi);

  const drawHighlight = (s: StubPx | null) => {
    if (!s) {
      hi.style.display = "none";
      return;
    }
    const lo = Math.min(s.basePx, s.mergePx);
    const len = Math.abs(s.basePx - s.mergePx);
    hi.style.display = "block";
    if (s.axis === "col") {
      hi.style.left = `${s.posPx - 1.5}px`;
      hi.style.top = `${lo}px`;
      hi.style.width = "3px";
      hi.style.height = `${len}px`;
    } else {
      hi.style.left = `${lo}px`;
      hi.style.top = `${s.posPx - 1.5}px`;
      hi.style.width = `${len}px`;
      hi.style.height = "3px";
    }
  };

  /** Re-resolve the armed/dragged stub's pixels from the live spec and redraw the highlight. */
  const refreshHighlight = (axis: TipAxis, leafKey: string) => {
    const s = allStubPx(gd, deps.getSpec(), container).find(
      (x) => x.axis === axis && x.stub.leafKey === leafKey,
    );
    drawHighlight(s ?? null);
  };

  const flush = () => {
    raf = 0;
    if (pendingExtra === null || !grab) return;
    const extra = pendingExtra;
    pendingExtra = null;
    const spec = deps.getSpec();
    deps.store.set(setLeafTipOps(spec, grab.axis, grab.leafKey, extra));
    refreshHighlight(grab.axis, grab.leafKey);
  };

  /** Map a client coordinate → the new per-leaf extra (over the uniform lever), clamped ≥ 0. */
  const extraAt = (g: Grab, clientX: number, clientY: number): number => {
    const rect = gd.getBoundingClientRect();
    const px = (g.vertical ? clientY - rect.top : clientX - rect.left) - g.offset;
    const value = g.v0 + g.slope * px; // distance-axis value under the cursor
    const e = Math.min(g.cap, Math.max(0, -value)); // leaf bases live at −e; clamp to the gutter
    const gap = tipGap(deps.getSpec(), g.axis);
    return Math.max(0, e - gap); // the per-leaf override sits ON TOP of the lever
  };

  const onProximityMove = (ev: MouseEvent) => {
    if (grab || !container) return;
    const found = nearest(gd, deps.getSpec(), container, ev.clientX, ev.clientY);
    armed = found;
    drawHighlight(found);
    gd.style.cursor = found ? (found.axis === "col" ? "ns-resize" : "ew-resize") : "";
  };

  const onMove = (ev: MouseEvent) => {
    if (!grab) return;
    pendingExtra = extraAt(grab, ev.clientX, ev.clientY);
    if (!raf) raf = requestAnimationFrame(flush);
  };

  const onUp = (ev: MouseEvent) => {
    const g = grab;
    grab = null;
    gd.style.cursor = "";
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (raf) {
      cancelAnimationFrame(raf);
      raf = 0;
    }
    pendingExtra = null;
    if (!g) return;
    const spec = deps.getSpec();
    deps.store.set(setLeafTipOps(spec, g.axis, g.leafKey, extraAt(g, ev.clientX, ev.clientY)));
    deps.store.flush(); // one undo entry for the whole drag
    drawHighlight(null);
  };

  const onDown = (ev: MouseEvent) => {
    if (ev.button !== 0 || !container) return;
    const s = armed ?? nearest(gd, deps.getSpec(), container, ev.clientX, ev.clientY);
    if (!s) return;
    const ax = axesFor(gd, s.axis);
    const off = ax ? num(ax.dist._offset) : null;
    const len = ax ? num(ax.dist._length) : null;
    if (!ax || off === null || len === null || !ax.dist.p2d) return;
    // Freeze the distance-axis pixel↔value mapping at grab time → direct manipulation even though the
    // gutter range re-flows live as the stub grows.
    const v0 = ax.dist.p2d(0);
    const slope = (ax.dist.p2d(len) - v0) / len;
    grab = {
      axis: s.axis,
      leafKey: s.stub.leafKey,
      v0,
      slope,
      offset: off,
      vertical: s.axis === "col",
      cap: Math.max(0.001, maxDistance(deps.getSpec(), s.axis) * 3),
    };
    gd.style.cursor = "grabbing";
    // Block Plotly's own gesture for this drag (capture-phase, before Plotly's inner mousedown).
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("mouseup", onUp, true);
  };

  // Double-click a stub → reset it to the uniform lever (clear the per-leaf override).
  const onDblClick = (ev: MouseEvent) => {
    if (!container) return;
    const s = nearest(gd, deps.getSpec(), container, ev.clientX, ev.clientY);
    if (!s) return;
    ev.preventDefault();
    ev.stopPropagation();
    deps.store.commit(setLeafTipOps(deps.getSpec(), s.axis, s.stub.leafKey, 0));
  };

  const onLeave = () => {
    if (!grab) {
      armed = null;
      drawHighlight(null);
      gd.style.cursor = "";
    }
  };

  gd.addEventListener("mousemove", onProximityMove);
  gd.addEventListener("mouseleave", onLeave);
  gd.addEventListener("mousedown", onDown, true);
  gd.addEventListener("dblclick", onDblClick, true);

  return () => {
    gd.removeEventListener("mousemove", onProximityMove);
    gd.removeEventListener("mouseleave", onLeave);
    gd.removeEventListener("mousedown", onDown, true);
    gd.removeEventListener("dblclick", onDblClick, true);
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (raf) cancelAnimationFrame(raf);
    hi.remove();
    gd.style.cursor = "";
  };
}

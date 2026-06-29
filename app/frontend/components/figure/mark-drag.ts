/**
 * Draggable ERG landmark dots (docs/records/erg-manual-marks/spec.md R5, the canvas half).
 *
 * The a/b (and N1/P1) dots the skill draws on the trace grid become draggable: grab a dot and slide
 * it along the trace in TIME — it stays sticky to the line (snaps to the nearest sample, its height
 * rides the trace), with a crosshair + live t/amplitude readout. On drop it commits the new time via
 * `onMarkMove`, which sets `manual_marks` and re-runs (the amplitude is re-measured server-side, so
 * the drag moves live and the measured value updates on release). Shares state with the numeric
 * Marks panel — a drag and a typed time are the same edit.
 *
 * This is imperative Plotly wiring (the cosmetic editor keeps data-point edits server-side, so we
 * don't use Plotly's blanket `editable`). It reads a few Plotly axis internals to map pixels↔data;
 * every access is guarded so a version mismatch degrades to "the dot just doesn't drag" — never a
 * broken canvas — with the numeric panel as the always-present fallback.
 */
import type { FigureSpec, PlotlyTrace } from "@/lib/figure/figure-spec";
import { readSeededMarks, roleTag, snapToSample, type MarkRole } from "@/lib/erg/marks";

export interface Crosshair {
  /** Pixel position (relative to the canvas container) of the guide line + readout. */
  xPx: number;
  yTopPx: number;
  yBotPx: number;
  /** The live dot's position on the line (where it will land) — rendered as an overlay circle. */
  dotXPx: number;
  dotYPx: number;
  label: string;
}

interface PlotlyAxis {
  _offset?: number;
  _length?: number;
  p2d?: (p: number) => number;
  d2p?: (d: number) => number;
}
interface GraphDiv extends HTMLElement {
  on?: (ev: string, cb: (e: unknown) => void) => void;
  removeListener?: (ev: string, cb: (e: unknown) => void) => void;
  data?: PlotlyTrace[];
  _fullLayout?: Record<string, PlotlyAxis>;
}

/** Resolve a subplot axis object (with _offset/p2d/d2p) from a trace's axis ref ("x2" → xaxis2). */
function axisFor(gd: GraphDiv, ref: unknown, kind: "x" | "y"): PlotlyAxis | null {
  const r = typeof ref === "string" && ref ? ref : kind; // unset → primary ("x"/"y")
  const key = r.replace(kind, `${kind}axis`); // "x2" → "xaxis2", "x" → "xaxis"
  const ax = gd._fullLayout?.[key];
  return ax && typeof ax.p2d === "function" ? ax : null;
}
export interface MarkDragDeps {
  /** Latest spec (read fresh each gesture so re-runs are reflected). */
  getSpec: () => FigureSpec;
  /** Commit a moved mark → set manual_marks + re-run. Absent → dragging is disabled. */
  onMarkMove?: (segment: string, role: MarkRole, tMs: number) => void;
  /** Position the crosshair + live dot overlay (null clears it). */
  setCrosshair: (c: Crosshair | null) => void;
  /** The canvas container, for converting client pixels → container-relative. */
  container: HTMLElement | null;
}

interface Armed {
  trace: number;
  point: number;
  segment: string;
  role: MarkRole;
  xaxis: PlotlyAxis;
  yaxis: PlotlyAxis;
  lineX: number[];
  lineY: number[];
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const fmt = (v: number) => (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10);

/** Magnet radius (px): the pointer arms (and can grab) a dot within this distance of its centre, so
 *  you never have to click the dot exactly. Generous — the dot itself is ~7px; this gives a soft pull. */
const GRAB_RADIUS_PX = 24;

/** Map curveNumber → the draggable marks on that marker-dot trace (by point index). */
function draggableByTrace(spec: FigureSpec): Map<number, Map<number, { segment: string; role: MarkRole }>> {
  const out = new Map<number, Map<number, { segment: string; role: MarkRole }>>();
  for (const m of readSeededMarks(spec)) {
    if (m.trace === undefined || m.point === undefined) continue;
    const byPt = out.get(m.trace) ?? new Map();
    byPt.set(m.point, { segment: m.segment, role: m.role });
    out.set(m.trace, byPt);
  }
  return out;
}

/** The line trace that shares a marker trace's subplot axes (its samples = the snap grid + the y the dot rides). */
function lineFor(data: PlotlyTrace[], markerTrace: number): { x: number[]; y: number[] } | null {
  const mk = data[markerTrace];
  if (!mk) return null;
  for (let i = 0; i < data.length; i++) {
    const t = data[i];
    if (i === markerTrace || t?.xaxis !== mk.xaxis) continue;
    if (!String(t?.mode ?? "").includes("lines")) continue;
    if (Array.isArray(t.x) && Array.isArray(t.y)) return { x: t.x as number[], y: t.y as number[] };
  }
  return null;
}

/**
 * The nearest draggable dot within the magnet radius of a client pixel, fully resolved for dragging
 * (or null). Each dot's screen position is computed from its data coords via its subplot axes — so
 * arming doesn't depend on Plotly's near-exact hover hit-testing; the pointer is "pulled" to a dot
 * once it's within GRAB_RADIUS_PX. Degrades to null if the axis internals aren't readable.
 */
function nearestArmed(gd: GraphDiv, spec: FigureSpec, clientX: number, clientY: number): Armed | null {
  const byTrace = draggableByTrace(spec);
  if (byTrace.size === 0) return null;
  const rect = gd.getBoundingClientRect();
  const data = gd.data ?? [];
  let best: Armed | null = null;
  let bestD = GRAB_RADIUS_PX;
  for (const [cn, byPt] of byTrace) {
    const mk = data[cn];
    const xs = mk?.x;
    const ys = mk?.y;
    if (!Array.isArray(xs) || !Array.isArray(ys)) continue;
    const xaxis = axisFor(gd, mk?.xaxis, "x");
    const yaxis = axisFor(gd, mk?.yaxis, "y");
    const xOff = num(xaxis?._offset);
    const yOff = num(yaxis?._offset);
    if (!xaxis?.d2p || !yaxis?.d2p || xOff === null || yOff === null) continue;
    const line = lineFor(data, cn);
    if (!line) continue;
    for (const [pn, hit] of byPt) {
      const dx = (xs as number[])[pn];
      const dy = (ys as number[])[pn];
      if (typeof dx !== "number" || typeof dy !== "number") continue;
      const px = rect.left + xOff + xaxis.d2p(dx);
      const py = rect.top + yOff + yaxis.d2p(dy);
      const d = Math.hypot(clientX - px, clientY - py);
      if (d < bestD) {
        bestD = d;
        best = { trace: cn, point: pn, ...hit, xaxis, yaxis, lineX: line.x, lineY: line.y };
      }
    }
  }
  return best;
}

/**
 * Wire dot-dragging onto a Plotly graph div. Returns a cleanup function. Safe to call repeatedly
 * (each call cleans up the prior binding via the returned disposer in the caller).
 */
export function wireMarkDrag(gd: GraphDiv, deps: MarkDragDeps): () => void {
  let armed: Armed | null = null;
  let dragging: Armed | null = null;

  const clearArmed = () => {
    armed = null;
    if (!dragging) gd.style.cursor = "";
  };

  // Proximity arming (the magnet): on any pointer move over the graph, arm the NEAREST dot within
  // GRAB_RADIUS_PX of the cursor and show the grab cursor — so you don't have to land on the dot
  // exactly. Cleared when the pointer drifts away (or leaves the figure).
  const onProximityMove = (ev: MouseEvent) => {
    if (dragging || !deps.onMarkMove) return;
    const found = nearestArmed(gd, deps.getSpec(), ev.clientX, ev.clientY);
    if (found) {
      armed = found;
      gd.style.cursor = "grab";
    } else {
      clearArmed();
    }
  };

  // Resolve the snapped time + the dot's y on the line + the readout, from a client X pixel.
  const resolve = (a: Armed, clientX: number) => {
    const off = num(a.xaxis._offset);
    const rect = gd.getBoundingClientRect();
    if (off === null || !a.xaxis.p2d) return null;
    const dataX = a.xaxis.p2d(clientX - rect.left - off);
    const tMs = snapToSample(a.lineX, dataX);
    const idx = a.lineX.findIndex((v) => v === tMs);
    const y = idx >= 0 ? a.lineY[idx] : 0;
    return { tMs, y };
  };

  const onMove = (ev: MouseEvent) => {
    const a = dragging;
    if (!a) return;
    const r = resolve(a, ev.clientX);
    if (!r) return;
    // The live dot rides the line at the snapped time — drawn as an HTML overlay (no Plotly API, so
    // plotly.js never enters the SSR graph). The real dot re-draws at the committed time on re-run.
    const crect = deps.container?.getBoundingClientRect();
    const grect = gd.getBoundingClientRect();
    const xOff = num(a.xaxis._offset);
    const yOff = num(a.yaxis._offset);
    const yLen = num(a.yaxis._length);
    if (!crect || xOff === null || yOff === null || yLen === null || !a.xaxis.d2p || !a.yaxis.d2p) return;
    const dx = grect.left - crect.left;
    const dy = grect.top - crect.top;
    const xPx = dx + xOff + a.xaxis.d2p(r.tMs);
    deps.setCrosshair({
      xPx,
      yTopPx: dy + yOff,
      yBotPx: dy + yOff + yLen,
      dotXPx: xPx,
      dotYPx: dy + yOff + a.yaxis.d2p(r.y),
      label: `${roleTag(a.role)} · ${fmt(r.tMs)} ms · ${fmt(r.y)} µV`,
    });
  };

  const onUp = (ev: MouseEvent) => {
    const a = dragging;
    dragging = null;
    gd.style.cursor = "";
    deps.setCrosshair(null);
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (!a) return;
    const r = resolve(a, ev.clientX);
    if (r) deps.onMarkMove?.(a.segment, a.role, r.tMs);
  };

  const onDown = (ev: MouseEvent) => {
    if (ev.button !== 0 || !deps.onMarkMove) return;
    // Magnet on click too: if no dot is armed from a prior move, do a fresh proximity check at the
    // press point — so a single click near a dot grabs it without needing a hover first.
    const a = armed ?? nearestArmed(gd, deps.getSpec(), ev.clientX, ev.clientY);
    if (!a) return;
    dragging = a;
    gd.style.cursor = "grabbing";
    // Block Plotly's own zoom/pan for this gesture — capture-phase on the gd fires before Plotly's
    // mousedown on the inner drag rect, and stopImmediatePropagation keeps it from starting a box-zoom.
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("mouseup", onUp, true);
    onMove(ev); // place the crosshair immediately
  };

  gd.addEventListener("mousemove", onProximityMove);
  gd.addEventListener("mouseleave", clearArmed);
  gd.addEventListener("mousedown", onDown, true);

  return () => {
    gd.removeEventListener("mousemove", onProximityMove);
    gd.removeEventListener("mouseleave", clearArmed);
    gd.removeEventListener("mousedown", onDown, true);
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    deps.setCrosshair(null);
  };
}

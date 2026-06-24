/**
 * Draggable ERG landmark dots (docs/erg-manual-marks/spec.md R5, the canvas half).
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
import type { FigureSpec, PlotlyTrace } from "@/lib/figure-spec";
import { readSeededMarks, snapToSample, type MarkRole } from "@/lib/erg/marks";

export interface Crosshair {
  /** Pixel position (relative to the canvas container) of the guide line + readout. */
  xPx: number;
  yTopPx: number;
  yBotPx: number;
  label: string;
}

interface PlotlyAxis {
  _offset?: number;
  _length?: number;
  p2d?: (p: number) => number;
  d2p?: (d: number) => number;
}
interface HoverPoint {
  curveNumber?: number;
  pointNumber?: number;
  xaxis?: PlotlyAxis;
  yaxis?: PlotlyAxis;
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
type PlotlyApi = { restyle: (gd: GraphDiv, update: Record<string, unknown>, traces: number[]) => void };

export interface MarkDragDeps {
  /** Latest spec (read fresh each gesture so re-runs are reflected). */
  getSpec: () => FigureSpec;
  /** Plotly (for the live restyle), read lazily — may still be loading when the drag is wired. */
  getPlotly: () => PlotlyApi | null;
  /** Commit a moved mark → set manual_marks + re-run. Absent → dragging is disabled. */
  onMarkMove?: (segment: string, role: MarkRole, tMs: number) => void;
  /** Position the crosshair overlay (null clears it). */
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

  const onHover = (e: unknown) => {
    if (dragging || !deps.onMarkMove) return;
    const pts = (e as { points?: HoverPoint[] })?.points ?? [];
    const byTrace = draggableByTrace(deps.getSpec());
    // Scan ALL hovered points (a dot sits ON the line, so points[0] may be the line, not the dot).
    for (const pt of pts) {
      const cn = pt?.curveNumber;
      const pn = pt?.pointNumber;
      if (cn === undefined || pn === undefined) continue;
      const hit = byTrace.get(cn)?.get(pn);
      if (!hit) continue;
      const mk = (gd.data ?? [])[cn];
      const xaxis = axisFor(gd, mk?.xaxis, "x");
      const yaxis = axisFor(gd, mk?.yaxis, "y");
      const line = lineFor(gd.data ?? [], cn);
      if (!xaxis || !yaxis || !line) continue;
      armed = { trace: cn, point: pn, ...hit, xaxis, yaxis, lineX: line.x, lineY: line.y };
      gd.style.cursor = "grab";
      return;
    }
    clearArmed();
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
    // Move the dot live (sticky to the line); the value re-measures on drop.
    const tr = (gd.data?.[a.trace] ?? {}) as { x?: number[]; y?: number[] };
    const x = Array.isArray(tr.x) ? [...tr.x] : [];
    const y = Array.isArray(tr.y) ? [...tr.y] : [];
    x[a.point] = r.tMs;
    y[a.point] = r.y;
    try {
      deps.getPlotly()?.restyle(gd, { x: [x], y: [y] }, [a.trace]);
    } catch {
      /* a transient Plotly state — skip this frame */
    }
    // Crosshair overlay (container-relative pixels).
    const crect = deps.container?.getBoundingClientRect();
    const grect = gd.getBoundingClientRect();
    const yOff = num(a.yaxis._offset);
    const yLen = num(a.yaxis._length);
    if (crect && yOff !== null && yLen !== null && a.xaxis.d2p && num(a.xaxis._offset) !== null) {
      const xPxGd = num(a.xaxis._offset)! + a.xaxis.d2p(r.tMs);
      deps.setCrosshair({
        xPx: grect.left - crect.left + xPxGd,
        yTopPx: grect.top - crect.top + yOff,
        yBotPx: grect.top - crect.top + yOff + yLen,
        label: `${fmt(r.tMs)} ms · ${fmt(r.y)} µV`,
      });
    }
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
    if (!armed || ev.button !== 0 || !deps.onMarkMove) return;
    dragging = armed;
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

  gd.on?.("plotly_hover", onHover);
  gd.on?.("plotly_unhover", clearArmed);
  gd.addEventListener("mousedown", onDown, true);

  return () => {
    gd.removeListener?.("plotly_hover", onHover);
    gd.removeListener?.("plotly_unhover", clearArmed);
    gd.removeEventListener("mousedown", onDown, true);
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    deps.setCrosshair(null);
  };
}

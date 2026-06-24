/**
 * FigureModel — the skills-agnostic bridge between a Plotly spec and the editor.
 *
 * The inspector must adapt to *any* skill's figure (marker scatter, line grid,
 * heatmap, bar, sankey, radar, …) — not assume "markers". The agnostic floor is
 * INFERENCE: everything the editor needs is derived from the raw Plotly spec, so a
 * figure from a third-party / future skill that emits nothing special still gets a
 * correct editor. Skills MAY optionally sharpen it by stamping `layout.meta.selom`
 * hints (render-inert; Plotly ignores `meta`), but the editor never depends on them.
 *
 * This module is the ONE place that answers, per trace: what kind is it, which colour
 * channel actually paints it (line.color vs marker.color — the ERG no-op bug), and how
 * traces group into editable series (42 ERG traces → 6 conditions). See
 * docs/figure-editor-contract/spec.md §3.1.
 *
 * Runtime note: this imports only TYPES from ./figure-spec, so figure-spec.ts can
 * import inferTraceKind() from here without a runtime import cycle.
 */
import type { FigureSpec, PlotlyTrace } from "./figure-spec";
import { set, type Operation } from "./patch";

export type TraceKind =
  | "markerScatter"
  | "lineScatter"
  | "lineMarkerScatter"
  | "heatmap"
  | "bar"
  | "box"
  | "violin"
  | "sankey"
  | "polar"
  | "network"
  | "other";

const HEATMAP_TYPES = new Set(["heatmap", "heatmapgl", "contour", "contourcarpet"]);
const SCATTER_TYPES = new Set(["scatter", "scattergl", "scatterternary", "scattercarpet"]);

/** Classify one trace from its `type` + `mode` (+ which sub-objects it carries). */
export function inferTraceKind(trace: PlotlyTrace): TraceKind {
  const type = String(trace?.type ?? "scatter").toLowerCase();
  if (HEATMAP_TYPES.has(type)) return "heatmap";
  if (type === "bar") return "bar";
  if (type === "box") return "box";
  if (type === "violin") return "violin";
  if (type === "sankey") return "sankey";
  if (type.startsWith("scatterpolar") || type === "barpolar") return "polar";
  if (SCATTER_TYPES.has(type)) {
    const mode = String(trace?.mode ?? "").toLowerCase();
    const hasLines = mode.includes("lines");
    const hasMarkers = mode.includes("markers");
    if (hasLines && hasMarkers) return "lineMarkerScatter";
    if (hasLines) return "lineScatter";
    if (hasMarkers) return "markerScatter";
    // mode unset → infer from which sub-object the trace carries; default to markers
    // (Plotly's own default for a small scatter and the editor's historical assumption).
    if (trace?.line && !trace?.marker) return "lineScatter";
    return "markerScatter";
  }
  return "other";
}

/** The colour channels that actually paint a trace of this kind (write order). */
function colorChannelsFor(kind: TraceKind): string[] {
  switch (kind) {
    case "lineScatter":
      return ["line"];
    case "lineMarkerScatter":
      return ["line", "marker"];
    case "markerScatter":
    case "bar":
    case "box":
    case "violin":
      return ["marker"];
    default:
      // heatmap / sankey / polar / network / other → no single solid per-trace colour
      return [];
  }
}

/** A trace's solid colour read from its real channel: string hex, or null (per-point / unset). */
function readTraceColor(
  trace: PlotlyTrace,
  channels: string[],
): { color: string | null; perPoint: boolean } {
  for (const ch of channels) {
    const raw = (trace?.[ch] as { color?: unknown } | undefined)?.color;
    if (Array.isArray(raw)) return { color: null, perPoint: true };
    if (typeof raw === "string") return { color: raw, perPoint: false };
  }
  return { color: null, perPoint: false };
}

/** An editable series — one or more traces that share an identity (the unit the panel edits). */
export interface Series {
  key: string;
  label: string;
  traceIndices: number[];
  /** Channels to write a colour to (e.g. ["line"] for ERG, ["marker"] for a scatter); [] = none. */
  colorChannels: string[];
  /** JSON-pointer to the first trace's colour (for reading), or null. */
  colorPath: string | null;
  /** Current resolved hex colour, or null (per-point / colorscale / unset). */
  color: string | null;
  /** Colour is a per-point array → can't show a single swatch. */
  perPoint: boolean;
  visible: boolean;
}

export type PrimitiveKind = "scalebar" | "threshold" | "colorbar" | "annotationSet" | "subplotGrid";

export interface FigurePrimitive {
  kind: PrimitiveKind;
  label: string;
}

/**
 * An editable scale-bar primitive, resolved from the skill's render-inert
 * `meta.selom.primitives` hint (deterministic shape/annotation indices — far safer than
 * guessing among `layout.shapes`). The editor can show/hide and resize it (change the
 * denoted length); the bar stays accurate because it is one paper-referenced pair sized to
 * the shared data→paper mapping. Present only when the skill stamps the hint (the trace-grid
 * does); a figure without the hint still flags `capabilities.scalebar` but isn't index-editable.
 */
export interface Scalebar {
  metaIdx: number; // index in layout.meta.selom.primitives (kept in sync on resize)
  shapeIdx: [number, number]; // [vertical (amplitude), horizontal (time)]
  annoIdx: [number, number]; // [vertical label, horizontal label]
  xLen: number;
  xUnit: string;
  yLen: number;
  yUnit: string;
  visible: boolean;
}

/** Plotly drag mode the editor applies; `false` = no-op (a stray drag does nothing). */
export type Dragmode = false | "select" | "pan" | "zoom";

/**
 * Resolved plot-area gesture config (generalization-spec §A). Comes from the figure's declared
 * `meta.selom.capabilities.gesture` over a GLOBAL no-op floor: a figure that declares nothing gets
 * `dragmode:false` (a stray drag does nothing), zoom/pan as modebar buttons, and wheel-zoom off. A
 * figure opts into a drag mode (e.g. box-zoom) by declaring `gesture.default`.
 */
export interface GestureConfig {
  /** Plotly `layout.dragmode` to apply. The GLOBAL default is `false` (no-op): a stray plot-area
   *  drag does nothing; zoom/pan are deliberate modebar buttons. A figure may opt INTO a drag mode
   *  via `meta.selom.capabilities.gesture.default` (generalization-spec §A). */
  dragmode: Dragmode;
  /** Keep zoom + pan as modebar buttons (a mode the user presses). Default true. */
  zoomTools: boolean;
  /** Plotly `config.scrollZoom`. Default `false` (wheel-zoom off app-wide); a figure may set true. */
  scrollZoom: boolean;
}

export interface FigureModel {
  traceKinds: TraceKind[];
  series: Series[];
  primitives: FigurePrimitive[];
  /** The index-editable scale bar (from the meta.selom hint), or null. Drives the Marks panel. */
  scalebar: Scalebar | null;
  capabilities: {
    markers: boolean;
    lines: boolean;
    colorscale: boolean;
    colorbar: boolean;
    scalebar: boolean;
    subplotRanges: boolean;
    /** Editable ERG landmark dots (a/b, N1/P1) → dot-drag + numeric Marks editor. Declared by the
     *  skill in meta.selom.capabilities.tools.landmarkMarks; falls back to "seeded marks present"
     *  during migration so today's ERG figures keep working before they declare it. */
    landmarkMarks: boolean;
    /** A tunable model fit the editor can expose (Naka-Rushton on intensity-response), or null.
     *  Schema-reserved in v1 — the fit-knobs panel is a follow-on. */
    modelFit: "naka_rushton" | null;
    /** Volcano FC/p-value threshold direct-manipulation (draggable lines + numeric editor + live
     *  re-bucket). Declared by the skill in meta.selom.capabilities.tools.thresholds (declared-only,
     *  no inference fallback). Gates lib/volcano/thresholds.ts + threshold-drag + threshold-editor. */
    thresholds: boolean;
    /** Gene labelling (generalization-spec §H): click a plotted point to pin its gene as a text
     *  annotation, and a Label toggle in the Statistics table — one shared set, instant (rides
     *  undo/JSON-Patch), no re-run. Declared by the skill (volcano) in
     *  meta.selom.capabilities.tools.geneLabels (declared-only). Needs per-point gene `customdata`. */
    geneLabels: boolean;
  };
  /** Resolved plot-area gesture config (dragmode / scrollZoom / zoom tools). */
  gesture: GestureConfig;
  /** Trace indices for the conditional Style groups (marker controls, line width, heatmap colorscale). */
  markerTraceIndices: number[];
  lineTraceIndices: number[];
  heatmapTraceIndices: number[];
  /** Small-multiples grid kind from the skill hint (e.g. "trace_grid"), or null. */
  figureKind: string | null;
  /** Current layout view for a grid-capable figure: "grid" (default) | "overlay". */
  layoutMode: "grid" | "overlay";
  /** The figure can toggle grid ↔ overlay (a trace-grid small-multiples figure). */
  overlayCapable: boolean;
  /** Overlay-view axis visibility (true = shown). Drives the hide/show toggles. */
  overlayAxes: { x: boolean; y: boolean };
}

// A trailing index/intensity token ("g1", "Group 3", "rep2", " 7", "#4") — stripped to find a
// shared series prefix. Only consulted alongside identical colour, so distinctly-coloured
// clusters ("Cluster 1"/"Cluster 2") never wrongly merge.
const INDEX_SUFFIX = /[\s_:#-]*(?:group|grp|rep|g|r)?\s*\d+\s*$/i;

function namePrefix(name: string): string {
  const stripped = name.replace(INDEX_SUFFIX, "").trim();
  return stripped || name;
}

interface TraceInfo {
  index: number;
  kind: TraceKind;
  channels: string[];
  color: string | null;
  perPoint: boolean;
  name: string;
  legendgroup: string | null;
  visible: boolean;
}

/**
 * The declared per-figure editing contract (docs/figure-data-capabilities/spec.md §1). Render-inert;
 * every field optional; absent → the inferred floor / today's behaviour (no regression). Declared wins.
 */
interface SelomCapabilities {
  /** Plot-area gesture config. Absent → keep Plotly's default (box-zoom). */
  gesture?: {
    /** Default dragmode. "none" → a stray drag is a no-op (ERG). */
    default?: "none" | "select" | "pan" | "zoom";
    /** Keep zoom + pan available as modebar buttons. Default true. */
    zoomTools?: boolean;
    /** Wheel-zoom. ERG → true (cartesian's default is off, so this must be set to keep it). */
    scrollZoom?: boolean;
  };
  /** Data-coupled tool gates (default false → a figure that declares nothing gets none of these). */
  tools?: {
    landmarkMarks?: boolean;
    modelFit?: "naka_rushton" | null;
    scaleBar?: boolean;
    /** Volcano FC/p-value threshold direct-manipulation → draggable threshold lines + numeric editor. */
    thresholds?: boolean;
    /** Gene labelling → click-to-label a point + a Statistics-table Label toggle (generalization-spec §H). */
    geneLabels?: boolean;
  };
}

/** Optional skill-stamped hint (render-inert; lives at layout.meta.selom). */
interface SelomHint {
  figureKind?: string;
  /** The active layout view for a small-multiples figure: "grid" (default) | "overlay". */
  layoutMode?: string;
  /** Overlay-view editor prefs: hide the time (x) / amplitude (y) axis. Default visible. */
  overlayHideX?: boolean;
  overlayHideY?: boolean;
  series?: { label: string; traceIndices: number[]; colorPath?: string }[];
  primitives?: { kind: PrimitiveKind; [k: string]: unknown }[];
  /** The declared per-figure editing contract (gesture + data-coupled tool gates). */
  capabilities?: SelomCapabilities;
}

/** Migration fallback for landmarkMarks: are seeded landmark dots present on this figure? */
function hasSeededMarks(spec: FigureSpec): boolean {
  const marks = (spec?.layout?.meta as { selom?: { marks?: unknown } } | undefined)?.selom?.marks;
  return Array.isArray(marks) && marks.length > 0;
}

/** Resolve the declared editing contract over the inferred floor (declared wins). */
function resolveContract(
  spec: FigureSpec,
  hint: SelomHint | null,
  inferredScalebar: boolean,
): {
  landmarkMarks: boolean;
  modelFit: "naka_rushton" | null;
  thresholds: boolean;
  geneLabels: boolean;
  scalebar: boolean;
  gesture: GestureConfig;
} {
  const caps = hint?.capabilities;
  const landmarkMarks = caps?.tools?.landmarkMarks === true || hasSeededMarks(spec);
  const modelFit = caps?.tools?.modelFit === "naka_rushton" ? "naka_rushton" : null;
  // Declared-only (no inference fallback): the volcano stamps these explicitly via _capabilities.py.
  const thresholds = caps?.tools?.thresholds === true;
  const geneLabels = caps?.tools?.geneLabels === true;
  const scalebar = inferredScalebar || caps?.tools?.scaleBar === true;

  const g = caps?.gesture;
  // The GLOBAL gesture default is no-op (generalization-spec §A): absent OR "none" → dragmode:false,
  // so a stray plot-area drag never box-zooms; zoom/pan are deliberate modebar buttons and wheel-zoom
  // is off app-wide. A figure opts INTO a drag mode by declaring gesture.default ∈ {zoom,pan,select}.
  const dragmode: Dragmode =
    g?.default === "select" || g?.default === "pan" || g?.default === "zoom" ? g.default : false;
  const gesture: GestureConfig = {
    dragmode,
    zoomTools: g?.zoomTools !== false,
    scrollZoom: g?.scrollZoom === true,
  };
  return { landmarkMarks, modelFit, thresholds, geneLabels, scalebar, gesture };
}

function readHint(spec: FigureSpec): SelomHint | null {
  const meta = spec?.layout?.meta as { selom?: SelomHint } | undefined;
  const h = meta?.selom;
  return h && typeof h === "object" ? h : null;
}

function traceVisible(t: PlotlyTrace): boolean {
  return t?.visible !== false && t?.visible !== "legendonly";
}

/** Build a Series from a set of trace infos that share an identity. */
function makeSeries(key: string, label: string, members: TraceInfo[]): Series {
  const first = members[0];
  const colorChannels = first.channels;
  const colorPath =
    colorChannels.length > 0 ? `/data/${first.index}/${colorChannels[0]}/color` : null;
  return {
    key,
    label,
    traceIndices: members.map((m) => m.index),
    colorChannels,
    colorPath,
    color: first.color,
    perPoint: first.perPoint,
    // A series reads as visible if ANY of its traces is visible.
    visible: members.some((m) => m.visible),
  };
}

/**
 * Derive the full editor model from a spec. Pure + cheap; callers memoise on `spec`. Tolerates a
 * null/undefined spec (every access is guarded) → an empty model, so a not-yet-rendered figure is safe.
 */
export function deriveFigureModel(specInput: FigureSpec | null | undefined): FigureModel {
  const spec: FigureSpec = specInput ?? ({ data: [], layout: {} } as unknown as FigureSpec);
  const data: PlotlyTrace[] = Array.isArray(spec?.data) ? spec.data : [];
  const infos: TraceInfo[] = data.map((t, index) => {
    const kind = inferTraceKind(t);
    const channels = colorChannelsFor(kind);
    const { color, perPoint } = readTraceColor(t, channels);
    return {
      index,
      kind,
      channels,
      color,
      perPoint,
      name: typeof t?.name === "string" && t.name ? t.name : `Trace ${index + 1}`,
      legendgroup: typeof t?.legendgroup === "string" && t.legendgroup ? t.legendgroup : null,
      visible: traceVisible(t),
    };
  });

  const traceKinds = infos.map((i) => i.kind);
  const series = groupSeries(spec, infos);
  const { capabilities: inferred, primitives, markerTraceIndices, lineTraceIndices, heatmapTraceIndices } =
    deriveCapabilities(spec, infos);
  const scalebar = deriveScalebar(spec);

  const hint = readHint(spec);
  // Resolve the declared editing contract (meta.selom.capabilities) over the inferred floor.
  const contract = resolveContract(spec, hint, inferred.scalebar);
  const capabilities = {
    ...inferred,
    scalebar: contract.scalebar,
    landmarkMarks: contract.landmarkMarks,
    modelFit: contract.modelFit,
    thresholds: contract.thresholds,
    geneLabels: contract.geneLabels,
  };

  const figureKind = typeof hint?.figureKind === "string" ? hint.figureKind : null;
  const layoutMode = hint?.layoutMode === "overlay" ? "overlay" : "grid";
  const overlayCapable = figureKind === "trace_grid";
  const overlayAxes = { x: hint?.overlayHideX !== true, y: hint?.overlayHideY !== true };

  return {
    traceKinds,
    series,
    primitives,
    scalebar,
    capabilities,
    gesture: contract.gesture,
    markerTraceIndices,
    lineTraceIndices,
    heatmapTraceIndices,
    figureKind,
    layoutMode,
    overlayCapable,
    overlayAxes,
  };
}

/** Resolve the index-editable scale bar from the meta.selom hint (+ its live visibility). */
function deriveScalebar(spec: FigureSpec): Scalebar | null {
  const hint = readHint(spec);
  const prims = hint?.primitives ?? [];
  const idx = prims.findIndex((p) => p.kind === "scalebar");
  if (idx < 0) return null;
  const p = prims[idx] as Record<string, unknown>;
  const shapeIdx = p.shapeIdx as number[] | undefined;
  const annoIdx = p.annoIdx as number[] | undefined;
  if (!Array.isArray(shapeIdx) || shapeIdx.length < 2) return null;
  const shapes = (spec?.layout?.shapes as { visible?: boolean }[]) ?? [];
  const visible = shapes[shapeIdx[0]]?.visible !== false;
  return {
    metaIdx: idx,
    shapeIdx: [shapeIdx[0], shapeIdx[1]],
    annoIdx: Array.isArray(annoIdx) && annoIdx.length >= 2 ? [annoIdx[0], annoIdx[1]] : [-1, -1],
    xLen: typeof p.xLen === "number" ? p.xLen : 0,
    xUnit: typeof p.xUnit === "string" ? p.xUnit : "",
    yLen: typeof p.yLen === "number" ? p.yLen : 0,
    yUnit: typeof p.yUnit === "string" ? p.yUnit : "",
    visible,
  };
}

/** Group traces into editable series: meta.selom.series → legendgroup → inference. */
function groupSeries(spec: FigureSpec, infos: TraceInfo[]): Series[] {
  if (infos.length === 0) return [];

  // (1) Explicit skill hint wins — deterministic.
  const hint = readHint(spec);
  if (hint?.series?.length) {
    const byIndex = new Map(infos.map((i) => [i.index, i]));
    const out: Series[] = [];
    const claimed = new Set<number>();
    for (const h of hint.series) {
      const members = (h.traceIndices ?? []).map((i) => byIndex.get(i)).filter(Boolean) as TraceInfo[];
      if (!members.length) continue;
      members.forEach((m) => claimed.add(m.index));
      out.push(makeSeries(`hint:${h.label}`, h.label, members));
    }
    // Any trace the hint didn't cover → one series each (never silently dropped).
    for (const info of infos) {
      if (!claimed.has(info.index)) out.push(makeSeries(`solo:${info.index}`, info.name, [info]));
    }
    if (out.length) return out;
  }

  // (2) legendgroup, when the skill set it (the trace-grid will, P3).
  if (infos.some((i) => i.legendgroup)) {
    const groups = new Map<string, TraceInfo[]>();
    for (const info of infos) {
      const key = info.legendgroup ?? `solo:${info.index}`;
      (groups.get(key) ?? groups.set(key, []).get(key)!).push(info);
    }
    return [...groups.entries()].map(([key, members]) =>
      makeSeries(
        key,
        members[0].legendgroup ?? members[0].name,
        members,
      ),
    );
  }

  // (3) Inference fallback: merge traces of the same KIND that share an identical solid
  // COLOUR *and* name-prefix. Colour-identity is required, so distinctly-coloured clusters
  // never merge; the prefix keeps two same-colour-but-different conditions apart (the ERG
  // PDE6B/stuffer pair both render grey but are separate experimental arms).
  const groups = new Map<string, TraceInfo[]>();
  const order: string[] = [];
  for (const info of infos) {
    const key =
      info.color && !info.perPoint
        ? `${info.kind}|${info.color.toLowerCase()}|${namePrefix(info.name)}`
        : `solo:${info.index}`;
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key)!.push(info);
  }
  return order.map((key) => {
    const members = groups.get(key)!;
    const label = members.length > 1 ? namePrefix(members[0].name) : members[0].name;
    return makeSeries(key, label, members);
  });
}

/** Detect a paper-referenced L-shaped scale bar: ≥2 paper/paper line shapes (the trace-grid emits exactly this). */
function hasScalebar(spec: FigureSpec, hint: SelomHint | null): boolean {
  if (hint?.primitives?.some((p) => p.kind === "scalebar")) return true;
  const shapes = (spec?.layout?.shapes as { type?: string; xref?: string; yref?: string }[]) ?? [];
  const paperLines = shapes.filter(
    (s) => s?.type === "line" && s?.xref === "paper" && s?.yref === "paper",
  );
  return paperLines.length >= 2;
}

/** Does any trace paint colour via a colorscale (heatmap z, or a numeric marker.color array)? */
function hasColorscale(data: PlotlyTrace[]): boolean {
  return data.some((t) => {
    const kind = inferTraceKind(t);
    if (kind === "heatmap") return true;
    const m = t?.marker as { color?: unknown; colorscale?: unknown } | undefined;
    return !!m && Array.isArray(m.color) && m.colorscale != null;
  });
}

function deriveCapabilities(spec: FigureSpec, infos: TraceInfo[]) {
  const data: PlotlyTrace[] = Array.isArray(spec?.data) ? spec.data : [];
  const hint = readHint(spec);

  const markerTraceIndices = infos
    .filter((i) => i.kind === "markerScatter" || i.kind === "lineMarkerScatter")
    .map((i) => i.index);
  const lineTraceIndices = infos
    .filter((i) => i.kind === "lineScatter" || i.kind === "lineMarkerScatter")
    .map((i) => i.index);
  const heatmapTraceIndices = infos.filter((i) => i.kind === "heatmap").map((i) => i.index);

  // Multiple subplot axes (xaxis2/xaxis3/…) ⇒ a small-multiples grid.
  const layout = spec?.layout ?? {};
  const axisKeys = Object.keys(layout).filter((k) => /^xaxis\d+$/.test(k));
  const subplotRanges = axisKeys.length > 0;

  const colorbar = findColorbarLike(data);
  const scalebar = hasScalebar(spec, hint);

  const primitives: FigurePrimitive[] = [];
  if (scalebar) primitives.push({ kind: "scalebar", label: "Scale bar" });
  if (colorbar) primitives.push({ kind: "colorbar", label: "Colour bar" });
  if (subplotRanges) primitives.push({ kind: "subplotGrid", label: "Subplot grid" });
  const annoCount = Array.isArray(layout.annotations) ? layout.annotations.length : 0;
  if (annoCount > 0) primitives.push({ kind: "annotationSet", label: `Annotations · ${annoCount}` });

  return {
    capabilities: {
      markers: markerTraceIndices.length > 0,
      lines: lineTraceIndices.length > 0,
      colorscale: hasColorscale(data),
      colorbar,
      scalebar,
      subplotRanges,
    },
    primitives,
    markerTraceIndices,
    lineTraceIndices,
    heatmapTraceIndices,
  };
}

/** Light colour-bar presence check (kept independent of figure-spec's pointer helper). */
function findColorbarLike(data: PlotlyTrace[]): boolean {
  return data.some((t) => {
    const heatmapLike =
      t?.type === "heatmap" || t?.type === "heatmapgl" || t?.type === "contour" || !!t?.colorbar;
    if (heatmapLike && t?.showscale !== false) return true;
    const m = t?.marker as
      | { showscale?: unknown; colorbar?: unknown; colorscale?: unknown; color?: unknown }
      | undefined;
    return (
      !!m &&
      m.showscale !== false &&
      (!!m.colorbar || !!m.showscale || (m.colorscale != null && m.color !== undefined))
    );
  });
}

/** Ops to recolour an entire series via its real channel(s) on every member trace. */
export function seriesColorOps(series: Series, color: string): Operation[] {
  const ops: Operation[] = [];
  for (const i of series.traceIndices) {
    for (const ch of series.colorChannels) {
      ops.push(set(`/data/${i}/${ch}/color`, color));
    }
  }
  return ops;
}

/** Ops to set visibility on every trace in a series (toggles the whole condition at once). */
export function seriesVisibilityOps(series: Series, visible: boolean): Operation[] {
  return series.traceIndices.map((i) => set(`/data/${i}/visible`, visible ? true : "legendonly"));
}

/** Resolve which series a clicked Plotly curve belongs to (click-to-select, P3). */
export function seriesForTrace(model: FigureModel, traceIndex: number): Series | null {
  return model.series.find((s) => s.traceIndices.includes(traceIndex)) ?? null;
}

// --- scale-bar primitive ops (P3 §3.5) -------------------------------------------------

/** Show/hide the scale bar — toggles `visible` on both line shapes + both unit labels. */
export function scalebarVisibilityOps(sb: Scalebar, visible: boolean): Operation[] {
  const ops: Operation[] = [];
  for (const i of sb.shapeIdx) ops.push(set(`/layout/shapes/${i}/visible`, visible));
  for (const i of sb.annoIdx) if (i >= 0) ops.push(set(`/layout/annotations/${i}/visible`, visible));
  return ops;
}

/** Format a denoted length for the unit label. JS numbers already drop a trailing `.0`. */
function fmtNum(n: number): string {
  return String(n);
}

/**
 * Resize the scale bar = change the *denoted* length (e.g. a 200 µV bar → 100 µV). The drawn
 * paper length scales proportionally from the current geometry, the unit label is rewritten,
 * and the label is recentred. `meta.selom` is kept in sync (render-inert) so repeated resizes
 * stay proportional. Returns [] if the geometry can't be read. `axis` selects which arm.
 */
export function scalebarResizeOps(
  spec: FigureSpec,
  sb: Scalebar,
  axis: "x" | "y",
  newLen: number,
): Operation[] {
  if (!(newLen > 0)) return [];
  const shapes = (spec?.layout?.shapes as Record<string, number>[]) ?? [];
  const annos = (spec?.layout?.annotations as Record<string, unknown>[]) ?? [];
  const ops: Operation[] = [];
  if (axis === "y") {
    const s = shapes[sb.shapeIdx[0]];
    if (!s || sb.yLen <= 0) return [];
    const y0 = Number(s.y0);
    const curLen = Number(s.y1) - y0;
    const newPaper = curLen * (newLen / sb.yLen);
    ops.push(set(`/layout/shapes/${sb.shapeIdx[0]}/y1`, round5(y0 + newPaper)));
    if (sb.annoIdx[0] >= 0 && annos[sb.annoIdx[0]]) {
      ops.push(set(`/layout/annotations/${sb.annoIdx[0]}/text`, `${fmtNum(newLen)} ${sb.yUnit}`));
      ops.push(set(`/layout/annotations/${sb.annoIdx[0]}/y`, round5(y0 + newPaper / 2)));
    }
    ops.push(set(`/layout/meta/selom/primitives/${sb.metaIdx}/yLen`, newLen));
  } else {
    const s = shapes[sb.shapeIdx[1]];
    if (!s || sb.xLen <= 0) return [];
    const x0 = Number(s.x0);
    const curLen = Number(s.x1) - x0;
    const newPaper = curLen * (newLen / sb.xLen);
    ops.push(set(`/layout/shapes/${sb.shapeIdx[1]}/x1`, round5(x0 + newPaper)));
    if (sb.annoIdx[1] >= 0 && annos[sb.annoIdx[1]]) {
      ops.push(set(`/layout/annotations/${sb.annoIdx[1]}/text`, `${fmtNum(newLen)} ${sb.xUnit}`));
      ops.push(set(`/layout/annotations/${sb.annoIdx[1]}/x`, round5(x0 + newPaper / 2)));
    }
    ops.push(set(`/layout/meta/selom/primitives/${sb.metaIdx}/xLen`, newLen));
  }
  return ops;
}

function round5(n: number): number {
  return Math.round(n * 1e5) / 1e5;
}

// --- annotations (threshold lines / labels) — list + show/hide/edit (P3 §3.5) -----------

export interface AnnotationItem {
  index: number;
  text: string;
  visible: boolean;
}

/** Every layout annotation as an editable item (text + visibility). */
export function annotationItems(spec: FigureSpec): AnnotationItem[] {
  const annos = (spec?.layout?.annotations as { text?: unknown; visible?: boolean }[]) ?? [];
  return annos.map((a, index) => ({
    index,
    text: typeof a?.text === "string" ? a.text : "",
    visible: a?.visible !== false,
  }));
}

export function annotationVisibilityOp(index: number, visible: boolean): Operation {
  return set(`/layout/annotations/${index}/visible`, visible);
}

export function annotationTextOp(index: number, text: string): Operation {
  return set(`/layout/annotations/${index}/text`, text);
}

// --- trace-grid layout mode: grid (small multiples) ↔ overlay (one line graph) ----------

/** Toggle the layout view of a trace-grid figure. One tiny, undoable patch: the canonical spec
 *  stays the grid; the overlay is a render-time projection (see `projectOverlay`). The parent
 *  `/layout/meta/selom` always exists on a trace-grid (the skill stamps it), so `add` is safe. */
export function layoutModeOp(mode: "grid" | "overlay"): Operation {
  return set("/layout/meta/selom/layoutMode", mode);
}

/** Show/hide the overlay's time (x) or amplitude (y) axis. Stored as a `meta.selom` pref the
 *  projection reads, so the canonical grid spec is untouched and the choice survives a toggle. */
export function overlayAxisOp(axis: "x" | "y", visible: boolean): Operation {
  return set(`/layout/meta/selom/overlayHide${axis === "x" ? "X" : "Y"}`, !visible);
}

/** The scale-bar primitive's units (for the overlay axis titles), or null. */
function readScalebarUnits(spec: FigureSpec): { xUnit: string; yUnit: string } | null {
  const prims = readHint(spec)?.primitives ?? [];
  const p = prims.find((x) => x.kind === "scalebar") as Record<string, unknown> | undefined;
  if (!p) return null;
  return {
    xUnit: typeof p.xUnit === "string" ? p.xUnit : "",
    yUnit: typeof p.yUnit === "string" ? p.yUnit : "",
  };
}

/**
 * Project a small-multiples trace-grid spec to a single-axis OVERLAY — "all traces on one set of
 * axes, like a normal line graph". Pure + reversible: the canonical stored spec stays the grid;
 * this is a display-time view the canvas applies when `meta.selom.layoutMode === "overlay"`. Every
 * trace is re-pointed to the shared x/y axis; the per-panel hidden axes, the scale bar, and the
 * grid's row/column labels are dropped; the axes become visible with titles (units read from the
 * scale-bar primitive); and one legend entry per condition (legendgroup) is shown. Per-trace
 * styling (line.color, width) is preserved, so recolours done in the editor show through in either
 * layout. Falls back to the input unchanged if there's nothing to overlay.
 */
export function projectOverlay(spec: FigureSpec): FigureSpec {
  const data: PlotlyTrace[] = Array.isArray(spec?.data) ? spec.data : [];
  if (!data.length) return spec;
  const layout = (spec?.layout ?? {}) as Record<string, unknown>;
  const xAxis0 = layout.xaxis as { range?: number[] } | undefined;
  const yAxis0 = layout.yaxis as { range?: number[] } | undefined;
  const units = readScalebarUnits(spec);
  const xTitle = `Time${units?.xUnit ? ` (${units.xUnit})` : ""}`;
  const yTitle = `Amplitude${units?.yUnit ? ` (${units.yUnit})` : ""}`;
  const hint = readHint(spec);
  const showX = hint?.overlayHideX !== true;
  const showY = hint?.overlayHideY !== true;

  // One legend entry per condition: show only the first trace of each legendgroup, named for it.
  const seen = new Set<string>();
  const newData: PlotlyTrace[] = data.map((t, i) => {
    const lg = typeof t?.legendgroup === "string" && t.legendgroup ? t.legendgroup : null;
    const key = lg ?? `__solo${i}`;
    const first = !seen.has(key);
    seen.add(key);
    return {
      ...t,
      xaxis: "x",
      yaxis: "y",
      showlegend: first,
      name: lg ?? (typeof t?.name === "string" && t.name ? t.name : `Trace ${i + 1}`),
    };
  });

  // Drop every per-panel axis (xaxis2…/yaxis2…) + the scale-bar shapes + the grid's paper labels;
  // rebuild a single visible axis pair. Everything else (title, theme template, meta, size) carries.
  const newLayout: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(layout)) {
    if (/^[xy]axis\d*$/.test(k)) continue;
    if (k === "shapes" || k === "annotations" || k === "margin" || k === "showlegend" || k === "legend") {
      continue;
    }
    newLayout[k] = v;
  }
  newLayout.showlegend = true;
  newLayout.legend = { orientation: "v", x: 1.02, y: 1, xanchor: "left", yanchor: "top" };
  newLayout.margin = { t: layout.title ? 48 : 24, r: 132, b: 52, l: 64 };
  newLayout.xaxis = {
    visible: showX, title: { text: xTitle }, anchor: "y", domain: [0, 1],
    ...(Array.isArray(xAxis0?.range) ? { range: xAxis0!.range } : {}),
  };
  newLayout.yaxis = {
    visible: showY, title: { text: yTitle }, anchor: "x", domain: [0, 1], zeroline: true,
    ...(Array.isArray(yAxis0?.range) ? { range: yAxis0!.range } : {}),
  };
  newLayout.shapes = [];
  newLayout.annotations = [];
  return { ...spec, data: newData, layout: newLayout };
}

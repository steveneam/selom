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

export interface FigureModel {
  traceKinds: TraceKind[];
  series: Series[];
  primitives: FigurePrimitive[];
  capabilities: {
    markers: boolean;
    lines: boolean;
    colorscale: boolean;
    colorbar: boolean;
    scalebar: boolean;
    subplotRanges: boolean;
  };
  /** Trace indices for the conditional Style groups (marker controls, line width, heatmap colorscale). */
  markerTraceIndices: number[];
  lineTraceIndices: number[];
  heatmapTraceIndices: number[];
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

/** Optional skill-stamped hint (render-inert; lives at layout.meta.selom). */
interface SelomHint {
  figureKind?: string;
  series?: { label: string; traceIndices: number[]; colorPath?: string }[];
  primitives?: { kind: PrimitiveKind; [k: string]: unknown }[];
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
 * Derive the full editor model from a spec. Pure + cheap; callers memoise on `spec`.
 */
export function deriveFigureModel(spec: FigureSpec): FigureModel {
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
  const { capabilities, primitives, markerTraceIndices, lineTraceIndices, heatmapTraceIndices } =
    deriveCapabilities(spec, infos);

  return {
    traceKinds,
    series,
    primitives,
    capabilities,
    markerTraceIndices,
    lineTraceIndices,
    heatmapTraceIndices,
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

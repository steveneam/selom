/**
 * The figure spec — Selom's single source of truth.
 *
 * A figure is a Plotly JSON spec ({ data, layout }), never a baked image. Both the
 * property panel and (later) the LLM copilot mutate it via RFC-6902 JSON-Patch.
 * Render = f(spec). The `layout`/`data` split is the cheap-vs-expensive boundary:
 * editing layout/marker/line is client-only and instant; editing data[].x/y means
 * a backend recompute (see lib/patch.ts → classifyPatch).
 *
 * Types are intentionally loose (Plotly's schema is enormous); we keep just enough
 * structure to be ergonomic and document the editable paths the panel touches.
 */
export type PlotlyTrace = Record<string, any>;
export type PlotlyLayout = Record<string, any>;

export interface FigureSpec {
  data: PlotlyTrace[];
  layout: PlotlyLayout;
}

/** Figure text font — independent of the app UI font; a clean default for plots. */
const FIGURE_FONT = "Inter, ui-sans-serif, system-ui, sans-serif";
const INK = "#0f172a";
const GRID = "#e2e8f0";
const AXIS_LINE = "#cbd5e1";

/** Named colourways for the palette swap (colourblind-safe defaults first). */
export const COLORWAYS: Record<string, { label: string; colors: string[] }> = {
  okabeito: {
    label: "Okabe–Ito (CB-safe)",
    colors: ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"],
  },
  selom: {
    label: "Selom",
    colors: ["#0ea5b7", "#a855f7", "#f97316", "#10b981", "#ec4899", "#eab308", "#3b82f6", "#ef4444"],
  },
  tableau: {
    label: "Tableau 10",
    colors: ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#ff9da7"],
  },
  viridis: {
    label: "Viridis",
    colors: ["#440154", "#414487", "#2a788e", "#22a884", "#7ad151", "#fde725"],
  },
  grayscale: {
    label: "Grayscale",
    colors: ["#111827", "#374151", "#6b7280", "#9ca3af", "#d1d5db"],
  },
};

/** Figure font-family options surfaced in the Page tab. */
export const FONT_FAMILIES: { label: string; value: string }[] = [
  { label: "Inter", value: FIGURE_FONT },
  { label: "Arial / Helvetica", value: "Arial, Helvetica, sans-serif" },
  { label: "Times New Roman", value: "'Times New Roman', Times, serif" },
  { label: "Georgia", value: "Georgia, serif" },
  { label: "Courier (mono)", value: "'Courier New', monospace" },
];

/**
 * Ensure the editable substructure exists with publication-ready defaults, so the
 * panel can read current values and JSON-Patch `add` ops always have a live parent.
 * Existing backend values win; we only fill gaps (plus force a white "paper"
 * artboard — the journal default). Returns a NEW spec; the input is untouched.
 */
export function normalizeSpec(input: FigureSpec): FigureSpec {
  const spec: FigureSpec = structuredClone(input);
  const L: PlotlyLayout = (spec.layout ??= {});

  L.paper_bgcolor ??= "#ffffff";
  L.plot_bgcolor ??= "#ffffff";
  L.autosize ??= true;

  L.font ??= {};
  L.font.family ??= FIGURE_FONT;
  L.font.size ??= 12;
  L.font.color ??= INK;

  if (typeof L.title === "string") L.title = { text: L.title };
  L.title ??= {};
  L.title.text ??= "";
  L.title.font ??= {};
  L.title.font.size ??= 17;
  L.title.font.color ??= INK;

  L.colorway ??= COLORWAYS.okabeito.colors;

  const traceCount = Array.isArray(spec.data) ? spec.data.length : 0;
  L.showlegend ??= traceCount > 1;
  L.legend ??= {};
  L.legend.orientation ??= "v";

  for (const ax of ["xaxis", "yaxis"] as const) {
    const A: PlotlyLayout = (L[ax] ??= {});
    if (typeof A.title === "string") A.title = { text: A.title };
    A.title ??= {};
    A.title.text ??= "";
    A.title.font ??= {};
    A.showgrid ??= true;
    A.gridcolor ??= GRID;
    A.zeroline ??= false;
    A.linecolor ??= AXIS_LINE;
    A.ticks ??= "outside";
    A.tickcolor ??= AXIS_LINE;
    A.type ??= "-"; // "-" = auto-detect
  }

  L.margin ??= { l: 64, r: 28, t: 52, b: 56 };

  spec.data = (Array.isArray(spec.data) ? spec.data : []).map((t) => {
    const trace: PlotlyTrace = { ...t };
    trace.marker = { size: 7, opacity: 0.9, ...(trace.marker ?? {}) };
    return trace;
  });

  return spec;
}

/** Legend position presets → the layout.legend anchor props they set. */
export const LEGEND_POSITIONS: Record<
  string,
  { label: string; x: number; y: number; xanchor: string; yanchor: string }
> = {
  "top-right": { label: "Top right", x: 0.99, y: 0.99, xanchor: "right", yanchor: "top" },
  "top-left": { label: "Top left", x: 0.01, y: 0.99, xanchor: "left", yanchor: "top" },
  "bottom-right": { label: "Bottom right", x: 0.99, y: 0.01, xanchor: "right", yanchor: "bottom" },
  "outside-right": { label: "Outside right", x: 1.02, y: 1, xanchor: "left", yanchor: "top" },
};

/** Colour-bar position presets → the colorbar props they set (orientation baked in). */
export const COLORBAR_POSITIONS: Record<
  string,
  { label: string; x: number; y: number; xanchor: string; yanchor: string; orientation: string }
> = {
  right: { label: "Right", x: 1.02, y: 0.5, xanchor: "left", yanchor: "middle", orientation: "v" },
  bottom: { label: "Bottom", x: 0.5, y: -0.2, xanchor: "center", yanchor: "top", orientation: "h" },
  left: { label: "Left", x: -0.15, y: 0.5, xanchor: "right", yanchor: "middle", orientation: "v" },
};

/**
 * Locate the figure's colour bar, if any, and return the JSON-pointer base to its
 * colorbar object. Heatmap/contour-style traces carry it at `data[i].colorbar`;
 * colour-mapped markers (UMAP-by-gene, etc.) at `data[i].marker.colorbar`. Returns
 * null when the figure has no colour bar (so the panel section stays hidden).
 */
export function findColorbarTrace(spec: FigureSpec): { index: number; base: string } | null {
  const data = Array.isArray(spec.data) ? spec.data : [];
  for (let i = 0; i < data.length; i++) {
    const t = data[i] ?? {};
    const heatmapLike =
      t.type === "heatmap" || t.type === "heatmapgl" || t.type === "contour" || t.colorbar;
    if (heatmapLike && t.showscale !== false) return { index: i, base: `/data/${i}/colorbar` };
    const m = t.marker;
    if (m && m.showscale !== false && (m.colorbar || m.showscale || (m.colorscale && m.color !== undefined))) {
      return { index: i, base: `/data/${i}/marker/colorbar` };
    }
  }
  return null;
}

/* ---- Journal-style stamp (journal-styles v1) ---------------------------------
 * The active journal style lives INSIDE the spec (layout.meta.selomStyle), not in
 * separate React state — so it rides the same undo/redo history as the restyle it
 * describes. Undo a style-pick → the spec (and its stamp) reverts → the toolbar
 * picker + export label rewind automatically. `meta` is Plotly's free-form layout
 * escape hatch (ignored at render), so this never affects the figure or the export.
 */
export interface StyleStamp {
  id: string;
  label: string;
}

export const DEFAULT_STYLE: StyleStamp = { id: "selom", label: "Selom default" };

/** The journal style stamped into a spec, or the default when none is stamped. */
export function readStyleStamp(spec: FigureSpec | null | undefined): StyleStamp {
  const s = (spec?.layout?.meta as { selomStyle?: Partial<StyleStamp> } | undefined)?.selomStyle;
  return s && typeof s === "object" && typeof s.id === "string"
    ? { id: s.id, label: typeof s.label === "string" ? s.label : s.id }
    : DEFAULT_STYLE;
}

/** Return a copy of `layout` with the style stamp written into meta (other meta kept). */
export function stampStyle(layout: PlotlyLayout, stamp: StyleStamp): PlotlyLayout {
  const meta = layout?.meta;
  const base = meta && typeof meta === "object" && !Array.isArray(meta) ? meta : {};
  return { ...layout, meta: { ...base, selomStyle: stamp } };
}

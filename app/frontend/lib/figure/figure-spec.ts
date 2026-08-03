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
import { inferTraceKind } from "./figure-model";

export type PlotlyTrace = Record<string, any>;
export type PlotlyLayout = Record<string, any>;

export interface FigureSpec {
  data: PlotlyTrace[];
  layout: PlotlyLayout;
}

/**
 * Figure text font — independent of the app UI font (Geist); a clean default for plots.
 *
 * Must stay in step with `skills/styles.py` SANS_OPEN. This used to read
 * `Inter, ui-sans-serif, system-ui, sans-serif`, but Inter is bundled by nothing — so the browser
 * fell through to `system-ui` (DejaVu Sans on Linux) while the export's stack fell through to
 * Arial metrics. One figure, two typefaces, an 11% difference in string width, which moves label
 * wrapping and overlap between what you edit and what you download (parity-audit D3).
 */
const FIGURE_FONT = "Arimo, Arial, Helvetica, sans-serif";

/**
 * Figure defaults, kept in step with the backend style registry (`skills/styles.py`, the `selom`
 * style) so a figure looks the same whether a skill produced it or the editor did.
 *
 * These fill only what the backend theme did NOT set (`??=` throughout), so a themed figure keeps
 * its ported values untouched — but a figure created client-side (a digitized chart, a blank one)
 * gets its defaults from here, and if these drifted the two would sit side by side in the same
 * library looking like different products. Values ported from cnsplots via
 * `docs/cnsplots-port/parity-audit.md` §3.
 */
const INK = "#2b2b2b";
const INK_STRONG = "#111111";
const GRID = "#e2e8f0";
const AXIS_LINE = "#1a1a1a";
const AXIS_WIDTH = 0.8;
const TICK_LEN = 3;

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
  // Labelled by what actually renders. An option named for a font nobody ships is a lie the
  // picker tells every time it is used.
  { label: "Helvetica / Arial (default)", value: FIGURE_FONT },
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
  // Defense-in-depth at the seam (Task B2): a null / non-object / partial input must never throw here.
  // The figure store already runs validateFigureContract before this; coerce again so a direct caller
  // (or a future one) is equally safe. A blank `{ data: [], layout: {} }` normalizes to a valid figure.
  const safe =
    input && typeof input === "object" && !Array.isArray(input)
      ? input
      : ({ data: [], layout: {} } as FigureSpec);
  const spec: FigureSpec = structuredClone(safe);
  const L: PlotlyLayout = (spec.layout ??= {});

  L.paper_bgcolor ??= "#ffffff";
  L.plot_bgcolor ??= "#ffffff";
  L.autosize ??= true;

  L.font ??= {};
  L.font.family ??= FIGURE_FONT;
  L.font.size ??= 13;
  L.font.color ??= INK;

  if (typeof L.title === "string") L.title = { text: L.title };
  L.title ??= {};
  L.title.text ??= "";
  L.title.font ??= {};
  L.title.font.size ??= 14;
  L.title.font.color ??= INK_STRONG;
  L.title.font.weight ??= "bold";

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
    A.showgrid ??= false; // publication default is gridless (parity-audit row 5)
    A.gridcolor ??= GRID;
    A.zeroline ??= false;
    A.linecolor ??= AXIS_LINE;
    A.linewidth ??= AXIS_WIDTH;
    A.ticks ??= "outside";
    A.tickcolor ??= AXIS_LINE;
    A.ticklen ??= TICK_LEN;
    A.tickwidth ??= AXIS_WIDTH;
    A.type ??= "-"; // "-" = auto-detect
  }

  L.margin ??= { l: 64, r: 28, t: 52, b: 56 };

  // Ensure ONLY the substructure each trace's kind will actually edit — so a JSON-Patch
  // `add` always has a live parent — WITHOUT force-injecting `marker` onto line/heatmap/
  // sankey traces (which made the inspector falsely marker-centric; see figure-model.ts).
  spec.data = (Array.isArray(spec.data) ? spec.data : []).map((t) => {
    const trace: PlotlyTrace = { ...t };
    const kind = inferTraceKind(trace);
    if (kind === "markerScatter" || kind === "lineMarkerScatter") {
      trace.marker = { size: 7, opacity: 0.9, ...(trace.marker ?? {}) };
    } else if (kind === "bar" || kind === "box" || kind === "violin") {
      trace.marker = { ...(trace.marker ?? {}) }; // parent for marker.color, no point defaults
    }
    if (kind === "lineScatter" || kind === "lineMarkerScatter") {
      trace.line = { ...(trace.line ?? {}) }; // parent for line.color / line.width edits
    }
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

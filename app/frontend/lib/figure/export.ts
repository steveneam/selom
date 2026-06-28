import type { FigureSpec } from "./figure-spec";

/** A journal size preset from the backend (export.py PRESETS). */
export interface ExportPreset {
  id: string;
  label: string;
  width_mm: number;
  dpi: number;
  note: string;
}

export type ExportFormat = "png" | "svg" | "pdf";

const EXT: Record<ExportFormat, string> = { png: "png", svg: "svg", pdf: "pdf" };

/* ---- Output-size preview --------------------------------------------------------
 * Tiny mirror of app/backend/export.py `resolve_dimensions`, kept in one place so the
 * export menu can show the EXACT file the backend will produce before the user clicks.
 * The backend stays authoritative for the actual render — this is a preview label only.
 * Key fact it surfaces: a journal preset sets the column WIDTH + DPI; the height keeps
 * the figure's own aspect (4:3 for an autosize figure), so the export isn't cropped.
 */
const CSS_DPI = 96;
const MM_PER_IN = 25.4;
const DEFAULT_WIDTH_PX = 800;
const DEFAULT_ASPECT = 4 / 3;

/** The aspect ratio the export uses: the figure's own w/h if it has both, else 4:3. */
export function figureExportAspect(figure: FigureSpec): number {
  const w = figure.layout?.width;
  const h = figure.layout?.height;
  return typeof w === "number" && typeof h === "number" && h ? w / h : DEFAULT_ASPECT;
}

export interface ExportDimensions {
  /** Final delivered pixels (already includes the DPI `scale` multiplier). */
  widthPx: number;
  heightPx: number;
  /** Physical size in mm when a journal preset is chosen (else undefined). */
  widthMm?: number;
  heightMm?: number;
  dpi?: number;
}

/** Compute the export's output size for a format + optional preset (mirrors the backend). */
export function resolveExportDimensions(
  figure: FigureSpec,
  format: ExportFormat,
  preset: ExportPreset | undefined,
): ExportDimensions {
  const raster = format === "png";
  const aspect = figureExportAspect(figure);
  let baseWidth: number;
  let scale = 1;
  if (preset) {
    baseWidth = Math.round((preset.width_mm / MM_PER_IN) * CSS_DPI);
    if (raster) scale = preset.dpi / CSS_DPI;
  } else {
    const w = figure.layout?.width;
    baseWidth = typeof w === "number" ? Math.round(w) : DEFAULT_WIDTH_PX;
    if (raster) scale = 2; // retina default when exporting at the figure's own size
  }
  const baseHeight = Math.round(baseWidth / aspect);
  const dims: ExportDimensions = {
    widthPx: Math.max(1, Math.round(baseWidth * scale)),
    heightPx: Math.max(1, Math.round(baseHeight * scale)),
  };
  if (preset) {
    dims.widthMm = preset.width_mm;
    dims.heightMm = Math.round((preset.width_mm / aspect) * 10) / 10;
    dims.dpi = preset.dpi;
  }
  return dims;
}

/**
 * Journal size presets the export menu offers. Mirrors GET /figures/export/presets
 * (app/backend/main.py); the menu still works if this fails — it falls back to
 * exporting at the figure's own on-screen size.
 */
export async function fetchExportPresets(): Promise<ExportPreset[]> {
  const res = await fetch("/api/figures/export/presets");
  if (!res.ok) throw new Error("Couldn't load export presets.");
  const json = (await res.json()) as { presets?: ExportPreset[] };
  return json.presets ?? [];
}

/**
 * Render the edited figure to a publication-ready file and trigger a download.
 *
 * Posts the live Plotly spec to POST /figures/export, where Kaleido + the system
 * Chrome rasterize it (PNG) or emit vector (SVG/PDF). `preset` picks a journal size
 * (column width + DPI); omit it to export at the figure's own size. Throws a
 * scientist-readable Error on failure (e.g. a 503 when the server lacks Chrome).
 */
export async function exportFigure(
  figure: FigureSpec,
  opts: { format: ExportFormat; preset?: string; filename?: string },
): Promise<void> {
  const { format, preset, filename = "selom-figure" } = opts;
  const res = await fetch("/api/figures/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ figure, format, preset, filename }),
  });

  if (!res.ok) {
    let detail =
      res.status === 503
        ? "the export service can't reach a browser to render the figure"
        : res.status >= 500
          ? "the export service is temporarily unavailable"
          : `the request was rejected (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`Couldn't export this figure — ${detail}.`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename.replace(/\.[a-z0-9]+$/i, "")}.${EXT[format]}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

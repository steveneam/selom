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

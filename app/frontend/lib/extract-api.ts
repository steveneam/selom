import type { FigureSpec } from "./figure-spec";
import type { StatsTable } from "./skills-api";

/** The recovered series the backend returns (extract/chart_to_data.RecoveredSeries). */
export interface RecoveredSeries {
  form: string;
  values?: number[];
  points?: [number, number][];
  confidence: number;
  note?: string;
  source?: string;
}

export interface ExtractChartResponse {
  series: RecoveredSeries;
  table: StatsTable;
  figure: FigureSpec;
  confidence: number;
  note?: string;
}

/**
 * Recover a chart panel's underlying data from an image + an axis calibration.
 *
 * Mirrors the live contract (app/backend/main.py POST /extract/chart): a multipart POST
 * with the image in field `figure` and the calibration / form / naming as the query
 * string, responding with the recovered series + an editable Statistics table + an
 * editable Plotly figure. The MSW mock (mocks/handlers.ts) mirrors it, so this works
 * under `npm run dev:mock`.
 *
 * Recovery is calibration-first and VISION-GRADE (confidence ~0.7) — the caller must
 * surface that the values are for review, not an exact reading (sub-spec E4).
 */
export async function extractChart(
  image: File,
  params: Record<string, string>,
): Promise<ExtractChartResponse> {
  const fd = new FormData();
  fd.append("figure", image);
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api/extract/chart${qs ? `?${qs}` : ""}`, { method: "POST", body: fd });
  if (!res.ok) {
    let detail =
      res.status >= 500
        ? "the extraction service is temporarily unavailable"
        : `the request was rejected (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`Couldn't recover this chart — ${detail}. Check the calibration and try again.`);
  }
  const json = (await res.json()) as Partial<ExtractChartResponse>;
  if (!json.figure || !Array.isArray(json.figure.data) || !json.table) {
    throw new Error("Server returned a malformed recovery result.");
  }
  return {
    series: json.series as RecoveredSeries,
    table: json.table as StatsTable,
    figure: json.figure as FigureSpec,
    confidence: json.confidence ?? json.series?.confidence ?? 0,
    note: json.note ?? json.series?.note,
  };
}

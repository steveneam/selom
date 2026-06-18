import type { FigureSpec } from "@/lib/figure-spec";
import type { ExtractChartResponse } from "@/lib/extract-api";

/**
 * Offline stand-in for POST /extract/chart. The live backend recovers the series from
 * the actual image + calibration; in dev:mock we return a representative recovered
 * series so the picker's full flow (editable figure + Statistics table + the
 * vision-grade confidence treatment) is verifiable without Python. Shapes mirror
 * extract/chart_intake.recovered_to_{table,figure}.
 */
const CONFIDENCE = 0.7;
const NOTE = "Vision-grade recovery — review before using as data.";

export function mockExtractChart(form: string, params: URLSearchParams): ExtractChartResponse {
  const seriesName = params.get("series_name") || "value";
  const xName = params.get("x_name") || "x";
  const yName = params.get("y_name") || "y";
  const title = (n: string) => `Recovered ${n} — vision-grade (confidence ${CONFIDENCE})`;

  if (form === "bar") {
    const values = [25, 50, 75, 90];
    const provided = (params.get("labels") || "").split(",").map((s) => s.trim()).filter(Boolean);
    const cats = values.map((_, i) => provided[i] || `Bar ${i + 1}`);
    const figure: FigureSpec = {
      data: [{ type: "bar", x: cats, y: values, name: seriesName }],
      layout: { title: { text: `Recovered from figure — vision-grade (confidence ${CONFIDENCE})` }, yaxis: { title: { text: seriesName } } },
    };
    return {
      series: { form: "bar", values, confidence: CONFIDENCE, note: NOTE, source: "extracted" },
      table: { columns: ["category", seriesName], rows: cats.map((c, i) => [c, values[i]]), title: title(`bars (${values.length})`) },
      figure,
      confidence: CONFIDENCE,
      note: NOTE,
    };
  }

  const points: [number, number][] = [
    [0, 5],
    [1, 12],
    [2, 18],
    [3, 27],
    [4, 33],
  ];
  const mode = form === "line" ? "lines" : "markers";
  const figure: FigureSpec = {
    data: [{ type: "scatter", mode, x: points.map((p) => p[0]), y: points.map((p) => p[1]), name: seriesName }],
    layout: {
      title: { text: `Recovered from figure — vision-grade (confidence ${CONFIDENCE})` },
      xaxis: { title: { text: xName } },
      yaxis: { title: { text: yName } },
    },
  };
  return {
    series: { form, points, confidence: CONFIDENCE, note: NOTE, source: "extracted" },
    table: { columns: [xName, yName], rows: points.map(([x, y]) => [x, y]), title: title(`${form} (${points.length} points)`) },
    figure,
    confidence: CONFIDENCE,
    note: NOTE,
  };
}

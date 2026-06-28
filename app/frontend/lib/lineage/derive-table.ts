import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { StatsTable } from "@/lib/skills/api";

/**
 * FE fallback (Pillar 1, Decision D3): derive a minimal Statistics table from a
 * figure's traces when the backend didn't supply one. Handles the common
 * "labelled category vs value" shape (bar / dotplot) — a trace with a string y-axis
 * and a numeric x-axis → [label, value], using the axis titles as column headers.
 * Returns null when nothing tabular is found, so the Statistics node is omitted
 * (not shown empty) rather than fabricated from purely-visual figures.
 */
export function deriveTable(spec: FigureSpec | null | undefined): StatsTable | null {
  const data = spec && Array.isArray(spec.data) ? spec.data : [];
  for (const trace of data) {
    const y = trace?.y;
    const x = trace?.x;
    if (!Array.isArray(y) || !Array.isArray(x) || y.length === 0 || y.length !== x.length) continue;
    const yIsLabel = y.every((v: unknown) => typeof v === "string");
    const xIsNumber = x.every((v: unknown) => typeof v === "number");
    if (!yIsLabel || !xIsNumber) continue;
    const label = axisTitle(spec, "yaxis") ?? "label";
    const value = axisTitle(spec, "xaxis") ?? "value";
    const rows = y.map((cat: string, i: number): (string | number)[] => [cat, x[i] as number]);
    return { columns: [label, value], rows, title: "Figure data" };
  }
  return null;
}

function axisTitle(spec: FigureSpec | null | undefined, axis: "xaxis" | "yaxis"): string | null {
  const t = (spec?.layout?.[axis] as { title?: { text?: string } } | undefined)?.title?.text;
  return typeof t === "string" && t.trim() ? t.trim() : null;
}

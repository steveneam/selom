/**
 * Fail-safe at the spec→component seam (architecture-consistency-gate, Task B2).
 *
 * Selom's panes are bespoke per data/skill and read capability-specific shapes off the figure spec.
 * On a dataset/skill switch — or when a corrupt figure is restored from localStorage — a pane can be
 * handed a spec it doesn't expect. Task B1 catches a *throw* with an error boundary; B2 stops the throw
 * happening at the seam: a malformed/partial spec is coerced to a render-safe shape BEFORE it reaches
 * `normalizeSpec`/the panes, and a capability that's declared without backing data resolves to an
 * explicit empty state rather than crashing or silently vanishing.
 *
 * Pure + dependency-free so it unit-tests in node-env vitest; the figure store + the Style panel consume it.
 */

import type { FigureSpec, PlotlyLayout, PlotlyTrace } from "@/lib/figure-spec";

/** The render-safe floor: an object Plotly can draw (a blank plot) and the model can derive from. */
export const EMPTY_FIGURE: FigureSpec = { data: [], layout: {} };

export interface FigureContractResult {
  /** True when the input was a usable figure (an object with a `data` array). */
  ok: boolean;
  /** A render-safe spec — ALWAYS `{ data: PlotlyTrace[], layout: PlotlyLayout }`, never null/garbage. */
  spec: FigureSpec;
  /** Why the input wasn't usable (null when ok) — for an error state / telemetry. */
  reason: string | null;
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * Validate + coerce an untrusted figure spec at the data→component boundary. NEVER throws: any input
 * (null, a string, a half-written object, a corrupt stored figure) yields a render-safe spec. `ok`
 * reports whether the input was a genuine figure so a caller can show an empty/error state; the
 * coerced `spec` is always safe to hand to `normalizeSpec`, `deriveFigureModel`, and the panes.
 *
 * An empty `data: []` is VALID (a volcano before its run, a figure with no points) — only a missing /
 * non-array `data` or a non-object input is a contract violation.
 */
export function validateFigureContract(input: unknown): FigureContractResult {
  if (!isObject(input)) {
    return { ok: false, spec: { data: [], layout: {} }, reason: "Figure is empty or not an object." };
  }
  const layoutRaw = (input as { layout?: unknown }).layout;
  const layout: PlotlyLayout = isObject(layoutRaw) ? (layoutRaw as PlotlyLayout) : {};
  const dataRaw = (input as { data?: unknown }).data;
  if (!Array.isArray(dataRaw)) {
    return { ok: false, spec: { data: [], layout }, reason: "Figure has no traces array." };
  }
  return { ok: true, spec: { data: dataRaw as PlotlyTrace[], layout }, reason: null };
}

/**
 * The render state of the heatmap colour-scale section — the "default fallback renderer" decision for a
 * capability-gated pane (the seam fail-safe applied to a *section*, not just the whole spec):
 *
 * - `ready`   — a heatmap trace is present → render the re-tone controls.
 * - `empty`   — the figure DECLARES a heatmap capability (tones/labels) but ships no heatmap trace
 *               (a contract violation) → render "No heatmap trace in this figure.", not a crash.
 * - `hidden`  — not heatmap-intent at all → the section stays hidden, as before.
 *
 * The `hidden` case matters: a trajectory / markers figure colours its markers by a continuous value
 * (a marker colorscale), so `capabilities.colorscale` is true with NO heatmap trace and NO heatmap
 * capability. That must NOT show an empty heatmap section — heatmap-intent is the declared heatmap
 * capability, never the generic colorscale flag.
 */
export type SectionState = "ready" | "empty" | "hidden";

export function heatmapColorscaleState(opts: {
  heatmapTones: boolean;
  heatmapLabels: boolean;
  heatmapTraceCount: number;
}): SectionState {
  if (opts.heatmapTraceCount > 0) return "ready";
  if (opts.heatmapTones || opts.heatmapLabels) return "empty";
  return "hidden";
}

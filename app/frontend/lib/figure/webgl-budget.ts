import type { Data } from "plotly.js";

/**
 * WebGL context budget (architecture-consistency Task E1).
 *
 * Plotly's `scattergl` / `*gl` traces each consume a WebGL context. A browser keeps
 * only ~16 live at once and silently *loses the oldest* past that ceiling — the figure
 * goes blank and the console logs "too many active WebGL contexts" (the exact failure
 * the Task B exit smoke watched for). The Selom editor mounts at most two GL canvases
 * today (Compare A/B; the editor canvas and the Figure-data preview are mutually-
 * exclusive views), so this is a forward safety net, not a present-day limiter:
 *
 *   • under budget — every canvas renders GL unchanged (no behaviour change at ≤2 panes);
 *   • over budget — only the *overflow* canvas degrades GL→SVG (slower for a big point
 *     cloud, but a drawn figure beats a lost context), and re-upgrades to GL the moment a
 *     slot frees (a holder unmounts).
 *
 * The cap is a single named constant; the live grants are a tiny module-local registry
 * (one per browser tab) with subscribe/snapshot semantics so FigureCanvas can read it via
 * `useSyncExternalStore`. A canvas claims a slot keyed by a stable per-instance token.
 */
export const MAX_GL_CONTEXTS = 8;

/** A trace is WebGL-backed when its Plotly `type` ends in "gl" (scattergl, heatmapgl, …). */
export function isGlTrace(trace: unknown): boolean {
  const type = (trace as { type?: unknown } | null | undefined)?.type;
  return typeof type === "string" && type.toLowerCase().endsWith("gl");
}

/** Does this figure's data contain any WebGL-backed trace? */
export function usesWebgl(data: readonly unknown[] | undefined | null): boolean {
  return Array.isArray(data) && data.some(isGlTrace);
}

/**
 * Project every WebGL trace to its SVG equivalent (`scattergl`→`scatter`,
 * `heatmapgl`→`heatmap`, …) by dropping the trailing "gl". Pure — returns a new array
 * and leaves the input untouched; non-GL traces pass through by reference. Used only on
 * the over-budget overflow path, so the canonical spec and the in-budget canvases are
 * never altered.
 */
export function toSvgTraces(data: readonly Data[]): Data[] {
  return data.map((trace) => {
    if (!isGlTrace(trace)) return trace;
    const type = String((trace as { type?: unknown }).type);
    return { ...(trace as object), type: type.slice(0, -2) } as Data;
  });
}

// --- live GL-context registry (module-local; one per browser tab) -----------------

const holders = new Set<string>();
const listeners = new Set<() => void>();

function notify(): void {
  for (const l of listeners) l();
}

/** Subscribe to budget changes (for `useSyncExternalStore`). Returns an unsubscribe fn. */
export function subscribeGl(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Grant `token` a GL slot if one is free (idempotent — re-asking when already held is a
 * no-op that returns true). Returns false when the budget is full and `token` isn't a
 * holder, in which case the caller renders SVG and never took a context.
 */
export function ensureGl(token: string): boolean {
  if (holders.has(token)) return true;
  if (holders.size >= MAX_GL_CONTEXTS) return false;
  holders.add(token);
  notify();
  return true;
}

/** Release `token`'s slot (no-op if it never held one). */
export function dropGl(token: string): void {
  if (holders.delete(token)) notify();
}

/** Whether `token` currently holds a GL slot. */
export function holdsGl(token: string): boolean {
  return holders.has(token);
}

/** Current live GL-context count — telemetry / test inspection. */
export function glLoad(): number {
  return holders.size;
}

/** Reset the registry. TEST ONLY — never called in app code. */
export function __resetGlBudget(): void {
  holders.clear();
  listeners.clear();
}

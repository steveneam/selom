/**
 * Render-timing telemetry (architecture-consistency Task E2).
 *
 * A tiny, dependency-free ring buffer of figure-draw durations (ms) plus the summary
 * stats a perf audit reads: count, mean, p50, p95, peak. FigureCanvas records one sample
 * per Plotly draw; `installPerfHook()` exposes a read API on `window.__selomPerf` so the
 * perf-audit script (and a chrome-devtools `evaluate_script` probe) can pull p50/p95 cold
 * vs warm without scraping the DOM.
 *
 * It measures the commit→draw latency reported by react-plotly's lifecycle — a relative
 * signal for catching regressions across switches, not an absolute frame budget. Pure and
 * SSR-safe (the window hook no-ops without a `window`).
 */

const CAP = 256; // ring-buffer size — enough for a 20-switch audit run, bounded memory.
const samples: number[] = [];

export interface RenderStats {
  count: number;
  mean: number;
  p50: number;
  p95: number;
  peak: number;
}

/** Record one figure-draw duration (ms). Non-finite / negative samples are ignored. */
export function recordRenderMs(ms: number): void {
  if (!Number.isFinite(ms) || ms < 0) return;
  samples.push(ms);
  if (samples.length > CAP) samples.shift();
}

/** The q-th percentile (0..1) of a numeric sample via nearest-rank on the sorted copy. */
export function percentile(values: readonly number[], q: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const rank = Math.ceil(q * sorted.length);
  const idx = Math.min(sorted.length - 1, Math.max(0, rank - 1));
  return sorted[idx];
}

/** Summary stats over the current buffer. */
export function renderStats(): RenderStats {
  const count = samples.length;
  if (count === 0) return { count: 0, mean: 0, p50: 0, p95: 0, peak: 0 };
  const sum = samples.reduce((a, b) => a + b, 0);
  return {
    count,
    mean: sum / count,
    p50: percentile(samples, 0.5),
    p95: percentile(samples, 0.95),
    peak: Math.max(...samples),
  };
}

/** Clear all samples — used by the audit between cold and warm passes, and by tests. */
export function resetPerf(): void {
  samples.length = 0;
}

interface SelomPerf {
  stats: () => RenderStats;
  reset: () => void;
  /** Browser heap snapshot in MB if the engine exposes it (Chromium `performance.memory`). */
  heapMB: () => number | null;
}

/**
 * Expose the read API on `window.__selomPerf` for the perf-audit script / a devtools probe.
 * Idempotent and SSR-safe. The heap reader is best-effort — `performance.memory` is a
 * non-standard Chromium extension, absent elsewhere (returns null).
 */
export function installPerfHook(): void {
  if (typeof window === "undefined") return;
  const w = window as unknown as { __selomPerf?: SelomPerf };
  if (w.__selomPerf) return;
  w.__selomPerf = {
    stats: renderStats,
    reset: resetPerf,
    heapMB: () => {
      const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory;
      return mem ? Math.round((mem.usedJSHeapSize / 1024 / 1024) * 100) / 100 : null;
    },
  };
}

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  installPerfHook,
  percentile,
  recordRenderMs,
  renderStats,
  resetPerf,
} from "./perf";

beforeEach(() => resetPerf());
afterEach(() => resetPerf());

describe("percentile", () => {
  it("returns 0 for an empty set", () => {
    expect(percentile([], 0.5)).toBe(0);
  });

  it("computes nearest-rank percentiles", () => {
    const v = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    expect(percentile(v, 0.5)).toBe(50);
    expect(percentile(v, 0.95)).toBe(100);
    expect(percentile(v, 0)).toBe(10);
    expect(percentile(v, 1)).toBe(100);
  });

  it("does not mutate the input array", () => {
    const v = [3, 1, 2];
    percentile(v, 0.5);
    expect(v).toEqual([3, 1, 2]);
  });
});

describe("recordRenderMs / renderStats", () => {
  it("starts empty", () => {
    expect(renderStats()).toEqual({ count: 0, mean: 0, p50: 0, p95: 0, peak: 0 });
  });

  it("ignores non-finite and negative samples", () => {
    recordRenderMs(Number.NaN);
    recordRenderMs(Number.POSITIVE_INFINITY);
    recordRenderMs(-5);
    expect(renderStats().count).toBe(0);
  });

  it("aggregates count / mean / p50 / p95 / peak", () => {
    for (const ms of [10, 20, 30, 40, 100]) recordRenderMs(ms);
    const s = renderStats();
    expect(s.count).toBe(5);
    expect(s.mean).toBeCloseTo(40, 5);
    expect(s.p50).toBe(30);
    expect(s.peak).toBe(100);
  });

  it("bounds memory to the ring-buffer cap (keeps the most recent)", () => {
    for (let i = 0; i < 300; i += 1) recordRenderMs(i);
    const s = renderStats();
    expect(s.count).toBe(256); // CAP
    expect(s.peak).toBe(299); // newest retained, oldest evicted
  });
});

describe("installPerfHook", () => {
  const w = globalThis as unknown as { window?: unknown };

  afterEach(() => {
    delete (globalThis as unknown as { window?: unknown }).window;
  });

  it("no-ops without a window (SSR-safe)", () => {
    delete w.window;
    expect(() => installPerfHook()).not.toThrow();
  });

  it("exposes stats/reset/heapMB on window.__selomPerf and is idempotent", () => {
    const fakeWindow: Record<string, unknown> = {};
    w.window = fakeWindow;
    installPerfHook();
    installPerfHook(); // idempotent — does not replace the hook
    const hook = (fakeWindow as { __selomPerf?: { stats: () => unknown; reset: () => void; heapMB: () => number | null } })
      .__selomPerf!;
    expect(typeof hook.stats).toBe("function");
    expect(typeof hook.reset).toBe("function");
    recordRenderMs(42);
    expect((hook.stats() as { count: number }).count).toBe(1);
    hook.reset();
    expect((hook.stats() as { count: number }).count).toBe(0);
    expect(hook.heapMB()).toBeNull(); // no performance.memory in node
  });
});

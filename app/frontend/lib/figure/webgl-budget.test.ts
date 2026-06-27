import { afterEach, describe, expect, it, vi } from "vitest";
import type { Data } from "plotly.js";

import {
  __resetGlBudget,
  dropGl,
  ensureGl,
  glLoad,
  holdsGl,
  isGlTrace,
  MAX_GL_CONTEXTS,
  subscribeGl,
  toSvgTraces,
  usesWebgl,
} from "./webgl-budget";

afterEach(() => __resetGlBudget());

describe("isGlTrace / usesWebgl", () => {
  it("flags WebGL trace types (case-insensitive)", () => {
    expect(isGlTrace({ type: "scattergl" })).toBe(true);
    expect(isGlTrace({ type: "ScatterGL" })).toBe(true);
    expect(isGlTrace({ type: "heatmapgl" })).toBe(true);
  });

  it("does not flag SVG trace types or junk", () => {
    expect(isGlTrace({ type: "scatter" })).toBe(false);
    expect(isGlTrace({ type: "heatmap" })).toBe(false);
    expect(isGlTrace({ type: "bar" })).toBe(false);
    expect(isGlTrace({})).toBe(false);
    expect(isGlTrace(null)).toBe(false);
    expect(isGlTrace(undefined)).toBe(false);
  });

  it("usesWebgl is true iff any trace is GL", () => {
    expect(usesWebgl([{ type: "scatter" }, { type: "scattergl" }])).toBe(true);
    expect(usesWebgl([{ type: "scatter" }, { type: "bar" }])).toBe(false);
    expect(usesWebgl([])).toBe(false);
    expect(usesWebgl(undefined)).toBe(false);
    expect(usesWebgl(null)).toBe(false);
  });
});

describe("toSvgTraces", () => {
  it("downgrades GL traces to their SVG equivalent and leaves SVG traces by reference", () => {
    const svg = { type: "scatter", x: [1], y: [2] } as unknown as Data;
    const gl = { type: "scattergl", x: [3], y: [4], marker: { size: 6 } } as unknown as Data;
    const out = toSvgTraces([svg, gl]);

    expect(out[0]).toBe(svg); // non-GL passes through untouched (same ref)
    expect((out[1] as { type: string }).type).toBe("scatter");
    // payload preserved on the downgraded trace
    expect((out[1] as { x: number[] }).x).toEqual([3]);
    expect((out[1] as { marker: { size: number } }).marker.size).toBe(6);
  });

  it("is pure — the input array and traces are not mutated", () => {
    const gl = { type: "scattergl", x: [1] } as unknown as Data;
    const input = [gl];
    const out = toSvgTraces(input);

    expect(input[0]).toBe(gl); // original array element unchanged
    expect((gl as { type: string }).type).toBe("scattergl"); // original trace unchanged
    expect(out[0]).not.toBe(gl); // a fresh object was returned
  });

  it("handles heatmapgl → heatmap", () => {
    const out = toSvgTraces([{ type: "heatmapgl", z: [[1]] } as unknown as Data]);
    expect((out[0] as { type: string }).type).toBe("heatmap");
  });
});

describe("GL-context budget registry", () => {
  it("starts empty and tracks claims/releases by token", () => {
    expect(glLoad()).toBe(0);
    expect(ensureGl("a")).toBe(true);
    expect(holdsGl("a")).toBe(true);
    expect(glLoad()).toBe(1);
    dropGl("a");
    expect(holdsGl("a")).toBe(false);
    expect(glLoad()).toBe(0);
  });

  it("ensureGl is idempotent for an existing holder (no double-count)", () => {
    ensureGl("a");
    ensureGl("a");
    expect(glLoad()).toBe(1);
  });

  it("grants up to MAX_GL_CONTEXTS then denies an overflow token without seating it", () => {
    for (let i = 0; i < MAX_GL_CONTEXTS; i += 1) {
      expect(ensureGl(`t${i}`)).toBe(true);
    }
    expect(glLoad()).toBe(MAX_GL_CONTEXTS);
    // overflow: denied, count unchanged, token is not a holder
    expect(ensureGl("overflow")).toBe(false);
    expect(holdsGl("overflow")).toBe(false);
    expect(glLoad()).toBe(MAX_GL_CONTEXTS);
  });

  it("frees a slot for a previously-denied token after a release", () => {
    for (let i = 0; i < MAX_GL_CONTEXTS; i += 1) ensureGl(`t${i}`);
    expect(ensureGl("late")).toBe(false); // full
    dropGl("t0"); // a holder unmounts
    expect(ensureGl("late")).toBe(true); // the next claim now fits
  });

  it("dropping an unknown token never drives the count below zero", () => {
    dropGl("ghost");
    dropGl("ghost");
    expect(glLoad()).toBe(0);
    expect(ensureGl("a")).toBe(true);
    expect(glLoad()).toBe(1);
  });

  it("notifies subscribers on grant and release (the useSyncExternalStore signal)", () => {
    const fn = vi.fn();
    const unsub = subscribeGl(fn);
    ensureGl("a");
    expect(fn).toHaveBeenCalledTimes(1);
    dropGl("a");
    expect(fn).toHaveBeenCalledTimes(2);
    // a denied (no-op) claim does not notify
    for (let i = 0; i < MAX_GL_CONTEXTS; i += 1) ensureGl(`t${i}`);
    fn.mockClear();
    expect(ensureGl("overflow")).toBe(false);
    expect(fn).not.toHaveBeenCalled();
    unsub();
  });
});

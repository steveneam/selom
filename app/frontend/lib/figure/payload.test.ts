import { describe, expect, it } from "vitest";
import type { FigureSpec } from "@/lib/figure/figure-spec";

import {
  figurePayload,
  PAYLOAD_POINT_CEILING,
  payloadWarnings,
} from "./payload";

const spec = (data: unknown[]): FigureSpec => ({ data, layout: {} }) as unknown as FigureSpec;

describe("figurePayload", () => {
  it("counts scatter points by the widest coordinate array", () => {
    const s = spec([
      { type: "scattergl", x: [1, 2, 3], y: [1, 2, 3] },
      { type: "scatter", x: [1, 2], y: [1, 2] },
    ]);
    const p = figurePayload(s);
    expect(p.points).toBe(5);
    expect(p.traces).toBe(2);
    expect(p.bytes).toBeGreaterThan(0);
  });

  it("flattens 2-D heatmap z to rows × cols", () => {
    const s = spec([{ type: "heatmap", z: [[1, 2, 3], [4, 5, 6]] }]);
    expect(figurePayload(s).points).toBe(6);
  });

  it("counts bar/values traces", () => {
    expect(figurePayload(spec([{ type: "bar", x: ["a", "b", "c"], y: [1, 2, 3] }])).points).toBe(3);
    expect(figurePayload(spec([{ type: "pie", values: [1, 2] }])).points).toBe(2);
  });

  it("is robust to empty / missing data", () => {
    expect(figurePayload(spec([])).points).toBe(0);
    expect(figurePayload(null).points).toBe(0);
    expect(figurePayload(undefined).traces).toBe(0);
  });
});

describe("payloadWarnings", () => {
  it("is empty for a normal figure", () => {
    expect(payloadWarnings(spec([{ type: "scattergl", x: [1, 2], y: [3, 4] }]))).toEqual([]);
  });

  it("flags an over-ceiling point count", () => {
    const big = Array.from({ length: PAYLOAD_POINT_CEILING + 1 }, (_, i) => i);
    const warnings = payloadWarnings(spec([{ type: "scattergl", x: big, y: big }]));
    expect(warnings.length).toBe(1);
    expect(warnings[0]).toMatch(/points/);
  });
});

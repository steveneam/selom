import { describe, expect, it } from "vitest";

import { heatmapColorscaleState, validateFigureContract } from "./contract";

/**
 * The spec→component seam (Task B2): validateFigureContract must NEVER throw and always hand back a
 * render-safe `{ data, layout }`; heatmapColorscaleState picks the section's fail-safe render state.
 */
describe("validateFigureContract", () => {
  it("passes a genuine figure through (ok) with its data + layout intact", () => {
    const fig = { data: [{ type: "scatter", x: [1], y: [2] }], layout: { title: { text: "x" } } };
    const r = validateFigureContract(fig);
    expect(r.ok).toBe(true);
    expect(r.reason).toBeNull();
    expect(r.spec.data).toBe(fig.data);
    expect(r.spec.layout).toBe(fig.layout);
  });

  it("treats an empty data array as a VALID figure (a volcano before its run)", () => {
    const r = validateFigureContract({ data: [], layout: {} });
    expect(r.ok).toBe(true);
    expect(r.spec.data).toEqual([]);
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
    ["a string", "{}"],
    ["a number", 42],
    ["an array", [{ type: "scatter" }]],
  ])("coerces %s to a render-safe empty figure (not ok, never throws)", (_label, input) => {
    const r = validateFigureContract(input);
    expect(r.ok).toBe(false);
    expect(r.reason).toBeTruthy();
    expect(r.spec).toEqual({ data: [], layout: {} });
    expect(Array.isArray(r.spec.data)).toBe(true);
  });

  it("coerces a partial spec (no data array) but keeps a usable layout", () => {
    const r = validateFigureContract({ layout: { title: { text: "kept" } } });
    expect(r.ok).toBe(false);
    expect(r.spec.data).toEqual([]);
    expect(r.spec.layout).toEqual({ title: { text: "kept" } });
  });

  it("drops a non-object layout to {} while keeping the data", () => {
    const r = validateFigureContract({ data: [{ type: "bar" }], layout: "bad" });
    expect(r.ok).toBe(true);
    expect(r.spec.layout).toEqual({});
    expect(r.spec.data).toHaveLength(1);
  });
});

describe("heatmapColorscaleState", () => {
  it("renders the controls (ready) when a heatmap trace is present", () => {
    expect(
      heatmapColorscaleState({ heatmapTones: false, heatmapLabels: false, heatmapTraceCount: 1 }),
    ).toBe("ready");
  });

  it("shows an empty note when a heatmap capability is declared but no heatmap trace exists", () => {
    // The acceptance case: a heatmap-intent spec with no heatmap trace renders "no heatmap trace",
    // never a crash.
    expect(
      heatmapColorscaleState({ heatmapTones: true, heatmapLabels: false, heatmapTraceCount: 0 }),
    ).toBe("empty");
    expect(
      heatmapColorscaleState({ heatmapTones: false, heatmapLabels: true, heatmapTraceCount: 0 }),
    ).toBe("empty");
  });

  it("stays hidden for a non-heatmap colorscale (trajectory/markers continuous colour)", () => {
    // No heatmap trace AND no declared heatmap capability → the section must NOT appear (no regression
    // on a markers-by-pseudotime figure, which sets capabilities.colorscale via a marker colorscale).
    expect(
      heatmapColorscaleState({ heatmapTones: false, heatmapLabels: false, heatmapTraceCount: 0 }),
    ).toBe("hidden");
  });
});

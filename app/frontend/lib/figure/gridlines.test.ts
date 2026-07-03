import { describe, expect, it } from "vitest";

import {
  GRID_DEFAULTS,
  gridColorOps,
  gridDashOps,
  gridShowOps,
  gridSpacingOps,
  gridWidthOps,
  minorDashOps,
  minorShowOps,
  readGridlines,
} from "./gridlines";
import { classifyPatch } from "./patch";
import type { FigureSpec } from "./figure-spec";

/**
 * Axis gridlines (Pillar-2 slice 1) must write NATIVE Plotly layout leaves as client-classified
 * JSON-Patch `set` ops on BOTH axes — so every edit is instant, undoable, and never triggers a
 * backend re-run. `minor` is written as a whole merged object (normalizeSpec never creates it).
 */

function spec(layout: Record<string, unknown> = {}): FigureSpec {
  return { data: [], layout } as unknown as FigureSpec;
}

describe("gridline ops write both axes as client-side layout leaves", () => {
  it("showgrid → xaxis + yaxis, as add(set) ops", () => {
    expect(gridShowOps(false)).toEqual([
      { op: "add", path: "/layout/xaxis/showgrid", value: false },
      { op: "add", path: "/layout/yaxis/showgrid", value: false },
    ]);
  });

  it("gridcolor / gridwidth / griddash hit the real Plotly leaves on both axes", () => {
    expect(gridColorOps("#94a3b8")).toEqual([
      { op: "add", path: "/layout/xaxis/gridcolor", value: "#94a3b8" },
      { op: "add", path: "/layout/yaxis/gridcolor", value: "#94a3b8" },
    ]);
    expect(gridWidthOps(2)).toEqual([
      { op: "add", path: "/layout/xaxis/gridwidth", value: 2 },
      { op: "add", path: "/layout/yaxis/gridwidth", value: 2 },
    ]);
    expect(gridDashOps("dash")).toEqual([
      { op: "add", path: "/layout/xaxis/griddash", value: "dash" },
      { op: "add", path: "/layout/yaxis/griddash", value: "dash" },
    ]);
  });

  it("dtick: a positive number pins spacing; null / 0 / negative revert to auto", () => {
    expect(gridSpacingOps(25)).toEqual([
      { op: "add", path: "/layout/xaxis/dtick", value: 25 },
      { op: "add", path: "/layout/yaxis/dtick", value: 25 },
    ]);
    for (const v of [null, 0, -5] as const) {
      expect(gridSpacingOps(v)).toEqual([
        { op: "add", path: "/layout/xaxis/dtick", value: null },
        { op: "add", path: "/layout/yaxis/dtick", value: null },
      ]);
    }
  });

  it("EVERY gridline op is client-classified (never a backend re-run)", () => {
    const all = [
      ...gridShowOps(true),
      ...gridColorOps("#000"),
      ...gridWidthOps(1.5),
      ...gridDashOps("dot"),
      ...gridSpacingOps(10),
      ...gridSpacingOps(null),
      ...minorShowOps(spec(), true),
      ...minorDashOps(spec(), "dot"),
    ];
    expect(classifyPatch(all)).toBe("client");
  });
});

describe("minor gridlines write the whole merged minor object (no orphan-parent add)", () => {
  it("creates minor when absent", () => {
    expect(minorShowOps(spec(), true)).toEqual([
      { op: "add", path: "/layout/xaxis/minor", value: { showgrid: true } },
      { op: "add", path: "/layout/yaxis/minor", value: { showgrid: true } },
    ]);
  });

  it("preserves existing minor props while setting the changed field", () => {
    const s = spec({
      xaxis: { minor: { ticks: "outside", showgrid: false } },
      yaxis: { minor: { ticks: "outside", showgrid: false } },
    });
    expect(minorShowOps(s, true)).toEqual([
      { op: "add", path: "/layout/xaxis/minor", value: { ticks: "outside", showgrid: true } },
      { op: "add", path: "/layout/yaxis/minor", value: { ticks: "outside", showgrid: true } },
    ]);
    expect(minorDashOps(s, "dash")).toEqual([
      { op: "add", path: "/layout/xaxis/minor", value: { ticks: "outside", showgrid: false, griddash: "dash" } },
      { op: "add", path: "/layout/yaxis/minor", value: { ticks: "outside", showgrid: false, griddash: "dash" } },
    ]);
  });
});

describe("readGridlines", () => {
  it("falls back to normalizeSpec / Plotly defaults on a bare spec", () => {
    expect(readGridlines(spec())).toEqual({
      showgrid: GRID_DEFAULTS.showgrid,
      gridcolor: GRID_DEFAULTS.gridcolor,
      gridwidth: GRID_DEFAULTS.gridwidth,
      griddash: GRID_DEFAULTS.griddash,
      dtick: null,
      minorShow: false,
      minorDash: GRID_DEFAULTS.minorDash,
    });
  });

  it("reads explicit x-axis values (the writers keep x + y symmetric)", () => {
    const s = spec({
      xaxis: {
        showgrid: false,
        gridcolor: "#111827",
        gridwidth: 2,
        griddash: "dash",
        dtick: 50,
        minor: { showgrid: true, griddash: "dot" },
      },
    });
    expect(readGridlines(s)).toEqual({
      showgrid: false,
      gridcolor: "#111827",
      gridwidth: 2,
      griddash: "dash",
      dtick: 50,
      minorShow: true,
      minorDash: "dot",
    });
  });
});

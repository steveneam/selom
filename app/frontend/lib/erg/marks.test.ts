import { describe, expect, it } from "vitest";

import {
  clearManualMark,
  manualMarkCount,
  manualMarkValue,
  parseManualMarks,
  readSeededMarks,
  roleField,
  roleLabel,
  serializeManualMarks,
  setManualMark,
  snapToSample,
} from "./marks";
import type { FigureSpec } from "@/lib/figure-spec";

describe("role helpers", () => {
  it("maps roles to manual_marks fields + labels", () => {
    expect(roleField("a")).toBe("a_ms");
    expect(roleField("b")).toBe("b_ms");
    expect(roleField("n1")).toBe("n1_ms");
    expect(roleField("p1")).toBe("p1_ms");
    expect(roleLabel("a")).toBe("a-wave");
    expect(roleLabel("p1")).toBe("P1");
  });
});

describe("readSeededMarks", () => {
  it("reads valid marks from meta.selom.marks and drops malformed entries", () => {
    const spec = {
      data: [],
      layout: {
        meta: {
          selom: {
            marks: [
              { segment: "Control||Group4|", role: "a", t_ms: 12.4, source: "auto", label: "Control · 1.0", trace: 3, point: 0 },
              { segment: "Control||Group4|", role: "b", t_ms: 58, source: "manual", label: "Control · 1.0" },
              { segment: "x", role: "bogus", t_ms: 1 }, // bad role → dropped
              { role: "a", t_ms: 1 }, // no segment → dropped
              null,
            ],
          },
        },
      },
    } as unknown as FigureSpec;
    const marks = readSeededMarks(spec);
    expect(marks).toHaveLength(2);
    expect(marks[0]).toMatchObject({ segment: "Control||Group4|", role: "a", tMs: 12.4, source: "auto", trace: 3, point: 0 });
    expect(marks[1]).toMatchObject({ role: "b", tMs: 58, source: "manual" });
    expect(marks[1].trace).toBeUndefined();
  });

  it("returns [] when there are no seeded marks", () => {
    expect(readSeededMarks(undefined)).toEqual([]);
    expect(readSeededMarks({ data: [], layout: {} } as unknown as FigureSpec)).toEqual([]);
  });
});

describe("manual_marks map round-trip", () => {
  it("parses a JSON string, an object, and junk tolerantly", () => {
    expect(parseManualMarks("")).toEqual({});
    expect(parseManualMarks("not json")).toEqual({});
    expect(parseManualMarks('{"Control||Group4|": {"a_ms": 12.4, "b_ms": 58, "junk": 9}}')).toEqual({
      "Control||Group4|": { a_ms: 12.4, b_ms: 58 },
    });
    expect(parseManualMarks({ "A|B|C|D": { n1_ms: 10 } })).toEqual({ "A|B|C|D": { n1_ms: 10 } });
  });

  it("serializes to a compact param ('' when empty → default path)", () => {
    expect(serializeManualMarks({})).toBe("");
    expect(serializeManualMarks({ s: {} })).toBe("");
    expect(serializeManualMarks({ "Control||Group4|": { b_ms: 50 } })).toBe(
      '{"Control||Group4|":{"b_ms":50}}',
    );
  });

  it("sets, reads, and clears overrides immutably", () => {
    let m = setManualMark({}, "Control||Group4|", "b", 50);
    expect(manualMarkValue(m, "Control||Group4|", "b")).toBe(50);
    expect(manualMarkValue(m, "Control||Group4|", "a")).toBeUndefined();
    m = setManualMark(m, "Control||Group4|", "a", 12);
    expect(manualMarkCount(m)).toBe(2);
    m = clearManualMark(m, "Control||Group4|", "b");
    expect(manualMarkValue(m, "Control||Group4|", "b")).toBeUndefined();
    expect(manualMarkValue(m, "Control||Group4|", "a")).toBe(12);
    // clearing the last field drops the segment entirely
    m = clearManualMark(m, "Control||Group4|", "a");
    expect(m).toEqual({});
  });
});

describe("snapToSample", () => {
  it("snaps a dragged time to the nearest sample (sticky to the line)", () => {
    const xs = [0, 1, 2, 3, 4, 5];
    expect(snapToSample(xs, 2.4)).toBe(2);
    expect(snapToSample(xs, 2.6)).toBe(3);
    expect(snapToSample(xs, -5)).toBe(0); // clamps to the ends
    expect(snapToSample(xs, 99)).toBe(5);
    expect(snapToSample([], 3)).toBe(3);
  });
});

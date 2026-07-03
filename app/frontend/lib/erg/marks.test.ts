import { describe, expect, it } from "vitest";

import {
  applyStagedMarks,
  clearManualMark,
  hideDotLabels,
  manualMarkCount,
  manualMarkValue,
  parseManualMarks,
  readSeededMarks,
  roleField,
  roleLabel,
  ROLE_COLORS,
  rolesPresent,
  roleTag,
  serializeManualMarks,
  setManualMark,
  snapToSample,
  type SeededMark,
} from "./marks";
import type { FigureSpec } from "@/lib/figure/figure-spec";

describe("live preview transforms (no re-run)", () => {
  // A line trace (0) + its a/b dot trace (1) with the meta.selom.marks hint binding the dots.
  const withDots = () =>
    ({
      data: [
        { mode: "lines", xaxis: "x", x: [0, 10, 20, 30], y: [0, 5, 9, 2] },
        { mode: "markers+text", xaxis: "x", x: [10, 20], y: [5, 9], text: ["a", "b"] },
      ],
      layout: {
        meta: {
          selom: {
            marks: [
              { segment: "C||G1|", role: "a", t_ms: 10, source: "auto", trace: 1, point: 0 },
              { segment: "C||G1|", role: "b", t_ms: 20, source: "auto", trace: 1, point: 1 },
            ],
          },
        },
      },
    }) as unknown as FigureSpec;

  it("applyStagedMarks moves a dot to the staged time + the line's value there (immutably)", () => {
    const spec = withDots();
    const out = applyStagedMarks(spec, parseManualMarks('{"C||G1|":{"a_ms":30}}'));
    // a-dot (point 0) snaps to sample 30, riding the line value (2) there
    expect((out.data[1].x as number[])[0]).toBe(30);
    expect((out.data[1].y as number[])[0]).toBe(2);
    // b-dot (point 1) is untouched; original spec untouched
    expect((out.data[1].x as number[])[1]).toBe(20);
    expect((spec.data[1].x as number[])[0]).toBe(10);
  });

  it("applyStagedMarks is a no-op with nothing staged", () => {
    const spec = withDots();
    expect(applyStagedMarks(spec, {})).toBe(spec);
  });

  it("hideDotLabels flips the dot trace to markers (drops the pinned text)", () => {
    const out = hideDotLabels(withDots());
    expect(out.data[1].mode).toBe("markers");
    expect(out.data[0].mode).toBe("lines"); // the line trace is untouched
  });
});

describe("role styling helpers (figure-data-capabilities §6)", () => {
  it("gives each role a distinct colour + a compact tag", () => {
    expect(new Set(Object.values(ROLE_COLORS)).size).toBe(4); // all distinct
    expect(roleTag("a")).toBe("a");
    expect(roleTag("b")).toBe("b");
    expect(roleTag("n1")).toBe("N1");
    expect(roleTag("p1")).toBe("P1");
  });

  it("lists the distinct roles present, in first-seen order (the legend)", () => {
    const marks = [
      { segment: "s", role: "a", tMs: 1, source: "auto", label: "x" },
      { segment: "s", role: "b", tMs: 2, source: "auto", label: "x" },
      { segment: "t", role: "a", tMs: 3, source: "auto", label: "y" },
    ] as SeededMark[];
    expect(rolesPresent(marks)).toEqual(["a", "b"]);
    expect(rolesPresent([])).toEqual([]);
  });
});

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

  it("reads the auto seed time (autoTMs) on an operator-moved mark, undefined when absent (R6)", () => {
    const spec = {
      data: [],
      layout: {
        meta: {
          selom: {
            marks: [
              { segment: "Control||Group4|", role: "b", t_ms: 50, source: "manual", auto_t_ms: 70, label: "c" },
              { segment: "Control||Group4|", role: "a", t_ms: 30, source: "auto", label: "c" },
            ],
          },
        },
      },
    } as unknown as FigureSpec;
    const marks = readSeededMarks(spec);
    expect(marks[0]).toMatchObject({ role: "b", source: "manual", autoTMs: 70 });
    expect(marks[1].autoTMs).toBeUndefined(); // auto mark carries no separate seed
  });

  it("returns [] when there are no seeded marks", () => {
    expect(readSeededMarks(undefined)).toEqual([]);
    expect(readSeededMarks({ data: [], layout: {} } as unknown as FigureSpec)).toEqual([]);
  });

  it("is null-safe at the seam (null / garbage spec → [], never throws)", () => {
    // Task B2: the Marks panel reads this off whatever spec it's handed.
    expect(readSeededMarks(null)).toEqual([]);
    expect(readSeededMarks({} as unknown as FigureSpec)).toEqual([]);
    expect(readSeededMarks({ layout: { meta: { selom: { marks: "nope" } } } } as unknown as FigureSpec)).toEqual([]);
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

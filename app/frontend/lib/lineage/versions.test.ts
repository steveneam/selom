import { describe, expect, it } from "vitest";
import { familySize, groupFamilies, rootFigureId, versionFamily } from "./versions";
import type { Figure } from "@/lib/projects/types";

/** Minimal figure factory — only the fields the version helpers read. */
function fig(id: string, parentFigureId: string | undefined, createdAt: number): Figure {
  return { id, projectId: "p", title: id, createdAt, parentFigureId };
}

// A family: original `f1` → swept into `f2` (res 0.5) + `f3` (res 1.0); `f3` re-run → `f4`.
// Plus a standalone unrelated figure `g1`.
const FIGS: Figure[] = [
  fig("f1", undefined, 10),
  fig("f2", "f1", 20),
  fig("f3", "f1", 30),
  fig("f4", "f3", 40),
  fig("g1", undefined, 25),
];

describe("rootFigureId", () => {
  const byId = new Map(FIGS.map((f) => [f.id, f]));
  it("walks parents to the root", () => {
    expect(rootFigureId("f4", byId)).toBe("f1");
    expect(rootFigureId("f2", byId)).toBe("f1");
    expect(rootFigureId("f1", byId)).toBe("f1");
    expect(rootFigureId("g1", byId)).toBe("g1");
  });
  it("treats a missing parent as a root (no crash)", () => {
    const orphan = new Map([["x", fig("x", "gone", 1)]]);
    expect(rootFigureId("x", orphan)).toBe("x");
  });
  it("guards against a cycle", () => {
    const cyc = new Map([
      ["a", fig("a", "b", 1)],
      ["b", fig("b", "a", 2)],
    ]);
    expect(() => rootFigureId("a", cyc)).not.toThrow();
  });
});

describe("versionFamily / familySize", () => {
  it("returns the whole family, oldest → newest, including self", () => {
    expect(versionFamily(FIGS, "f3").map((f) => f.id)).toEqual(["f1", "f2", "f3", "f4"]);
    expect(versionFamily(FIGS, "f1").map((f) => f.id)).toEqual(["f1", "f2", "f3", "f4"]);
  });
  it("a standalone figure is its own family of one", () => {
    expect(versionFamily(FIGS, "g1").map((f) => f.id)).toEqual(["g1"]);
    expect(familySize(FIGS, "g1")).toBe(1);
    expect(familySize(FIGS, "f1")).toBe(4);
  });
  it("returns [] for an unknown id", () => {
    expect(versionFamily(FIGS, "nope")).toEqual([]);
  });
});

describe("groupFamilies", () => {
  it("groups items by family, root first, ordered by root creation", () => {
    const groups = groupFamilies(FIGS, (f) => f);
    expect(groups.map((g) => g.root.id)).toEqual(["f1", "g1"]); // f1 (created 10) before g1 (25)
    expect(groups[0].items.map((f) => f.id)).toEqual(["f1", "f2", "f3", "f4"]);
    expect(groups[1].items.map((f) => f.id)).toEqual(["g1"]);
  });
  it("works over wrapper items (e.g. rail nodes)", () => {
    const nodes = FIGS.map((f) => ({ figure: f, extra: 1 }));
    const groups = groupFamilies(nodes, (n) => n.figure);
    expect(groups.map((g) => g.root.id)).toEqual(["f1", "g1"]);
    expect(groups[0].items).toHaveLength(4);
  });
});

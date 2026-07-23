import { describe, expect, it } from "vitest";

import {
  addArrowOps,
  addSigBracketOps,
  addTextLabelOps,
  annotationTextOps,
  annotationVisibilityOps,
  bracketGeometry,
  isSelomAnnotation,
  nonSelomAnnotationItems,
  removeAnnotationOps,
  selomAnnotations,
  starsForP,
} from "./annotations";
import { applyPatches, classifyPatch } from "./patch";
import type { FigureSpec } from "./figure-spec";

/**
 * Annotation & drawing layer (Pillar-2 slice 5 — the export-killer). The op builders must emit
 * NATIVE, `selom`-tagged `layout.shapes` / `layout.annotations` as client-classified JSON-Patch — so
 * every add / edit / remove is instant, undoable, and never triggers a backend re-run — and resolve the
 * live index by scanning the tag (drift-proof), not a stored index.
 */
function spec(layout: Record<string, unknown> = {}, data: unknown[] = []): FigureSpec {
  return { data, layout } as unknown as FigureSpec;
}

/** Read the appended value off an `add` op (the Operation union hides `value` behind RemoveOperation). */
function added(op: unknown): Record<string, unknown>[] {
  return (op as { value: Record<string, unknown>[] }).value;
}

describe("every add is a client-only, selom-tagged patch", () => {
  it("significance bracket = one path shape + one stars annotation sharing an id", () => {
    const ops = addSigBracketOps(spec(), { id: "sig-1" });
    expect(classifyPatch(ops)).toBe("client");
    expect(ops).toHaveLength(2);

    const [shapeOp, annoOp] = ops;
    expect(shapeOp).toMatchObject({ op: "add", path: "/layout/shapes" });
    const shape = added(shapeOp)[0];
    expect(shape.type).toBe("path");
    expect(shape.xref).toBe("x");
    expect(shape.yref).toBe("y");
    expect(typeof shape.path).toBe("string");
    expect(shape.selom).toEqual({ kind: "sigBracket", id: "sig-1", role: "bracket" });

    expect(annoOp).toMatchObject({ op: "add", path: "/layout/annotations" });
    const anno = added(annoOp)[0];
    expect(anno.text).toBe("*");
    expect(anno.showarrow).toBe(false);
    expect(anno.selom).toEqual({ kind: "sigBracket", id: "sig-1", role: "label" });
  });

  it("text label = a paper-referenced free annotation", () => {
    const ops = addTextLabelOps(spec(), { id: "txt-1", text: "A" });
    expect(classifyPatch(ops)).toBe("client");
    const anno = added(ops[0])[0];
    expect(anno).toMatchObject({ xref: "paper", yref: "paper", text: "A", showarrow: false });
    expect(anno.selom).toEqual({ kind: "textLabel", id: "txt-1" });
  });

  it("arrow = an annotation carrying an arrowhead", () => {
    const ops = addArrowOps(spec(), { id: "arr-1" });
    expect(classifyPatch(ops)).toBe("client");
    const anno = added(ops[0])[0];
    expect(anno).toMatchObject({ showarrow: true, arrowhead: 2 });
    expect(anno.selom).toEqual({ kind: "arrow", id: "arr-1" });
  });

  it("generates a non-empty id when none is supplied", () => {
    const anno = added(addTextLabelOps(spec())[0])[0];
    const tag = anno.selom as { id?: unknown };
    expect(typeof tag.id).toBe("string");
    expect((tag.id as string).length).toBeGreaterThan(0);
  });

  it("appends with /- when the array already exists (does not clobber existing items)", () => {
    const existing = spec({ annotations: [{ text: "keep" }] });
    const ops = addTextLabelOps(existing, { id: "txt-2" });
    expect(ops[0]).toMatchObject({ op: "add", path: "/layout/annotations/-" });
    const next = applyPatches(existing, ops);
    expect(next.layout.annotations).toHaveLength(2);
    expect(next.layout.annotations[0].text).toBe("keep");
  });
});

describe("bracket geometry clears the tallest bar and spans the first two groups", () => {
  it("uses category positions 0,1 for categorical x", () => {
    const g = bracketGeometry(spec({}, [{ x: ["ctrl", "treat", "rescue"], y: [3, 7, 5], type: "bar" }]));
    expect(g.x1).toBe(0);
    expect(g.x2).toBe(1);
    expect(g.yt).toBeGreaterThan(7); // above the tallest bar
    expect(g.yt).toBeGreaterThan(g.yb);
  });

  it("uses the two smallest distinct values for numeric x", () => {
    const g = bracketGeometry(spec({}, [{ x: [10, 20, 30], y: [1, 2, 1], type: "scatter" }]));
    expect(g.x1).toBe(10);
    expect(g.x2).toBe(20);
  });

  it("falls back to a sane default on an empty figure", () => {
    const g = bracketGeometry(spec());
    expect(g.x1).toBe(0);
    expect(g.x2).toBe(1);
    expect(g.yt).toBeGreaterThan(g.yb);
  });
});

describe("starsForP follows the GraphPad convention", () => {
  it.each([
    [0.0005, "***"],
    [0.005, "**"],
    [0.03, "*"],
    [0.2, "ns"],
    [Number.NaN, "ns"],
  ])("p=%s → %s", (p, tier) => {
    expect(starsForP(p as number)).toBe(tier);
  });

  it("derives the bracket stars from a p-value when given", () => {
    const anno = added(addSigBracketOps(spec(), { id: "s", p: 0.004 })[1])[0];
    expect(anno.text).toBe("**");
  });
});

describe("read model: selom vs non-selom split", () => {
  const withMix = spec({
    annotations: [
      { text: "n = 6", showarrow: false }, // skill unit label (non-selom)
      { text: "*", selom: { kind: "sigBracket", id: "sig-1", role: "label" } },
      { text: "A", selom: { kind: "textLabel", id: "txt-1" } },
    ],
    shapes: [{ type: "path", selom: { kind: "sigBracket", id: "sig-1", role: "bracket" } }],
  });

  it("lists only Selom items, pairing a bracket's shape + annotation by id", () => {
    const items = selomAnnotations(withMix);
    expect(items.map((i) => i.id)).toEqual(["sig-1", "txt-1"]);
    const bracket = items[0];
    expect(bracket.kind).toBe("sigBracket");
    expect(bracket.text).toBe("*");
    expect(bracket.annoIndex).toBe(1);
    expect(bracket.shapeIndex).toBe(0);
  });

  it("nonSelomAnnotationItems returns only the untagged annotations (the Marks list)", () => {
    const items = nonSelomAnnotationItems(withMix);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ index: 0, text: "n = 6", visible: true });
  });

  it("isSelomAnnotation recognises the tag", () => {
    expect(isSelomAnnotation({ selom: { kind: "arrow", id: "x" } })).toBe(true);
    expect(isSelomAnnotation({ text: "plain" })).toBe(false);
  });
});

describe("edit / remove resolve the live index by id and stay client-side", () => {
  const s = spec({
    annotations: [
      { text: "*", selom: { kind: "sigBracket", id: "sig-1", role: "label" } },
      { text: "A", selom: { kind: "textLabel", id: "txt-1" } },
    ],
    shapes: [{ type: "path", selom: { kind: "sigBracket", id: "sig-1", role: "bracket" } }],
  });

  it("annotationTextOps retexts the right annotation", () => {
    const ops = annotationTextOps(s, "sig-1", "***");
    expect(classifyPatch(ops)).toBe("client");
    expect(ops).toEqual([{ op: "add", path: "/layout/annotations/0/text", value: "***" }]);
  });

  it("annotationVisibilityOps hides both halves of a bracket", () => {
    const ops = annotationVisibilityOps(s, "sig-1", false);
    expect(ops).toEqual([
      { op: "add", path: "/layout/annotations/0/visible", value: false },
      { op: "add", path: "/layout/shapes/0/visible", value: false },
    ]);
  });

  it("removeAnnotationOps drops both the shape and the annotation", () => {
    const ops = removeAnnotationOps(s, "sig-1");
    expect(ops).toEqual([
      { op: "remove", path: "/layout/annotations/0" },
      { op: "remove", path: "/layout/shapes/0" },
    ]);
    const next = applyPatches(s, ops);
    expect(selomAnnotations(next).map((i) => i.id)).toEqual(["txt-1"]);
  });

  it("returns no ops for an unknown id", () => {
    expect(removeAnnotationOps(s, "nope")).toEqual([]);
    expect(annotationTextOps(s, "nope", "x")).toEqual([]);
  });
});

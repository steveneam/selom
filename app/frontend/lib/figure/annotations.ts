/**
 * Annotation & drawing-layer op builders (Pillar-2 slice 5,
 * docs/pillar-2-direct-manipulation/spec.md §5.5 — the export-killer).
 *
 * The owner finishes figures today by round-tripping to Illustrator, chiefly to add the annotations
 * generic vector editors can't (or won't) do well: **significance brackets + asterisks**, arrows /
 * callout lines, and free text labels. This module builds those as NATIVE Plotly `layout.shapes` +
 * `layout.annotations`, so every add / edit / remove is a client-only, instant, undoable JSON-Patch on
 * the spec (classifyPatch → "client"; render = f(spec); WYSIWYG export unchanged — no persisted-contract
 * change). Once an item is in the spec it is draggable on the artboard for free: figure-canvas already
 * enables Plotly's `shapePosition` / `annotationPosition` / `annotationTail` edits, and a drag rides
 * `plotly_relayout` → `relayoutToOps` → one commit — so this slice adds no imperative canvas wiring.
 *
 * Each Selom-created item is tagged in a `selom` namespace ON the item (`{ kind, id, role? }`) — Plotly
 * ignores unknown sub-object keys (render-inert), and the tag makes the item identifiable WITHOUT a
 * stored index (indices drift when items are added/removed): every read/edit/remove re-resolves the live
 * index by scanning for the id, the same drift-proof pattern the volcano gene-labels use. A significance
 * bracket is a coordinated pair — one `path` shape (the bracket) + one annotation (the stars) sharing an
 * id — so show/hide and remove act on both.
 *
 * Pure + dependency-free (only the patch helpers + the FigureSpec type + the AnnotationItem type) so it
 * unit-tests in node-env vitest; the Annotate panel + the tools rail consume it.
 */
import type { FigureSpec } from "./figure-spec";
import type { AnnotationItem } from "./figure-model";
import { getAt, remove, set, type Operation } from "./patch";

/** The Selom annotation primitives this slice draws (the owner's Illustrator toolset). */
export type SelomAnnoKind = "sigBracket" | "textLabel" | "arrow";

/** Ink colour for annotation strokes/text — the figure default (matches figure-spec INK). */
const INK = "#0f172a";

/** The four significance tiers (GraphPad "stars on graph"). Hand-set in v1; `starsForP` derives them. */
export const STAR_TIERS = ["*", "**", "***", "ns"] as const;
export type StarTier = (typeof STAR_TIERS)[number];

const KIND_LABEL: Record<SelomAnnoKind, string> = {
  sigBracket: "Significance",
  textLabel: "Text label",
  arrow: "Arrow / callout",
};

interface SelomTag {
  kind: SelomAnnoKind;
  id: string;
  role?: "bracket" | "label";
}

/** Read the render-inert `selom` tag off a shape/annotation, or null when it isn't a Selom item. */
function tagOf(item: unknown): SelomTag | null {
  const t = (item as { selom?: unknown } | null | undefined)?.selom;
  if (!t || typeof t !== "object") return null;
  const { kind, id, role } = t as { kind?: unknown; id?: unknown; role?: unknown };
  if (typeof id !== "string" || !id) return null;
  if (kind !== "sigBracket" && kind !== "textLabel" && kind !== "arrow") return null;
  return { kind, id, role: role === "bracket" || role === "label" ? role : undefined };
}

/** Is this shape/annotation object a Selom-tagged annotation-layer item? */
export function isSelomAnnotation(item: unknown): boolean {
  return tagOf(item) !== null;
}

function arrayAt(spec: FigureSpec, pointer: string): unknown[] {
  const v = getAt<unknown>(spec, pointer);
  return Array.isArray(v) ? v : [];
}

/**
 * One editable Selom annotation, merged across its parts (a bracket spans a shape + an annotation).
 * `annoIndex`/`shapeIndex` are the LIVE indices at read time — never persisted (they drift).
 */
export interface SelomAnnotation {
  id: string;
  kind: SelomAnnoKind;
  /** Human label for the panel row ("Significance" / "Text label" / "Arrow / callout"). */
  label: string;
  /** The editable text — the stars for a bracket, the caption for a label/arrow. */
  text: string;
  visible: boolean;
  /** Index into `layout.annotations` (the text-bearing part), or -1. */
  annoIndex: number;
  /** Index into `layout.shapes` (the bracket path), or -1. */
  shapeIndex: number;
}

/**
 * Every Selom annotation-layer item on the figure, in first-seen order. Scans both `layout.annotations`
 * and `layout.shapes`, grouping the two halves of a bracket by their shared id. Non-Selom annotations
 * (skill unit labels, threshold callouts, gene labels) are ignored — they live in the Marks panel.
 */
export function selomAnnotations(spec: FigureSpec): SelomAnnotation[] {
  const annos = arrayAt(spec, "/layout/annotations");
  const shapes = arrayAt(spec, "/layout/shapes");
  const byId = new Map<string, SelomAnnotation>();
  const order: string[] = [];
  const ensure = (tag: SelomTag): SelomAnnotation => {
    let e = byId.get(tag.id);
    if (!e) {
      e = { id: tag.id, kind: tag.kind, label: KIND_LABEL[tag.kind], text: "", visible: true, annoIndex: -1, shapeIndex: -1 };
      byId.set(tag.id, e);
      order.push(tag.id);
    }
    return e;
  };

  annos.forEach((a, i) => {
    const tag = tagOf(a);
    if (!tag) return;
    const e = ensure(tag);
    e.annoIndex = i;
    e.text = typeof (a as { text?: unknown }).text === "string" ? ((a as { text: string }).text) : "";
    e.visible = (a as { visible?: boolean }).visible !== false;
  });
  shapes.forEach((s, i) => {
    const tag = tagOf(s);
    if (!tag) return;
    const e = ensure(tag);
    e.shapeIndex = i;
    // The annotation half owns the visibility read (it always exists for a bracket); fall back to the
    // shape only when a bracket somehow lost its label.
    if (e.annoIndex < 0) e.visible = (s as { visible?: boolean }).visible !== false;
  });

  return order.map((id) => byId.get(id)!);
}

/**
 * Every NON-Selom `layout.annotations` entry, as an editable item — the generic Marks panel's list
 * (skill unit labels, threshold callouts) minus the annotation-layer items this panel owns, so an item
 * never appears in both places.
 */
export function nonSelomAnnotationItems(spec: FigureSpec): AnnotationItem[] {
  const annos = arrayAt(spec, "/layout/annotations");
  const out: AnnotationItem[] = [];
  annos.forEach((a, index) => {
    if (isSelomAnnotation(a)) return;
    out.push({
      index,
      text: typeof (a as { text?: unknown }).text === "string" ? (a as { text: string }).text : "",
      visible: (a as { visible?: boolean }).visible !== false,
    });
  });
  return out;
}

// --- add builders ----------------------------------------------------------------------

/** A short unique id for a new annotation item (not security-sensitive). */
function newId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * JSON-Patch ops to APPEND one item to a layout array (`layout.shapes` / `layout.annotations`).
 * normalizeSpec never creates these arrays, so a bare `add /…/-` could hit a missing parent — set the
 * whole array when it's absent/empty, else append with `/-`. `/layout` always exists (normalizeSpec).
 */
function appendOps(spec: FigureSpec, pointer: string, item: Record<string, unknown>): Operation[] {
  const arr = arrayAt(spec, pointer);
  return arr.length > 0 ? [set(`${pointer}/-`, item)] : [set(pointer, [item])];
}

/** Derive the star tier from a p-value (GraphPad convention). Non-finite / n.s. → "ns". */
export function starsForP(p: number): StarTier {
  if (!Number.isFinite(p) || p > 0.05) return "ns";
  if (p <= 0.001) return "***";
  if (p <= 0.01) return "**";
  return "*";
}

function finiteNumbers(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((n): n is number => typeof n === "number" && Number.isFinite(n)) : [];
}

/** Default bracket geometry (data coords): span the first two groups, sit just above the tallest bar. */
export interface BracketGeometry {
  x1: number;
  x2: number;
  /** Bracket bottom (tick ends). */
  yb: number;
  /** Bracket top (the horizontal bar + the stars). */
  yt: number;
}

export function bracketGeometry(spec: FigureSpec): BracketGeometry {
  const data = Array.isArray(spec?.data) ? spec.data : [];

  // y extent across every trace's plotted values → the bar tops the bracket clears.
  let yMax = -Infinity;
  let yMin = Infinity;
  for (const t of data) {
    for (const y of finiteNumbers((t as { y?: unknown })?.y)) {
      if (y > yMax) yMax = y;
      if (y < yMin) yMin = y;
    }
  }
  if (!Number.isFinite(yMax)) yMax = 1;
  if (!Number.isFinite(yMin)) yMin = 0;
  const span = yMax - yMin || Math.abs(yMax) || 1;
  const yb = yMax + span * 0.06;
  const yt = yMax + span * 0.12;

  // x anchors: the first two groups. Categorical x (bar/box/violin) sits at integer positions 0,1…;
  // numeric x uses the two smallest distinct values. Either way Plotly linearises the coords.
  let x1 = 0;
  let x2 = 1;
  const xt = data.find((t) => Array.isArray((t as { x?: unknown }).x) && (t as { x: unknown[] }).x.length > 0);
  if (xt) {
    const xs = (xt as { x: unknown[] }).x;
    if (typeof xs[0] === "number") {
      const nums = [...new Set(finiteNumbers(xs))].sort((a, b) => a - b);
      if (nums.length >= 2) {
        x1 = nums[0];
        x2 = nums[1];
      } else if (nums.length === 1) {
        x1 = nums[0];
        x2 = nums[0] + 1;
      }
    } else {
      x1 = 0;
      x2 = xs.length >= 2 ? 1 : 0.6;
    }
  }
  return { x1, x2, yb, yt };
}

export interface AddSigBracketOptions {
  /** Override the generated id (tests + deterministic wiring). */
  id?: string;
  /** The stars to show; defaults to `starsForP(p)` when a p-value is given, else "*". */
  stars?: string;
  /** A p-value to derive the stars from (the semi-data-aware path). */
  p?: number;
  /** Override the default geometry (e.g. a caller that knows the two groups' positions). */
  geometry?: Partial<BracketGeometry>;
}

/**
 * Add a significance bracket — a `path` shape (the staple) + an annotation (the stars) sharing one id.
 * The bracket hangs down from the top bar over the two groups; the stars sit centred just above it.
 * ONE commit → both parts appear + revert together on undo.
 */
export function addSigBracketOps(spec: FigureSpec, opts: AddSigBracketOptions = {}): Operation[] {
  const id = opts.id ?? newId("sig");
  const stars = opts.stars ?? (typeof opts.p === "number" ? starsForP(opts.p) : "*");
  const g = { ...bracketGeometry(spec), ...opts.geometry };
  const { x1, x2, yb, yt } = g;

  const shape: Record<string, unknown> = {
    type: "path",
    xref: "x",
    yref: "y",
    path: `M ${x1},${yb} L ${x1},${yt} L ${x2},${yt} L ${x2},${yb}`,
    line: { color: INK, width: 1.4 },
    fillcolor: "rgba(0,0,0,0)",
    layer: "above",
    selom: { kind: "sigBracket", id, role: "bracket" },
  };
  const anno: Record<string, unknown> = {
    x: (x1 + x2) / 2,
    y: yt,
    xref: "x",
    yref: "y",
    text: stars,
    showarrow: false,
    xanchor: "center",
    yanchor: "bottom",
    yshift: 1,
    font: { size: 15, color: INK },
    selom: { kind: "sigBracket", id, role: "label" },
  };
  return [...appendOps(spec, "/layout/shapes", shape), ...appendOps(spec, "/layout/annotations", anno)];
}

export interface AddTextOptions {
  id?: string;
  text?: string;
}

/**
 * Add a free text label — a paper-referenced floating annotation (panel letter A/B/C, gene name, custom
 * title). Defaults to the top-left corner; drag it on the artboard to place it. ONE commit.
 */
export function addTextLabelOps(spec: FigureSpec, opts: AddTextOptions = {}): Operation[] {
  const id = opts.id ?? newId("txt");
  const anno: Record<string, unknown> = {
    x: 0.02,
    y: 0.98,
    xref: "paper",
    yref: "paper",
    xanchor: "left",
    yanchor: "top",
    text: opts.text ?? "Text",
    showarrow: false,
    font: { size: 16, color: INK },
    selom: { kind: "textLabel", id },
  };
  return appendOps(spec, "/layout/annotations", anno);
}

/**
 * Add an arrow / callout — a paper-referenced annotation whose arrow points at the figure. The head is
 * the annotation anchor; the tail is a pixel offset (draggable via `annotationTail`). An empty caption
 * draws just the arrow; type a caption in the panel for a labelled callout. ONE commit.
 */
export function addArrowOps(spec: FigureSpec, opts: AddTextOptions = {}): Operation[] {
  const id = opts.id ?? newId("arr");
  const anno: Record<string, unknown> = {
    x: 0.5,
    y: 0.5,
    xref: "paper",
    yref: "paper",
    ax: -55,
    ay: 45,
    axref: "pixel",
    ayref: "pixel",
    showarrow: true,
    arrowhead: 2,
    arrowsize: 1.2,
    arrowwidth: 1.6,
    arrowcolor: INK,
    text: opts.text ?? "",
    font: { size: 12, color: INK },
    standoff: 2,
    selom: { kind: "arrow", id },
  };
  return appendOps(spec, "/layout/annotations", anno);
}

// --- edit / remove (resolve the live index by id each call — drift-proof) ----------------

/** Set an item's editable text (the stars for a bracket, the caption for a label/arrow). */
export function annotationTextOps(spec: FigureSpec, id: string, text: string): Operation[] {
  const item = selomAnnotations(spec).find((a) => a.id === id);
  return item && item.annoIndex >= 0 ? [set(`/layout/annotations/${item.annoIndex}/text`, text)] : [];
}

/** Show/hide an item — toggles both halves of a bracket (shape + stars) together. */
export function annotationVisibilityOps(spec: FigureSpec, id: string, visible: boolean): Operation[] {
  const item = selomAnnotations(spec).find((a) => a.id === id);
  if (!item) return [];
  const ops: Operation[] = [];
  if (item.annoIndex >= 0) ops.push(set(`/layout/annotations/${item.annoIndex}/visible`, visible));
  if (item.shapeIndex >= 0) ops.push(set(`/layout/shapes/${item.shapeIndex}/visible`, visible));
  return ops;
}

/**
 * Remove an item entirely (both halves of a bracket). The shape + annotation live in independent arrays,
 * so their removals never shift each other's index; only ONE item's parts are touched per call, so the
 * live indices resolved above stay valid through the batch.
 */
export function removeAnnotationOps(spec: FigureSpec, id: string): Operation[] {
  const item = selomAnnotations(spec).find((a) => a.id === id);
  if (!item) return [];
  const ops: Operation[] = [];
  if (item.annoIndex >= 0) ops.push(remove(`/layout/annotations/${item.annoIndex}`));
  if (item.shapeIndex >= 0) ops.push(remove(`/layout/shapes/${item.shapeIndex}`));
  return ops;
}

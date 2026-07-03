/**
 * ERG manual landmark marks (docs/records/erg-manual-marks/spec.md) — the shared front-end logic for
 * editing a/b (flash) and N1/P1 (flicker) landmark TIMES, used by both surfaces: the numeric Marks
 * panel (Figure-data) and the draggable dots on the canvas. Pure + framework-free so it unit-tests
 * in node-env vitest; the React pieces consume it.
 *
 * The skill seeds `layout.meta.selom.marks` (per panel: the auto/manual landmark times + source +,
 * when the dots are drawn, the marker-dot trace/point indices for hit-testing a drag). The user's
 * overrides travel back as the `manual_marks` JSON param, keyed by the segment identity, and the
 * skill re-measures the amplitude AT the chosen time. This module owns that round-trip.
 */

import type { FigureSpec } from "@/lib/figure/figure-spec";

export type MarkRole = "a" | "b" | "n1" | "p1";
export type MarkSource = "auto" | "manual" | "device";

/** A landmark dot seeded by the skill (read from meta.selom.marks). */
export interface SeededMark {
  /** Segment identity key — "{condition}|{stimulus_type}|{intensity_group}|{eye}" (flicker: hz). */
  segment: string;
  role: MarkRole;
  /** Current landmark time (ms) — the auto seed, or the operator's set time. */
  tMs: number;
  source: MarkSource;
  /** Where the auto detector placed this mark (ms) — present only on an operator-moved mark
   *  (erg-manual-marks R6 provenance), so the editor can show "moved from …". */
  autoTMs?: number;
  /** Measured amplitude (µV) at the mark — the resulting value the panel shows. */
  uv?: number;
  /** Human label for the cell, e.g. "Control · 1.0". */
  label: string;
  /** Data index of the marker-dot overlay trace (present only when the dots are drawn). */
  trace?: number;
  /** Point index within that trace (0 = first role, …) — for binding a dragged dot. */
  point?: number;
}

/** The `manual_marks` override map: { segmentKey: { field: ms } }. */
export type ManualMarks = Record<string, Partial<Record<MarkField, number>>>;
export type MarkField = "a_ms" | "b_ms" | "n1_ms" | "p1_ms";

const ROLE_FIELD: Record<MarkRole, MarkField> = { a: "a_ms", b: "b_ms", n1: "n1_ms", p1: "p1_ms" };
const ROLE_LABEL: Record<MarkRole, string> = { a: "a-wave", b: "b-wave", n1: "N1", p1: "P1" };
const ALL_FIELDS: MarkField[] = ["a_ms", "b_ms", "n1_ms", "p1_ms"];

/** Landmark role colours for the dots + the legend (docs/figure-data-capabilities/spec.md §6).
 *  KEEP IN SYNC with app/backend/skills/_erg.py ROLE_COLORS. */
export const ROLE_COLORS: Record<MarkRole, string> = {
  a: "#2563eb",
  b: "#d97706",
  n1: "#0d9488",
  p1: "#7c3aed",
};

/** A compact role tag for the drag readout ("a"/"b"/"N1"/"P1"). */
export function roleTag(role: MarkRole): string {
  return role === "n1" ? "N1" : role === "p1" ? "P1" : role;
}

/** Distinct roles present across a set of seeded marks, in first-seen order — drives the legend. */
export function rolesPresent(marks: SeededMark[]): MarkRole[] {
  const seen: MarkRole[] = [];
  for (const m of marks) if (!seen.includes(m.role)) seen.push(m.role);
  return seen;
}

export function roleField(role: MarkRole): MarkField {
  return ROLE_FIELD[role];
}

export function roleLabel(role: MarkRole): string {
  return ROLE_LABEL[role] ?? role;
}

/** Read the skill-seeded marks from a figure spec (empty when the skill emits none). */
export function readSeededMarks(spec: FigureSpec | null | undefined): SeededMark[] {
  const raw = (spec?.layout?.meta as { selom?: { marks?: unknown } } | undefined)?.selom?.marks;
  if (!Array.isArray(raw)) return [];
  const out: SeededMark[] = [];
  for (const m of raw) {
    if (!m || typeof m !== "object") continue;
    const r = m as Record<string, unknown>;
    const role = r.role as MarkRole;
    if (role !== "a" && role !== "b" && role !== "n1" && role !== "p1") continue;
    if (typeof r.segment !== "string" || typeof r.t_ms !== "number") continue;
    const src = r.source;
    out.push({
      segment: r.segment,
      role,
      tMs: r.t_ms,
      source: src === "manual" || src === "device" ? src : "auto",
      autoTMs: typeof r.auto_t_ms === "number" ? r.auto_t_ms : undefined,
      uv: typeof r.uv === "number" ? r.uv : undefined,
      label: typeof r.label === "string" ? r.label : r.segment,
      trace: typeof r.trace === "number" ? r.trace : undefined,
      point: typeof r.point === "number" ? r.point : undefined,
    });
  }
  return out;
}

/** Tolerant parse of a `manual_marks` param (JSON string or object) → the override map. */
export function parseManualMarks(raw: unknown): ManualMarks {
  let obj: unknown = raw;
  if (typeof raw === "string") {
    if (!raw.trim()) return {};
    try {
      obj = JSON.parse(raw);
    } catch {
      return {};
    }
  }
  if (!obj || typeof obj !== "object") return {};
  const out: ManualMarks = {};
  for (const [seg, val] of Object.entries(obj as Record<string, unknown>)) {
    if (!val || typeof val !== "object") continue;
    const fields: Partial<Record<MarkField, number>> = {};
    for (const f of ALL_FIELDS) {
      const v = (val as Record<string, unknown>)[f];
      if (typeof v === "number" && Number.isFinite(v)) fields[f] = v;
    }
    if (Object.keys(fields).length) out[seg] = fields;
  }
  return out;
}

/** Serialize the override map to the `manual_marks` param value ("" when empty → default path). */
export function serializeManualMarks(marks: ManualMarks): string {
  const entries = Object.entries(marks).filter(([, v]) => v && Object.keys(v).length);
  return entries.length ? JSON.stringify(Object.fromEntries(entries)) : "";
}

/** Set one segment×role override time (immutable). */
export function setManualMark(
  marks: ManualMarks,
  segment: string,
  role: MarkRole,
  tMs: number,
): ManualMarks {
  const seg = { ...(marks[segment] ?? {}), [roleField(role)]: tMs };
  return { ...marks, [segment]: seg };
}

/** Clear one segment×role override (drops the field, and the segment if now empty). */
export function clearManualMark(marks: ManualMarks, segment: string, role: MarkRole): ManualMarks {
  const seg = { ...(marks[segment] ?? {}) };
  delete seg[roleField(role)];
  const next = { ...marks };
  if (Object.keys(seg).length) next[segment] = seg;
  else delete next[segment];
  return next;
}

/** The override time for a segment×role, or undefined (still auto). */
export function manualMarkValue(
  marks: ManualMarks,
  segment: string,
  role: MarkRole,
): number | undefined {
  return marks[segment]?.[roleField(role)];
}

/** Count of operator-set overrides across all segments (for the panel summary). */
export function manualMarkCount(marks: ManualMarks): number {
  return Object.values(marks).reduce((n, seg) => n + Object.keys(seg).length, 0);
}

/**
 * Hide the a/b (N1/P1) TEXT labels on the drawn dot traces — flips each dot trace's mode from
 * "markers+text" to "markers". A pure, instant client-side restyle for the "show labels" toggle in
 * the Figure-data preview (no backend re-run needed; labels are cosmetic on already-drawn dots).
 * No-op when no dots are drawn. The dots themselves stay; only their pinned text is dropped.
 */
export function hideDotLabels(spec: FigureSpec): FigureSpec {
  const traces = new Set<number>();
  for (const m of readSeededMarks(spec)) if (m.trace !== undefined) traces.add(m.trace);
  if (!traces.size || !Array.isArray(spec?.data)) return spec;
  const data = spec.data.map((t, i) =>
    traces.has(i) && typeof t?.mode === "string" && t.mode.includes("text")
      ? { ...t, mode: "markers" }
      : t,
  );
  return { ...spec, data };
}

/**
 * Reposition the drawn dots to the STAGED manual-mark times — a pure, instant client-side preview of
 * a dot drag / numeric time edit, so the dot moves the moment you let go (no backend re-run). Each
 * overridden dot snaps to the nearest sample of its line and rides the trace's amplitude there. The
 * re-run later re-measures the value server-side; this is just the live preview. No-op when nothing
 * is staged or no dots are drawn.
 */
export function applyStagedMarks(spec: FigureSpec, manual: ManualMarks): FigureSpec {
  if (!manual || !Object.keys(manual).length || !Array.isArray(spec?.data)) return spec;
  const marks = readSeededMarks(spec);
  if (!marks.length) return spec;
  const data = [...spec.data];
  let changed = false;
  for (const m of marks) {
    if (m.trace === undefined || m.point === undefined) continue;
    const t = manualMarkValue(manual, m.segment, m.role);
    if (t === undefined) continue;
    const dot = data[m.trace];
    if (!dot || !Array.isArray(dot.x) || !Array.isArray(dot.y)) continue;
    // The line trace sharing this dot's subplot axis carries the samples the dot rides.
    const line = data.find(
      (d, i) =>
        i !== m.trace &&
        d?.xaxis === dot.xaxis &&
        typeof d?.mode === "string" &&
        d.mode.includes("lines") &&
        Array.isArray(d.x) &&
        Array.isArray(d.y),
    );
    if (!line) continue;
    const xs = line.x as number[];
    const ys = line.y as number[];
    const snapped = snapToSample(xs, t);
    const idx = xs.indexOf(snapped);
    const y = idx >= 0 ? ys[idx] : (dot.y as number[])[m.point];
    const nx = [...(dot.x as number[])];
    const ny = [...(dot.y as number[])];
    nx[m.point] = snapped;
    ny[m.point] = y;
    data[m.trace] = { ...dot, x: nx, y: ny };
    changed = true;
  }
  return changed ? { ...spec, data } : spec;
}

/** Snap a dragged x-time to the nearest sample on a trace's x-array (the dot is sticky to the line). */
export function snapToSample(xs: readonly number[], x: number): number {
  if (!xs.length) return x;
  let best = xs[0];
  let bestD = Math.abs(xs[0] - x);
  for (let i = 1; i < xs.length; i++) {
    const d = Math.abs(xs[i] - x);
    if (d < bestD) {
      bestD = d;
      best = xs[i];
    }
  }
  return best;
}

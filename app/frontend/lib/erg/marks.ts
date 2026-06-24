/**
 * ERG manual landmark marks (docs/erg-manual-marks/spec.md) — the shared front-end logic for
 * editing a/b (flash) and N1/P1 (flicker) landmark TIMES, used by both surfaces: the numeric Marks
 * panel (Figure-data) and the draggable dots on the canvas. Pure + framework-free so it unit-tests
 * in node-env vitest; the React pieces consume it.
 *
 * The skill seeds `layout.meta.selom.marks` (per panel: the auto/manual landmark times + source +,
 * when the dots are drawn, the marker-dot trace/point indices for hit-testing a drag). The user's
 * overrides travel back as the `manual_marks` JSON param, keyed by the segment identity, and the
 * skill re-measures the amplitude AT the chosen time. This module owns that round-trip.
 */

import type { FigureSpec } from "@/lib/figure-spec";

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

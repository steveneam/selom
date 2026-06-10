import { applyPatch, getValueByPointer, type Operation } from "fast-json-patch";
import type { FigureSpec } from "./figure-spec";

export type { Operation };

/** Read a value at a JSON pointer, or `fallback` if the path is absent. */
export function getAt<T = unknown>(spec: unknown, pointer: string, fallback?: T): T | undefined {
  try {
    const v = getValueByPointer(spec, pointer);
    return (v === undefined ? fallback : (v as T));
  } catch {
    return fallback;
  }
}

/**
 * Apply RFC-6902 ops to a figure spec immutably (input untouched, new doc out).
 * This is the ONE engine: property-panel clicks and the future LLM copilot both
 * funnel through here, so undo/redo, persistence, and export behave identically.
 */
export function applyPatches(spec: FigureSpec, ops: Operation[]): FigureSpec {
  return applyPatch(spec, ops, /* validate */ false, /* mutate */ false)
    .newDocument as FigureSpec;
}

/**
 * `add` doubles as set: on an existing object member it replaces, on a missing one
 * it creates — robust for optional leaves (marker.color, legend.x, …) as long as
 * normalizeSpec() guaranteed the parent object exists.
 */
export const set = (path: string, value: unknown): Operation => ({ op: "add", path, value });
export const remove = (path: string): Operation => ({ op: "remove", path });

/** Build the set ops for a legend position preset. */
export function legendPosOps(p: {
  x: number;
  y: number;
  xanchor: string;
  yanchor: string;
}): Operation[] {
  return [
    set("/layout/legend/x", p.x),
    set("/layout/legend/y", p.y),
    set("/layout/legend/xanchor", p.xanchor),
    set("/layout/legend/yanchor", p.yanchor),
  ];
}

// data[].x/y/z (and structural trace add/remove) require a backend recompute;
// everything else (layout.*, marker, line, name, visible) is client-only/instant.
const DATA_VALUE_PATH = /^\/data\/\d+\/(x|y|z|values|labels|locations|customdata)(\/|$)/;
const TRACE_STRUCT_PATH = /^\/data\/(-|\d+)$/;

export function isServerOp(op: Operation): boolean {
  if (DATA_VALUE_PATH.test(op.path)) return true;
  if (TRACE_STRUCT_PATH.test(op.path) && op.op !== "replace") return true;
  return false;
}

/** "client" → apply locally and re-render; "server" → POST to re-run the pipeline. */
export function classifyPatch(ops: Operation[]): "client" | "server" {
  return ops.some(isServerOp) ? "server" : "client";
}

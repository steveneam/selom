import type { FigureSpec } from "@/lib/figure-spec";

/**
 * Figure payload audit (architecture-consistency Task E2).
 *
 * A figure is the unit that crosses the wire and lives in the editor's history. An
 * unbounded one (a skill that ships every one of 500k points, or a giant embedded data
 * URI) bloats the payload, the localStorage project store, and the render. This is the
 * pure size/point accounting + named advisory ceilings; `payloadWarnings` returns the
 * human-readable flags FigureCanvas surfaces as a once-per-figure dev warning (the same
 * non-blocking telemetry discipline as `warnDeadKnob`). Advisory, never throws.
 */

/** Soft ceiling on a figure's serialized size (bytes) — over this, investigate the skill. */
export const PAYLOAD_BYTE_CEILING = 8 * 1024 * 1024; // 8 MB
/** Soft ceiling on total plotted points across all traces. */
export const PAYLOAD_POINT_CEILING = 200_000;

export interface PayloadStats {
  bytes: number;
  points: number;
  traces: number;
}

function arrLen(v: unknown): number {
  return Array.isArray(v) ? v.length : 0;
}

/** Points contributed by one trace: the largest coordinate array, with 2-D `z` flattened. */
function tracePoints(trace: unknown): number {
  const t = (trace ?? {}) as Record<string, unknown>;
  const z = t.z;
  if (Array.isArray(z)) {
    // heatmap/contour: rows × widest row (cells); falls back to row count for a 1-D z.
    const rows = z.length;
    const cols = Array.isArray(z[0]) ? Math.max(...z.map((r) => arrLen(r))) : 1;
    return rows * cols;
  }
  return Math.max(arrLen(t.x), arrLen(t.y), arrLen(t.lat), arrLen(t.lon), arrLen(t.values));
}

/** Serialized byte size (UTF-8) of an object via JSON. Fail-soft → 0 on a cyclic/odd value. */
function jsonBytes(value: unknown): number {
  try {
    const json = JSON.stringify(value) ?? "";
    // Blob gives an exact UTF-8 byte count where available; else fall back to char length.
    if (typeof Blob !== "undefined") return new Blob([json]).size;
    return json.length;
  } catch {
    return 0;
  }
}

/** Size + point accounting for a figure spec. */
export function figurePayload(spec: Pick<FigureSpec, "data"> | null | undefined): PayloadStats {
  const data = Array.isArray(spec?.data) ? spec.data : [];
  const points = data.reduce<number>((sum, tr) => sum + tracePoints(tr), 0);
  return { bytes: jsonBytes(spec ?? {}), points, traces: data.length };
}

/** Human-readable advisory flags for a figure that exceeds a ceiling (empty = within budget). */
export function payloadWarnings(spec: Pick<FigureSpec, "data"> | null | undefined): string[] {
  const { bytes, points } = figurePayload(spec);
  const out: string[] = [];
  if (bytes > PAYLOAD_BYTE_CEILING) {
    out.push(
      `figure payload ${(bytes / 1024 / 1024).toFixed(1)} MB exceeds the ${(
        PAYLOAD_BYTE_CEILING /
        1024 /
        1024
      ).toFixed(0)} MB ceiling`,
    );
  }
  if (points > PAYLOAD_POINT_CEILING) {
    out.push(
      `figure plots ${points.toLocaleString()} points, over the ${PAYLOAD_POINT_CEILING.toLocaleString()} ceiling — consider decimating`,
    );
  }
  return out;
}

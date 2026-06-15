/**
 * Bridge from Plotly's own canvas gestures (drag a legend, drag/retext an
 * annotation, double-click an axis title, drag a colour bar) into the SAME
 * RFC-6902 JSON-Patch store the Inspector and the future LLM copilot write to.
 *
 * Plotly fires `plotly_relayout` for layout-level edits (legend / annotations /
 * shapes / titles) and `plotly_restyle` for trace-level ones (colour bar, legend
 * label = trace name). Both arrive as flat dotted/bracketed keys; we translate
 * the editable ones into `/layout/...` or `/data/{i}/...` set-ops and ignore all
 * transient view state (zoom, pan, autosize, dragmode, axis ranges) so a single
 * drag becomes exactly one undo entry.
 */
import { getAt, set, type Operation } from "@/lib/patch";
import type { FigureSpec } from "@/lib/figure-spec";

/** Layout keys that represent a persisted reposition/retext gesture. */
function isEditableLayoutKey(key: string): boolean {
  return (
    key.startsWith("legend.") ||
    key.startsWith("annotations[") ||
    key.startsWith("shapes[") ||
    key === "title.text" ||
    /^[xy]axis\d*\.title\.text$/.test(key)
  );
}

/** Trace keys we persist from a restyle gesture (colour bar move/retext, rename). */
function isEditableTraceKey(key: string): boolean {
  return key.includes("colorbar") || key === "name";
}

/**
 * "annotations[0].x" → ["annotations","0","x"]; "legend.x" → ["legend","x"];
 * "xaxis.title.text" → ["xaxis","title","text"]. Plotly keys never contain the
 * JSON-pointer escape chars (`/` `~`), so the segments map straight to a pointer.
 */
export function keyToSegments(key: string): string[] {
  const segs: string[] = [];
  for (const part of key.split(".")) {
    const name = part.replace(/\[\d+\]/g, "");
    if (name) segs.push(name);
    const idx = part.match(/\[(\d+)\]/g);
    if (idx) for (const m of idx) segs.push(m.slice(1, -1));
  }
  return segs;
}

/**
 * Append a set-op for `pointer`, first creating any missing ancestor objects so
 * fast-json-patch never adds a leaf under an undefined parent. A colour-bar drag,
 * for instance, emits `colorbar.x` even when the trace carries no explicit
 * `colorbar` object (Plotly defaults it), so `/data/i/colorbar` must be created
 * before `/data/i/colorbar/x`. `ensured` dedupes ancestor creation across the batch
 * so a shared parent isn't re-created (which would wipe a sibling set earlier in it).
 */
function pushSet(
  ops: Operation[],
  ensured: Set<string>,
  spec: FigureSpec,
  pointer: string,
  value: unknown,
): void {
  const segs = pointer.split("/").slice(1);
  let path = "";
  for (let i = 0; i < segs.length - 1; i++) {
    path += "/" + segs[i];
    if (ensured.has(path)) continue;
    ensured.add(path);
    if (getAt(spec, path) === undefined) ops.push({ op: "add", path, value: {} });
  }
  ops.push(set(pointer, value));
}

/** Translate a `plotly_relayout` event into layout set-ops (no-ops dropped). */
export function relayoutToOps(spec: FigureSpec, update: Record<string, unknown>): Operation[] {
  const ops: Operation[] = [];
  const ensured = new Set<string>();
  for (const [key, value] of Object.entries(update)) {
    if (value === undefined || value === null) continue;
    if (!isEditableLayoutKey(key)) continue;
    const pointer = "/layout/" + keyToSegments(key).join("/");
    if (getAt(spec, pointer) === value) continue;
    pushSet(ops, ensured, spec, pointer, value);
  }
  return ops;
}

/**
 * Translate a `plotly_restyle` event (`[update, traceIndices]`) into trace set-ops.
 * Restyle values are arrays aligned to `traceIndices` (a length-1 array applies to
 * every listed trace); a bare scalar applies to all.
 */
export function restyleToOps(
  spec: FigureSpec,
  update: Record<string, unknown>,
  traceIndices: number[],
): Operation[] {
  const ops: Operation[] = [];
  const ensured = new Set<string>();
  const indices = traceIndices?.length ? traceIndices : spec.data.map((_, i) => i);
  for (const [key, raw] of Object.entries(update)) {
    if (!isEditableTraceKey(key)) continue;
    const tail = keyToSegments(key).join("/");
    indices.forEach((ti, j) => {
      const value = Array.isArray(raw) ? (raw.length === 1 ? raw[0] : raw[j]) : raw;
      if (value === undefined || value === null) return;
      const pointer = `/data/${ti}/${tail}`;
      if (getAt(spec, pointer) === value) return;
      pushSet(ops, ensured, spec, pointer, value);
    });
  }
  return ops;
}

/**
 * Axis-gridline op builders (Pillar-2 slice 1, docs/pillar-2-direct-manipulation/spec.md §5.1).
 *
 * The Style panel's "Axis gridlines" group edits NATIVE Plotly layout leaves — showgrid /
 * gridcolor / gridwidth / griddash / dtick, plus a minor.* sub-grid — so every gridline change is a
 * client-only, instant, undoable JSON-Patch on the spec (classifyPatch → "client"; render = f(spec);
 * WYSIWYG export unchanged — no persisted-contract change). Both x and y axes are written together
 * (uniform gridlines, matching the Axes panel convention); `/layout/xaxis` + `/layout/yaxis` always
 * exist (normalizeSpec guarantees them), so a leaf `set` (add) always has a live parent.
 *
 * `minor` is the one exception written as a whole merged object: normalizeSpec does NOT create it, so
 * a bare `add /layout/xaxis/minor/showgrid` would fail with no parent — we read the current minor and
 * write it back with the changed field.
 *
 * Pure + dependency-free (only the patch helpers + the FigureSpec type) so it unit-tests in node-env
 * vitest; the Style panel's GridlineControls consume it.
 */
import type { FigureSpec } from "./figure-spec";
import { getAt, set, type Operation } from "./patch";

/** The two Cartesian axes a uniform gridline edit targets. */
const AXES = ["xaxis", "yaxis"] as const;

/** Plotly `griddash` presets surfaced in the line-style picker. */
export const GRID_DASH_OPTIONS: { value: string; label: string }[] = [
  { value: "solid", label: "Solid" },
  { value: "dot", label: "Dot" },
  { value: "dash", label: "Dash" },
  { value: "dashdot", label: "Dash-dot" },
];

/** Read-time fallbacks — mirror normalizeSpec's axis defaults (showgrid, gridcolor) + Plotly's own
 *  defaults for the leaves normalizeSpec leaves unset (gridwidth 1, griddash solid). */
export const GRID_DEFAULTS = {
  showgrid: false, // normalizeSpec now defaults gridless (parity-audit row 5) — keep these in step
  gridcolor: "#e2e8f0",
  gridwidth: 1,
  griddash: "solid",
  minorDash: "dot",
} as const;

/** The current gridline state, read off the x-axis (the writers keep x + y symmetric). */
export interface GridlineState {
  showgrid: boolean;
  gridcolor: string;
  gridwidth: number;
  griddash: string;
  /** Fixed tick/grid spacing, or null when auto (unset). */
  dtick: number | null;
  minorShow: boolean;
  minorDash: string;
}

export function readGridlines(spec: FigureSpec): GridlineState {
  const dtickRaw = getAt<unknown>(spec, "/layout/xaxis/dtick");
  return {
    showgrid: getAt<boolean>(spec, "/layout/xaxis/showgrid", GRID_DEFAULTS.showgrid)!,
    gridcolor: getAt<string>(spec, "/layout/xaxis/gridcolor", GRID_DEFAULTS.gridcolor)!,
    gridwidth: getAt<number>(spec, "/layout/xaxis/gridwidth", GRID_DEFAULTS.gridwidth)!,
    griddash: getAt<string>(spec, "/layout/xaxis/griddash", GRID_DEFAULTS.griddash)!,
    dtick: typeof dtickRaw === "number" ? dtickRaw : null,
    minorShow: getAt<boolean>(spec, "/layout/xaxis/minor/showgrid", false)!,
    minorDash: getAt<string>(spec, "/layout/xaxis/minor/griddash", GRID_DEFAULTS.minorDash)!,
  };
}

/** One layout leaf, set uniformly on both axes. */
function bothAxes(leaf: string, value: unknown): Operation[] {
  return AXES.map((ax) => set(`/layout/${ax}/${leaf}`, value));
}

export const gridShowOps = (show: boolean): Operation[] => bothAxes("showgrid", show);
export const gridColorOps = (color: string): Operation[] => bothAxes("gridcolor", color);
export const gridWidthOps = (width: number): Operation[] => bothAxes("gridwidth", width);
export const gridDashOps = (dash: string): Operation[] => bothAxes("griddash", dash);

/**
 * Grid spacing (`dtick`): a positive number pins a fixed interval — Plotly then coerces
 * `tickmode` to "linear" on its own — while null reverts to auto (Plotly's default tick spacing).
 */
export function gridSpacingOps(dtick: number | null): Operation[] {
  return bothAxes("dtick", dtick != null && dtick > 0 ? dtick : null);
}

/**
 * Minor gridlines write the WHOLE `minor` object (merged over whatever's present) because
 * normalizeSpec never creates it — a bare leaf `add` would have no parent. Existing minor props are
 * preserved; only the changed field is overwritten.
 */
function minorMergeOps(spec: FigureSpec, patch: Record<string, unknown>): Operation[] {
  return AXES.map((ax) => {
    const cur = getAt<Record<string, unknown>>(spec, `/layout/${ax}/minor`, {})!;
    return set(`/layout/${ax}/minor`, { ...cur, ...patch });
  });
}

/**
 * Toggle-ON also writes the minor dash the control is showing (`readGridlines().minorDash` — the
 * live value or the "dot" fallback), not just `showgrid:true`. Without it the "Minor style" select
 * displays the fallback dash while Plotly renders its own default until the user re-picks it — the
 * panel's live/WYSIWYG promise fails for this one leaf (docs/parallel-sprint-1/followups.md P1).
 * Toggle-OFF leaves any existing dash untouched (it's hidden anyway).
 */
export const minorShowOps = (spec: FigureSpec, show: boolean): Operation[] =>
  minorMergeOps(spec, show ? { showgrid: true, griddash: readGridlines(spec).minorDash } : { showgrid: false });
export const minorDashOps = (spec: FigureSpec, dash: string): Operation[] =>
  minorMergeOps(spec, { griddash: dash });

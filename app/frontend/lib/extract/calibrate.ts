/**
 * Calibration math for the chart-extractor (X4 picker). Pure + unit-tested so the one
 * load-bearing bit — mapping a click on a scaled <img> to the natural-pixel coordinate
 * the backend's recover_* expects — is verified without a browser.
 *
 * A click is stored as a FRACTION (0..1) of the image (resize-robust for marker overlay),
 * then converted to natural pixels at request time via the image's naturalWidth/Height.
 * The backend (extract/chart_to_data.Axis) keys each axis off px0/px1: the x-axis refs
 * contribute their horizontal pixel, the y-axis refs their vertical pixel.
 */

export type AxisKey = "x" | "y";

export type ChartForm = "bar" | "line" | "scatter";
export const CHART_FORMS: ChartForm[] = ["bar", "line", "scatter"];

/** A placed calibration reference: a click (as image fractions) the user assigns a data value. */
export interface RefPoint {
  fx: number; // fraction across the image width [0,1]
  fy: number; // fraction down the image height [0,1]
  value: number | null; // the data value typed at this tick (null until entered)
}

export interface CalibrationState {
  x: [RefPoint | null, RefPoint | null];
  y: [RefPoint | null, RefPoint | null];
  xLog: boolean;
  yLog: boolean;
}

export const EMPTY_CALIBRATION: CalibrationState = {
  x: [null, null],
  y: [null, null],
  xLog: false,
  yLog: false,
};

const clamp01 = (n: number) => (n < 0 ? 0 : n > 1 ? 1 : n);

/** Click offset on a rendered image (px) -> fraction of the image [0,1]. */
export function toFraction(
  offsetX: number,
  offsetY: number,
  width: number,
  height: number,
): { fx: number; fy: number } {
  if (width <= 0 || height <= 0) return { fx: 0, fy: 0 };
  return { fx: clamp01(offsetX / width), fy: clamp01(offsetY / height) };
}

/** A ref is usable once it is placed AND given a finite numeric value. */
function ready(r: RefPoint | null): r is RefPoint & { value: number } {
  return !!r && r.value !== null && Number.isFinite(r.value);
}

export function calibrationComplete(c: CalibrationState): boolean {
  return ready(c.x[0]) && ready(c.x[1]) && ready(c.y[0]) && ready(c.y[1]);
}

/** Two refs on the same axis must not share a pixel — the backend divides by Δpx. */
export function calibrationDegenerate(c: CalibrationState, naturalW: number, naturalH: number): boolean {
  const dx = c.x[0] && c.x[1] ? Math.abs(c.x[0].fx - c.x[1].fx) * naturalW : 1;
  const dy = c.y[0] && c.y[1] ? Math.abs(c.y[0].fy - c.y[1].fy) * naturalH : 1;
  return dx < 1 || dy < 1;
}

export interface ExtractOptions {
  color?: string | null; // #rrggbb or r,g,b
  labels?: string[] | null; // bar labels
  seriesName?: string;
  xName?: string;
  yName?: string;
}

/**
 * Assemble the flat query params the /extract/chart endpoint reads. Throws if the
 * calibration is incomplete — the caller gates the Extract button on calibrationComplete,
 * so this is a guard, not a UX path.
 */
export function buildExtractParams(
  c: CalibrationState,
  form: ChartForm,
  naturalW: number,
  naturalH: number,
  opts: ExtractOptions = {},
): Record<string, string> {
  if (!calibrationComplete(c)) throw new Error("calibration is incomplete");
  const [x0, x1] = c.x as [RefPoint & { value: number }, RefPoint & { value: number }];
  const [y0, y1] = c.y as [RefPoint & { value: number }, RefPoint & { value: number }];
  const params: Record<string, string> = {
    form,
    x_px0: String(x0.fx * naturalW),
    x_val0: String(x0.value),
    x_px1: String(x1.fx * naturalW),
    x_val1: String(x1.value),
    y_px0: String(y0.fy * naturalH),
    y_val0: String(y0.value),
    y_px1: String(y1.fy * naturalH),
    y_val1: String(y1.value),
  };
  if (c.xLog) params.x_log = "1";
  if (c.yLog) params.y_log = "1";
  if (opts.color) params.color = opts.color;
  if (opts.labels && opts.labels.length) params.labels = opts.labels.join(",");
  if (opts.seriesName) params.series_name = opts.seriesName;
  if (opts.xName) params.x_name = opts.xName;
  if (opts.yName) params.y_name = opts.yName;
  return params;
}

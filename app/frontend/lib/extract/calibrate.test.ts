import { describe, expect, it } from "vitest";

import {
  buildExtractParams,
  calibrationComplete,
  calibrationDegenerate,
  EMPTY_CALIBRATION,
  toFraction,
  type CalibrationState,
} from "./calibrate";

const FULL: CalibrationState = {
  x: [
    { fx: 0.1, fy: 0.9, value: 0 },
    { fx: 0.9, fy: 0.9, value: 100 },
  ],
  y: [
    { fx: 0.1, fy: 0.9, value: 0 },
    { fx: 0.1, fy: 0.1, value: 50 },
  ],
  xLog: false,
  yLog: false,
};

describe("toFraction", () => {
  it("maps a click offset to a [0,1] fraction of the rendered image", () => {
    expect(toFraction(50, 25, 200, 100)).toEqual({ fx: 0.25, fy: 0.25 });
  });
  it("clamps out-of-bounds offsets", () => {
    expect(toFraction(-10, 250, 200, 100)).toEqual({ fx: 0, fy: 1 });
  });
  it("is safe on a zero-size image", () => {
    expect(toFraction(10, 10, 0, 0)).toEqual({ fx: 0, fy: 0 });
  });
});

describe("calibrationComplete", () => {
  it("is false until all four refs are placed AND valued", () => {
    expect(calibrationComplete(EMPTY_CALIBRATION)).toBe(false);
    // placed but no value typed yet
    const placedOnly: CalibrationState = { ...FULL, x: [{ fx: 0.1, fy: 0.9, value: null }, FULL.x[1]] };
    expect(calibrationComplete(placedOnly)).toBe(false);
  });
  it("is true once every axis has two placed, valued refs", () => {
    expect(calibrationComplete(FULL)).toBe(true);
  });
});

describe("buildExtractParams", () => {
  it("converts fractions to natural pixels per axis and carries the typed values", () => {
    const p = buildExtractParams(FULL, "bar", 1000, 800);
    expect(p.form).toBe("bar");
    expect(p.x_px0).toBe("100"); // 0.1 * 1000 (x uses the horizontal fraction)
    expect(p.x_px1).toBe("900");
    expect(p.x_val0).toBe("0");
    expect(p.x_val1).toBe("100");
    expect(p.y_px0).toBe("720"); // 0.9 * 800 (y uses the vertical fraction)
    expect(p.y_px1).toBe("80"); // 0.1 * 800
    expect(p.y_val1).toBe("50");
    expect("x_log" in p).toBe(false);
  });
  it("adds log flags + optional naming/labels/colour when set", () => {
    const p = buildExtractParams({ ...FULL, yLog: true }, "bar", 100, 100, {
      color: "#ff0000",
      labels: ["WT", "KO"],
      seriesName: "expr",
      xName: "genotype",
      yName: "TPM",
    });
    expect(p.y_log).toBe("1");
    expect(p.color).toBe("#ff0000");
    expect(p.labels).toBe("WT,KO");
    expect(p.series_name).toBe("expr");
    expect(p.x_name).toBe("genotype");
  });
  it("throws if the calibration is incomplete", () => {
    expect(() => buildExtractParams(EMPTY_CALIBRATION, "bar", 100, 100)).toThrow();
  });
});

describe("calibrationDegenerate", () => {
  it("flags coincident refs on an axis (backend divides by Δpx)", () => {
    const same: CalibrationState = { ...FULL, x: [FULL.x[0], { fx: 0.1, fy: 0.9, value: 100 }] };
    expect(calibrationDegenerate(same, 1000, 800)).toBe(true);
  });
  it("passes a well-separated calibration", () => {
    expect(calibrationDegenerate(FULL, 1000, 800)).toBe(false);
  });
});

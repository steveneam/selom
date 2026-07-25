import { describe, expect, it } from "vitest";

import {
  AUTO_COLLAPSE_MAX_WIDTH,
  ZOOM_LADDER,
  fitScale,
  formatZoom,
  shouldAutoCollapse,
  stepZoom,
} from "@/lib/ui/editor-room";

/**
 * The room-budget rule (`W-2`). Small, but it decides what the editor looks like the moment a user
 * arrives, and it is consulted by TWO rails (the project workrail and the inspector dock) that must
 * agree — the ~506px target at 1280 is unreachable unless both collapse. A drift here shows up as
 * "the inspector is closed but the workrail isn't", which reads as a bug rather than a layout.
 */
describe("shouldAutoCollapse", () => {
  it("collapses at and below the threshold — the boundary is INCLUDED", () => {
    // The owner declined to treat 1280 as degraded, so 1280 itself must work. An exclusive
    // comparison at the boundary would leave exactly the width this was built for uncollapsed.
    expect(shouldAutoCollapse(AUTO_COLLAPSE_MAX_WIDTH)).toBe(true);
    expect(shouldAutoCollapse(AUTO_COLLAPSE_MAX_WIDTH - 1)).toBe(true);
    expect(shouldAutoCollapse(1280)).toBe(true);
    expect(shouldAutoCollapse(1024)).toBe(true);
  });

  it("covers 1440 — the width that proved a 1280 threshold wrong", () => {
    // With both rails expanded the fixed chrome measures 1193px, so 1440 leaves the plot 247px:
    // WORSE than the 571px a collapsed 1280 gives. A threshold of 1280 meant widening the window
    // shrank the figure. This case is the regression guard for that, and it is why the threshold is
    // derived from the 506px target (506 + 1193 ≈ 1699) instead of from the reported viewport.
    expect(shouldAutoCollapse(1440)).toBe(true);
    expect(shouldAutoCollapse(1600)).toBe(true);
  });

  it("leaves a genuinely wide viewport alone", () => {
    // Past the threshold the expanded layout can afford the target on its own (1920 measures 718px
    // of plot), so collapsing there would take the inspector away to solve a problem that is gone.
    expect(shouldAutoCollapse(AUTO_COLLAPSE_MAX_WIDTH + 1)).toBe(false);
    expect(shouldAutoCollapse(1920)).toBe(false);
    expect(shouldAutoCollapse(2560)).toBe(false);
  });

  it("answers NO when the width is unknown, rather than guessing", () => {
    // SSR and the first client paint cannot read `window`. Arriving expanded and collapsing a frame
    // later is a smaller error than rendering a hidden inspector on a wide screen for no visible
    // reason — so an unknown width must never read as "narrow".
    expect(shouldAutoCollapse(0)).toBe(false);
    expect(shouldAutoCollapse(Number.NaN)).toBe(false);
    expect(shouldAutoCollapse(-1)).toBe(false);
    expect(shouldAutoCollapse(Number.POSITIVE_INFINITY)).toBe(false);
  });
});

describe("stepZoom", () => {
  it("always moves in the direction pressed, from a value BETWEEN rungs", () => {
    // The case a naive nearest-rung snap gets wrong: "fit" resolves to an arbitrary scale like 0.63,
    // and pressing + must never make the figure smaller (0.63 → 0.75, not → 0.5).
    expect(stepZoom(0.63, 1)).toBe(0.75);
    expect(stepZoom(0.63, -1)).toBe(0.5);
    expect(stepZoom(1.2, 1)).toBe(1.5);
    expect(stepZoom(1.2, -1)).toBe(1);
  });

  it("moves off a rung rather than sticking to it", () => {
    // Float equality is the trap here: 1 is ON the ladder, so a `>=` comparison would return 1
    // again and the button would look dead.
    expect(stepZoom(1, 1)).toBe(1.5);
    expect(stepZoom(1, -1)).toBe(0.75);
  });

  it("clamps at both ends instead of running off the ladder", () => {
    const min = ZOOM_LADDER[0];
    const max = ZOOM_LADDER[ZOOM_LADDER.length - 1];
    expect(stepZoom(min, -1)).toBe(min);
    expect(stepZoom(max, 1)).toBe(max);
  });
});

describe("fitScale", () => {
  it("returns exactly 1 for a figure the size of its stage — the responsive case", () => {
    // A responsive figure IS the card, so it already fits. Anything but 1 here would be the zoom
    // control lying about a figure that was never scaled.
    expect(fitScale({ width: 800, height: 600 }, { width: 800, height: 600 })).toBe(1);
  });

  it("shrinks a fixed-size figure to fit, on its tightest axis", () => {
    // The real case: an ERG trace grid declares 960x640 and lands in a stage far narrower.
    expect(fitScale({ width: 480, height: 640 }, { width: 960, height: 640 })).toBeCloseTo(0.5);
    expect(fitScale({ width: 960, height: 320 }, { width: 960, height: 640 })).toBeCloseTo(0.5);
  });

  it("never magnifies past 1:1 — Fit means see all of it, not fill the stage", () => {
    expect(fitScale({ width: 2000, height: 2000 }, { width: 400, height: 300 })).toBe(1);
  });

  it("falls back to 1:1 when anything is unmeasurable", () => {
    // A hidden or not-yet-laid-out editor reports zeros; scaling by 0 or Infinity would render the
    // figure invisible or astronomically large, so identity is the only safe answer.
    expect(fitScale({ width: 0, height: 0 }, { width: 960, height: 640 })).toBe(1);
    expect(fitScale({ width: 800, height: 600 }, { width: 0, height: 0 })).toBe(1);
    expect(fitScale({ width: Number.NaN, height: 600 }, { width: 960, height: 640 })).toBe(1);
  });
});

describe("formatZoom", () => {
  it("reports whole percentages", () => {
    expect(formatZoom(1)).toBe("100%");
    expect(formatZoom(0.634)).toBe("63%");
    expect(formatZoom(4)).toBe("400%");
  });

  it("degrades to 100% rather than showing NaN%", () => {
    expect(formatZoom(Number.NaN)).toBe("100%");
    expect(formatZoom(0)).toBe("100%");
  });
});

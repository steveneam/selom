import { describe, expect, it } from "vitest";

import { keysChanged } from "./reset-keys";

/** The reset-key semantics that decide whether a stuck PaneBoundary auto-clears on a switch. */
describe("error-boundary resetKeys comparison", () => {
  it("is false for identical keys (no spurious reset within a figure)", () => {
    const spec = { a: 1 };
    expect(keysChanged(["fig1", spec], ["fig1", spec])).toBe(false);
    expect(keysChanged([], [])).toBe(false);
    expect(keysChanged(undefined, undefined)).toBe(false);
  });

  it("is true when a key value changes (figure/dataset/skill switch)", () => {
    expect(keysChanged(["fig1"], ["fig2"])).toBe(true);
    const a = { z: 1 };
    const b = { z: 1 };
    expect(keysChanged([a], [b])).toBe(true); // different object refs = a new spec → reset
  });

  it("is true when the key count changes", () => {
    expect(keysChanged(["fig1"], ["fig1", "skill"])).toBe(true);
    expect(keysChanged([], ["fig1"])).toBe(true);
  });

  it("uses Object.is so a stable reference (incl. NaN) does not false-trigger", () => {
    expect(keysChanged([NaN], [NaN])).toBe(false);
    const ref = {};
    expect(keysChanged([ref], [ref])).toBe(false);
  });
});

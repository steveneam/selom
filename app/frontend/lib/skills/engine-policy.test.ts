import { describe, expect, it } from "vitest";
import { isStubEngineFigure } from "./engine-policy";

describe("isStubEngineFigure (WS1.1 honesty predicate)", () => {
  it("warns for a stub-engine run", () => {
    expect(isStubEngineFigure({ environment: { engine_policy: "stub" } })).toBe(true);
  });

  it("does NOT warn for a real run", () => {
    expect(isStubEngineFigure({ environment: { engine_policy: "real" } })).toBe(false);
  });

  it("does NOT warn for a legacy raw 'auto' value — only the resolved 'stub' warns", () => {
    // A pre-WS1.1 figure stamped the raw env ("auto"); it must not cry wolf on a real run.
    expect(isStubEngineFigure({ environment: { engine_policy: "auto" } })).toBe(false);
  });

  it("does NOT warn when the bundle / environment is absent", () => {
    expect(isStubEngineFigure(undefined)).toBe(false);
    expect(isStubEngineFigure(null)).toBe(false);
    expect(isStubEngineFigure({})).toBe(false);
    expect(isStubEngineFigure({ environment: {} })).toBe(false);
  });
});

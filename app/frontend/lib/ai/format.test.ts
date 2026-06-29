import { describe, expect, it } from "vitest";

/**
 * Unit tests for the pure presentational helpers behind the AI marker + activity feed (S5).
 * The components are presentational and verified live in the browser (no component-render harness
 * — node-env logic tests are the repo convention); these cover the logic those views depend on:
 * the provenance timestamp format and the action verb map.
 */

import { describeAction, formatApprovedAt } from "./format";

describe("formatApprovedAt", () => {
  it("returns an empty string for a missing or unparseable timestamp (tolerant tooltip)", () => {
    expect(formatApprovedAt(undefined)).toBe("");
    expect(formatApprovedAt("")).toBe("");
    expect(formatApprovedAt("not-a-date")).toBe("");
  });

  it("formats a valid ISO timestamp to a short label", () => {
    const out = formatApprovedAt("2026-06-29T14:32:00Z");
    expect(out).not.toBe("");
    // Locale-dependent exact text, but the month + day must appear.
    expect(out).toMatch(/Jun/);
    expect(out).toMatch(/29|30/); // tz can shift the day by one
  });
});

describe("describeAction", () => {
  it("maps each action type to a plain-language verb", () => {
    expect(describeAction({ type: "set_param" })).toBe("Set parameter");
    expect(describeAction({ type: "select_skill" })).toBe("Selected skill");
    expect(describeAction({ type: "restyle_figure" })).toBe("Restyled figure");
    expect(describeAction({ type: "apply_cleaning_step" })).toBe("Applied cleaning step");
  });

  it("falls back to a generic verb for an unknown type", () => {
    expect(describeAction({ type: "future_action" as never })).toBe("Changed");
  });
});

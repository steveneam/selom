import { describe, expect, it } from "vitest";

/**
 * Unit tests for the pure presentational helpers behind the AI marker + activity feed (S5).
 * The components are presentational and verified live in the browser (no component-render harness
 * — node-env logic tests are the repo convention); these cover the logic those views depend on:
 * the provenance timestamp format and the action verb map.
 */

import {
  appliedMarkerTip,
  describeAction,
  formatApprovedAt,
  proposedMarkerTip,
  stagedMarkerTip,
} from "./format";
import type { AiAction } from "./types";

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

describe("the ✨ marker tooltips (#12 approver · #13 'proposed by')", () => {
  const action: AiAction = {
    action_id: "a1", actor: "ai", type: "set_param", target: "resolution", prompt: "tighten",
    model: "llama-3.3-70b", approved_by: "user-42", approved_at: "2026-06-29T14:32:00Z",
  };

  it("applied tip surfaces actor · model · date · approved_by (#12)", () => {
    const tip = appliedMarkerTip(action);
    expect(tip).toContain("ai");
    expect(tip).toContain("llama-3.3-70b");
    expect(tip).toMatch(/Jun/);
    expect(tip).toContain("approved by user-42"); // the server-trusted approver is now surfaced
  });

  it("applied tip omits an absent approver / model / date (no blank fields)", () => {
    const tip = appliedMarkerTip({ actor: "ai", model: "", approved_at: "", approved_by: "" });
    expect(tip).toBe("ai");
    expect(appliedMarkerTip(undefined)).toBe("Applied by AI");
  });

  it("staged tip labels the model 'proposed by' — it's the proposing gateway, not the committed one (#13)", () => {
    expect(stagedMarkerTip("llama-3.3-70b")).toBe("Staged by AI · proposed by llama-3.3-70b");
    expect(stagedMarkerTip()).toBe("Staged by AI"); // no model → no trailing separator
  });

  it("proposed tip shows the proposing model plainly", () => {
    expect(proposedMarkerTip("claude-x")).toBe("Proposed by AI · claude-x");
    expect(proposedMarkerTip()).toBe("Proposed by AI");
  });
});

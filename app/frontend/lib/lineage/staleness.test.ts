import { describe, expect, it } from "vitest";
import { figureStaleness, skillVersionGates, stalenessLabel, type LiveTriggerSet } from "./staleness";
import type { Figure } from "@/lib/projects/types";
import type { SkillProvenance } from "@/lib/skills-api";

/** A figure carrying a baseline provenance bundle; overrides merge over the defaults. */
function figProv(over: Partial<SkillProvenance> = {}): Figure {
  const provenance: SkillProvenance = {
    skill: { id: "deg", version: "1.0.0", title: "DEG", engine: "pydeseq2", ...(over.skill ?? {}) },
    params: over.params ?? { lfc: 1, padj: 0.05 },
    input: { filename: "counts.csv", sha256: "sha_v1", n_bytes: 100, ...(over.input ?? {}) },
    environment: {
      python: "3.12.1",
      platform: "win32",
      engine_policy: "real",
      packages: {},
      ...(over.environment ?? {}),
    },
  };
  return { id: "f1", projectId: "p1", title: "Fig", createdAt: 0, provenance };
}

/** A live trigger-set that matches `figProv()`'s baseline exactly. */
const LIVE_SAME: LiveTriggerSet = {
  sha256: "sha_v1",
  params: { lfc: 1, padj: 0.05 },
  skillVersion: "1.0.0",
  env: "3.12.1|win32|real",
};

describe("figureStaleness", () => {
  it("is fresh when every factor matches", () => {
    const r = figureStaleness(figProv(), LIVE_SAME);
    expect(r.stale).toBe(false);
    expect(r.reasons).toHaveLength(0);
  });

  it("has no opinion on a figure with no recorded provenance", () => {
    const fig: Figure = { id: "f", projectId: "p", title: "legacy", createdAt: 0 };
    const r = figureStaleness(fig, LIVE_SAME);
    expect(r.stale).toBe(false);
    expect(r.reasons).toHaveLength(0);
  });

  it("flags a changed input hash as data (gates)", () => {
    const r = figureStaleness(figProv(), { ...LIVE_SAME, sha256: "sha_v2" });
    expect(r.stale).toBe(true);
    expect(r.reasons.map((x) => x.factor)).toEqual(["data"]);
  });

  it("flags changed params (gates), order-independently", () => {
    // Same params, different key order → NOT stale.
    const reordered = figureStaleness(figProv(), { ...LIVE_SAME, params: { padj: 0.05, lfc: 1 } });
    expect(reordered.stale).toBe(false);
    // A genuine value change → stale on params.
    const r = figureStaleness(figProv(), { ...LIVE_SAME, params: { lfc: 2, padj: 0.05 } });
    expect(r.stale).toBe(true);
    expect(r.reasons.map((x) => x.factor)).toEqual(["params"]);
  });

  it("ignores a skill patch bump but gates a minor or major bump", () => {
    expect(figureStaleness(figProv(), { ...LIVE_SAME, skillVersion: "1.0.9" }).stale).toBe(false);
    expect(figureStaleness(figProv(), { ...LIVE_SAME, skillVersion: "1.1.0" }).stale).toBe(true);
    expect(figureStaleness(figProv(), { ...LIVE_SAME, skillVersion: "2.0.0" }).stale).toBe(true);
  });

  it("treats env as info only — a reason, but never stale on its own", () => {
    const r = figureStaleness(figProv(), { ...LIVE_SAME, env: "3.13.0|linux|real" });
    expect(r.stale).toBe(false);
    expect(r.reasons.map((x) => x.factor)).toEqual(["env"]);
  });

  it("env alongside a gating factor → stale, with both reasons", () => {
    const r = figureStaleness(figProv(), { ...LIVE_SAME, sha256: "sha_v2", env: "3.13.0|linux|real" });
    expect(r.stale).toBe(true);
    expect(r.reasons.map((x) => x.factor).sort()).toEqual(["data", "env"]);
  });

  it("skips factors the caller can't supply (undefined = unknown)", () => {
    // Only the hash is known and it differs; params/skill/env unknown → only data fires.
    const r = figureStaleness(figProv(), { sha256: "sha_v2" });
    expect(r.stale).toBe(true);
    expect(r.reasons.map((x) => x.factor)).toEqual(["data"]);
  });

  it("reports every gating factor when several diverge at once", () => {
    const r = figureStaleness(figProv(), {
      sha256: "sha_v2",
      params: { lfc: 3 },
      skillVersion: "3.0.0",
      env: "x|y|z",
    });
    expect(r.stale).toBe(true);
    expect(r.reasons.map((x) => x.factor).sort()).toEqual(["data", "env", "params", "skill"]);
  });
});

describe("skillVersionGates", () => {
  it("same version never gates", () => {
    expect(skillVersionGates("1.2.3", "1.2.3")).toBe(false);
  });
  it("patch bump does not gate; minor/major do", () => {
    expect(skillVersionGates("1.2.3", "1.2.9")).toBe(false);
    expect(skillVersionGates("1.2.3", "1.3.0")).toBe(true);
    expect(skillVersionGates("1.2.3", "2.0.0")).toBe(true);
  });
  it("non-semver versions gate on any difference", () => {
    expect(skillVersionGates("2024-01-01", "2024-02-01")).toBe(true);
    expect(skillVersionGates("v1", "v1")).toBe(false);
  });
});

describe("stalenessLabel", () => {
  it("summarizes gating factors and ignores env", () => {
    expect(stalenessLabel({ stale: false, reasons: [] })).toBe("Up to date");
    expect(
      stalenessLabel({ stale: true, reasons: [{ factor: "data", was: "a", now: "b" }] }),
    ).toBe("Stale — data changed");
    expect(
      stalenessLabel({
        stale: true,
        reasons: [
          { factor: "data", was: "a", now: "b" },
          { factor: "params", was: "x", now: "y" },
          { factor: "env", was: "e1", now: "e2" },
        ],
      }),
    ).toBe("Stale — data + parameters changed");
  });
});

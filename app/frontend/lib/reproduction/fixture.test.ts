import { describe, expect, it } from "vitest";

import { shortName, tierLabel } from "./api";
import { REPRO_LEDGERS, REPRO_PAPERS } from "./fixture";

// The fixture is the real engine output; these guard the headline the view renders.

describe("REPRO_PAPERS (the index spectrum)", () => {
  it("is the three dogfood papers in ascending reproducibility (red -> green)", () => {
    expect(REPRO_PAPERS.map((p) => p.slug)).toEqual(["rpgrip1", "jev", "hani"]);
    const repros = REPRO_PAPERS.map((p) => p.score?.reproducibility);
    expect(repros).toEqual([63, 86, 96]);
    expect(repros).toEqual([...repros].sort((a, b) => (a ?? 0) - (b ?? 0)));
  });

  it("every card carries a title, a tier hex color, and a non-empty heatmap strip", () => {
    for (const p of REPRO_PAPERS) {
      expect(p.title.length).toBeGreaterThan(0);
      expect(p.score?.color).toMatch(/^#[0-9a-f]{6}$/i);
      expect(p.cells.length).toBeGreaterThan(0);
      expect(p.cells.every((c) => /^#[0-9a-f]{6}$/i.test(c.color))).toBe(true);
    }
  });
});

describe("REPRO_LEDGERS (the detail data)", () => {
  it("scorecard score agrees with the matching paper-summary score", () => {
    for (const p of REPRO_PAPERS) {
      const led = REPRO_LEDGERS[p.slug];
      expect(led).toBeTruthy();
      expect(led.scorecard?.score?.reproducibility).toBe(p.score?.reproducibility);
    }
  });

  it("every validation joins to a panel by key (the golden-vs-computed table relies on it)", () => {
    for (const slug of Object.keys(REPRO_LEDGERS)) {
      const led = REPRO_LEDGERS[slug];
      const keys = new Set(led.panels.map((p) => `${p.figure}${p.panel}`));
      for (const v of led.validations) {
        expect(keys.has(v.panel_key)).toBe(true);
        expect(v.results.length).toBeGreaterThan(0);
      }
    }
  });

  it("JEV surfaces the D14 source-provenance divergence, not a blame", () => {
    expect(REPRO_LEDGERS.jev.scorecard?.provenance_divergences).toEqual(["4e: ST6+ Fig4e−"]);
  });

  it("RPGRIP1 has zero Selom defects despite low reproducibility (the two-axis story)", () => {
    const sc = REPRO_LEDGERS.rpgrip1.scorecard;
    expect(sc?.findings.selom_engine_bugs).toBe(0);
    expect(sc?.score?.selom_confidence).toBeGreaterThan(sc?.score?.reproducibility ?? 0);
  });
});

describe("label helpers", () => {
  it("tierLabel maps the named tiers", () => {
    expect(tierLabel("deposit-faithful")).toBe("Deposit-faithful");
    expect(tierLabel("verified")).toBe("Verified");
    expect(tierLabel("unknown-x")).toBe("unknown-x");
  });

  it("shortName maps the slugs", () => {
    expect(shortName("rpgrip1")).toBe("RPGRIP1");
    expect(shortName("hani")).toBe("Hani");
  });
});

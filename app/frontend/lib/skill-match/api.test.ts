import { describe, expect, it } from "vitest";

import {
  authorSummary,
  citationLine,
  confidenceColor,
  figureSkills,
  isSkill,
  needsReview,
  oosLabel,
  oosReason,
  reviewCount,
  skillId,
  tierMeta,
  toSavedPaper,
} from "./api";
import type { FeasibilityMap, FigureRoute, PaperMetadata } from "./types";

function fig(over: Partial<FigureRoute>): FigureRoute {
  return {
    figure: "1",
    candidates: [],
    top: null,
    in_scope: true,
    reason: "",
    confidence: 1,
    attribution: "legend",
    tier: "structured",
    ai: null,
    ...over,
  };
}

describe("target parsing", () => {
  it("splits skill: and oos: targets", () => {
    expect(isSkill("skill:deg")).toBe(true);
    expect(isSkill("oos:atac")).toBe(false);
    expect(skillId("skill:umap_scrna")).toBe("umap_scrna");
    expect(skillId("oos:atac")).toBe("");
    expect(oosReason("oos:wet_lab")).toBe("wet_lab");
    expect(oosReason("skill:deg")).toBe("");
  });
});

describe("figureSkills", () => {
  it("returns the in-scope skills, ranked, dropping oos candidates", () => {
    const fr = fig({
      candidates: [
        { target: "skill:trajectory", score: 3 },
        { target: "oos:wet_lab", score: 2 },
        { target: "skill:markers", score: 1 },
      ],
    });
    expect(figureSkills(fr)).toEqual(["trajectory", "markers"]);
  });
});

describe("needsReview (the upsell signal)", () => {
  it("flags recovered-tier figures", () => {
    expect(needsReview(fig({ tier: "recovered", confidence: 0.9 }))).toBe(true);
  });
  it("flags low-confidence structured figures", () => {
    expect(needsReview(fig({ tier: "structured", confidence: 0.3 }))).toBe(true);
  });
  it("leaves a clean, confident structured figure alone", () => {
    expect(needsReview(fig({ tier: "structured", confidence: 0.9 }))).toBe(false);
  });
});

describe("reviewCount", () => {
  it("counts the figures the Pro tier would verify", () => {
    const map = {
      figures: [
        fig({ figure: "1", tier: "structured", confidence: 1 }),
        fig({ figure: "2", tier: "recovered", confidence: 0.8 }),
        fig({ figure: "3", tier: "structured", confidence: 0.2 }),
      ],
    } as FeasibilityMap;
    expect(reviewCount(map)).toBe(2);
  });
});

describe("authorSummary", () => {
  it("shows surnames, collapsing 3+ authors to a +N remainder", () => {
    expect(authorSummary([])).toBe("");
    expect(authorSummary(null)).toBe("");
    expect(authorSummary(["Adrian V. Cioanca", "Yvette Wooff"])).toBe("Cioanca, Wooff");
    expect(authorSummary(["Adrian V. Cioanca", "Yvette Wooff", "R. Sekar", "C. Dietrich"])).toBe(
      "Cioanca, Wooff +2",
    );
  });
});

describe("citationLine", () => {
  it("formats venue · vol(issue):pages · year, skipping missing parts", () => {
    expect(
      citationLine({ venue: "J. Extracellular Vesicles", volume: "12", issue: "12", pages: "e12393", year: 2023 }),
    ).toBe("J. Extracellular Vesicles · 12(12):e12393 · 2023");
    expect(citationLine({ venue: "Nature", year: 2021 })).toBe("Nature · 2021");
    expect(citationLine({ volume: "15", pages: "3567" })).toBe("15:3567");
    expect(citationLine(null)).toBe("");
    expect(citationLine({})).toBe("");
  });
});

describe("confidenceColor (5-step temperature scale)", () => {
  it("bands very-low (red) → very-high (green)", () => {
    expect(confidenceColor(0.95)).toBe("#22c55e"); // very high — green
    expect(confidenceColor(0.7)).toBe("#84cc16"); // high — lime
    expect(confidenceColor(0.5)).toBe("#f59e0b"); // medium — amber
    expect(confidenceColor(0.3)).toBe("#f97316"); // low — orange
    expect(confidenceColor(0.1)).toBe("#ef4444"); // very low — red
  });
});

describe("toSavedPaper (the Library summary)", () => {
  const map = {
    paper_id: "JEV",
    skills: ["deg", "volcano"],
    out_of_scope: ["wet_lab"],
    figures: [fig({ figure: "1" }), fig({ figure: "2" })],
    paper_targets: [],
    tier_summary: { structured: 2, recovered: 0 },
    unmatched_terms: [],
  } as FeasibilityMap;
  const meta: PaperMetadata = {
    title: "EV paper",
    authors: ["A. Cioanca", "Y. Wooff"],
    venue: "JEV",
    year: 2023,
    doi: "10.1/abc",
    pmid: "999",
    is_preprint: false,
  };

  it("maps metadata + the routing rollup into the compact summary (no PDF bytes)", () => {
    const p = toSavedPaper(map, meta, "JEV.pdf");
    expect(p).toMatchObject({
      filename: "JEV.pdf",
      doi: "10.1/abc",
      pmid: "999",
      title: "EV paper",
      skills: ["deg", "volcano"],
      outOfScope: ["wet_lab"],
      figureCount: 2,
      tierSummary: { structured: 2, recovered: 0 },
      isPreprint: false,
    });
    expect("id" in p).toBe(false); // the store assigns id + savedAt
  });

  it("degrades to nulls + a zero tier summary when metadata is absent", () => {
    const p = toSavedPaper({ ...map, tier_summary: undefined as unknown as FeasibilityMap["tier_summary"] }, null, "x.pdf");
    expect(p.doi).toBeNull();
    expect(p.title).toBeNull();
    expect(p.tierSummary).toEqual({ structured: 0, recovered: 0 });
  });
});

describe("display metadata", () => {
  it("maps tiers and oos reasons to human labels (with a fallback)", () => {
    expect(tierMeta("structured").label).toBe("Structured");
    expect(tierMeta("recovered").color).toBe("#f59e0b");
    expect(tierMeta("unknown").label).toBe("Recovered"); // safe fallback
    expect(oosLabel("atac")).toBe("scATAC-seq");
    expect(oosLabel("mystery_assay")).toBe("mystery assay"); // underscores humanized
  });
});

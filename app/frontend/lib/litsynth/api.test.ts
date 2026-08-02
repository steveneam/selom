import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api/client";
import type { Scorecard } from "@/lib/reproduction/types";
import {
  citationByDoi,
  composeMethods,
  formatCitation,
  getPaperLegends,
  getPaperMethods,
  getPaperScorecard,
  legendBlock,
  reproducibilityStatement,
  searchCitations,
  type Citation,
} from "./api";

// Spy on the REAL transport (the house convention in lib/workspace/api.test.ts) so the module
// identity stays the one `./api` imported.
afterEach(() => vi.restoreAllMocks());

const CITATION: Citation = {
  title: "Uncovering cell identity through differential stability with Cepo.",
  authors: ["Kim HJ", "Wang K", "Chen C"],
  year: 2021,
  venue: "Nature Computational Science",
  doi: "10.1038/s43588-021-00172-2",
  pmid: "12345",
  url: null,
  source: "pubmed",
  metadata_license: null,
};

function scorecard(patch: Partial<Scorecard["score"]> = {}): Scorecard {
  return {
    paper_id: "rpgrip1",
    n_panels: 14,
    n_in_scope: 9,
    totals_by_verdict: {},
    totals_by_blame: {},
    findings: {},
    provenance_divergences: [],
    panel_scores: [],
    score: {
      paper_id: "rpgrip1",
      reproducibility: 63,
      selom_confidence: 88,
      tier: "recoverable",
      color: "#84cc16",
      n_scored: 7,
      n_in_scope: 9,
      n_out_of_scope: 5,
      n_form_only: 0,
      coverage: "7/9",
      ...patch,
    },
    generated_at: "2026-08-03T00:00:00",
  };
}

describe("route wiring (R-01 · R-03)", () => {
  it("POSTs /methods/compose with the run sequence", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ text: "…" } as never);
    await composeMethods([{ skill_id: "deg", params: { p: 0.05 } }], { dataset: "GSE1 was analyzed" });
    expect(post).toHaveBeenCalledWith("/methods/compose", {
      runs: [{ skill_id: "deg", params: { p: 0.05 } }],
      modality: "",
      dataset: "GSE1 was analyzed",
    });
  });

  it("refuses an empty run sequence without a request — there is nothing to ask about", async () => {
    const post = vi.spyOn(api, "post");
    await expect(composeMethods([])).rejects.toThrow(/at least one skill run/);
    expect(post).not.toHaveBeenCalled();
  });

  it("GETs the paper-level routes, url-encoding the slug", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ legends: [] } as never);
    await getPaperMethods("jev");
    await getPaperMethods("jev", "bulk");
    await getPaperLegends("hani");
    await getPaperScorecard("rpgrip1");
    expect(get.mock.calls.map((c) => c[0])).toEqual([
      "/papers/jev/methods",
      "/papers/jev/methods?modality=bulk",
      "/papers/hani/legends",
      "/papers/rpgrip1/scorecard",
    ]);
  });

  it("returns [] when a legends payload has no legends array — never undefined", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ slug: "jev" } as never);
    await expect(getPaperLegends("jev")).resolves.toEqual([]);
  });
});

describe("citation lookup is advisory — it never breaks the caller", () => {
  it("short-circuits a blank query with a clean empty, making NO request", async () => {
    const get = vi.spyOn(api, "get");
    await expect(searchCitations("   ")).resolves.toEqual({ results: [], degraded: false });
    await expect(citationByDoi("")).resolves.toEqual({ citation: null, degraded: false });
    expect(get).not.toHaveBeenCalled();
  });

  it("passes source / max_results / min_year through as query params", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ results: [], degraded: false } as never);
    await searchCitations(" retinal organoid ", { source: "pubmed", maxResults: 5, minYear: 2020 });
    expect(get).toHaveBeenCalledWith(
      "/citations/search?q=retinal+organoid&source=pubmed&max_results=5&min_year=2020",
    );
  });

  it("encodes a DOI's slashes rather than splitting the path", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ citation: null, degraded: false } as never);
    await citationByDoi("10.1038/s43588-021-00172-2");
    expect(get).toHaveBeenCalledWith(
      "/citations/by-doi?doi=10.1038%2Fs43588-021-00172-2&source=both",
    );
  });
});

describe("formatCitation is honest about absence", () => {
  it("collapses 3+ authors to 'First et al.' and appends the doi", () => {
    expect(formatCitation(CITATION)).toBe(
      "Kim HJ et al. Uncovering cell identity through differential stability with Cepo. " +
        "Nature Computational Science 2021. doi:10.1038/s43588-021-00172-2",
    );
  });

  it("joins exactly two authors with '&'", () => {
    expect(formatCitation({ ...CITATION, authors: ["Kim HJ", "Wang K"] })).toMatch(
      /^Kim HJ & Wang K\./,
    );
  });

  it("DROPS a missing field instead of filling a placeholder", () => {
    const bare: Citation = { ...CITATION, authors: [], venue: null, year: null, doi: null };
    expect(formatCitation(bare)).toBe(
      "Uncovering cell identity through differential stability with Cepo.",
    );
  });
});

describe("reproducibilityStatement", () => {
  it("reports both axes and names them as separate properties", () => {
    const s = reproducibilityStatement(scorecard(), { tierLabel: () => "Recoverable" });
    expect(s).toContain("7 of 9 in-scope panels");
    expect(s).toContain("63/100");
    expect(s).toContain("Recoverable");
    expect(s).toContain("Selom confidence of 88/100");
    // The two axes must never be presented as one number, and the paper-side axis must never read
    // as a grade of the user (lib/reproduction/types.ts).
    expect(s).toContain("Reproducibility reflects the paper and its data");
  });

  it("returns '' rather than a sentence with a hole when there is no rollup score", () => {
    expect(reproducibilityStatement(null)).toBe("");
    expect(reproducibilityStatement({ ...scorecard(), score: null })).toBe("");
    expect(reproducibilityStatement(scorecard({ reproducibility: null }))).toBe("");
  });

  it("omits the confidence clause when only that axis is unscored", () => {
    const s = reproducibilityStatement(scorecard({ selom_confidence: null }));
    expect(s).toContain("63/100");
    expect(s).not.toContain("Selom confidence");
  });

  it("singularises a one-panel scope", () => {
    expect(reproducibilityStatement(scorecard({ n_scored: 1, n_in_scope: 1 }))).toContain(
      "1 of 1 in-scope panel,",
    );
  });
});

describe("legendBlock", () => {
  it("prefixes each caption with its ledger label and blank-line separates them", () => {
    expect(
      legendBlock([
        { figure: "4", panel: "e", label: "Figure 4e.", skill_id: "deg", text: "Volcano of…" },
        { figure: "5", panel: "", label: "Figure 5.", skill_id: "gsea", text: "GSEA of…" },
      ]),
    ).toBe("Figure 4e. Volcano of…\n\nFigure 5. GSEA of…");
  });
});

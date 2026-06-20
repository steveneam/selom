import { describe, expect, it } from "vitest";

import {
  exportFilename,
  exportMatrix,
  serializeMatrix,
  toCSV,
  toTSV,
  type SkillMatchExport,
} from "./export";

function sample(over: Partial<SkillMatchExport> = {}): SkillMatchExport {
  return {
    paper: {
      title: "Multiomic integration, revealed",
      authors: ["Adrian V. Cioanca", "Yvette Wooff"],
      venue: "Journal of Extracellular Vesicles",
      year: 2023,
      volume: "12",
      issue: "12",
      pages: "e12393",
      doi: "10.1002/jev2.12393",
      pmid: "38082562",
      filename: "JEV.pdf",
    },
    skills: [
      { name: "Leiden clustering", slug: "umap_scrna", installed: true },
      { name: "Differential expression", slug: "deg", installed: false },
    ],
    outOfScope: ["wet-lab assay"],
    figures: [
      {
        figure: "1",
        skills: ["Leiden clustering", "Differential expression"],
        tier: "Recovered",
        confidencePct: 42,
        attribution: "from a Results in-text reference",
        outOfScope: [],
      },
    ],
    unmatchedTerms: ["western blot"],
    ...over,
  };
}

describe("exportMatrix", () => {
  it("emits all four sections in order", () => {
    const flat = exportMatrix(sample())
      .filter((r) => r.length === 1)
      .map((r) => r[0]);
    expect(flat).toContain("Paper");
    expect(flat).toContain("Skill inventory");
    expect(flat).toContain("Per-figure routing");
    expect(flat).toContain("Method terms with no Selom skill");
  });

  it("drops empty paper fields but keeps a title (falls back to filename)", () => {
    const m = exportMatrix(sample({ paper: { filename: "x.pdf", title: null } }));
    const labels = m.map((r) => r[0]);
    expect(labels).not.toContain("DOI"); // absent value → no row
    expect(m.find((r) => r[0] === "Title")?.[1]).toBe("x.pdf");
  });

  it("marks installed state as yes/no", () => {
    const m = exportMatrix(sample());
    expect(m.find((r) => r[0] === "Leiden clustering")).toEqual(["Leiden clustering", "yes"]);
    expect(m.find((r) => r[0] === "Differential expression")).toEqual(["Differential expression", "no"]);
  });

  it("renders a per-figure row with joined skills and a percentage", () => {
    const m = exportMatrix(sample());
    const row = m.find((r) => r[0] === "1" && r.length > 2);
    expect(row).toEqual(["1", "Leiden clustering; Differential expression", "Recovered", "42%", "from a Results in-text reference", ""]);
  });

  it("omits the per-figure section when no figures exist", () => {
    const flat = exportMatrix(sample({ figures: [] })).map((r) => r[0]);
    expect(flat).not.toContain("Per-figure routing");
  });
});

describe("serializeMatrix", () => {
  it("escapes CSV cells containing commas, quotes and newlines", () => {
    const out = serializeMatrix([["a,b", 'he said "hi"', "line\nbreak"]], ",");
    expect(out).toBe('"a,b","he said ""hi""","line\nbreak"');
  });

  it("sanitises tabs/newlines in TSV cells (cannot quote)", () => {
    const out = serializeMatrix([["a\tb", "c\nd"]], "\t");
    expect(out).toBe("a b\tc d");
  });

  it("joins rows with CRLF", () => {
    expect(serializeMatrix([["a"], ["b"]], ",")).toBe("a\r\nb");
  });
});

describe("toCSV / toTSV", () => {
  it("CSV quotes the comma-bearing title; TSV does not", () => {
    expect(toCSV(sample())).toContain('"Multiomic integration, revealed"');
    expect(toTSV(sample())).toContain("Multiomic integration, revealed");
  });

  it("TSV separates skill columns with a tab", () => {
    expect(toTSV(sample())).toContain("Leiden clustering\tyes");
  });
});

describe("exportFilename", () => {
  it("derives a safe name from the source file", () => {
    expect(exportFilename(sample())).toBe("JEV-skill-match.csv");
    expect(exportFilename(sample({ paper: { filename: "Cioanca 2023.pdf" } }), "tsv")).toBe(
      "Cioanca_2023-skill-match.tsv",
    );
    expect(exportFilename(sample({ paper: { filename: "" } }))).toBe("paper-skill-match.csv");
  });
});

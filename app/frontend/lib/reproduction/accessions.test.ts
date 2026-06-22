import { describe, expect, it } from "vitest";

/**
 * Cited-dataset accessions (Slice 5B). The wire shape mirrors the backend; here we lock the
 * per-access-class display vocabulary + the lead-in rollup the handoff surface depends on.
 */

import { ACCESS_META, accessionSummary, type Accession } from "./accessions";

function acc(over: Partial<Accession> = {}): Accession {
  return {
    repo: "geo",
    id: "GSE1",
    access: "open",
    ingestable: true,
    url: "https://example.test/GSE1",
    label: "Gene Expression Omnibus",
    section: "availability",
    note: "",
    download_hint: "grab the matrix",
    ...over,
  };
}

describe("accession display metadata", () => {
  it("has a labelled, colored badge for every access class", () => {
    for (const cls of ["open", "raw", "controlled"] as const) {
      expect(ACCESS_META[cls].label).toBeTruthy();
      expect(ACCESS_META[cls].color).toMatch(/^#/);
      expect(ACCESS_META[cls].short).toBeTruthy();
    }
  });
});

describe("accessionSummary", () => {
  it("counts the total and the fetchable subset", () => {
    const list = [
      acc({ id: "GSE1", ingestable: true }),
      acc({ id: "PRJNA1", access: "raw", ingestable: false }),
      acc({ id: "phs1", access: "controlled", ingestable: false }),
    ];
    expect(accessionSummary(list)).toEqual({ total: 3, ingestable: 1 });
  });

  it("is zero for an empty list", () => {
    expect(accessionSummary([])).toEqual({ total: 0, ingestable: 0 });
  });
});

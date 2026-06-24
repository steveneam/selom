import { describe, expect, it } from "vitest";

import {
  hasSkillInfo,
  referenceHref,
  referenceMeta,
  referenceTypeLabel,
} from "./references";
import type { SkillReference } from "./types";

describe("referenceHref", () => {
  it("expands a bare DOI to the doi.org resolver (DOI wins over url)", () => {
    expect(referenceHref({ doi: "10.1167/iovs.19-27242" })).toBe(
      "https://doi.org/10.1167/iovs.19-27242",
    );
    expect(referenceHref({ doi: "10.1/x", url: "https://example.com" })).toBe(
      "https://doi.org/10.1/x",
    );
  });

  it("strips a doi: prefix and passes through a full DOI URL", () => {
    expect(referenceHref({ doi: "doi:10.1/x" })).toBe("https://doi.org/10.1/x");
    expect(referenceHref({ doi: "https://doi.org/10.1/x" })).toBe("https://doi.org/10.1/x");
  });

  it("falls back to a well-formed url", () => {
    expect(referenceHref({ url: "https://github.com/zqfang/GSEApy" })).toBe(
      "https://github.com/zqfang/GSEApy",
    );
  });

  it("returns null when neither doi nor a valid url is present (renders as plain text)", () => {
    expect(referenceHref({})).toBeNull();
    expect(referenceHref({ url: "not-a-url" })).toBeNull();
    expect(referenceHref({ doi: "" })).toBeNull();
  });
});

describe("referenceTypeLabel", () => {
  it("labels known types and falls back gracefully", () => {
    expect(referenceTypeLabel("publication")).toBe("Publication");
    expect(referenceTypeLabel("standard")).toBe("Standard");
    expect(referenceTypeLabel("repo")).toBe("Repository");
    expect(referenceTypeLabel("mystery")).toBe("Reference");
  });
});

describe("referenceMeta", () => {
  it("joins authors and year, omitting absent parts", () => {
    expect(referenceMeta({ authors: "Bush RA, et al.", year: 2019 })).toBe(
      "Bush RA, et al. · 2019",
    );
    expect(referenceMeta({ year: 2022 })).toBe("2022");
    expect(referenceMeta({ authors: "Korsunsky I, et al." })).toBe("Korsunsky I, et al.");
    expect(referenceMeta({})).toBe("");
  });
});

describe("hasSkillInfo", () => {
  const ref: SkillReference = { type: "publication", title: "X" };
  it("is true with a background or any reference, false otherwise", () => {
    expect(hasSkillInfo({ background: "About this skill." })).toBe(true);
    expect(hasSkillInfo({ references: [ref] })).toBe(true);
    expect(hasSkillInfo({ background: "  ", references: [] })).toBe(false);
    expect(hasSkillInfo({})).toBe(false);
  });
});

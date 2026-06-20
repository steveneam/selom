import { describe, expect, it } from "vitest";

import { KIND_LABEL, formatBytes, supplementKind } from "./supplements";

describe("supplementKind", () => {
  it("maps Excel suffixes (xlsx/xls/xlsm) to the xlsx kind", () => {
    expect(supplementKind("mmc2.xlsx")).toBe("xlsx");
    expect(supplementKind("table.xls")).toBe("xlsx");
    expect(supplementKind("macro.xlsm")).toBe("xlsx");
  });

  it("maps csv to csv and pdf to pdf", () => {
    expect(supplementKind("ST6.csv")).toBe("csv");
    expect(supplementKind("extended_methods.pdf")).toBe("pdf");
  });

  it("is case-insensitive on the extension", () => {
    expect(supplementKind("DATA.XLSX")).toBe("xlsx");
    expect(supplementKind("Methods.PDF")).toBe("pdf");
  });

  it("handles dotted names by using the LAST extension", () => {
    expect(supplementKind("supp.v2.final.csv")).toBe("csv");
  });

  it("returns null for unsupported or extensionless files", () => {
    expect(supplementKind("figure.png")).toBeNull();
    expect(supplementKind("notes.docx")).toBeNull();
    expect(supplementKind("README")).toBeNull();
    expect(supplementKind("trailing.")).toBeNull();
  });
});

describe("KIND_LABEL", () => {
  it("labels pdf as extended methods and tables as supplementary tables", () => {
    expect(KIND_LABEL.pdf).toBe("Extended methods");
    expect(KIND_LABEL.xlsx).toBe("Supplementary table");
    expect(KIND_LABEL.csv).toBe("Supplementary table");
  });
});

describe("formatBytes", () => {
  it("formats bytes, KB and MB", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatBytes(20 * 1024 * 1024)).toBe("20 MB");
  });

  it("is empty for unknown / invalid sizes", () => {
    expect(formatBytes(undefined)).toBe("");
    expect(formatBytes(-1)).toBe("");
    expect(formatBytes(NaN)).toBe("");
  });
});

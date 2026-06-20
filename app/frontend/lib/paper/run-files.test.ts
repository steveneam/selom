import { describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the session File cache (`paperFiles`) — the non-persistent home for the dropped
 * PDF + supplement bytes (I5). Like the workspace store it holds module-scoped state, so each test
 * imports a FRESH module instance (`vi.resetModules()`) to start clean. No real File needed — the
 * cache only reads `.name`/`.size`, so a minimal cast keeps the test env-agnostic.
 */

const f = (name: string, size = 10) => ({ name, size }) as unknown as File;

async function fresh() {
  vi.resetModules();
  return (await import("./run-files")).paperFiles;
}

describe("paperFiles — main PDF", () => {
  it("stores and returns the main PDF per paper", async () => {
    const paperFiles = await fresh();
    expect(paperFiles.getMain("p1")).toBeUndefined();
    paperFiles.setMain("p1", f("paper.pdf"));
    expect(paperFiles.getMain("p1")?.name).toBe("paper.pdf");
    expect(paperFiles.getMain("p2")).toBeUndefined(); // keyed per paper
  });
});

describe("paperFiles — supplements", () => {
  it("adds supplement bytes, deduped on lowercased filename", async () => {
    const paperFiles = await fresh();
    paperFiles.addSupplements("p1", [f("mmc2.xlsx"), f("data.csv")]);
    paperFiles.addSupplements("p1", [f("MMC2.XLSX")]); // same file, different case → replaces, no dup
    const names = paperFiles.getSupplementFiles("p1").map((x) => x.name.toLowerCase());
    expect(names.sort()).toEqual(["data.csv", "mmc2.xlsx"]);
  });

  it("removeSupplement detaches by filename (case-insensitive)", async () => {
    const paperFiles = await fresh();
    paperFiles.addSupplements("p1", [f("a.csv"), f("b.xlsx")]);
    paperFiles.removeSupplement("p1", "A.CSV");
    expect(paperFiles.getSupplementFiles("p1").map((x) => x.name)).toEqual(["b.xlsx"]);
  });

  it("empty paper yields no supplement files", async () => {
    const paperFiles = await fresh();
    expect(paperFiles.getSupplementFiles("ghost")).toEqual([]);
  });
});

describe("paperFiles — subscribe", () => {
  it("notifies listeners on a real change only", async () => {
    const paperFiles = await fresh();
    const cb = vi.fn();
    const unsub = paperFiles.subscribe(cb);
    paperFiles.setMain("p1", f("paper.pdf"));
    paperFiles.addSupplements("p1", [f("a.csv")]);
    paperFiles.addSupplements("p1", []); // no files → no emit
    expect(cb).toHaveBeenCalledTimes(2);
    unsub();
    paperFiles.setMain("p1", f("other.pdf"));
    expect(cb).toHaveBeenCalledTimes(2); // unsubscribed
  });
});

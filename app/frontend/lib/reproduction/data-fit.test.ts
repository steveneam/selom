import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the dropped-data fit CLIENT (Slice 2). The `useDataFit` hook is browser-verified
 * (it pulls the session File cache); here we stub `fetch` to lock the wire contract + the band map.
 */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { assessData, CONFIDENCE_META } from "./data-fit";

function res(status: number, body: unknown): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as unknown as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe("assessData", () => {
  it("POSTs main + supplements and returns the data_fits ranking", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(
        res(200, { data_fits: [{ filename: "de.csv", confidence: "confident", score: 100 }] }),
      );
    });
    const main = new File(["pdf"], "paper.pdf", { type: "application/pdf" });
    const supp = new File(["gene,log2FC,padj"], "de.csv", { type: "text/csv" });
    const fits = await assessData("p1", main, [supp]);

    expect(calls[0].url).toBe("/api/papers/p1/assess-data");
    expect(calls[0].init.method).toBe("POST");
    const body = calls[0].init.body as FormData;
    expect((body.get("main") as File).name).toBe("paper.pdf");
    expect(body.getAll("supplements")).toHaveLength(1);
    expect(fits[0]).toMatchObject({ filename: "de.csv", confidence: "confident" });
  });

  it("short-circuits with no supplements (no request)", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    expect(await assessData("p1", undefined, [])).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("maps a 413 to a friendly upload-limit error", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(res(413, {})));
    const supp = new File(["x"], "big.csv");
    await expect(assessData("p1", undefined, [supp])).rejects.toThrow(/upload limit/);
  });

  it("has display metadata for every confidence band", () => {
    for (const band of ["confident", "usable", "uncertain", "not_a_fit", "unreadable"] as const) {
      expect(CONFIDENCE_META[band].label).toBeTruthy();
      expect(CONFIDENCE_META[band].color).toMatch(/^#/);
    }
  });
});

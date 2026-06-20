import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the live-reproduction run CLIENT (the fetch functions). The React controllers
 * (`usePaperRun`/`useReproductionRun`) are hooks → browser-verified, not unit-tested here. Env is
 * "node", which provides `fetch`/`FormData`/`File`; we stub `fetch` to assert the wire contract.
 * `next/navigation` is mocked so importing the module (which the hooks pull in) is node-safe.
 */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { fetchRun, startReproduction } from "./run";

function res(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe("startReproduction", () => {
  it("POSTs main + supplements as multipart to the run endpoint", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(res(200, { run_id: "r1", status: "succeeded" }));
    });
    const main = new File(["pdf"], "paper.pdf", { type: "application/pdf" });
    const supp = new File(["a,b"], "data.csv", { type: "text/csv" });
    const out = await startReproduction("p1", main, [supp]);

    expect(out).toEqual({ run_id: "r1", status: "succeeded" });
    expect(calls[0].url).toBe("/api/papers/p1/reproduce");
    expect(calls[0].init.method).toBe("POST");
    const body = calls[0].init.body as FormData;
    expect((body.get("main") as File).name).toBe("paper.pdf");
    expect(body.getAll("supplements")).toHaveLength(1);
  });

  it("maps a 413 to a friendly upload-limit error", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(res(413, { detail: "exceeds the 50 MB upload limit" })));
    const main = new File(["x"], "p.pdf");
    await expect(startReproduction("p1", main, [])).rejects.toThrow(/upload limit/);
  });

  it("surfaces the backend detail on other errors", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(res(400, { detail: "no main file" })));
    const main = new File(["x"], "p.pdf");
    await expect(startReproduction("p1", main, [])).rejects.toThrow(/no main file/);
  });
});

describe("fetchRun", () => {
  it("GETs the run and returns the parsed payload", async () => {
    const payload = { run_id: "r1", status: "succeeded", ledger: { paper: { id: "p1" } } };
    let seen = "";
    vi.stubGlobal("fetch", (url: string) => {
      seen = url;
      return Promise.resolve(res(200, payload));
    });
    const out = await fetchRun("r1");
    expect(seen).toBe("/api/reproduction-runs/r1");
    expect(out.status).toBe("succeeded");
  });

  it("throws when the run is unknown (non-ok)", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(res(404, { detail: "unknown" })));
    await expect(fetchRun("nope")).rejects.toThrow();
  });
});

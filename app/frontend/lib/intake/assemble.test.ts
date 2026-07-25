import { afterEach, describe, expect, it, vi } from "vitest";

import { assembleScrna, looksLikeScrnaDeposit } from "./assemble";

/**
 * The scRNA cohort-assembly client (L2-05). `/data/assemble-scrna` shipped working with NO frontend
 * call site at all — the example that motivated the reachability ratchet. What is asserted here is
 * the routing decision (which multi-file drops are a single-cell deposit rather than an ERG cohort)
 * and the honesty of the failure path; the assembly itself is verified against the live backend on a
 * real deposit, never here.
 */

const f = (name: string) => new File(["x"], name);

afterEach(() => vi.unstubAllGlobals());

describe("looksLikeScrnaDeposit — routing a multi-file drop", () => {
  it("recognizes loose 10x triplet members, gzipped or not", () => {
    expect(
      looksLikeScrnaDeposit([
        f("GSM6061839_2niPE2-ANAI-3_matrix.mtx.gz"),
        f("GSM6061839_2niPE2-ANAI-3_barcodes.tsv.gz"),
        f("GSM6061839_2niPE2-ANAI-3_features.tsv.gz"),
      ]),
    ).toBe(true);
    expect(looksLikeScrnaDeposit([f("matrix.mtx"), f("barcodes.tsv"), f("genes.tsv")])).toBe(true);
  });

  it("recognizes several per-sample .h5ad files", () => {
    expect(looksLikeScrnaDeposit([f("sample_a.h5ad"), f("sample_b.h5ad")])).toBe(true);
  });

  it("leaves ERG cohorts to /data/combine — a wrong guess sends the user to the wrong error", () => {
    expect(looksLikeScrnaDeposit([f("C57_eye1.iwxdata"), f("Rd10_eye1.iwxdata")])).toBe(false);
    expect(looksLikeScrnaDeposit([f("ctrl.csv"), f("treat.csv")])).toBe(false);
    // A mixed drop is not a deposit: one .h5ad plus a table is an ambiguity, not a cohort.
    expect(looksLikeScrnaDeposit([f("sample_a.h5ad"), f("notes.csv")])).toBe(false);
  });

  it("a single file is never a deposit — it falls through to normal ingest", () => {
    expect(looksLikeScrnaDeposit([f("sample_a.h5ad")])).toBe(false);
  });
});

describe("assembleScrna — the transport", () => {
  it("posts every file as `files` and returns the cohort named by its sample count", async () => {
    const summary = {
      filename: "assembled_scrna.h5ad",
      n_files: 2,
      n_cells: 4200,
      n_genes: 20000,
      n_samples: 2,
      samples: ["s1", "s2"],
      obs_columns: ["sample_id", "sample"],
      per_sample_n: { s1: 2000, s2: 2200 },
    };
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      new Response(new Blob(["h5"]), {
        headers: { "X-Assemble-Summary": JSON.stringify(summary) },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await assembleScrna([f("s1.h5ad"), f("s2.h5ad")]);
    expect(result).not.toBeNull();
    expect(result!.summary.n_cells).toBe(4200);
    expect(result!.file.name).toBe("Assembled scRNA — 2 samples (2 files).h5ad");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/data/assemble-scrna");
    expect((init!.body as FormData).getAll("files")).toHaveLength(2);
  });

  it("sends obs_map as JSON only when a design overlay is given", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      new Response(new Blob(["h5"]), { headers: { "X-Assemble-Summary": "{}" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await assembleScrna([f("s1.h5ad"), f("s2.h5ad")]);
    expect((fetchMock.mock.calls[0][1]!.body as FormData).get("obs_map")).toBeNull();

    await assembleScrna([f("s1.h5ad")], { s1: { line: "2niPE2" } });
    expect((fetchMock.mock.calls[1][1]!.body as FormData).get("obs_map")).toBe(
      '{"s1":{"line":"2niPE2"}}',
    );
  });

  it("returns null — never a partial cohort — when the backend refuses", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("bad", { status: 400 })));
    expect(await assembleScrna([f("s1.h5ad"), f("s2.h5ad")])).toBeNull();
  });

  it("returns null when the summary header is missing — an undescribable cohort is not a cohort", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new Blob(["h5"]))));
    expect(await assembleScrna([f("s1.h5ad"), f("s2.h5ad")])).toBeNull();
  });

  it("returns null on a network error rather than throwing into the drop handler", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    expect(await assembleScrna([f("s1.h5ad"), f("s2.h5ad")])).toBeNull();
  });
});

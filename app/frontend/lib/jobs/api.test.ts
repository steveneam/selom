import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchJob,
  fetchJobResult,
  isJobTerminal,
  jobEventsUrl,
  jobResultUrl,
  jobStatusUrl,
  submitSkillJob,
  submitSkillJobFromDataset,
  type JobRecord,
} from "./api";

const JOB: JobRecord = {
  id: "j1",
  skill_id: "umap_scrna",
  status: "queued",
  result_url: null,
  error: null,
  created_at: 1,
  updated_at: 1,
};

function ok(payload: unknown): Response {
  return { ok: true, status: 200, json: async () => payload } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("job route urls", () => {
  it("build the three /jobs paths through the /api proxy", () => {
    expect(jobStatusUrl("j1")).toBe("/api/jobs/j1");
    expect(jobEventsUrl("j1")).toBe("/api/jobs/j1/events");
    expect(jobResultUrl("j1")).toBe("/api/jobs/j1/result");
  });

  it("escapes an id so it cannot break out of its path segment", () => {
    expect(jobStatusUrl("a/b")).toBe("/api/jobs/a%2Fb");
  });
});

describe("isJobTerminal", () => {
  it("mirrors jobs.store.TERMINAL", () => {
    expect(isJobTerminal({ ...JOB, status: "queued" })).toBe(false);
    expect(isJobTerminal({ ...JOB, status: "running" })).toBe(false);
    expect(isJobTerminal({ ...JOB, status: "succeeded" })).toBe(true);
    expect(isJobTerminal({ ...JOB, status: "failed" })).toBe(true);
  });
});

describe("submitSkillJob", () => {
  it("POSTs multipart to /skills/{id}/jobs with params as the query string", async () => {
    const fetchMock = vi.fn(async () => ok(JOB));
    vi.stubGlobal("fetch", fetchMock);
    const job = await submitSkillJob(
      "umap_scrna",
      new File(["x"], "pbmc3k.h5ad"),
      { n_neighbors: 15 },
      { override: true },
    );
    expect(job).toEqual(JOB);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/skills/umap_scrna/jobs?n_neighbors=15&override=true");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("matrix")).toBeTruthy();
  });

  it("surfaces the backend's detail when the submit is rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 404,
        json: async () => ({ detail: "unknown skill" }),
      })),
    );
    await expect(submitSkillJob("nope", new File(["x"], "d.csv"))).rejects.toThrow("unknown skill");
  });
});

describe("submitSkillJobFromDataset", () => {
  it("POSTs JSON to /skills/{id}/jobs-dataset — no multipart re-upload", async () => {
    const fetchMock = vi.fn(async () => ok(JOB));
    vi.stubGlobal("fetch", fetchMock);
    await submitSkillJobFromDataset("deg", "ds-7", { method: "wilcoxon" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/skills/deg/jobs-dataset");
    expect(JSON.parse(init.body as string)).toEqual({
      dataset_id: "ds-7",
      params: { method: "wilcoxon" },
      override: false,
    });
  });
});

describe("fetchJob", () => {
  it("reads the job wire shape", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ok({ ...JOB, status: "running" })));
    expect(await fetchJob("j1")).toMatchObject({ id: "j1", status: "running" });
  });
});

describe("fetchJobResult", () => {
  it("parses the stored bundle with the SAME reader as a synchronous run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        ok({
          figure: { data: [{ type: "scatter" }], layout: {} },
          provenance: { skill: { id: "umap_scrna" } },
          methods: { text: "…", citations: [] },
          table: null,
        }),
      ),
    );
    const res = await fetchJobResult("j1");
    expect(res.figure.data).toHaveLength(1);
    expect(res.methods?.text).toBe("…");
    // The job bundle is a strict SUBSET of the /run bundle: no legend, no data-check, no data-fit.
    // Those are optional, so the figure still renders and the extra panels simply have nothing.
    expect(res.legend).toBeUndefined();
    expect(res.dataCheck).toBeUndefined();
    expect(res.dataFit).toBeNull();
  });
});

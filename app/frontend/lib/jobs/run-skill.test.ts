import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getActivities, resetActivities } from "./activity";
import { runFailureCode, runSkillByDatasetTracked, runSkillTracked, skillLabel } from "./run-skill";

const FIGURE = { figure: { data: [{ type: "scatter" }], layout: {} } };

function ok(payload: unknown): Response {
  return { ok: true, status: 200, json: async () => payload } as unknown as Response;
}

/** The backend's 504 for a run killed by SELOM_SKILL_TIMEOUT_S (routers/_run.py). */
function timeout504(): Response {
  return {
    ok: false,
    status: 504,
    json: async () => ({
      detail: {
        error: "skill_timeout",
        category: "internal",
        message: "'umap_scrna' exceeded the 120s execution limit and was abandoned.",
        fix: "Try a smaller input or a lighter analysis.",
      },
    }),
  } as unknown as Response;
}

function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () =>
          i < frames.length
            ? { done: false, value: encoder.encode(frames[i++]) }
            : { done: true, value: undefined },
        cancel: async () => {},
      }),
    },
  } as unknown as Response;
}

/** Route a fake fetch by URL so a test states the whole server it is running against. */
function router(routes: Array<[RegExp, () => Response]>) {
  return vi.fn(async (url: string) => {
    for (const [pattern, make] of routes) if (pattern.test(url)) return make();
    throw new Error(`unrouted request: ${url}`);
  });
}

beforeEach(resetActivities);
afterEach(() => vi.unstubAllGlobals());

describe("runFailureCode", () => {
  it("reads the taxonomy code the run parser stamps on the error", () => {
    const e = Object.assign(new Error("boom"), { code: "skill_timeout" });
    expect(runFailureCode(e)).toBe("skill_timeout");
    expect(runFailureCode(new Error("boom"))).toBe("");
    expect(runFailureCode(null)).toBe("");
  });
});

describe("skillLabel", () => {
  it("resolves the catalog name from the bare runtime slug", () => {
    // The registry is keyed by the bare slug; the catalog namespaces its ids.
    expect(skillLabel("umap_scrna")).not.toBe("umap_scrna");
  });

  it("degrades to a readable slug for a skill the catalog does not carry", () => {
    expect(skillLabel("not_a_real_skill")).toBe("not a real skill");
  });
});

describe("runSkillTracked", () => {
  it("registers the run and marks it succeeded", async () => {
    vi.stubGlobal("fetch", router([[/\/run/, () => ok(FIGURE)]]));
    const res = await runSkillTracked("umap_scrna", new File(["x"], "pbmc3k.h5ad"));
    expect(res.figure.data).toHaveLength(1);
    const [entry] = getActivities();
    expect(entry).toMatchObject({ kind: "skill", context: "pbmc3k.h5ad", status: "succeeded" });
  });

  it("records the failure on the entry and still rethrows for the caller", async () => {
    vi.stubGlobal(
      "fetch",
      router([
        [
          /\/run/,
          () =>
            ({
              ok: false,
              status: 400,
              json: async () => ({
                detail: { error: "skill_run_failed", message: "no groups to compare" },
              }),
            }) as unknown as Response,
        ],
      ]),
    );
    await expect(runSkillTracked("deg", new File(["x"], "d.csv"))).rejects.toThrow(
      "no groups to compare",
    );
    expect(getActivities()[0]).toMatchObject({
      status: "failed",
      error: expect.stringContaining("no groups to compare"),
    });
  });

  it("hands a run killed by the 120s ceiling to the job lane and delivers its figure", async () => {
    const fetchMock = router([
      [/\/jobs\/j1\/result/, () => ok(FIGURE)],
      [/\/jobs\/j1\/events/, () => sseResponse(['data: {"id":"j1","status":"succeeded"}\n\n'])],
      [/\/skills\/umap_scrna\/jobs/, () => ok({ id: "j1", status: "running" })],
      [/\/run/, () => timeout504()],
    ]);
    vi.stubGlobal("fetch", fetchMock);

    const res = await runSkillTracked("umap_scrna", new File(["x"], "big.h5ad"));

    expect(res.figure.data).toHaveLength(1);
    const [entry] = getActivities();
    expect(entry).toMatchObject({ status: "succeeded", background: true, serverId: "j1" });
    // The synchronous attempt ran first; the job lane is a fallback, not the default path.
    const urls = fetchMock.mock.calls.map((c) => c[0] as string);
    expect(urls[0]).toContain("/run");
    expect(urls).toContain("/api/skills/umap_scrna/jobs");
    expect(urls).toContain("/api/jobs/j1/result");
  });

  it("reports a background job that FAILED, with the job's own error", async () => {
    vi.stubGlobal(
      "fetch",
      router([
        [
          /\/jobs\/j1\/events/,
          () => sseResponse(['data: {"id":"j1","status":"failed","error":"out of memory"}\n\n']),
        ],
        [/\/skills\/\w+\/jobs/, () => ok({ id: "j1", status: "running" })],
        [/\/run/, () => timeout504()],
      ]),
    );
    await expect(runSkillTracked("umap_scrna", new File(["x"], "big.h5ad"))).rejects.toThrow(
      "out of memory",
    );
    expect(getActivities()[0]).toMatchObject({ status: "failed", error: "out of memory" });
  });

  it("reports a background submit that was itself rejected", async () => {
    vi.stubGlobal(
      "fetch",
      router([
        [
          /\/skills\/\w+\/jobs/,
          () =>
            ({ ok: false, status: 503, json: async () => ({}) }) as unknown as Response,
        ],
        [/\/run/, () => timeout504()],
      ]),
    );
    await expect(runSkillTracked("umap_scrna", new File(["x"], "big.h5ad"))).rejects.toThrow(
      /background/,
    );
    expect(getActivities()[0]).toMatchObject({ status: "failed" });
  });
});

describe("runSkillByDatasetTracked", () => {
  it("falls back to the dataset-backed job route, with no multipart re-upload", async () => {
    const fetchMock = router([
      [/\/jobs\/j9\/result/, () => ok(FIGURE)],
      [/\/jobs\/j9\/events/, () => sseResponse(['data: {"id":"j9","status":"succeeded"}\n\n'])],
      [/\/skills\/deg\/jobs-dataset/, () => ok({ id: "j9", status: "running" })],
      [/\/run-dataset/, () => timeout504()],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const res = await runSkillByDatasetTracked("deg", "ds-7", { method: "wilcoxon" });
    expect(res.figure.data).toHaveLength(1);
    expect(fetchMock.mock.calls.map((c) => c[0])).toContain("/api/skills/deg/jobs-dataset");
    expect(getActivities()[0]).toMatchObject({ status: "succeeded", background: true });
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the four AI gateway endpoint wrappers (S5). Env is "node" (provides
 * fetch/FormData/File); we stub `fetch` to assert the wire contract: the right route, method,
 * and (for /ai/apply) the multipart form fields, plus that errors degrade to thrown messages.
 */

import { applyAiActions, explain, fetchGaps, proposeActions } from "./api";
import type { AiActionDelta, HelperTurn } from "./types";

function jsonRes(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

const EMPTY_TURN: HelperTurn = {
  goal: "g",
  plan: { goal: "g", actions: [], notes: "" },
  results: [],
  staged_params: {},
  figure_spec: null,
  gaps: [],
  provenance_actions: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("proposeActions", () => {
  it("POSTs JSON to /api/ai/propose and returns the HelperTurn", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(jsonRes(200, EMPTY_TURN));
    });
    const turn = await proposeActions({ skill_id: "umap_scrna", goal: "tighten" });
    expect(calls[0].url).toBe("/api/ai/propose");
    expect(calls[0].init.method).toBe("POST");
    const body = JSON.parse(calls[0].init.body as string);
    expect(body).toMatchObject({ skill_id: "umap_scrna", goal: "tighten", stage: "analyze" });
    expect(turn.plan.actions).toEqual([]);
  });

  it("throws a friendly message on a non-OK response (the editor is unaffected)", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(jsonRes(503, {})));
    await expect(proposeActions({ goal: "x" })).rejects.toThrow(/AI helper/i);
  });
});

describe("applyAiActions", () => {
  // The POST shape is the descriptive DELTA only — no actor/model/approved_by/approved_at (the server
  // re-derives those at the NEXT#1 chokepoint). A forgeable tag must never leave the FE.
  const actions: AiActionDelta[] = [
    { action_id: "a1", type: "set_param", target: "resolution", prompt: "" },
  ];

  it("POSTs multipart to /api/ai/apply with the approved delta + final params (no attribution)", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(jsonRes(200, { figure: { data: [{ type: "scatter" }], layout: {} } }));
    });
    const out = await applyAiActions("umap_scrna", new File(["x"], "m.csv"), { resolution: 1.2 }, actions, {
      goal: "tighten",
    });
    expect(calls[0].url).toBe("/api/ai/apply");
    expect(calls[0].init.method).toBe("POST");
    const fd = calls[0].init.body as FormData;
    expect(fd.get("skill_id")).toBe("umap_scrna");
    expect(fd.get("goal")).toBe("tighten");
    expect(JSON.parse(fd.get("params") as string)).toEqual({ resolution: 1.2 });
    const posted = JSON.parse(fd.get("ai_actions") as string);
    expect(posted).toHaveLength(1);
    // The wire must not carry forgeable attribution.
    expect(Object.keys(posted[0]).sort()).toEqual(["action_id", "prompt", "target", "type"]);
    expect(out.figure.data[0].type).toBe("scatter");
  });

  it("threads the design sheet through as the `design` multipart field (deg/heatmap re-run fidelity)", async () => {
    let fd: FormData | null = null;
    vi.stubGlobal("fetch", (_url: string, init: RequestInit) => {
      fd = init.body as FormData;
      return Promise.resolve(jsonRes(200, { figure: { data: [{ type: "scatter" }], layout: {} } }));
    });
    await applyAiActions("deg", new File(["x"], "m.csv"), {}, actions, {
      design: new File(["sample,group"], "design.csv"),
    });
    expect((fd!.get("design") as File).name).toBe("design.csv");
  });

  it("omits the design field when no design sheet is given", async () => {
    let fd: FormData | null = null;
    vi.stubGlobal("fetch", (_url: string, init: RequestInit) => {
      fd = init.body as FormData;
      return Promise.resolve(jsonRes(200, { figure: { data: [{ type: "scatter" }], layout: {} } }));
    });
    await applyAiActions("umap_scrna", new File(["x"], "m.csv"), {}, actions);
    expect(fd!.get("design")).toBeNull();
  });

  it("reuses the shared run-response error path (a typed gate message surfaces as-is)", async () => {
    vi.stubGlobal("fetch", () =>
      Promise.resolve(jsonRes(400, { detail: { message: "This column map is invalid." } })),
    );
    await expect(
      applyAiActions("deg", new File(["x"], "m.csv"), {}, actions),
    ).rejects.toThrow("This column map is invalid.");
  });
});

describe("fetchGaps", () => {
  it("GETs /api/ai/gaps and returns the backlog", async () => {
    const entries = [
      { context_hash: "h1", stage: "analyze", unmet: "param_not_in_spec", category: "param_spec_gap", skill_id: "deg", count: 3, sample_attempt: {} },
    ];
    const calls: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      calls.push(url);
      return Promise.resolve(jsonRes(200, entries));
    });
    const out = await fetchGaps();
    expect(calls[0]).toBe("/api/ai/gaps");
    expect(out).toHaveLength(1);
    expect(out[0].count).toBe(3);
  });

  it("throws on a non-OK response", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(jsonRes(500, {})));
    await expect(fetchGaps()).rejects.toThrow(/backlog/i);
  });
});

describe("explain", () => {
  it("POSTs JSON and returns {request, text, source}", async () => {
    vi.stubGlobal("fetch", () =>
      Promise.resolve(jsonRes(200, { request: "explain_score", text: "Score is 82.", source: "deterministic" })),
    );
    const out = await explain({ request: "explain_score", scorecard: { score: 82 } });
    expect(out.source).toBe("deterministic");
    expect(out.text).toContain("82");
  });

  it("surfaces the ranked sweep suggestions for propose_sweep (the preselect source)", async () => {
    vi.stubGlobal("fetch", () =>
      Promise.resolve(
        jsonRes(200, {
          request: "propose_sweep",
          text: "Suggested sweeps: Cluster resolution …",
          source: "deterministic",
          suggestions: [{ param: "resolution", label: "Cluster resolution", reason: "widest declared range" }],
        }),
      ),
    );
    const out = await explain({ request: "propose_sweep", sweep_space: { resolution: { type: "range" } } });
    expect(out.suggestions?.[0].param).toBe("resolution");
  });

  it("threads grade_advice + the stats method descriptor and returns the advisory (Phase 3)", async () => {
    let sentBody: Record<string, unknown> = {};
    vi.stubGlobal("fetch", (_url: string, init: RequestInit) => {
      sentBody = JSON.parse(String(init.body));
      return Promise.resolve(
        jsonRes(200, {
          request: "grade_advice",
          text: "Test: pyDESeq2 Wald. Correction: BH FDR.",
          source: "deterministic",
        }),
      );
    });
    const out = await explain({ request: "grade_advice", stats: { skill_id: "deg", mode: "bulk" } });
    expect(sentBody.request).toBe("grade_advice");
    expect(sentBody.stats).toEqual({ skill_id: "deg", mode: "bulk" });
    expect(out.source).toBe("deterministic");
    expect(out.text).toContain("pyDESeq2");
  });

  it("throws a friendly message on a non-OK response", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(jsonRes(500, {})));
    await expect(explain({ request: "explain_score" })).rejects.toThrow(/explanation/i);
  });
});

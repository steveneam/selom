import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the skill-run CLIENT — specifically the P1c "is-my-data-clean?" wiring on
 * `runSkill`: the structured 422 block → a typed {@link DataCheckError}, the `override` re-run,
 * and mapping the run response's `figure_legend`/`data_check` onto the FE shape. Env is "node",
 * which provides `fetch`/`FormData`/`File`; we stub `fetch` to assert the wire contract.
 */

import { DataCheckError, recommendParams, runSkill, runSkillByDataset, stageableRecommendations, type ParamRec } from "./api";

function jsonRes(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

const FIGURE = { data: [{ type: "scatter", x: [1], y: [1] }], layout: {} };

afterEach(() => vi.unstubAllGlobals());

describe("runSkill — is-my-data-clean guardrail", () => {
  it("turns a 422 data_check_failed into a DataCheckError carrying the verdict", async () => {
    const detail = {
      error: "data_check_failed",
      message: "This data has a blocking problem for analysis.",
      kind: "bulk_counts",
      qc: {
        ran: true,
        ok: false,
        blocked: true,
        flags: [{ severity: "block", code: "negative_counts", message: "Negative values.", fix: "Use raw counts." }],
        stats: {},
      },
      routing: null,
    };
    vi.stubGlobal("fetch", () => Promise.resolve(jsonRes(422, { detail })));

    const file = new File(["x"], "counts.csv");
    await expect(runSkill("deg", file)).rejects.toBeInstanceOf(DataCheckError);
    try {
      await runSkill("deg", file);
    } catch (e) {
      const err = e as DataCheckError;
      expect(err.dataCheck.kind).toBe("bulk_counts");
      expect(err.dataCheck.qc?.blocked).toBe(true);
      expect(err.dataCheck.qc?.flags[0].fix).toBe("Use raw counts.");
    }
  });

  it("appends override=true to the query when opts.override is set", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      calls.push(url);
      return Promise.resolve(jsonRes(200, { figure: FIGURE }));
    });
    await runSkill("deg", new File(["x"], "counts.csv"), { top_n: 50 }, null, { override: true });
    expect(calls[0]).toContain("override=true");
    expect(calls[0]).toContain("top_n=50");
  });

  it("maps figure_legend → legend and data_check → dataCheck on success", async () => {
    vi.stubGlobal("fetch", () =>
      Promise.resolve(
        jsonRes(200, {
          figure: FIGURE,
          figure_legend: { text: "Figure caption." },
          data_check: { kind: "sc_counts", qc: { ran: true, ok: true, blocked: false, flags: [], stats: {} }, routing: null },
          table: { columns: ["a"], rows: [[1]], synthesized: true, source: "figure" },
        }),
      ),
    );
    const out = await runSkill("pca", new File(["x"], "counts.csv"));
    expect(out.legend?.text).toBe("Figure caption.");
    expect(out.dataCheck?.kind).toBe("sc_counts");
    expect(out.table?.synthesized).toBe(true);
  });

  it("a non-block 422 still throws a plain error (not a DataCheckError)", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(jsonRes(422, { detail: "some other validation error" })));
    const p = runSkill("deg", new File(["x"], "counts.csv"));
    await expect(p).rejects.toThrow(/Couldn't run this skill/);
    await expect(p.catch((e) => e)).resolves.not.toBeInstanceOf(DataCheckError);
  });

  it("surfaces a typed gate's detail.message as-is (D1 data_contract_failed)", async () => {
    // The D1 data-contract gate returns a structured 422 whose `message` is a full, self-framed
    // sentence with a next step — show it verbatim (NOT inside the "Couldn't run … try again." frame,
    // which reads wrong for a data mismatch). NB: this stub's json() is re-callable, so it can't
    // reproduce the one-shot-stream double-read that broke this live — that needed a real browser.
    const message =
      "This data doesn't fit volcano: missing a fold-change column. Swap in a matching file.";
    vi.stubGlobal("fetch", () =>
      Promise.resolve(jsonRes(422, { detail: { error: "data_contract_failed", message } })),
    );
    const p = runSkill("volcano", new File(["x"], "counts.csv"));
    await expect(p).rejects.toThrow(/doesn't fit volcano/);
    await expect(p).rejects.not.toThrow(/Couldn't run this skill/); // shown as-is, not wrapped
    await expect(p.catch((e) => e)).resolves.not.toBeInstanceOf(DataCheckError);
  });
});

/**
 * Auto-tune (Layer A, docs/auto-tune/spec.md) — the DETERMINISTIC recommender client + the pure
 * staging helper. `stageableRecommendations` decides which recs actually change the run (only those
 * feed the pending queue); `recommendParams` is the fetch wrapper.
 */
describe("stageableRecommendations", () => {
  const rec = (key: string, value: ParamRec["value"], def: ParamRec["value"], scaled = false): ParamRec => ({
    key, value, default: def, why: scaled ? `set ${key}` : "skill default", scaled,
  });

  it("applies a rec whose value differs from the base the run would use (with the old→new+why diff)", () => {
    const { changes, applied, skipped } = stageableRecommendations([rec("n_hvg", 2000, 0, true)], {}, {});
    expect(changes).toEqual({ n_hvg: 2000 });
    expect(applied).toEqual([{ key: "n_hvg", from: 0, to: 2000, why: "set n_hvg" }]);
    expect(skipped).toEqual([]);
  });

  it("skips an unchanged baseline rec (value === base)", () => {
    const { applied } = stageableRecommendations([rec("method", "wilcoxon", "wilcoxon")], {}, {});
    expect(applied).toEqual([]);
  });

  it("is a no-op when the recommendation already equals the current staged value", () => {
    const { applied, skipped } = stageableRecommendations([rec("n_hvg", 2000, 0, true)], { n_hvg: 2000 }, {});
    expect(applied).toEqual([]);
    expect(skipped).toEqual([]); // matches the user's value → nothing to skip, nothing to apply
  });

  it("does NOT overwrite a user's hand-edited staged value — it reports it as skipped", () => {
    // user staged n_hvg=500 (≠ base 0); the rec would set 2000 → decline + report, never clobber.
    const { changes, applied, skipped } = stageableRecommendations([rec("n_hvg", 2000, 0, true)], { n_hvg: 500 }, {});
    expect(changes).toEqual({});
    expect(applied).toEqual([]);
    expect(skipped).toEqual(["n_hvg"]);
  });

  it("counts applied against the committed BASE (from = base), so the note matches the visible cue", () => {
    // base fdr=0.05; rec fdr=0.01, untouched → applied with from=0.05.
    const { applied } = stageableRecommendations([rec("fdr", 0.01, 0.05, true)], {}, { fdr: 0.05 });
    expect(applied).toEqual([{ key: "fdr", from: 0.05, to: 0.01, why: "set fdr" }]);
  });

  it("compares as strings (a numeric rec equals a stringified base value)", () => {
    const { applied } = stageableRecommendations([rec("top_n", 15, 15)], {}, { top_n: "15" });
    expect(applied).toEqual([]);
  });

  it("does NOT clobber a committed bulk deg contrast with the static defaults (the deg-clobber fix)", () => {
    // Regression: a set bulk-RNA-seq contrast. The backend emits reference/treatment/mode/method as
    // raw param_spec defaults (scaled=false ⇔ value===default) — those diff against the committed
    // values but must NOT wipe the design or downgrade pyDESeq2→Wilcoxon. Clean no-op.
    const recs = [
      rec("reference", "", ""),
      rec("treatment", "", ""),
      rec("mode", "auto", "auto"),
      rec("method", "wilcoxon", "wilcoxon"),
    ];
    const base = { reference: "CE4_4_iRPE", treatment: "CE4_5_iRPE", mode: "bulk", method: "pydeseq2" };
    const { changes, applied, skipped } = stageableRecommendations(recs, {}, base);
    expect(changes).toEqual({});
    expect(applied).toEqual([]);
    expect(skipped).toEqual([]); // a correctly-configured figure isn't "your edits left as-is" noise
  });

  it("still fills a genuinely empty/unset input from a static default (the OR-clause)", () => {
    // The gate blocks a static default only from OVERWRITING a committed value — it must still FILL an
    // empty one. A param whose committed value is "" gets its non-empty default.
    const { changes, applied } = stageableRecommendations([rec("layer", "X", "X")], {}, { layer: "" });
    expect(changes).toEqual({ layer: "X" });
    expect(applied).toEqual([{ key: "layer", from: "", to: "X", why: "skill default" }]);
  });
});

describe("recommendParams", () => {
  it("posts to the recommend-params endpoint and returns the parsed recs", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      calls.push(url);
      return Promise.resolve(
        jsonRes(200, {
          skill_id: "umap_scrna",
          recs: [{ key: "n_hvg", value: 2000, default: 0, why: "hvg", scaled: true }],
          note: "Set 1 best-practice input.",
        }),
      );
    });
    const out = await recommendParams("umap_scrna", { data_kind: "sc_counts" });
    expect(calls[0]).toContain("/api/skills/umap_scrna/recommend-params");
    expect(out.recs[0].value).toBe(2000);
    expect(out.recs[0].scaled).toBe(true);
  });

  it("throws on a 404 (unknown skill)", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(jsonRes(404, {})));
    await expect(recommendParams("nope")).rejects.toThrow(/404/);
  });
});

describe("runSkillByDataset — run-from-dataset_id (WS2.1)", () => {
  it("POSTs { dataset_id, params, override } as JSON and returns the parsed figure", async () => {
    const calls: Array<[string, { method: string; body: string }]> = [];
    vi.stubGlobal("fetch", (url: string, init: { method: string; body: string }) => {
      calls.push([url, init]);
      return Promise.resolve(jsonRes(200, { figure: FIGURE, provenance: { skill: { id: "volcano" } } }));
    });

    const out = await runSkillByDataset("volcano", "srv_ds_1", { fc_threshold: 1 }, { override: true });

    expect(out.figure).toEqual(FIGURE);
    expect(calls[0][0]).toBe("/api/skills/volcano/run-dataset");
    expect(calls[0][1].method).toBe("POST");
    expect(JSON.parse(calls[0][1].body)).toEqual({
      dataset_id: "srv_ds_1",
      params: { fc_threshold: 1 },
      override: true,
    });
  });

  it("defaults override to false and shares the typed 422 QC-block error surface", async () => {
    const detail = {
      error: "data_check_failed",
      message: "This data has a blocking problem for analysis.",
      kind: "bulk_counts",
      qc: { ran: true, ok: false, blocked: true, flags: [], stats: {} },
      routing: null,
    };
    let sentBody = "";
    vi.stubGlobal("fetch", (_url: string, init: { body: string }) => {
      sentBody = init.body;
      return Promise.resolve(jsonRes(422, { detail }));
    });
    await expect(runSkillByDataset("deg", "srv_ds_1")).rejects.toBeInstanceOf(DataCheckError);
    expect(JSON.parse(sentBody).override).toBe(false);
  });
});

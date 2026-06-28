import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the skill-run CLIENT — specifically the P1c "is-my-data-clean?" wiring on
 * `runSkill`: the structured 422 block → a typed {@link DataCheckError}, the `override` re-run,
 * and mapping the run response's `figure_legend`/`data_check` onto the FE shape. Env is "node",
 * which provides `fetch`/`FormData`/`File`; we stub `fetch` to assert the wire contract.
 */

import { DataCheckError, runSkill } from "./api";

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

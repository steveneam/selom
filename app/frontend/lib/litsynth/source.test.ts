import { describe, expect, it } from "vitest";

import type { Ledger, Panel } from "@/lib/reproduction/types";
import {
  datasetDescriptor,
  isReferenceSlug,
  OUT_OF_SCOPE_SCOPES,
  runsFromLedger,
  REFERENCE_SLUGS,
} from "./source";

type WirePanel = Panel & { params?: Record<string, unknown> };

function panel(patch: Partial<WirePanel>): WirePanel {
  return {
    paper_id: "p",
    figure: "1",
    panel: "a",
    chart_form: "volcano",
    scope: "transcriptomic",
    data_source: "",
    skill_id: "deg",
    golden: [],
    weight: 1,
    note: "",
    status: "validated",
    params: {},
    ...patch,
  };
}

function ledger(panels: WirePanel[]): Ledger {
  return {
    paper: {
      id: "p",
      slug: "p",
      title: "A paper",
      doi: "",
      pmid: "",
      authors: [],
      venue: "",
      year: null,
      volume: "",
      issue: "",
      pages: "",
      geo: [],
    },
    panels: panels as Panel[],
    validations: [],
    scorecard: null,
  };
}

describe("runsFromLedger mirrors litsynth/from_ledger.ledger_skill_runs", () => {
  it("keeps in-scope analysis panels in figure order", () => {
    const runs = runsFromLedger(
      ledger([
        panel({ figure: "1", skill_id: "deg" }),
        panel({ figure: "2", skill_id: "gsea" }),
      ]),
    );
    expect(runs.map((r) => r.skill_id)).toEqual(["deg", "gsea"]);
  });

  it("DROPS every out-of-scope scope — a Methods section must not claim a wet-lab readout", () => {
    // The exact set the backend excludes (reproduction.core.OUT_OF_SCOPE_SCOPES). If the backend
    // adds one and this drifts, a paper's Methods would describe work Selom never reproduced.
    expect([...OUT_OF_SCOPE_SCOPES].sort()).toEqual([
      "data_not_deposited",
      "modality_unsupported",
      "wet_lab",
    ]);
    const runs = runsFromLedger(
      ledger([
        panel({ scope: "wet_lab", skill_id: "erg_traces" }),
        panel({ scope: "data_not_deposited", skill_id: "umap" }),
        panel({ scope: "modality_unsupported", skill_id: "spatial" }),
        panel({ scope: "transcriptomic", skill_id: "deg" }),
      ]),
    );
    expect(runs.map((r) => r.skill_id)).toEqual(["deg"]);
  });

  it("drops form/claim panels that name no skill", () => {
    expect(runsFromLedger(ledger([panel({ skill_id: null })]))).toEqual([]);
  });

  it("collapses repeats of the same (skill_id, params) to one entry, first-seen order", () => {
    const runs = runsFromLedger(
      ledger([
        panel({ figure: "1", skill_id: "deg", params: { padj: 0.05 } }),
        panel({ figure: "2", skill_id: "deg", params: { padj: 0.05 } }),
        panel({ figure: "3", skill_id: "deg", params: { padj: 0.01 } }),
      ]),
    );
    expect(runs).toEqual([
      { skill_id: "deg", params: { padj: 0.05 } },
      { skill_id: "deg", params: { padj: 0.01 } },
    ]);
  });

  it("treats key order as irrelevant when deduping (the server sorts keys too)", () => {
    const runs = runsFromLedger(
      ledger([
        panel({ figure: "1", params: { a: 1, b: 2 } }),
        panel({ figure: "2", params: { b: 2, a: 1 } }),
      ]),
    );
    expect(runs).toHaveLength(1);
  });

  it("treats a panel with no params as {} rather than crashing", () => {
    const p = panel({});
    delete p.params;
    expect(runsFromLedger(ledger([p]))).toEqual([{ skill_id: "deg", params: {} }]);
  });

  it("is empty for a null/undefined ledger — the stage renders nothing to compose", () => {
    expect(runsFromLedger(null)).toEqual([]);
    expect(runsFromLedger(undefined)).toEqual([]);
  });
});

describe("the mirror agrees with the live engine on a real ledger", () => {
  /**
   * The RPGRIP1 panel table exactly as `GET /papers/rpgrip1` serves it (verified against the live
   * backend on 2026-08-03). This is the regression that matters: `runsFromLedger` runs client-side
   * to build the POST body for a user's own run, and if it ever diverges from
   * `litsynth/from_ledger.ledger_skill_runs` the user's Methods section silently stops matching the
   * one the same ledger would produce server-side.
   *
   * Note the two `deg` entries: 5sig ran with real params and 5C/6G with none, so they are
   * genuinely different methods and must NOT collapse — while the three `gsea` panels share empty
   * params and must.
   */
  const RPGRIP1 = ledger([
    panel({ figure: "5", panel: "sig", skill_id: "deg", params: { normalization: "tmm", reference: "Control1", treatment: "MSVUS" } }),
    panel({ figure: "5", panel: "A", skill_id: "gsea" }),
    panel({ figure: "5", panel: "B", skill_id: "pca" }),
    panel({ figure: "5", panel: "C", skill_id: "deg" }),
    panel({ figure: "5", panel: "D", scope: "wet_lab", skill_id: null }),
    panel({ figure: "5", panel: "E", scope: "wet_lab", skill_id: null }),
    panel({ figure: "5", panel: "F", scope: "wet_lab", skill_id: null }),
    panel({ figure: "6", panel: "A", skill_id: "annotate" }),
    panel({ figure: "6", panel: "C", skill_id: "composition" }),
    panel({ figure: "6", panel: "D", skill_id: "composition" }),
    panel({ figure: "6", panel: "E", skill_id: "gsea" }),
    panel({ figure: "6", panel: "F", skill_id: "gsea" }),
    panel({ figure: "6", panel: "G", skill_id: "deg" }),
  ]);

  it("derives the same skill sequence the backend reports in /papers/rpgrip1/methods", () => {
    // The live `skill_ids` of GET /papers/rpgrip1/methods, verbatim.
    expect(runsFromLedger(RPGRIP1).map((r) => r.skill_id)).toEqual([
      "deg",
      "gsea",
      "pca",
      "deg",
      "annotate",
      "composition",
    ]);
  });

  it("keeps the differently-parameterised deg run distinct from the bare one", () => {
    const degs = runsFromLedger(RPGRIP1).filter((r) => r.skill_id === "deg");
    expect(degs).toHaveLength(2);
    expect(degs[0].params).toMatchObject({ treatment: "MSVUS" });
    expect(degs[1].params).toEqual({});
  });
});

describe("datasetDescriptor mirrors from_ledger.dataset_descriptor", () => {
  it("leads with the deposited accessions when the paper has them", () => {
    expect(datasetDescriptor(["GSE201356", "GSE1"], "A paper")).toBe(
      "Data deposited under GSE201356, GSE1 were analyzed",
    );
  });

  it("falls back to the title, and to null when there is neither", () => {
    expect(datasetDescriptor([], "A paper")).toBe("A paper");
    expect(datasetDescriptor(undefined, "  ")).toBeNull();
    expect(datasetDescriptor(undefined, undefined)).toBeNull();
  });
});

describe("reference slugs", () => {
  it("are exactly the backend's papers_api.SLUGS", () => {
    expect([...REFERENCE_SLUGS]).toEqual(["rpgrip1", "jev", "hani"]);
  });

  it("rejects a saved-paper id, so a workspace paper never routes to the reference path", () => {
    expect(isReferenceSlug("rpgrip1")).toBe(true);
    expect(isReferenceSlug("paper_01H8X")).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import { modalityFromKind, qcFromInspect, type InspectResult } from "./inspect";

function result(over: Partial<InspectResult> = {}): InspectResult {
  return {
    kind: "generic_table",
    profile: { code: "generic_table", label: "Data table", confidence: "unsure", reason: "r", overridden: false },
    plan: { kind: "generic_table", profile: "generic_table", applies: false, obs_label: "rows",
            var_label: "columns", n_obs: 10, n_var: 4, steps: [], note: "Used as-is." },
    qc: { ran: true, ok: true, blocked: false, flags: [], stats: {} },
    routing: null,
    ...over,
  };
}

describe("modalityFromKind", () => {
  it("maps omics kinds, buckets the rest to unknown", () => {
    expect(modalityFromKind("sc_counts")).toBe("scRNA-seq");
    expect(modalityFromKind("bulk_counts")).toBe("bulk RNA-seq");
    expect(modalityFromKind("proteomics")).toBe("proteomics");
    expect(modalityFromKind("erg")).toBe("unknown");
    expect(modalityFromKind("generic_table")).toBe("unknown");
  });
});

describe("qcFromInspect", () => {
  it("ERG / generic → empty plan, label carried, no cleaning steps", () => {
    const qc = qcFromInspect(result({
      kind: "generic_table",
      profile: { code: "erg", label: "ERG / electrophysiology", confidence: "likely", reason: "a-/b-wave…", overridden: false },
      plan: { kind: "generic_table", profile: "erg", applies: false, obs_label: "rows", var_label: "columns",
              n_obs: 210, n_var: 11, steps: [], note: "ERG measurements table — used as-is." },
    }));
    expect(qc.applies).toBe(false);
    expect(qc.cleaningSteps).toEqual([]);
    expect(qc.profileLabel).toBe("ERG / electrophysiology");
    expect(qc.nObs).toBe(210); // no deltas → unchanged
    expect(qc.cleaning).toEqual(["ERG measurements table — used as-is."]);
  });

  it("count matrix → steps mapped + before/after applied + axis labels", () => {
    const qc = qcFromInspect(result({
      kind: "bulk_counts",
      profile: { code: "bulk_counts", label: "Bulk RNA-seq counts", confidence: "likely", reason: "", overridden: false },
      plan: {
        kind: "bulk_counts", profile: "bulk_counts", applies: true, obs_label: "samples", var_label: "genes",
        n_obs: 4, n_var: 50,
        steps: [{ id: "drop_low", label: "Drop low-count genes", kind: "filter", var_delta: -22 },
                { id: "size_factor", label: "Size-factor normalization", kind: "transform" }],
        note: "Standard bulk RNA-seq cleaning.",
      },
    }));
    expect(qc.applies).toBe(true);
    expect(qc.obsLabel).toBe("samples");
    expect(qc.varLabel).toBe("genes");
    expect(qc.nVar).toBe(28); // 50 - 22
    expect(qc.cleaningSteps?.map((s) => s.id)).toEqual(["drop_low", "size_factor"]);
    expect(qc.cleaningSteps?.[0].varDelta).toBe(-22);
  });

  it("drops the redundant `unclassified` info flag, keeps real warnings", () => {
    const qc = qcFromInspect(result({
      qc: { ran: true, ok: false, blocked: false, stats: {},
            flags: [
              { severity: "info", code: "unclassified", message: "Modality not recognized", fix: "" },
              { severity: "warn", code: "high_missingness", message: "30% missing", fix: "Impute it." },
            ] },
    }));
    expect(qc.guardrails).toHaveLength(1);
    expect(qc.guardrails[0].level).toBe("warn");
    expect(qc.guardrails[0].msg).toBe("30% missing Impute it.");
  });
});

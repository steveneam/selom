import { describe, expect, it } from "vitest";
import {
  COLUMN_NAMES_KEY,
  defaultDesignChoice,
  designRunParams,
  type DesignChoice,
  type DesignHints,
} from "./design";

const bulkHints: DesignHints = {
  needs_design: true,
  source: "column_names",
  modality: "bulk_counts",
  best_group: COLUMN_NAMES_KEY,
  sample_col: null,
  note: "",
  group_candidates: [
    {
      key: COLUMN_NAMES_KEY,
      label: "sample columns",
      n_levels: 2,
      reference_guess: "Control",
      levels: [
        { name: "PDE6B", n_replicates: 3, replicate_unit: "samples" },
        { name: "Control", n_replicates: 3, replicate_unit: "samples" },
      ],
    },
  ],
};

describe("defaultDesignChoice", () => {
  it("seeds the contrast from the control guess (reference) + the other level (treatment)", () => {
    const choice = defaultDesignChoice(bulkHints);
    expect(choice).toEqual<DesignChoice>({
      groupKey: COLUMN_NAMES_KEY,
      source: "column_names",
      reference: "Control",
      treatment: "PDE6B",
      levels: ["PDE6B", "Control"],
      sampleCol: null,
    });
  });

  it("is null when there is no design to capture", () => {
    expect(defaultDesignChoice(null)).toBeNull();
    expect(defaultDesignChoice({ ...bulkHints, needs_design: false })).toBeNull();
  });

  it("falls back to the first level when no control keyword matched", () => {
    const noGuess: DesignHints = {
      ...bulkHints,
      group_candidates: [{ ...bulkHints.group_candidates[0], reference_guess: null }],
    };
    const choice = defaultDesignChoice(noGuess);
    expect(choice?.reference).toBe("PDE6B"); // first level
    expect(choice?.treatment).toBe("Control");
  });
});

describe("designRunParams", () => {
  it("bulk (column_names) → reference/treatment + mode=bulk, no group_col", () => {
    const params = designRunParams(defaultDesignChoice(bulkHints)!);
    expect(params).toEqual({ reference: "Control", treatment: "PDE6B", mode: "bulk" });
    expect(params.group_col).toBeUndefined();
  });

  it("scRNA (obs) → pseudobulk + condition_col + sample_col", () => {
    const choice: DesignChoice = {
      groupKey: "condition", source: "obs", reference: "Control", treatment: "Mutant",
      levels: ["Control", "Mutant"], sampleCol: "sample",
    };
    expect(designRunParams(choice)).toEqual({
      reference: "Control", treatment: "Mutant", mode: "pseudobulk",
      condition_col: "condition", sample_col: "sample",
    });
  });

  it("design sheet → group_col keyed contrast", () => {
    const choice: DesignChoice = {
      groupKey: "genotype", source: "design_sheet", reference: "WT", treatment: "KO",
      levels: ["WT", "KO"],
    };
    expect(designRunParams(choice)).toEqual({ reference: "WT", treatment: "KO", group_col: "genotype" });
  });
});

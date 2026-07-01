import { describe, expect, it } from "vitest";
import {
  COLUMN_NAMES_KEY,
  defaultDesignChoice,
  designRunParams,
  timeCourseDesignFile,
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

// --- time-course (2c) -------------------------------------------------------------------------------

const timecourseHints: DesignHints = {
  needs_design: true,
  source: "column_names",
  modality: "bulk_counts",
  best_group: COLUMN_NAMES_KEY,
  sample_col: null,
  note: "detected a time-course across 3 timepoints",
  group_candidates: [
    {
      key: COLUMN_NAMES_KEY,
      label: "timepoints",
      kind: "time_course",
      n_levels: 3,
      reference_guess: "t0",
      levels: [
        { name: "t0", n_replicates: 2, replicate_unit: "samples" },
        { name: "t24", n_replicates: 2, replicate_unit: "samples" },
        { name: "t48", n_replicates: 2, replicate_unit: "samples" },
      ],
      time_rows: [
        { sample: "t0_1", time: 0 }, { sample: "t0_2", time: 0 },
        { sample: "t24_1", time: 24 }, { sample: "t24_2", time: 24 },
        { sample: "t48_1", time: 48 }, { sample: "t48_2", time: 48 },
      ],
    },
  ],
};

describe("defaultDesignChoice (time-course)", () => {
  it("marks the choice time_course, baseline = earliest, and carries the design rows", () => {
    const choice = defaultDesignChoice(timecourseHints);
    expect(choice?.kind).toBe("time_course");
    expect(choice?.reference).toBe("t0"); // baseline (earliest)
    expect(choice?.treatment).toBe("t48"); // last timepoint (kept for shape; unused by the run)
    expect(choice?.levels).toEqual(["t0", "t24", "t48"]);
    expect(choice?.timeRows).toHaveLength(6);
  });
});

describe("designRunParams (time-course)", () => {
  it("→ mode=timecourse + time_col=time, with no reference/treatment contrast", () => {
    const params = designRunParams(defaultDesignChoice(timecourseHints)!);
    expect(params).toEqual({ mode: "timecourse", time_col: "time" });
    expect(params.reference).toBeUndefined();
    expect(params.group_col).toBeUndefined();
  });
});

describe("timeCourseDesignFile", () => {
  it("serializes the rows into a `sample_id` + `time` CSV the runner reads", async () => {
    const file = timeCourseDesignFile(defaultDesignChoice(timecourseHints)!);
    expect(file).not.toBeNull();
    const text = await file!.text();
    const lines = text.trim().split("\n");
    expect(lines[0]).toBe("sample_id,time");
    expect(lines).toContain("t0_1,0");
    expect(lines).toContain("t48_2,48");
    expect(lines).toHaveLength(7); // header + 6 sample rows
  });

  it("returns null for a non-time-course choice (an attached/absent sheet is used instead)", () => {
    expect(timeCourseDesignFile(defaultDesignChoice(bulkHints)!)).toBeNull();
  });
});

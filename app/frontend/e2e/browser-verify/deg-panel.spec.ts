import { expect, test } from "@playwright/test";

import { openWorkbench, runFromWorkbench } from "./fixtures";

/**
 * The `deg` panel — NEXT#1(d), `docs/deg-panel/spec.md`.
 *
 * `deg` is the flagship DE skill and had **two** controls out of eighteen knobs. It is also four
 * disjoint engines behind one `mode` knob, and `mode` itself was API-only — the knob deciding which
 * of the other seventeen do anything could not be touched.
 *
 * WHY A BROWSER CHECK AND NOT JUST THE GUARD. `registry-completeness.test.ts` proves an overlay
 * entry exists and merges; `params.test.ts` proves the mode gate filters the field list. Neither
 * runs a browser or applies a skill, so neither can see whether a value a user SETS arrives at the
 * engine. The first check below asserts on the RENDERED figure [[plotly-spec-can-encode-a-lie]].
 *
 * ⚑ THE FIRST CHECK PROVES BOTH HALVES OF THIS SESSION AT ONCE, which is why it is the one to keep.
 * The axis title of a `deg` single-cell run is COMPUTED from `method` — because the same session
 * found that the axis had been hard-coded to "log2 fold-change" while the bar plots scanpy's
 * `scores`, which its own docstring calls "the z-score underlying the computation of a p-value".
 * So driving the `method` control and reading the axis proves (a) the knob is reachable, (b) it
 * reaches the engine, and (c) the figure names the quantity it actually drew. On the real corpus
 * that mislabel claimed a log2 fold-change of 44.6 — a 26-trillion-fold change — and nine gates
 * were green on it.
 */

/** The real single-cell corpus file the smoke matrix drives for every scRNA skill. */
const JEV = "jev/retina_fadl.h5ad";
/**
 * ⚑ A DIFFERENT file for the picker checks, and the reason is a finding worth keeping.
 *
 * `retina_fadl.h5ad` carries exactly TWO obs columns — `n_genes` (continuous) and `leiden` (17
 * clusters). It has **no condition column at all**, so the engine detects no group candidates and
 * the level picker correctly degrades to the text box it has always been. The first draft of the
 * check below asserted the picker on this file and failed, which is the fail-soft contract working
 * rather than a defect: a picker is only offered when there is a vocabulary to fill it.
 *
 * `hani_irpe_subset.h5ad` does: the engine detects one grouping (`batch`, 4 levels) and a separate
 * replicate list (`sample`, `batch`). One candidate is the interesting case, not a weak one — it is
 * the sole-candidate branch of `resolveLevelField`, on a real file.
 *
 * ⚑ AND NOT `rpgrip1_merged.h5ad`, which is the file this check WANTED. It is the
 * paper-reproduction dataset with the best design in the corpus (`genotype` WT/C3/FS/PT, `sample`
 * ×9, `celltypes` ×7) and the engine detects all of it correctly — but at **1.2 GB** the dev
 * upload proxy drops the request (`socket hang up`) and the dataset is never inspected, so the
 * picker degrades to text through no fault of its own. That is a harness/infra limit worth knowing
 * about, not a product defect: the largest file in the corpus cannot be driven through the browser
 * harness at all. Recorded rather than worked around.
 */
const HANI = "hani/processed/hani_irpe_subset.h5ad";
const DEG = "Differential expression";

async function axisTitle(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { layout?: { xaxis?: { title?: { text?: string } } } })
      | null;
    return plot?.layout?.xaxis?.title?.text ?? "";
  });
}

test("the ranking test reaches the engine, and the axis names the statistic it drew", async ({
  page,
}) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · deg ranking test",
    csvRelPath: JEV,
    skillName: DEG,
    awaitControl: ["Analysis mode", "Ranking test"],
    params: {
      // `t-test`, not the default `wilcoxon`. scanpy ranks by a DIFFERENT statistic per method, so
      // the axis title is a consequence of the knob rather than a re-read of the input.
      "Ranking test": "t-test",
      "Genes shown": "10",
    },
  });

  expect(
    await axisTitle(page),
    "the ranking test did not reach the engine, or the axis is still hard-coded",
  ).toBe("t-statistic");

  // …and the Statistics table's column agrees with the axis. They disagreed before: the table said
  // "log2 fold-change" for numbers the axis had already (correctly) refused to call one. Driven the
  // `stats-view.spec.ts` way — the rail auto-collapses to its icon spine at this viewport.
  const expand = page.getByRole("button", { name: "Expand rail" });
  if (await expand.isVisible().catch(() => false)) await expand.click();
  await page.getByRole("button", { name: /Top differential genes/i }).first().click();
  const headers = await page.locator("table").first().locator("thead th").allInnerTexts();
  expect(
    headers.map((h) => h.trim()),
    "the Statistics column must name the same statistic as the axis",
  ).toEqual(expect.arrayContaining(["t-statistic"]));
});

test("the default single-cell run names the Wilcoxon z-score, not a fold change", async ({
  page,
}) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · deg default statistic",
    csvRelPath: JEV,
    skillName: DEG,
    awaitControl: ["Analysis mode", "Ranking test"],
    params: { "Genes shown": "10" },
  });

  const title = await axisTitle(page);
  expect(title, "the DEFAULT path is the one that shipped the mislabel").toBe("Wilcoxon z-score");
  expect(title).not.toContain("fold-change");
});

test("the mode select gates the panel — four engines, one dock", async ({ page }) => {
  await openWorkbench(page, {
    projectName: "Browser-verify · deg mode gating",
    csvRelPath: JEV,
    skillName: DEG,
    awaitControl: ["Analysis mode", "Ranking test"],
  });

  const mode = page.getByLabel("Analysis mode", { exact: true });
  const visible = (label: string) => page.getByLabel(label, { exact: true });

  // Under the default `auto`, the knobs of BOTH engines auto can resolve to are reachable — and the
  // nine that belong only to pseudo-bulk / time-course, which auto never picks, are not. Hiding the
  // contrast boxes under `auto` would have been a regression: they ship as text fields today.
  await expect(visible("Reference group")).toBeVisible();
  await expect(visible("Ranking test")).toBeVisible();
  await expect(visible("Replicate column")).toHaveCount(0);
  await expect(visible("Time column")).toHaveCount(0);

  // Naming the mode narrows the dock to that engine.
  await mode.selectOption("pseudobulk");
  await expect(visible("Replicate column")).toBeVisible();
  await expect(visible("Condition column")).toBeVisible();
  await expect(visible("Ranking test")).toHaveCount(0);

  await mode.selectOption("timecourse");
  await expect(visible("Time column")).toBeVisible();
  await expect(visible("Adjust for")).toBeVisible();
  // `normalization` reaches the two DESeq2 CONTRAST paths and neither of the others — the `oneOf`
  // gate, which no single `equals` and no `not` could express.
  await expect(visible("Size-factor normalization")).toHaveCount(0);
  await mode.selectOption("bulk");
  await expect(visible("Size-factor normalization")).toBeVisible();
});

test("the contrast is picked from the file's REAL levels once its column is chosen", async ({
  page,
}) => {
  // ⚑ The level widget on the surface that motivated it. `columns` is `[]` for an h5ad BY
  // CONSTRUCTION (`engine/compat.py:175`), so every obs knob here was a free-text box on exactly
  // the files it consumes — review finding (f). These options come from `design.group_candidates`,
  // which rode `/data/inspect` and was already persisted: no new request, no new backend field.
  await openWorkbench(page, {
    projectName: "Browser-verify · deg level picker",
    csvRelPath: HANI,
    skillName: DEG,
    awaitControl: ["Analysis mode", "Ranking test"],
  });

  await page.getByLabel("Analysis mode", { exact: true }).selectOption("pseudobulk");
  const condition = page.getByLabel("Condition column", { exact: true });
  await expect(condition).toBeVisible();

  // The obs columns the engine detected — a picker, where an h5ad used to get a text box. They
  // carry their level counts, which is the distinction that decides a grouping column.
  const columns = (await condition.locator("option").allTextContents()).map((c) => c.trim());
  expect(columns, "the h5ad's obs columns are not reaching the picker").toEqual(
    expect.arrayContaining([expect.stringContaining("batch")]),
  );
  expect(columns.find((c) => c.startsWith("batch"))).toMatch(/batch — \d+ levels/);

  // The replicate picker reads a DIFFERENT list — `sample_col_candidates`, detected for exactly
  // this and never threaded until now. A sample id is not a grouping factor, so `sample` appears
  // here and NOT in the condition list above (the engine excludes the detected replicate column).
  const samples = (await page.getByLabel("Replicate column", { exact: true })
    .locator("option").allTextContents()).map((c) => c.trim());
  expect(samples, "the replicate-column candidates are not threaded").toContain("sample");
  expect(columns.some((c) => c.startsWith("sample")), "a replicate id is not a grouping factor")
    .toBe(false);

  // The contrast boxes offer that column's REAL levels. This file publishes exactly one grouping,
  // which is the sole-candidate branch: with nothing to disambiguate, the picker resolves without
  // waiting for the column to be named. (With several candidates it stays text until one is
  // chosen — blank means the backend's alias auto-detect, a rule the frontend cannot evaluate.)
  const reference = page.getByLabel("Reference group", { exact: true });
  await expect(reference).toBeVisible();
  const levels = (await reference.locator("option").allTextContents())
    .map((l) => l.trim())
    .filter((l) => l !== "auto-detect");
  expect(levels, "the real batch levels, not a guess").toEqual(
    expect.arrayContaining(["2niPE2-3", "2niPE2-4", "JKCMRI2-2", "ToHa-iPE2-3"]),
  );
  // Nothing is pre-selected: the backend already defaults the contrast when a column has exactly
  // two levels, and writing a value in would turn that inferred default into a recorded choice.
  expect(await reference.inputValue()).toBe("");
});

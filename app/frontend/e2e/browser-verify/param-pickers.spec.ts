import { expect, test } from "@playwright/test";

import { openWorkbench } from "./fixtures";

/**
 * The inline column / pair pickers, verified where they actually live: a REAL browser, a REAL
 * backend, and the real `erg_metrics_long.csv` off the corpus.
 *
 * This check cannot be done any other way. The whole feature IS the `/data/inspect` payload —
 * `data_fit.columns` fills the column select and `design.group_candidates[].levels` fills the pair
 * picker — so a unit test proves the merge and MSW would prove only the wire
 * ([[verify-on-real-data-not-mock]]). `dev:mock` is doubly useless here: it is header-only, so it
 * has no row values to derive levels from and deliberately returns no group candidates at all.
 *
 * The expected values are not invented — they are what the live engine returns for this file
 * (checked 2026-08-04): 11 columns, and `condition` carrying the six real treatment arms.
 */

const CSV = "erg-fig1e/erg_metrics_long.csv";

/** The display name — which is the skill's `title`, and only its title. A `catalog.name` used to
 *  shadow it, so this constant read "Selom Box Plot" while the skill had been retitled. */
const BOXPLOT = "Box / strip plot";

/** Every column the real file has, in file order. */
const REAL_COLUMNS = [
  "sample_id", "condition", "animal", "eye", "intensity_group", "intensity_log_cd_s_m2",
  "b_wave_uv", "a_wave_uv", "b_wave_implicit_ms", "a_wave_implicit_ms", "qc_excluded",
];

/** The six treatment arms in `condition`, sorted as the engine returns them. */
const REAL_ARMS = [
  "AAV8-CMV-GFP", "AAV8-RK-GFP-polyA-stuffer", "AAV8-RK-PDE6B",
  "AAV8-RK-PDE6B-3UTR", "Control", "Untreated",
];

test("the column picker offers the dataset's REAL columns, annotated by level count", async ({ page }) => {
  await openWorkbench(page, {
    projectName: "Browser-verify · ERG long-form pickers",
    csvRelPath: CSV,
    skillName: BOXPLOT,
  });

  const group = page.getByLabel("Group column");
  // The affordance itself is the first claim: this used to be a text box you had to type into.
  await expect(group).toHaveJSProperty("tagName", "SELECT");

  const values = await group.locator("option").evaluateAll((os) =>
    os.map((o) => (o as HTMLOptionElement).value),
  );
  // Blank leads (the backend's auto-detect, named rather than an empty row), then the real columns.
  expect(values[0]).toBe("");
  expect(values.slice(1)).toEqual(REAL_COLUMNS);

  const labels = await group.locator("option").evaluateAll((os) => os.map((o) => o.textContent?.trim()));
  // The categorical columns carry their level count; a measurement column stays bare. That is the
  // honest form of the type glyph mature builders show — inspect carries no per-column dtype.
  expect(labels).toContain("condition — 6 levels");
  expect(labels).toContain("intensity_group — 7 levels");
  expect(labels).toContain("b_wave_uv");
  // `sample_id` is a column you can PICK, but never a grouping factor — so no level annotation.
  expect(labels).toContain("sample_id");
});

test("the pair picker is text until a group column is chosen, then offers that column's real levels", async ({ page }) => {
  await openWorkbench(page, {
    projectName: "Browser-verify · ERG pair picker",
    csvRelPath: CSV,
    skillName: BOXPLOT,
  });

  // Blank group = the backend's auto-detect (first non-numeric column = `sample_id` here), a rule
  // the frontend cannot evaluate. So the picker stays a text field rather than offering levels from
  // a column the run is not grouping by.
  await expect(page.getByLabel("Compare groups")).toHaveJSProperty("tagName", "INPUT");

  await page.getByLabel("Group column").selectOption("condition");

  // Now it is the row-list. Empty until asked — no phantom row implying a comparison exists.
  await expect(page.getByRole("group", { name: "Compare groups" })).toBeVisible();
  const add = page.getByRole("button", { name: "Add comparison" });
  await expect(add).toBeVisible();
  await expect(page.getByLabel("Comparison 1, first group")).toHaveCount(0);

  await add.click();
  const first = page.getByLabel("Comparison 1, first group");
  const second = page.getByLabel("Comparison 1, second group");
  await expect(first).toBeVisible();

  const options = await first.locator("option").evaluateAll((os) =>
    os.map((o) => (o as HTMLOptionElement).value).filter(Boolean),
  );
  expect(options).toEqual(REAL_ARMS);

  // Build a real comparison and confirm it round-trips into the `"A~B"` string the backend parses.
  await first.selectOption("Control");
  await second.selectOption("AAV8-RK-PDE6B");
  await add.click();
  await page.getByLabel("Comparison 2, first group").selectOption("Untreated");
  await page.getByLabel("Comparison 2, second group").selectOption("AAV8-RK-PDE6B");
  await expect(page.getByLabel("Comparison 2, second group")).toHaveValue("AAV8-RK-PDE6B");

  // Removing a row leaves the other intact (the rows are indices into one serialized string, so an
  // off-by-one here would silently delete the wrong comparison).
  await page.getByRole("button", { name: "Remove comparison 1" }).click();
  await expect(page.getByLabel("Comparison 1, first group")).toHaveValue("Untreated");
  await expect(page.getByLabel("Comparison 2, first group")).toHaveCount(0);
});

test("picking a different group column re-points the pair vocabulary", async ({ page }) => {
  await openWorkbench(page, {
    projectName: "Browser-verify · ERG pair vocabulary",
    csvRelPath: CSV,
    skillName: BOXPLOT,
  });

  await page.getByLabel("Group column").selectOption("eye");
  await page.getByRole("button", { name: "Add comparison" }).click();
  const opts = () =>
    page.getByLabel("Comparison 1, first group").locator("option")
      .evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value).filter(Boolean));
  expect(await opts()).toEqual(["LE", "RE"]);

  // Switch to a MEASUREMENT column: it has no levels, so the picker must drop back to the text
  // field rather than keep offering `eye`'s levels for a grouping that no longer exists.
  await page.getByLabel("Group column").selectOption("b_wave_uv");
  await expect(page.getByLabel("Compare groups")).toHaveJSProperty("tagName", "INPUT");
});

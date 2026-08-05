import { expect, test } from "@playwright/test";

import { runFromWorkbench } from "./fixtures";

/**
 * The Statistics surface, driven end-to-end — the seam the multi-table contract changes.
 *
 * WHY THIS EXISTS. Before this check, **no browser check opened the Statistics view at all**: the
 * suite drove the editor, the params and the export menu, and left the one surface that renders a
 * skill's computed numbers unproven. `docs/stats-tables/spec.md` slice 1 rewires exactly that path
 * — `figureTables` returns an array, the work rail's Statistics row reads it, and `StatsView` takes
 * a list — so the claim "slice 1 is a no-op" is not checkable without it. It is also the instrument
 * slices 2 (the stacked N-table presentation) and 3 (`lollipop` attaching both tables) each need,
 * so it is built once here rather than twice later [[compound-capability-each-task]].
 *
 * Every assertion is on the RENDERED surface, not on the response: a stored `table` that never
 * reaches a panel is the same class of defect as a param that never reaches the engine
 * [[selom-shipped-not-reachable]].
 */

/** A skill whose real-corpus run computes a table with a title the rail and the heading both show. */
const VOLCANO = {
  projectName: "Browser-verify · Statistics view",
  // volcano's own real-corpus smoke case (skills/smoke.py JEV_PROTEOME_DE) — gene / logFC /
  // P.Value / adj.P.Val, so the emitted de_table's columns are the engine's, not a fixture's.
  csvRelPath: "jev/proteome_de.csv",
  skillName: "Volcano plot",
  // openWorkbench's default wait is the categorical vocabulary, which volcano does not carry.
  awaitControl: ["Fold-change cutoff (log₂)", "Significance cutoff (adjusted p)"],
} as const;

/**
 * After Apply the editor opens on the figure, and at this viewport the work rail auto-collapses to
 * its icon spine (`useAutoCollapse`, editor-room R4) — so the Statistics ROW does not exist until
 * the rail is expanded. That is product behaviour, not harness friction, so the check drives it.
 */
/**
 * A panel's disclosure header — the button that carries the table's title and opens it.
 *
 * Located by ARIA state rather than by accessible name, because a panel now has TWO buttons naming
 * its table: the header and the CSV download ("Download <title> as CSV", added so N stacked
 * download buttons are not all announced as just "CSV"). A name-only query matches both and
 * Playwright fails strict mode. `aria-expanded` is what actually distinguishes a disclosure control
 * from a command, so the check keys on the thing that makes it a header rather than on its text.
 */
function panelHeader(panel: import("@playwright/test").Locator) {
  return panel.locator("button[aria-expanded]");
}

async function expandWorkrail(page: import("@playwright/test").Page) {
  const expand = page.getByRole("button", { name: "Expand rail" });
  if (await expand.isVisible().catch(() => false)) await expand.click();
  await expect(page.getByRole("navigation", { name: "Project lineage" })).toBeVisible({
    timeout: 30_000,
  });
}

test("a computed table reaches the Statistics view, titled, with its rows", async ({ page }) => {
  await runFromWorkbench(page, { ...VOLCANO });
  await expandWorkrail(page);

  // 1. The work rail announces the table BEFORE it is opened — title + shape. This is the site the
  //    spec's own consumer inventory missed, and the one where a bare list throws on `.rows`.
  const statsRow = page.getByRole("button", { name: /Differential expression/i }).first();
  await expect(statsRow, "the work rail must list the computed table").toBeVisible({ timeout: 60_000 });
  const railSub = await statsRow.innerText();
  expect(railSub, "the rail row states the table's shape").toMatch(/\d+ rows · \d+ cols/);

  // 2. Opening it renders the panel — the table's own title in the heading (D2's single-table
  //    invariant), and real rows under real column headers.
  await statsRow.click();
  const heading = page.getByRole("heading", { name: /Differential expression/i });
  await expect(heading, "one table keeps its title in the heading").toBeVisible({ timeout: 30_000 });

  const grid = page.locator("table").first();
  await expect(grid).toBeVisible();
  const headers = await grid.locator("thead th").allInnerTexts();
  expect(headers.map((h) => h.trim().toLowerCase())).toEqual(
    expect.arrayContaining(["gene", "log2fc", "padj"]),
  );
  const bodyRows = await grid.locator("tbody tr").count();
  expect(bodyRows, "the panel renders the computed rows, not an empty shell").toBeGreaterThan(0);
});

test("exactly one panel renders for a one-table run — the slice-1 no-op claim", async ({ page }) => {
  // G3 in the browser. Slice 1 widens the wire, the store and every consumer to a list while no
  // runner emits one, so the whole product must look identical. Counting PANELS is what makes that
  // checkable: an off-by-one in the array plumbing (a stray `[null]`, a fallback appended rather
  // than substituted) shows up here as a second, empty panel and nowhere else.
  await runFromWorkbench(page, { ...VOLCANO, projectName: "Browser-verify · Statistics single panel" });
  await expandWorkrail(page);

  await page.getByRole("button", { name: /Differential expression/i }).first().click();
  await expect(page.getByRole("heading", { name: /Differential expression/i })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator("table"), "one table in, one panel out").toHaveCount(1);
});

/**
 * Slice 3 — `lollipop` unsqueezed, verified where the claim actually lives.
 *
 * Until this change the skill DISCARDED its ranked-values table whenever the user asked for
 * pairwise statistics, because the wire carried exactly one. Both are attached now. This is the
 * check that proves it end-to-end: a real backend, the real ERG corpus file, and `pairs=` built
 * through the real row-list rather than posted — because a control that cannot express the value is
 * the layer below coverage, and `lollipop.pairs` had NO control at all until this change
 * [[selom-shipped-not-reachable]].
 */
test("lollipop keeps BOTH tables when pairs= is set through the real control", async ({ page }) => {
  const { openWorkbench } = await import("./fixtures");
  await openWorkbench(page, {
    projectName: "Browser-verify · Lollipop two tables",
    csvRelPath: "erg-fig1e/erg_metrics_long.csv",
    skillName: "Lollipop chart (ranked)",
    awaitControl: ["Category column", "Compare groups"],
  });

  // The pair picker is a free-text box until a group column is chosen — blank means the backend's
  // dtype auto-detect, which the frontend cannot evaluate. Choose one, and it becomes the row-list
  // over that column's REAL levels.
  await page.getByLabel("Category column").selectOption("condition");
  await page.getByLabel("Value column").selectOption("b_wave_uv");
  await page.getByRole("button", { name: "Add comparison" }).click();
  await page.getByLabel("Comparison 1, first group").selectOption("Control");
  await page.getByLabel("Comparison 1, second group").selectOption("AAV8-RK-PDE6B");

  await page.getByRole("button", { name: "Apply skill" }).click();
  await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 180_000 });

  await expandWorkrail(page);
  await page.getByRole("button", { name: /Ranked values/i }).first().click();

  // TWO panels, stacked, both open — the ranked values (which used to be thrown away) and the
  // p-values behind the bracket now drawn on the figure.
  const panels = page.getByTestId("stats-panel");
  await expect(panels).toHaveCount(2, { timeout: 30_000 });
  // Scoped to the panels: the work rail names the table too, so an unscoped role query is
  // ambiguous — and that ambiguity is itself the rail correctly announcing the primary table.
  await expect(panelHeader(panels.nth(0))).toHaveText(/Ranked values/i);
  await expect(panelHeader(panels.nth(1))).toHaveText(/Pairwise comparisons/i);

  // Both are OPEN, not merely present: a collapsed panel and an unselected tab hide the same
  // numbers, which is the reason D2 ruled tabs out in the first place.
  const grids = page.locator("[data-testid='stats-panel'] table");
  await expect(grids).toHaveCount(2);

  // The ranked table is the one that used to be discarded — it must carry the columns a dot cannot
  // show: the rank, the n, and the asymmetric bootstrap interval.
  const rankedHeaders = await grids.nth(0).locator("thead th").allInnerTexts();
  expect(rankedHeaders.map((h) => h.trim())).toEqual(expect.arrayContaining(["rank", "n", "CI low", "CI high"]));

  // ...and the pairwise table holds the p-value behind the star actually drawn on the canvas.
  const pairHeaders = await grids.nth(1).locator("thead th").allInnerTexts();
  expect(pairHeaders.map((h) => h.trim())).toEqual(expect.arrayContaining(["group A", "group B", "p"]));
  const pairRows = await grids.nth(1).locator("tbody tr").allInnerTexts();
  expect(pairRows.join(" ")).toContain("Control");
  expect(pairRows.join(" ")).toContain("AAV8-RK-PDE6B");
});

/**
 * Slice 4 — `boxplot` carries its native pairwise table AND its L3 distribution summary.
 *
 * Different from slice 3 in the thing that matters: lollipop's two tables are both the runner's own,
 * while here the second is SYNTHESIZED from the figure, so the panel must say so. That disclosure is
 * the whole reason synthesis is allowed to feed a reproducibility score at all — a re-shaped value
 * is honest only while it is labelled as one.
 */
test("boxplot shows its pairwise table AND the synthesized summary, labelled as synthesized", async ({ page }) => {
  const { openWorkbench } = await import("./fixtures");
  await openWorkbench(page, {
    projectName: "Browser-verify · Boxplot both tables",
    csvRelPath: "erg-fig1e/erg_metrics_long.csv",
    skillName: "Box / strip plot",
    awaitControl: ["Group column", "Compare groups"],
  });

  await page.getByLabel("Group column").selectOption("condition");
  await page.getByLabel("Value column").selectOption("b_wave_uv");
  await page.getByRole("button", { name: "Add comparison" }).click();
  await page.getByLabel("Comparison 1, first group").selectOption("Control");
  await page.getByLabel("Comparison 1, second group").selectOption("AAV8-RK-PDE6B");

  await page.getByRole("button", { name: "Apply skill" }).click();
  await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 180_000 });

  await expandWorkrail(page);
  await page.getByRole("button", { name: /Pairwise comparisons/i }).first().click();

  const panels = page.getByTestId("stats-panel");
  await expect(panels).toHaveCount(2, { timeout: 30_000 });
  // Array order: the runner's own table leads, the synthesized one follows (D4/D5 — the caption
  // reads the first, and a skill's own computation outranks a re-shape of its picture).
  await expect(panelHeader(panels.nth(0))).toHaveText(/Pairwise comparisons/i);
  await expect(panelHeader(panels.nth(1))).toHaveText(/Distribution summary/i);

  // ⚑ The synthesized panel must DISCLOSE that it was re-shaped rather than computed. Without this
  // the two tables read as equally authoritative, which is the one thing D3 refuses to allow.
  await expect(panels.nth(1)).toContainText(/Computed by Selom/i);
  await expect(panels.nth(0)).not.toContainText(/Computed by Selom/i);

  // The summary carries the five-number shape the box literally draws — the thing a `pairs=` run
  // used to lose entirely.
  const summaryHeaders = await panels.nth(1).locator("thead th").allInnerTexts();
  expect(summaryHeaders.map((h) => h.trim())).toEqual(
    expect.arrayContaining(["group", "n", "min", "q1", "median", "q3", "max"]),
  );
});

/**
 * Slice 5 — `confusion`'s agreement scalars leave the table TITLE for a one-row table.
 *
 * ⚑ THE REFUSAL IS THE CASE TO PROVE, not the value, and that is the inverse of the natural
 * assumption. On real data `confusion` is usually cross-tabulating two DIFFERENT label vocabularies
 * (clusters against cell types, condition against flash intensity), which have no diagonal — so
 * "the two label sets differ, so no κ is defined" is what the corpus produces by default, and the
 * κ-value case is the one needing a constructed input. Decided-question 1 is explicit that the
 * refusal must survive the move out of the title **as prominently as a value would**, because a
 * reader who has seen the old figure will go looking for κ in the title and find it gone. An
 * assertion that only ever checked the happy path would have proven the wrong half.
 *
 * It is also the check that makes the one-row SHAPE real: three surfaces printed "1 rows" and the
 * panel offered a sort on a table with nothing to sort, and neither was reachable before this run.
 */
test("confusion publishes its agreement scalars as a one-row table, refusal and all", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · Confusion agreement table",
    // Two label columns in one small real file. `condition` (treatment arm) against
    // `intensity_group` (flash level) is a genuine cross-tabulation and the vocabularies plainly
    // differ, so this is the refusal path on a file the browser can actually upload — the skill's
    // own smoke case is an 83k-cell h5ad.
    csvRelPath: "erg-fig1e/erg_metrics_long.csv",
    skillName: "Confusion / agreement matrix",
    awaitControl: ["Reference labels (rows)", "Compared labels (columns)"],
    params: {
      "Reference labels (rows)": "condition",
      "Compared labels (columns)": "intensity_group",
    },
  });
  await expandWorkrail(page);
  await page.getByRole("button", { name: /Confusion matrix/i }).first().click();

  const panels = page.getByTestId("stats-panel");
  await expect(panels).toHaveCount(2, { timeout: 30_000 });
  // The matrix LEADS. Not a presentation preference: `extract.readers._read_count` answers any
  // count-shaped metric from the first table with rows, so a scalar table in position 0 would
  // report a count of 1 into a reproducibility score.
  await expect(panelHeader(panels.nth(0))).toHaveText(/Confusion matrix/i);
  await expect(panelHeader(panels.nth(1))).toHaveText(/Agreement between/i);

  // ⚑ The refusal reaches a CELL. A title string exports to nothing and diffs against nothing;
  // this is the whole reason the scalars moved home.
  const scalar = panels.nth(1).locator("table");
  await expect(scalar).toContainText("the two label sets differ");
  await expect(scalar.locator("tbody tr")).toHaveCount(1);
  // And the header does not promise a number it never holds — no "Cohen's kappa" column above a
  // cell reading "not defined".
  const scalarHeaders = await scalar.locator("thead th").allInnerTexts();
  expect(scalarHeaders.map((h) => h.trim())).toEqual(["n", "note"]);

  // The one-row shape reads as English and offers no dead affordance.
  await expect(panels.nth(1)).toContainText("1 row");
  await expect(panels.nth(1)).not.toContainText("1 rows");
  await expect(panels.nth(1)).not.toContainText("click a header to sort");
  // ...while the matrix beside it, which has rows to order, keeps its sort.
  await expect(panels.nth(0)).toContainText("click a header to sort");
});

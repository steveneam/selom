import { expect, test } from "@playwright/test";

import { openWorkbench, sweepIntoCompare } from "./fixtures";

/**
 * Compare, driven — the milestone fix pass's one unproven claim.
 *
 * ⚑ WHY THIS CHECK EXISTS. For the whole of the multi-table contract (slices 1–5) `compare-view.tsx`
 * diffed `figureTables(a)[0]` — the FIRST table — under a card that announced "The results tables
 * are identical", plural. Four independent review lenses found it and not one of the nine gates
 * could: reading index 0 of an array is perfectly typed, so tsc, eslint, vitest and the structural
 * guards were all green over it for five slices. It also falsified the approved rationale for
 * moving κ and λ out of their titles in the first place — a table was preferred to a caption
 * because it "sorts, exports, DIFFS IN COMPARE and is readable", and the third of those was untrue
 * when written.
 *
 * The fix (`lib/lineage/diff.pairTableDiffs`) is unit-pinned and guard-ratcheted, but nothing had
 * ever driven the compare surface in a browser — because reaching it needs a two-version FAMILY,
 * which no fixture built. `sweepIntoCompare` is that capability [[compound-capability-each-task]].
 *
 * THE SCENARIO IS THE ONE THE REVIEW DESCRIBED: re-run `lollipop` with `correction` none→BH. The
 * ranked values are untouched by a multiplicity correction, so table 0 is byte-identical and the
 * ENTIRE change lives in table 1 — precisely the shape that read as "identical" while a Parameters
 * card beside it said `correction: none → bh`.
 */

/**
 * ⚑ TWO comparisons, not one, and this is load-bearing rather than thoroughness.
 *
 * Benjamini-Hochberg on a SINGLE p-value returns that p-value unchanged (rank n of n → p × n/n).
 * With one pair the only difference between the versions would be the added `p (bh)` column, and a
 * check that passed on that alone would still pass if the correction silently did nothing. Two
 * pairs make at least one adjusted VALUE move, so the pairwise diff is a real numeric change.
 */
const PAIRS = [
  ["Control", "AAV8-RK-PDE6B"],
  ["Control", "AAV8-CMV-GFP"],
] as const;

test("compare diffs EVERY table, not just the first — a correction that moves only table 1", async ({
  page,
}) => {
  await openWorkbench(page, {
    projectName: "Browser-verify · Compare multi-table diff",
    // The same real ERG file the two-table stats checks use — long-form, so every category has the
    // replicates a pairwise test needs (a pre-aggregated table is n=1 vs n=1 and lollipop correctly
    // drops the comparison, which would leave this run with one table and nothing to prove).
    csvRelPath: "erg-fig1e/erg_metrics_long.csv",
    skillName: "Lollipop chart (ranked)",
    awaitControl: ["Category column", "Compare groups"],
  });

  await page.getByLabel("Category column").selectOption("condition");
  await page.getByLabel("Value column").selectOption("b_wave_uv");
  for (const [i, [a, b]] of PAIRS.entries()) {
    await page.getByRole("button", { name: "Add comparison" }).click();
    await page.getByLabel(`Comparison ${i + 1}, first group`).selectOption(a);
    await page.getByLabel(`Comparison ${i + 1}, second group`).selectOption(b);
  }

  await page.getByRole("button", { name: "Apply skill" }).click();
  await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 180_000 });

  // Fork the figure into a family over the one knob that moves table 1 and leaves table 0 alone.
  await sweepIntoCompare(page, {
    param: "Multiple-comparison correction",
    values: ["none", "bh"],
  });

  // 1. The parameter that changed is stated — the context the table diff is read against, and the
  //    thing that made the old "identical" claim actively misleading rather than merely incomplete.
  const params = page.getByTestId("diff-card").filter({ hasText: "Parameters" });
  const paramDeltas = params.locator("li");
  // Exactly one: the sweep holds every other knob at the origin figure's recorded config, so a
  // second delta would mean the two runs differ by something this check never asked for — and the
  // table diff below would then be attributing a change to the wrong cause.
  await expect(paramDeltas, "the sweep varies one parameter and holds the rest").toHaveCount(1);
  await expect(paramDeltas).toContainText("correction");
  await expect(paramDeltas).toContainText("none");
  await expect(paramDeltas).toContainText("bh");

  // 2. ⇒ THE FIX. One card per table PAIR. Before it there was exactly one, whatever the run
  //    produced, so this count is the assertion the whole check exists for.
  const tableCards = page.getByTestId("table-diff-card");
  await expect(tableCards, "one diff card per table pair, not one per figure").toHaveCount(2, {
    timeout: 30_000,
  });
  // Titled by each table's OWN title, in the runner's array order — so a stack of them is readable
  // rather than two cards both called "Results table".
  await expect(tableCards.nth(0)).toContainText(/Ranked values/i);
  await expect(tableCards.nth(1)).toContainText(/Pairwise comparisons/i);

  // 3. Table 0 is unchanged — a multiplicity correction cannot touch a ranking, and the bootstrap
  //    CI is seeded, so this is the half that WAS being reported correctly all along.
  await expect(tableCards.nth(0), "the ranked values are identical across the two versions")
    .toContainText("This table is identical in both versions");
  await expect(tableCards.nth(0)).toContainText("no changes");

  // 4. ⇒ ...and table 1 is where the entire change lives. This is what compare dropped on the floor:
  //    the p-values behind the stars drawn on the canvas, silently absent from every version
  //    comparison for five slices.
  const pairwise = tableCards.nth(1);
  await expect(pairwise, "the pairwise p-values must report as CHANGED, not identical")
    .not.toContainText("This table is identical in both versions");
  await expect(pairwise, "the summary counts the changed rows").toContainText(/changed/);

  // The diff renders the real rows, with both compared groups named and a before→after per cell.
  const changed = pairwise.locator("tbody tr");
  await expect(changed).toHaveCount(PAIRS.length);
  const text = (await changed.allInnerTexts()).join(" ");
  for (const [a, b] of PAIRS) {
    expect(text, `the diff names the compared groups`).toContain(a);
    expect(text, `the diff names the compared groups`).toContain(b);
  }
  // The correction column only exists once a correction has run — so its presence in the diff is
  // the adjusted p arriving, which is the number a reader would come here to see.
  await expect(pairwise.locator("thead")).toContainText("p (bh)");

  // 5. The copy that made the defect invisible. It claimed ALL the tables matched while comparing
  //    one; nothing on this surface may say that again, and this is the string to fail on.
  await expect(page.getByText(/The results tables are identical/i)).toHaveCount(0);
});

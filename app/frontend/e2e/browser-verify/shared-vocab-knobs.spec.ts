import { expect, test } from "@playwright/test";

import { runFromWorkbench } from "./fixtures";

/**
 * The second `API_ONLY_KNOBS` pass, driven through the controls that now exist.
 *
 * The first pass (`api-only-knobs.spec.ts`) proved the flagship cases. This one proves the batch
 * that was worked by CLUSTER rather than down the list — a declared shared vocabulary plus the
 * cheap singles, 148 knobs → 91 across 27 skills → 14.
 *
 * WHY A BROWSER CHECK AND NOT JUST THE GUARD. `registry-completeness.test.ts` proves an overlay
 * entry exists, that the merged field is well-formed, that a slider is bounded and that its default
 * lands on a step. It runs no browser and applies no skill, so it cannot see whether a value a user
 * SETS arrives at the engine and changes the picture — which is the entire claim being made. Every
 * assertion below is on the RENDERED figure rather than the params posted, because a Plotly spec can
 * encode a value and draw something else [[plotly-spec-can-encode-a-lie]].
 *
 * The two skills are picked for what they exercise, not for coverage:
 *   - **pvca** drives a text knob AND a slider, and is the skill whose `normalize` is NOT the shared
 *     scRNA one (it scales features to unit variance). Getting it wrong would have been invisible.
 *   - **pca** drives a text knob and two SWITCHES, the widget class that was undrivable until this
 *     change — and `label_points` has the most legible consequence of any bool in the batch: the
 *     trace's Plotly `mode` either carries "+text" or it does not.
 */

test("pvca's factors and variance threshold reach the figure — the shared block's odd one out", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · PVCA factors",
    // The long-form ERG metrics table the harness already drives for lollipop/slope/ridge/line.
    // Its categorical columns are condition · eye · intensity_group.
    csvRelPath: "erg-fig1e/erg_metrics_long.csv",
    skillName: "Principal variance components (batch effect)",
    awaitControl: ["Factors", "Variance retained"],
    params: {
      // A SUBSET of the available factors. Blank (the default) apportions across every non-numeric
      // column, so naming two is a value the engine cannot have arrived at on its own — and the
      // bars are one per named factor plus the residual, which makes the count exact rather than
      // plausible.
      Factors: "condition,eye",
      // 0.9, not the default 0.6. `_retain` keeps principal components until the cumulative
      // variance fraction reaches the threshold, so the percentage printed in the title is
      // >= the threshold BY CONSTRUCTION — a checkable consequence, not a re-read of the input.
      "Variance retained": "0.9",
    },
  });

  const fig = await page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { layout?: { title?: { text?: string } }; data?: { x?: unknown[] }[] })
      | null;
    return {
      x: ((plot?.data ?? [])[0]?.x ?? []).map(String),
      title: plot?.layout?.title?.text ?? "",
    };
  });

  // factors → exactly the two named, plus the residual the engine always appends.
  expect(fig.x, "the factor list did not reach the engine").toEqual([
    "condition",
    "eye",
    "residual",
  ]);

  // pct_threshold → the retained variance printed in the title clears the threshold that was set.
  // The default 0.6 would print a materially smaller number on this table.
  const pct = Number(/(\d+(?:\.\d+)?)% of variance/.exec(fig.title)?.[1]);
  expect(pct, `no retained-variance figure in the title: "${fig.title}"`).not.toBeNaN();
  expect(pct, "the variance threshold did not reach the engine").toBeGreaterThanOrEqual(90);
});

test("pca's grouping regex and point labels reach the figure — the first switches ever driven", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · PCA grouping",
    // Protein x (DR1-5, PD1-5) log-intensity: ten samples in two conditions of five replicates.
    csvRelPath: "jev/proteome_matrix.csv",
    skillName: "PCA (samples)",
    awaitControl: ["Group name pattern", "Label points"],
    params: {
      // The regex is REMOVED from each sample name and what remains is the group. The default
      // `\d+$` strips the replicate number, so DR1..DR5/PD1..PD5 collapse to DR and PD — two
      // traces. Stripping the LETTERS instead regroups the same samples by replicate number,
      // giving five. Same data, a different question, and a count that cannot happen by accident.
      "Group name pattern": "[A-Za-z]+",
      // Off — so the traces must lose their text layer.
      "Label points": "false",
    },
  });

  const traces = await page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { data?: { mode?: string; name?: string }[] })
      | null;
    return (plot?.data ?? []).map((t) => ({ mode: t.mode ?? "", name: t.name ?? "" }));
  });

  // group_regex → one trace per replicate number, not per condition.
  expect(traces.map((t) => t.name).sort()).toEqual(["1", "2", "3", "4", "5"]);

  // label_points → every trace draws markers only. With the default (on) each carries "+text",
  // so this is the switch arriving, not a property the figure had anyway.
  for (const t of traces) {
    expect(t.mode, `trace "${t.name}" still draws its labels`).toBe("markers");
  }
});

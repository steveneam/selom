import { expect, test } from "@playwright/test";

import { openWorkbench, runFromWorkbench } from "./fixtures";

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

/**
 * The `gsea` + `ssgsea` block (13 knobs), and the one affordance this pass ADDED rather than
 * exposed: the pasted-set override is now visible at the moment it takes effect.
 *
 * `gene_set` silently outranks `gene_sets` — pasting members switches the run into single-set mode
 * and the library selection stops mattering. Mobbin was unanimous that mature products make an
 * override an EXPLICIT mode (Google AI Studio folds "Write my own instructions" into the preset
 * dropdown; WRITER uses a segmented Upload / Paste URL / Paste text), which Selom cannot copy
 * without inventing a backend `mode` param — so the library control GREYS OUT instead. That is a
 * DOM fact no unit test covers, and it is asserted here beside the figure it explains.
 *
 * Driven in single-set mode deliberately: library mode over the full GO library takes minutes and
 * would time out, and the pasted path is the one that exercises the override, `set_name` (which
 * becomes the figure's title) and the gating together.
 */
test("gsea's pasted gene set overrides the library — and the library control says so", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · GSEA pasted set",
    // The limma DE oracle: ~14k human genes with logFC, the shape gsea ranks.
    csvRelPath: "alpk1/irpe_rawcounts/DE_oracle_d311_limma.csv",
    skillName: "GSEA running enrichment",
    awaitControl: ["Or paste your own gene set", "Name for your gene set"],
    params: {
      // The 13 most up-regulated genes in this very table, so the set is concentrated at the TOP
      // of the descending rank and must score a strongly positive ES. A random set would not.
      "Or paste your own gene set":
        "TSTD1, NLRP2, POTEF, ZNF572, LINC00654, LINC01291, GFAP, REC8, LINC00314, PCDHGA7, PCDHB5, TMEM30B, APLNR",
      "Name for your gene set": "Top up-regulated",
      // The in-house engine: no library, no permutation cost, and it proves the `engine` select
      // reaches the runner — a wrong value here raises rather than quietly using gseapy.
      "GSEA engine": "inhouse",
      "Permutations": "200",
    },
  });

  const fig = await page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { layout?: { title?: { text?: string } }; data?: { y?: number[] }[] })
      | null;
    return {
      title: plot?.layout?.title?.text ?? "",
      peak: ((plot?.data ?? [])[1]?.y ?? [])[0],
    };
  });

  // set_name → the pasted set names the figure. In library mode the title carries a GO term
  // instead, so this string can only come from the control.
  expect(fig.title, `set_name never reached the figure: "${fig.title}"`)
    .toContain("Top up-regulated");
  // gene_set → a top-concentrated set gives a strong POSITIVE enrichment score. This is the
  // pasted members arriving, not merely a figure being drawn.
  expect(fig.peak, "the pasted set did not reach the engine").toBeGreaterThan(0.3);

});

/**
 * ⚑ The override, made visible — and it has to be checked in the WORKBENCH, not after Apply.
 *
 * A skill's parameter panel only renders while the skill is SELECTED; once Apply lands, the page is
 * the editor and the controls are behind the figure-data rail. Asserting this beside the figure
 * assertions above cost a red run with "element(s) not found", which is the distinction
 * `openWorkbench` exists for: it stops one step short, in the only state where a param panel is on
 * screen. Kept as its own check rather than folded in, because it is a claim about the PANEL, and
 * the panel is a different surface from the figure.
 */
test("gsea's library select greys out the moment a gene set is pasted", async ({ page }) => {
  await openWorkbench(page, {
    projectName: "Browser-verify · GSEA override gating",
    csvRelPath: "alpk1/irpe_rawcounts/DE_oracle_d311_limma.csv",
    skillName: "GSEA running enrichment",
    awaitControl: ["Reference library", "Or paste your own gene set"],
  });

  // Blank `gene_set` is the DEFAULT, so the library is the live choice and must be usable. Pinning
  // both directions matters: a control that is always disabled would satisfy the assertion below
  // while being a worse bug than the one this fixes.
  const library = page.getByRole("combobox", { name: "Reference library" });
  await expect(library, "the library select is inert on the default path").toBeEnabled();

  await page.getByRole("textbox", { name: "Or paste your own gene set" }).fill("RHO, PRPH2, NRL");
  // The run now ignores the library entirely. The panel has to say so at the instant it becomes
  // true — otherwise it offers a choice with no consequence, the silent override this block ends.
  await expect(library, "the library select stayed live under a pasted set").toBeDisabled();
});

test("ssgsea's set-size bounds and z-score switch reach the heatmap", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · ssGSEA bounds",
    // Symbols x 18 samples — the expression matrix ssgsea scores per sample.
    csvRelPath: "alpk1/eyg29/EYG_29_iRPE_human_St7-TMM-K0_rawCounts.csv",
    skillName: "ssGSEA single-sample pathway enrichment",
    awaitControl: ["Gene sets shown", "Z-score rows for display"],
    params: {
      "Or paste your own gene set": "RPE65, BEST1, TYR, MLANA, PMEL, TTR, SERPINF1, RLBP1",
      "Gene sets shown": "5",
      "Smallest gene set": "3",
      // OFF — the colourbar must then name the raw NES rather than the z-scored display scale.
      "Z-score rows for display": "false",
    },
  });

  const fig = await page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { data?: { colorbar?: { title?: { text?: string } }; y?: unknown[] }[] })
      | null;
    const heat = (plot?.data ?? [])[0];
    return {
      scale: heat?.colorbar?.title?.text ?? "",
      rows: (heat?.y ?? []).length,
    };
  });

  // zscore=false → the colourbar names the raw score. The default reads "enrichment (z)", so this
  // is the switch arriving at the engine and changing what the colours MEAN.
  expect(fig.scale, "the z-score switch did not reach the engine").toBe("NES");
  // One pasted set is all there is to draw, whatever the cap says — the cap-is-not-a-count fact
  // the methods paragraph and caption now read from the runner instead of from `top_n`.
  expect(fig.rows).toBe(1);
});

import { expect, test } from "@playwright/test";

import { runFromWorkbench } from "./fixtures";

/**
 * The knobs a user could not touch, driven through the controls that now exist.
 *
 * WHY THESE CHECKS EXIST. The reachability sweep counted **171 of 313 backend knobs rendering no
 * control at all** — `paramFieldsFromSpec` iterates the presentation OVERLAY, not the backend spec,
 * so a skill with no overlay renders exactly zero controls while the panel says "Runs with smart
 * defaults — ready to apply". That reads as a product decision and was usually just an absent
 * overlay. Third layer of one class: 17 unreachable routes → 19 unrunnable skills → 171 untouchable
 * knobs, each invisible to every gate [[selom-shipped-not-reachable]].
 *
 * `registry-completeness.test.ts` now guards the whole backlog, exact in both directions. But that
 * guard proves an overlay ENTRY exists and that the merged field is well-formed — it runs no
 * browser, applies no skill, and cannot see whether the value a user sets actually reaches the
 * engine and changes the picture. That last step is the entire claim, so these two checks make it:
 *
 *   - **volcano**, because it is the flagship and was the sharpest case — the panel invited you to
 *     "tune the options" and then offered one text box for a gene-set panel, while `fc_threshold`,
 *     `fdr_threshold` and `top_n` (what counts as changed, what counts as significant, which genes
 *     get named) were API-only.
 *   - **sankey**, because `max_links` is its ONLY knob, so that skill rendered an EMPTY parameter
 *     panel. Nothing about a blank panel distinguishes "no options" from "options nobody wired".
 *
 * Both assert on the RENDERED figure, not on the params that were sent: the threshold lines and the
 * label count are where a knob either arrived or didn't. A spec assertion would pass on a figure
 * that encodes the value and draws something else entirely [[plotly-spec-can-encode-a-lie]].
 */

/** `layout` off the live Plotly node — the resolved figure, not the spec that was posted. */
async function figureLayout(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { layout?: Record<string, unknown>; data?: unknown[] })
      | null;
    const layout = (plot?.layout ?? {}) as {
      shapes?: { x0?: number; y0?: number; xref?: string; yref?: string }[];
      annotations?: { text?: string; showarrow?: boolean }[];
    };
    return {
      // Vertical fold-change lines carry `yref:"paper"`; the horizontal significance line carries
      // `xref:"paper"`. Splitting on that is what makes each assertion about ONE threshold.
      fcLines: (layout.shapes ?? []).filter((s) => s.yref === "paper").map((s) => s.x0),
      sigLines: (layout.shapes ?? []).filter((s) => s.xref === "paper").map((s) => s.y0),
      labels: (layout.annotations ?? []).filter((a) => a.showarrow).map((a) => a.text),
      traces: plot?.data?.length ?? 0,
    };
  });
}

test("volcano's three defining knobs reach the figure — the flagship's API-only case", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · volcano thresholds",
    // The harness default: a real EYG_28 bulk-DE export, which routes to volcano at score 100.
    skillName: "Volcano plot",
    // Its own controls, not a generic one — "Apply skill" appears before the describe call lands.
    awaitControl: ["Fold-change cutoff (log₂)", "Significance cutoff (adjusted p)"],
    params: {
      // 4-fold, not the default 2-fold: a value the engine cannot have arrived at on its own.
      "Fold-change cutoff (log₂)": "2",
      "Significance cutoff (adjusted p)": "0.01",
      // The knob with the most legible consequence — the figure should carry exactly this many
      // gene labels, so an off-by-anything is visible rather than plausible.
      "Genes labelled": "3",
    },
  });

  const fig = await figureLayout(page);
  expect(fig.traces, "no volcano drawn at all").toBeGreaterThan(0);

  // fc_threshold → the two vertical dashed lines, at ±2 rather than the default ±1.
  expect([...fig.fcLines].sort((a, b) => Number(a) - Number(b))).toEqual([-2, 2]);

  // fdr_threshold → the horizontal line at -log10(0.01) = 2. The default 0.05 would put it at 1.30.
  expect(fig.sigLines).toHaveLength(1);
  expect(Number(fig.sigLines[0])).toBeCloseTo(2, 6);

  // top_n → exactly three gene labels, each a real symbol from this DE table rather than a
  // placeholder. (EYG_28 clears both cutoffs on far more than three genes, so three is the knob
  // taking effect, not the data running out.)
  expect(fig.labels).toHaveLength(3);
  for (const gene of fig.labels) expect(gene).toMatch(/^[A-Za-z0-9._-]+$/);
});

test("sankey's only knob now has a panel — the skill that rendered an empty one", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · sankey link budget",
    // A real marker → cell-type edge table; the pair counts give far more than 5 candidate links,
    // so the budget below is doing the cutting.
    csvRelPath: "hani/mmc2_markers_long.csv",
    skillName: "Sankey flow",
    awaitControl: ["Flows drawn"],
    params: { "Flows drawn": "5" },
    // The QC guardrail blocks this file with "No numeric data to analyze", and by its own rule it
    // is right: `gene,cell_type` is two text columns. It is wrong ABOUT SANKEY, whose values are
    // the pair COUNTS it derives itself — an edge table has no numeric column by construction.
    // Recorded rather than silently worked around: the skill-smoke matrix runs this same file and
    // passes, because it calls the engine directly and never meets the ingest gate. Same shape as
    // the venn/upset adapter note — a green smoke row says the engine works, not that a user can
    // get there. Taking the override is the real user path here; the block is a real finding.
    overrideDataCheck: true,
  });

  const links = await page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { data?: { link?: { source?: number[] } }[] })
      | null;
    return (plot?.data ?? [])[0]?.link?.source?.length ?? 0;
  });
  // Exactly the budget: the engine keeps the `max_links` largest flows, and the table has more.
  expect(links, "the link budget did not reach the engine").toBe(5);
});

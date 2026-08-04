import { expect, test } from "@playwright/test";

import { runFromWorkbench } from "./fixtures";

/**
 * The 19 skills that were unrunnable until 2026-08-04, driven to a real figure by a real user path.
 *
 * WHY THESE CHECKS EXIST. `getSkill(id)` read the static seed alone, so every skill built after the
 * seed was last hand-edited rendered in the Workbench as its raw id, badged "Queued", with Apply
 * DISABLED. Nineteen of the forty-four live skills — including every plot type built across the
 * preceding sessions — were installable from the Store and then dead. Nine green gates said nothing
 * [[selom-shipped-not-reachable]].
 *
 * `getSkill` is fixed and `registry-completeness.test.ts` guards it, but that guard only proves a
 * skill can be RESOLVED. Nobody has ever applied these from the Workbench. `skill-smoke` proves each
 * ENGINE against the real corpus and says nothing about the path a user takes to it: the Store
 * install, the intake, the param controls, the Apply, the render. That gap is the whole finding, so
 * this closes it for the four newest plot types.
 *
 * ONE FILE, FOUR SKILLS, ON PURPOSE. `erg_metrics_long.csv` is genuinely long-form — many eyes
 * recorded at each flash intensity — so every claim below is a real measurement rather than a
 * reshaping artefact: `condition` has six real treatment arms, `sample_id` identifies one eye across
 * intensities (a true within-subject pairing), and repeated rows at one x ARE replicates. It is also
 * the file the smoke matrix uses for all four, so a divergence here is a FE-path defect, not data.
 *
 * Each check sets the skill's params through its REAL controls, by accessible name. A knob whose
 * widget never renders fails the check instead of being silently defaulted — which is the difference
 * this whole class is about: reachable, not merely runnable.
 */

const CSV = "erg-fig1e/erg_metrics_long.csv";

/**
 * Trace count + the axis text, read off the RENDERED figure rather than the spec.
 *
 * Plotly splits a `<br>` into sibling `<tspan>`s, so a two-line tick label ("Control" over "n=56")
 * has a `textContent` of `"Controln=56"` — words fused with no separator. Joining the tspans with a
 * space is what makes a tick assertion mean what it looks like it means; without it, a check for
 * "Control" fails on a figure that plainly says Control [[plotly-spec-can-encode-a-lie]].
 */
async function figureShape(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as
      | (HTMLElement & { data?: unknown[]; layout?: Record<string, unknown> })
      | null;
    const flat = (n: Element) => {
      const spans = [...n.querySelectorAll("tspan")];
      const parts = (spans.length ? spans : [n]).map((s) => s.textContent?.trim() ?? "");
      return parts.filter(Boolean).join(" ");
    };
    const text = (sel: string) => [...(plot?.querySelectorAll(sel) ?? [])].map(flat);
    return {
      traces: plot?.data?.length ?? 0,
      title: (plot?.layout as { title?: { text?: string } })?.title?.text ?? "",
      ticks: text(".xtick text").concat(text(".ytick text")),
      legend: text(".legend .traces .legendtext"),
    };
  });
}

test("lollipop ranks the six real treatment arms and draws a bootstrap interval", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · ERG lollipop",
    csvRelPath: CSV,
    skillName: "Lollipop chart (ranked)",
    awaitControl: ["Category column", "Value column"],
    params: {
      "Category column": "condition",
      "Value column": "b_wave_uv",
      // Horizontal is the default, but pinning it makes the tick assertion below about the arms
      // rather than about the orientation default happening not to have changed.
      Direction: "h",
    },
  });

  const shape = await figureShape(page);
  expect(shape.traces).toBeGreaterThan(0);
  // The six arms are the CATEGORY axis. Horizontal → they are y ticks.
  expect(shape.ticks).toContain("Control");
  expect(shape.ticks).toContain("AAV8-RK-PDE6B");
  // n=21-56 per arm, so the bootstrap has real replicates and the interval is genuinely computed.
  // Its presence is the claim `lollipop` makes that `bar_figure` cannot (mean±SEM by construction).
  const hasInterval = await page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as (HTMLElement & { data?: { error_x?: unknown; error_y?: unknown }[] }) | null;
    return (plot?.data ?? []).some((t) => t.error_x || t.error_y);
  });
  expect(hasInterval, "no CI on a table with 21-56 values per arm").toBe(true);
});

test("slope pairs each eye across two flash levels — the columns it refuses to guess", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · ERG slope",
    csvRelPath: CSV,
    skillName: "Slope chart (paired before/after)",
    awaitControl: ["Subject column (required)", "Condition column (required)"],
    params: {
      // These three are the whole point: slope REFUSES to auto-detect them, because the wrong
      // pairing produces a confident, completely wrong figure. Before the picker they were a text
      // box you had to already know the answer to type into.
      "Subject column (required)": "sample_id",
      "Condition column (required)": "intensity_group",
      "Which two, in order": "Group1, Group4",
      "Value column": "b_wave_uv",
    },
  });

  const shape = await figureShape(page);
  // One line per paired eye plus the summary line — a real within-subject design, not two marginals.
  expect(shape.traces).toBeGreaterThan(1);
  expect(shape.ticks.join(" ")).toMatch(/Group1|Group4/);
});

test("ridge draws one density per arm and discloses what it smoothed", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · ERG ridge",
    csvRelPath: CSV,
    skillName: "Ridge plot (joyplot)",
    awaitControl: ["Category column", "Value column"],
    params: {
      "Category column": "condition",
      "Value column": "b_wave_uv",
    },
  });

  const shape = await figureShape(page);
  // Six arms → at least six filled density traces.
  expect(shape.traces).toBeGreaterThanOrEqual(6);
  // `add_count` is on, so each ridge's tick carries its own n — "Control n=56". That n is the only
  // size cue left once the densities are peak-normalized to equal height.
  expect(shape.ticks.join(" | ")).toMatch(/Control n=\d+/);
  // The grey-ridge class, checked where it actually manifests: the PAINTED pixels.
  //
  // `ridge` emits `fill:"toself"` with NO `fillcolor`, so each curve takes its colour from the
  // theme colourway at render time — and a `fill:"toself"` scatter derives that fill from its LINE
  // colour, which is how the whole panel went grey once the outline was pinned. Reading
  // `plot.data.fillcolor` cannot see any of that: it hands back the input spec, where the field is
  // simply absent. Only the resolved DOM fill distinguishes "six colours" from "six greys"
  // [[plotly-spec-can-encode-a-lie]].
  const fills = await page.evaluate(() =>
    [...document.querySelectorAll(".js-plotly-plot .scatterlayer .js-fill")].map((p) =>
      getComputedStyle(p).fill,
    ),
  );
  expect(fills.length, "no filled ridge painted at all").toBeGreaterThanOrEqual(6);
  expect(
    new Set(fills).size,
    `every ridge painted the same colour (${fills[0]}) — the grey-ridge class`,
  ).toBeGreaterThan(1);
});

test("line plots the intensity ladder with one series per arm and real replicate spread", async ({ page }) => {
  await runFromWorkbench(page, {
    projectName: "Browser-verify · ERG line",
    csvRelPath: CSV,
    skillName: "Line plot",
    awaitControl: ["X column", "Y column"],
    params: {
      "X column": "intensity_log_cd_s_m2",
      "Y column": "b_wave_uv",
      // Never auto-detected by design: guessing the series column silently changes what the figure
      // MEANS. So this is the knob whose picker matters most here.
      "One line per": "condition",
      "Spread shows": "band",
    },
  });

  const shape = await figureShape(page);
  // Six arms, each a mean line plus its band — so more traces than arms.
  expect(shape.traces).toBeGreaterThan(6);
  expect(shape.legend).toContain("Control");
  expect(shape.legend).toContain("AAV8-RK-PDE6B");
});

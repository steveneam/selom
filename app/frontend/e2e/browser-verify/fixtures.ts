import { join } from "node:path";

import { expect, test as base, type Locator, type Page } from "@playwright/test";

import { DATASETS_DIR, FIXTURE_CSV } from "../../scripts/browser-verify/paths.mjs";

/**
 * The harness: drive a REAL run through the UI until a real figure is open in the editor.
 *
 * This is the single dependency of D-5 and of D-1/D-3/D-4/D-6/D-7/D-10/D-11, the cloud round-trip,
 * and every future browser verification — so it is built once, here, rather than re-improvised.
 *
 * WHY IT MUST BE A REAL RUN (do not "optimise" this into a shortcut — four have already failed):
 *   · `figure-view.tsx` branches on the LIVE editor store's `figure.spec`, not the persisted record;
 *   · that store is seeded only by `figure.init(spec)` — from `openFigure` or a COMPLETED RUN;
 *   · so a demo project shows "Figure spec not stored" (its seeded figure has no spec), an
 *     API-created project shows "Project not found" (the FE store is localStorage-first), and
 *     localStorage injection is lost to the store's seed/reconcile on load.
 *   · `?demo=<skill>` is mock-mode only (`project-workspace.tsx` returns early unless
 *     `apiMockingEnabled`), so it cannot serve a real-data check at all.
 */

/** Geometry of the artboard stage — the D-5 measurement, as data. */
export type StageGeometry = {
  /** Visible height of the scroll container that holds the artboard card. */
  stageClient: number;
  /** Its scroll height — greater than `stageClient` means the hero is clipped. */
  stageScroll: number;
  /** The white artboard card's rendered height. */
  card: number;
  cardWidth: number;
  stageClientWidth: number;
  /** `stageScroll - stageClient`; PASS is 0. */
  overflow: number;
  /** Horizontal centring slack, left and right, inside the stage's content box. */
  gutterLeft: number;
  gutterRight: number;
  /** How many `.bg-artboard` elements matched — must be exactly 1 on the figure editor. */
  matches: number;
};

export type Editor = {
  page: Page;
  projectId: string;
  /** Resize and wait for the layout (and Plotly's debounced resize) to settle. */
  viewport(width: number, height: number): Promise<void>;
  /** The D-5 snippet, run in-page. */
  measureStage(): Promise<StageGeometry>;
  /** The shell's direct children with their heights — D-4's "what does fixed chrome cost?". */
  shellBands(): Promise<{ className: string; height: number }[]>;
  /** The width twin: every fixed column between the viewport edge and the artboard. */
  horizontalChrome(): Promise<Awaited<ReturnType<typeof horizontalChrome>>>;
  /** JS errors collected since the page opened (a render throw lands here). */
  pageErrors: string[];
};

/**
 * Click a button and keep clicking until its effect lands.
 *
 * A `next dev` page serves interactive-looking HTML before React has hydrated, so the FIRST click on
 * a freshly-loaded route is silently swallowed — the element is visible, enabled and hit-testable,
 * but no handler is attached yet. Playwright's auto-waiting cannot see that, so this is not a
 * flake-hiding retry: it is waiting for the one state the DOM does not expose.
 */
async function clickWhenLive(
  page: Page,
  locator: ReturnType<Page["getByRole"]>,
  landed: () => boolean | Promise<boolean>,
  attempts = 20,
) {
  await locator.waitFor({ state: "visible" });
  for (let i = 0; i < attempts; i++) {
    await locator.click({ trial: false }).catch(() => {});
    for (let j = 0; j < 10; j++) {
      if (await landed()) return;
      await page.waitForTimeout(100);
    }
  }
  throw new Error(`click never took effect after ${attempts} attempts: ${locator}`);
}

/** Wait until a measurement stops changing — layout + Plotly's resize are both async. */
async function settle(page: Page) {
  let last = "";
  for (let i = 0; i < 40; i++) {
    const now = await page.evaluate(() => {
      const el = document.querySelector(".bg-artboard");
      const r = el?.getBoundingClientRect();
      return r ? `${Math.round(r.width)}x${Math.round(r.height)}` : "none";
    });
    if (now === last && now !== "none") return;
    last = now;
    await page.waitForTimeout(120);
  }
}

/**
 * Drive: new project → name it → drop the real CSV → confirm intake → run the proposed skill →
 * figure open in the editor. Returns the project id.
 *
 * Named projects only — never "Untitled" (owner rule, stated twice) [[selom-name-test-projects]].
 */
export async function openRealFigure(
  page: Page,
  {
    projectName = "Browser-verify · EYG_28 volcano",
    /** Catalog display name of the skill to run. "Volcano plot" yields a RESPONSIVE spec (no
     *  `layout.width`) — the branch D-5 is about. A fixed-size figure (ERG trace grid) exercises
     *  `artboardFrame(fixed)`'s other branch. */
    skillName = "Volcano plot",
  }: { projectName?: string; skillName?: string } = {},
) {
  await page.goto("/");
  // Scoped to <main>: the sidebar carries a second, icon-only `aria-label="New project"` button, and
  // an unscoped `.first()` picks THAT one. Both work, but the hero button is the affordance a user
  // actually takes, so that is what the harness exercises.
  await clickWhenLive(
    page,
    page.getByRole("main").getByRole("button", { name: "New project" }).first(),
    () => /\/p\/.+/.test(page.url()),
  );
  const projectId = new URL(page.url()).pathname.split("/p/")[1];

  const nameInput = page.getByLabel("Project name");
  await nameInput.waitFor();
  await nameInput.fill(projectName);
  await nameInput.blur();

  // Step 1 — the overview dropzone. A real <label> wrapping a file <input>, so this is the same
  // path a drag-and-drop takes.
  await page.locator('input[type="file"]').first().setInputFiles(FIXTURE_CSV);

  // Step 2 — the intake questionnaire, once the real /data/inspect has come back. "Confirm & run"
  // is disabled until the design is valid; for a DE table there is no contrast to pick, so it
  // enables on its own. If routing resolves no skill the questionnaire points at Skip instead.
  const confirm = page.getByRole("button", { name: /Confirm & run/i });
  const skip = page.getByRole("button", { name: /Skip — I.ll pick skills/i });
  await expect(confirm.or(skip).first()).toBeVisible({ timeout: 120_000 });
  if (await confirm.isVisible().catch(() => false)) {
    await expect(confirm).toBeEnabled({ timeout: 60_000 });
    await confirm.click();
  } else {
    await skip.click();
  }

  // Step 3 — the workbench. Prefer the engine's own "Recommended for your data" chip: it is a real
  // <button> whose accessible name IS the skill name, it runs in one click, and taking it exercises
  // the live inspect→routing→data-fit path rather than a hand-picked skill. Fall back to the
  // installed-skill card's "Apply" if the routing produced no chip.
  //
  // A completed run is the ONLY thing that calls `figure.init(res.figure)` — the sole opener of the
  // editor. Everything above this line is just getting a real dataset in front of a real skill.
  const chip = page.getByRole("button", { name: skillName, exact: true });
  const applyRow = page
    .locator("div")
    .filter({ has: page.getByText(skillName, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Apply", exact: true }) })
    .last()
    .getByRole("button", { name: "Apply", exact: true });

  await expect(chip.or(applyRow).first()).toBeVisible({ timeout: 60_000 });
  if (await chip.isVisible().catch(() => false)) await chip.click();
  else await applyRow.click();

  // Step 4 — a real figure, really rendered.
  await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 120_000 });
  await settle(page);
  return projectId;
}

/**
 * Drive as far as the WORKBENCH with one skill selected and its inline params rendered — one step
 * short of {@link openRealFigure}, which runs the skill and lands in the editor.
 *
 * That stopping point is the whole reason this exists: a skill's parameter panel only renders while
 * a skill is SELECTED and un-applied, so every claim about the inputs (a picker vs a text box, what
 * a select offers) is unobservable from the editor. Installs start empty, so the skill is installed
 * through the real Store UI rather than injected — `workspaceStore` is localStorage-first and a
 * hand-written entry is lost to the store's own seed/reconcile on load, the same trap that defeated
 * four shortcuts on the figure path.
 *
 * Named projects only — never "Untitled" (owner rule, stated twice) [[selom-name-test-projects]].
 */
export async function openWorkbench(
  page: Page,
  {
    projectName,
    /** Corpus-relative input. Defaults to the harness's standard DE table. */
    csvRelPath,
    /** Catalog display name, e.g. "Box / strip plot". */
    skillName,
    /**
     * A control that proves this skill's param panel has actually rendered — its own, not a
     * generic one. "Apply skill" appears as soon as a skill is selected, including before the live
     * `GET /skills/{id}` describe lands, so waiting on that alone can return a panel with no
     * controls in it. Defaults to boxplot's pair, which is what the picker checks use.
     */
    awaitControl = ["Category order", "Value column"],
  }: {
    projectName: string;
    csvRelPath?: string;
    skillName: string;
    awaitControl?: string[];
  },
) {
  const csv = csvRelPath ? join(DATASETS_DIR, csvRelPath) : FIXTURE_CSV;

  // Step 1 — install the skill through the Store, so it appears in the workbench's installed list.
  await page.goto("/store");
  const search = page.getByLabel("Search skills");
  await search.waitFor();
  await search.fill(skillName);
  // Innermost div that holds BOTH the skill's name and its install toggle — the same idiom
  // `openRealFigure` uses for the workbench row, and it survives the button's Install→Installed flip.
  const card = page
    .locator("div")
    .filter({ has: page.getByText(skillName, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: /^(Install|Installed)$/ }) })
    .last();
  const installed = card.getByRole("button", { name: /^Installed$/ });
  const install = card.getByRole("button", { name: /^Install$/ });
  // Installs are ACCOUNT-WIDE and localStorage-backed, so they survive between specs in a run — the
  // toggle is already "Installed" for every spec after the first. Clicking it then would UNINSTALL.
  await expect(install.or(installed).first()).toBeVisible({ timeout: 60_000 });
  if ((await installed.count()) === 0) {
    // Hydration: the first click on a freshly-loaded route is swallowed (see `clickWhenLive`).
    await clickWhenLive(page, install, async () => (await installed.count()) > 0);
  }

  // Step 2 — a real project with the real file, through the same dropzone a drag-and-drop uses.
  await page.goto("/");
  await clickWhenLive(
    page,
    page.getByRole("main").getByRole("button", { name: "New project" }).first(),
    () => /\/p\/.+/.test(page.url()),
  );
  const projectId = new URL(page.url()).pathname.split("/p/")[1];

  const nameInput = page.getByLabel("Project name");
  await nameInput.waitFor();
  await nameInput.fill(projectName);
  await nameInput.blur();

  await page.locator('input[type="file"]').first().setInputFiles(csv);

  // Step 3 — clear the intake questionnaire. A long-form table has no deg contrast to confirm, so
  // this is normally the Skip path; both are handled because routing decides which appears.
  const confirm = page.getByRole("button", { name: /Confirm & run/i });
  const skip = page.getByRole("button", { name: /Skip — I.ll pick skills/i });
  await expect(confirm.or(skip).first()).toBeVisible({ timeout: 120_000 });
  if (await confirm.isVisible().catch(() => false)) {
    await expect(confirm).toBeEnabled({ timeout: 60_000 });
    await confirm.click();
  } else {
    await skip.click();
  }

  // Step 4 — SELECT the skill (click the installed card), never Apply: applying runs it and leaves
  // for the editor, taking the param panel with it.
  const row = page
    .locator("div")
    .filter({ has: page.getByText(skillName, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Apply", exact: true }) })
    .last();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.getByText(skillName, { exact: true }).click();

  // The params come from a live `GET /skills/{id}` describe, so wait for a real control, not a tick.
  await expect(page.getByRole("button", { name: "Apply skill" })).toBeVisible({ timeout: 60_000 });
  const [first, ...rest] = awaitControl;
  let control = page.getByLabel(first);
  for (const name of rest) control = control.or(page.getByLabel(name));
  await expect(control.first()).toBeVisible({ timeout: 60_000 });
  return projectId;
}

/**
 * Drive a skill from the Store all the way to a RENDERED FIGURE, setting its params on the way.
 *
 * This is {@link openWorkbench} + the Apply that {@link openRealFigure} gets for free from the
 * engine's "Recommended for your data" chip. Neither existing fixture covers it: `openRealFigure`
 * runs whatever routing proposes (in practice `volcano`) and cannot set a parameter, and
 * `openWorkbench` deliberately stops before Apply so the panel stays on screen.
 *
 * WHY IT IS WORTH ITS OWN FIXTURE. The picker session found 19 of 44 shipped skills unrunnable —
 * installable from the Store, then dead behind a disabled Apply — and no gate could see it, because
 * `skill-smoke` proves each ENGINE on real data and says nothing about the path a user takes to it
 * [[selom-shipped-not-reachable]]. This is the instrument for that second half: it exercises Store
 * install → real file → intake → param controls → Apply → a figure on the canvas, which is the
 * whole claim "this skill ships" makes.
 *
 * `params` are set through the REAL controls by accessible name, so a knob whose widget never
 * renders fails here rather than being silently defaulted — the difference between a skill that is
 * reachable and one that merely runs.
 */
/**
 * Set a slider by KEYBOARD, to the exact value, through events the browser marks as trusted.
 *
 * Playwright's `fill()` refuses an `input[type=range]` outright, so every threshold knob would
 * otherwise be undrivable — and the alternative (assigning `.value` and dispatching a synthetic
 * `input`) proves only that React's handler works when called, which is not the claim these checks
 * make. `Home` snaps to the control's own `min`, then one `ArrowRight` per step walks to the target,
 * which is exactly what a keyboard user does.
 *
 * The step count is read off the rendered element, so this stays correct when a spec's bounds move.
 * It refuses a target that is off the step lattice rather than silently landing one step away —
 * the same failure the `registry-completeness` slider-step guard catches at merge time.
 */
async function setRange(page: Page, field: Locator, target: number, label: string) {
  const { min, step } = await field.evaluate((el) => {
    const i = el as HTMLInputElement;
    return { min: Number(i.min || 0), step: Number(i.step || 1) };
  });
  const presses = (target - min) / step;
  expect(
    Math.abs(presses - Math.round(presses)),
    `"${label}" cannot reach ${target}: it steps by ${step} from ${min}`,
  ).toBeLessThan(1e-6);
  expect(presses, `"${label}": ${target} is below the control's min of ${min}`).toBeGreaterThanOrEqual(0);
  // A guard on the harness, not the UI: a 2000-press walk means the test is asking for a value at
  // the far end of a wide range and should say so, rather than spending a minute in key events.
  expect(presses, `"${label}" would need ${presses} key presses — pick a nearer value`).toBeLessThanOrEqual(300);

  await field.focus();
  await page.keyboard.press("Home");
  for (let i = 0; i < Math.round(presses); i++) await page.keyboard.press("ArrowRight");
  // Compared as a NUMBER: twenty 0.1 steps can land on "2" or on "2.0000000000000004" depending on
  // how the engine accumulates, and a string compare would fail on a slider that is exactly right.
  const landed = await field.evaluate((el) => Number((el as HTMLInputElement).value));
  expect(landed, `"${label}" did not land on ${target}`).toBeCloseTo(target, 6);
}

export async function runFromWorkbench(
  page: Page,
  opts: {
    projectName: string;
    csvRelPath?: string;
    skillName: string;
    awaitControl?: string[];
    /** Accessible label → value, applied in declaration order (later knobs can depend on earlier). */
    params?: Record<string, string>;
    /**
     * Take the QC block card's "Review & run anyway" when the run is gated. Only for inputs the
     * guardrail flags on a rule that does not apply to THIS skill — e.g. a pure edge table, which
     * has no numeric column because the skill derives its values by counting the pairs.
     */
    overrideDataCheck?: boolean;
  },
) {
  const projectId = await openWorkbench(page, opts);

  for (const [label, value] of Object.entries(opts.params ?? {})) {
    const field = page.getByLabel(label, { exact: true });
    await expect(field, `no control labelled "${label}" — the knob is API-only`).toBeVisible({
      timeout: 30_000,
    });
    // A switch is a `role="switch"` BUTTON (param-control.tsx), not an input — `fill()` throws on
    // it and `.type` is undefined, so every bool knob was undrivable here. It is set by comparing
    // the wanted state to `aria-checked` and clicking only on a difference, which makes the call
    // idempotent: passing "true" for a knob already on is a no-op rather than a silent toggle-off.
    // Bool knobs are the largest single class in the backend spec (`normalize` alone is 11 skills),
    // so this is the switch peer of `setRange`.
    const kind = await field.evaluate((el) =>
      el.getAttribute("role") === "switch"
        ? "switch"
        : el.tagName === "SELECT"
          ? "select"
          : (el as HTMLInputElement).type,
    );
    if (kind === "switch") {
      const want = ["true", "1", "on", "yes"].includes(value.trim().toLowerCase());
      const now = (await field.getAttribute("aria-checked")) === "true";
      if (want !== now) await field.click();
      await expect(field, `switch "${label}" did not settle on ${want}`).toHaveAttribute(
        "aria-checked",
        String(want),
      );
    } else if (kind === "select") await field.selectOption(value);
    else if (kind === "range") await setRange(page, field, Number(value), label);
    else await field.fill(value);
  }

  await page.getByRole("button", { name: "Apply skill" }).click();

  const canvas = page.locator(".js-plotly-plot");

  // The QC guardrail's own escape hatch, driven only when the caller asks for it.
  //
  // A blocking QC flag makes the run a 422 and puts up the block card, whose subordinate action is
  // "Review & run anyway" — a first-class path ("It's your data"), and one no browser check had
  // ever taken. It is OPT-IN so a check that expects clean data still fails loudly on an
  // unexpected block, rather than clicking through the guardrail and reporting a pass.
  if (opts.overrideDataCheck) {
    const override = page.getByRole("button", { name: /Review & run anyway/i });
    await expect(canvas.or(override).first()).toBeVisible({ timeout: 180_000 });
    if (await override.isVisible().catch(() => false)) await override.click();
  }

  // A rendered Plotly canvas is the only proof. A run that raises leaves the workbench standing
  // with an error banner, which is what this times out on — so the failure names the skill.
  await expect(canvas).toBeVisible({ timeout: 180_000 });
  await settle(page);
  return projectId;
}

/** The D-5 measurement, verbatim from the Lane 3 wrap, returned as data instead of console output. */
export async function measureStage(page: Page): Promise<StageGeometry> {
  return page.evaluate(() => {
    // `.bg-artboard` also matches the Figure-data preview and the compare panes — the views are
    // mutually exclusive, so a count > 1 means we are not on the figure editor.
    const cards = [...document.querySelectorAll(".bg-artboard")].filter((el) =>
      el.parentElement?.classList.contains("overflow-auto"),
    );
    const card = cards[0] as HTMLElement | undefined;
    const stage = card?.parentElement as HTMLElement | undefined;
    if (!card || !stage) {
      return {
        stageClient: 0, stageScroll: 0, card: 0, cardWidth: 0, stageClientWidth: 0,
        overflow: 0, gutterLeft: 0, gutterRight: 0, matches: cards.length,
      };
    }
    const cardBox = card.getBoundingClientRect();
    const stageBox = stage.getBoundingClientRect();
    const cs = getComputedStyle(stage);
    const padL = parseFloat(cs.paddingLeft) || 0;
    const padR = parseFloat(cs.paddingRight) || 0;
    return {
      stageClient: stage.clientHeight,
      stageScroll: stage.scrollHeight,
      card: Math.round(cardBox.height),
      cardWidth: Math.round(cardBox.width),
      stageClientWidth: stage.clientWidth,
      overflow: stage.scrollHeight - stage.clientHeight,
      gutterLeft: Math.round(cardBox.left - (stageBox.left + padL)),
      gutterRight: Math.round(stageBox.right - padR - cardBox.right),
      matches: cards.length,
    };
  });
}

/**
 * What the fixed CHROME costs the artboard horizontally, left to right across the viewport.
 *
 * D-5's height question has a width twin that §D never asked, because §D assumed the stage got
 * ~506px of plot at 1280. Every fixed column between the viewport edge and the artboard is measured
 * here so the shortfall can be attributed rather than guessed at.
 */
export async function horizontalChrome(page: Page) {
  return page.evaluate(() => {
    const px = (el: Element | null | undefined) =>
      el ? Math.round(el.getBoundingClientRect().width) : null;
    const cards = [...document.querySelectorAll(".bg-artboard")].filter((el) =>
      el.parentElement?.classList.contains("overflow-auto"),
    );
    const card = cards[0] as HTMLElement | undefined;
    const stage = card?.parentElement as HTMLElement | undefined;
    const plot = document.querySelector(".js-plotly-plot");
    // Plotly's drag layer spans exactly the plotting area (axes excluded) — the "plot width" §D means.
    const drag = plot?.querySelector(".nsewdrag");
    // Walk from the stage up to <main>, and at each level record every SIBLING's width. That
    // attributes the shortfall to real elements instead of guessed selectors: whatever is standing
    // beside the artboard shows up by name, whatever its classes happen to be.
    const columns: { level: number; className: string; width: number; isAncestor: boolean }[] = [];
    const main = document.querySelector("main");
    let node: HTMLElement | null | undefined = stage;
    let level = 0;
    while (node && node !== main && node !== document.body && level < 12) {
      const parent = node.parentElement;
      if (!parent) break;
      // Only a parent laid out as a ROW puts its children BESIDE the artboard. A column parent
      // stacks them above/below, where they cost height (D-4's question), not width — counting
      // those would triple the total and make the figure meaningless.
      const isRow = getComputedStyle(parent).flexDirection === "row";
      if (isRow && parent.children.length > 1) {
        for (const sib of parent.children) {
          const w = Math.round(sib.getBoundingClientRect().width);
          if (w > 0) {
            columns.push({
              level,
              className: sib.className.toString().slice(0, 44),
              width: w,
              isAncestor: sib === node || sib.contains(stage!),
            });
          }
        }
      }
      node = parent;
      level += 1;
    }

    return {
      viewport: window.innerWidth,
      sidebar: px(document.querySelector('aside[aria-label="Primary"]')),
      main: px(main),
      stage: px(stage),
      card: px(card),
      plotArea: px(drag),
      plotSvgWidth: px(plot?.querySelector(".main-svg")),
      /** Every element sharing a row with the artboard on the way up to <main>. */
      columns,
    };
  });
}

/** D-4: the shell's direct children and what each costs in height. */
export async function shellBands(page: Page) {
  return page.evaluate(() => {
    const art = document.querySelector(".bg-artboard");
    const shell = art?.closest(".overflow-hidden");
    if (!shell) return [];
    return [...shell.children].map((el) => ({
      className: el.className.toString().slice(0, 60),
      height: Math.round(el.getBoundingClientRect().height),
    }));
  });
}

export const test = base.extend<{ editor: Editor }>({
  // NB: Playwright's fixture callback is positional, so the second parameter is renamed off `use`.
  // eslint's react-hooks/rules-of-hooks reads a bare `use(...)` as React's `use` hook and errors
  // ("called in function 'editor' that is neither a component nor a custom Hook").
  editor: async ({ page }, provide) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(String(e)));
    page.on("console", (m) => {
      // Benign asset 404s from the dev server are not JS errors.
      if (m.type() === "error" && !m.text().includes("Failed to load resource")) {
        pageErrors.push(m.text());
      }
    });

    const projectId = await openRealFigure(page);

    await provide({
      page,
      projectId,
      pageErrors,
      viewport: async (width, height) => {
        await page.setViewportSize({ width, height });
        await settle(page);
      },
      measureStage: () => measureStage(page),
      shellBands: () => shellBands(page),
      horizontalChrome: () => horizontalChrome(page),
    });
  },
});

export { expect };

import { expect, test } from "@playwright/test";

/**
 * Annotation & drawing layer smoke (Pillar-2 slice 5 — the export-killer). `?demo=1` deep-links to a
 * live editable figure. This proves the slice end-to-end on a REAL rendered figure — the one thing the
 * pure op-builder unit tests can't: that Plotly renders the `selom`-tagged `path` shape + annotations
 * WITHOUT error (the tag is render-inert), that the Annotate panel + tools rail commit them, that they
 * land in the figure spec (render = f(spec), so what renders is what exports), and that Cmd-Z reverts.
 */

// Read the live Plotly graph-div layout (what was handed to Plotly = f(store.spec) = what exports).
async function layoutCounts(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const gd = document.querySelector(".js-plotly-plot") as unknown as {
      layout?: { shapes?: { selom?: unknown }[]; annotations?: { selom?: unknown }[] };
    } | null;
    const shapes = gd?.layout?.shapes ?? [];
    const annos = gd?.layout?.annotations ?? [];
    return {
      selomShapes: shapes.filter((s) => s && (s as { selom?: unknown }).selom).length,
      selomAnnos: annos.filter((a) => a && (a as { selom?: unknown }).selom).length,
      // Rendered SVG proof: the bracket path + annotation text actually drawn on the canvas.
      drawnShapePaths: document.querySelectorAll(".js-plotly-plot .shapelayer path").length,
    };
  });
}

test("add significance bracket + text + arrow, then undo — renders and reverts", async ({ page }) => {
  // Catch real JS / render failures (a Plotly throw on the tagged path shape would land here). Benign
  // network 404s from the mock dev server (a missing favicon/asset, present on any page load) are not
  // JS errors and are filtered out.
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text());
  });

  await page.goto("/p/demo-pbmc?demo=1");
  await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Cluster 0")).toBeVisible();

  // Open the always-present Annotate tab.
  await page.getByRole("tab", { name: "Annotate" }).click();

  const before = await layoutCounts(page);

  // Drive the adds from the left TOOLS RAIL (exact names hit the rail, not the panel's add buttons) —
  // verifying the rail wiring. The panel is the richer surface, asserted via the managed list below.
  const railButton = (name: string) => page.getByRole("button", { name, exact: true });

  // (a) Significance bracket — the anchor: a tagged path shape + a stars annotation.
  await railButton("Significance bracket").click();
  await expect
    .poll(async () => (await layoutCounts(page)).selomShapes)
    .toBe(before.selomShapes + 1);
  const afterBracket = await layoutCounts(page);
  expect(afterBracket.selomAnnos).toBe(before.selomAnnos + 1); // the stars annotation
  expect(afterBracket.drawnShapePaths).toBeGreaterThan(before.drawnShapePaths); // Plotly DREW it

  // (c) Free text label + (b) arrow — both tagged annotations.
  await railButton("Text label").click();
  await railButton("Arrow / callout").click();
  await expect
    .poll(async () => (await layoutCounts(page)).selomAnnos)
    .toBe(before.selomAnnos + 3); // stars + text + arrow

  // The panel lists all three as managed items.
  await expect(page.getByText("On the figure · 3")).toBeVisible();

  // Cmd-Z reverts each add (global undo → figure.undo()). Three undos → back to the start.
  for (let i = 0; i < 3; i++) await page.keyboard.press("Meta+z");
  await expect
    .poll(async () => {
      const c = await layoutCounts(page);
      return c.selomShapes + c.selomAnnos;
    })
    .toBe(before.selomShapes + before.selomAnnos);

  expect(errors, `console/page errors during the smoke:\n${errors.join("\n")}`).toEqual([]);
});

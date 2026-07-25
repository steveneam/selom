import { expect, test } from "./fixtures";

/**
 * The artboard zoom control (`W-2`, owner decision #13, `docs/editor-room/spec.md` R5/R6).
 *
 * Two things a unit test cannot settle: that the control is REACHABLE in the shipped editor, and
 * that pressing it actually changes the rendered size of the figure. Both are checked here against
 * a real figure, because the repo's own lesson is that a knob can be wired, typed and unit-tested
 * and still do nothing on screen.
 *
 * SCOPE, stated honestly: the harness fixture is a RESPONSIVE volcano, so this exercises the ladder
 * and the readout. Zoom's headline case — a FIXED-size figure (an ERG trace grid declares 960×640)
 * fitting into a stage narrower than itself — needs an ERG run to reach and is covered by
 * `fitScale`'s unit tests plus the `artboardFrame` contract, NOT by a browser here. `fitScale`
 * returning exactly 1 for a responsive figure is why "Fit" reads 100% below rather than something
 * smaller: the figure genuinely already fits.
 */
test("zoom — the control changes the rendered artboard, and the readout is truthful", async ({
  editor,
}) => {
  const { page } = editor;
  await editor.viewport(1280, 800);

  const card = page.locator(".bg-artboard").first();
  const readout = () => page.locator("text=/^\\d+%$/").first();

  const cardWidth = async () => {
    const box = await card.boundingBox();
    return Math.round(box?.width ?? 0);
  };

  // A responsive figure already fits its stage, so Fit is 100% — the honest answer, not a bug.
  await expect(readout()).toHaveText("100%");
  const at100 = await cardWidth();

  // Zoom IN: the rendered card must actually get bigger. `boundingBox` reports the transformed box,
  // so this fails if the transform never reached the DOM — which is the whole point of the check.
  await page.getByRole("button", { name: "Zoom artboard in" }).click();
  await page.waitForTimeout(400);
  await expect(readout()).toHaveText("150%");
  const at150 = await cardWidth();

  // Zoom OUT twice: past 100% and down to 75%.
  await page.getByRole("button", { name: "Zoom artboard out" }).click();
  await page.getByRole("button", { name: "Zoom artboard out" }).click();
  await page.waitForTimeout(400);
  await expect(readout()).toHaveText("75%");
  const at75 = await cardWidth();

  // Fit returns to the figure's natural size.
  await page.getByRole("button", { name: "Fit artboard to view" }).click();
  await page.waitForTimeout(400);
  await expect(readout()).toHaveText("100%");
  const backToFit = await cardWidth();

  console.log(
    `\n[zoom @1280×800] card width: 100%=${at100}px  150%=${at150}px  75%=${at75}px  ` +
      `fit=${backToFit}px\n`,
  );

  expect(at150, "zooming in must make the rendered card wider").toBeGreaterThan(at100);
  expect(at75, "zooming out must make it narrower").toBeLessThan(at100);
  expect(
    Math.abs(backToFit - at100),
    "Fit must return a responsive figure to its natural 1:1 size",
  ).toBeLessThanOrEqual(2);

  // R6: zoom is a VIEW property. It must not have written to the spec, so it cannot have created an
  // undo entry — an editor that offers to "undo" a zoom has put view state in the figure's history.
  const undo = page.getByRole("button", { name: /^undo$/i }).first();
  if (await undo.count()) {
    await expect(undo, "zoom must not create an undoable edit").toBeDisabled();
  }

  expect(editor.pageErrors, `page errors during zoom:\n${editor.pageErrors.join("\n")}`).toEqual([]);
});

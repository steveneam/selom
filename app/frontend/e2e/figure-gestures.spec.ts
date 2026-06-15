import { test, expect } from "@playwright/test";

/**
 * Regression guard for in-canvas figure repositioning. Encodes the exact bugs found
 * while building it, so they can't silently come back:
 *  1. A drag on a BRAND-NEW figure must persist — react-plotly only syncs its
 *     onRelayout/onRestyle props on the first *update*, not on mount, so gestures
 *     used to no-op until the user touched a property control.
 *  2. A colour-bar drag emits `colorbar.x` even when the trace has no colorbar
 *     object; the patch must create the missing parent rather than throw and
 *     white-screen the editor.
 *
 * `?demo=1` deep-links straight to a live editable figure (see project-workspace),
 * so the test skips the data/intake/workbench flow. We drive the gestures by
 * emitting the exact Plotly events a drag-release fires — the same code path a real
 * drag hits, without pixel math.
 */
const LIVE_FIGURE = "/p/demo-pbmc?demo=1";

async function gotoLiveFigure(page: import("@playwright/test").Page) {
  await page.goto(LIVE_FIGURE);
  await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Cluster 0")).toBeVisible();
}

test.describe("figure editor — in-canvas gestures", () => {
  test("legend + rename gestures persist on a fresh figure and undo reverts", async ({ page }) => {
    await gotoLiveFigure(page);

    const undo = page.getByRole("button", { name: "Undo" });
    await expect(undo).toBeDisabled(); // fresh figure, no edits yet

    // The exact events a legend drag-release and a legend-label rename fire.
    await page.evaluate(() => {
      const el = document.querySelector(".js-plotly-plot") as unknown as {
        emit: (ev: string, data: unknown) => void;
      };
      el.emit("plotly_relayout", { "legend.x": 0.22, "legend.y": 0.85 });
      el.emit("plotly_restyle", [{ name: "Renamed cluster" }, [0]]);
    });

    // Each gesture became one undoable edit...
    await expect(undo).toBeEnabled();
    await expect(page.getByText("Renamed cluster")).toBeVisible();

    // ...and persisted into the spec (survives the re-render the commit triggers).
    const persisted = await page.evaluate(() => {
      const gd = document.querySelector(".js-plotly-plot") as unknown as {
        layout?: { legend?: { x?: number } };
        data?: Array<{ name?: string }>;
      };
      return { legendX: gd.layout?.legend?.x, name0: gd.data?.[0]?.name };
    });
    expect(persisted.legendX).toBeCloseTo(0.22, 3);
    expect(persisted.name0).toBe("Renamed cluster");

    // Undo reverts the most recent gesture and enables redo.
    await undo.click();
    await expect(page.getByRole("button", { name: "Redo" })).toBeEnabled();
  });

  test("colour-bar gesture does not crash the editor", async ({ page }) => {
    await gotoLiveFigure(page);

    // A colour-bar move/retext on a trace with no explicit colorbar object.
    await page.evaluate(() => {
      const el = document.querySelector(".js-plotly-plot") as unknown as {
        emit: (ev: string, data: unknown) => void;
      };
      el.emit("plotly_restyle", [{ "colorbar.x": 1.05, "colorbar.title.text": "z-score" }, [0]]);
    });

    // No Next.js runtime-error overlay, and the canvas is still alive.
    await expect(page.getByText("Runtime TypeError")).toHaveCount(0);
    await expect(page.locator(".js-plotly-plot")).toBeVisible();

    // The Colour bar Inspector section now appears (detector picked up the colorbar).
    await expect(page.getByRole("heading", { name: "Colour bar" })).toBeVisible();
  });
});

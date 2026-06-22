import { test, expect } from "@playwright/test";

/**
 * P3 — routing-confidence "not sure" surface. When the engine ISN'T confident about how to
 * analyze a dropped dataset (engine/route.py `confident=false` — modality unclear / coming-soon /
 * unclassifiable), the Data check panel must surface that honestly: a "Not sure how to analyze
 * this" card that reframes any suggestions as exploratory and hands control back via "Choose a
 * skill yourself" — instead of presenting a low-confidence guess as a confident recommendation.
 *
 * Driven through the demo deep-link: `?demo=<skill>` auto-runs the skill, and any other query
 * param is forwarded as a run param, so `&data_check=unsure` makes the MSW mock return a
 * not-confident routing (mocks/stub-bundle.ts). The confident path is the default mock.
 */
test.describe("data check — routing confidence", () => {
  test("a not-sure routing shows the honest surface and hands off to a manual pick", async ({ page }) => {
    await page.goto("/p/demo-pbmc?demo=pca&data_check=unsure");

    // The run completed (a figure is live) ...
    await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 30_000 });

    // ... and the not-sure surface auto-opened, distinct from the confident "Suggested next steps".
    const unsure = page.getByTestId("data-check-unsure");
    await expect(unsure).toBeVisible();
    await expect(page.getByText("Not sure how to analyze this")).toBeVisible();
    await expect(page.getByText("Exploratory starting points")).toBeVisible();
    await expect(page.getByText("Suggested next steps")).toHaveCount(0);
    await page.screenshot({ path: "../../graphify-out/scratch/s56-routing-not-sure.png" });

    // "Choose a skill yourself" hands control to the workbench — the figure view unmounts.
    await page.getByTestId("data-check-pick-manually").click();
    await expect(page.locator(".js-plotly-plot")).toHaveCount(0);
  });

  test("a confident routing still shows the suggested pipeline", async ({ page }) => {
    await page.goto("/p/demo-pbmc?demo=umap_scrna");

    await expect(page.locator(".js-plotly-plot")).toBeVisible({ timeout: 30_000 });
    // No not-sure surface for a confident verdict. The confident panel collapses when QC is clean
    // (it doesn't nag) — expand it to confirm the suggested pipeline is intact.
    await expect(page.getByTestId("data-check-unsure")).toHaveCount(0);
    await page.getByRole("button", { name: /Data check/ }).click();
    await expect(page.getByText("Suggested next steps")).toBeVisible();
  });
});

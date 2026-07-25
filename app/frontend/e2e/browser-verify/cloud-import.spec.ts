import { expect, test } from "./fixtures";

import { DROPBOX_REF, GDRIVE_REF } from "../../scripts/browser-verify/paths.mjs";

/**
 * V-2 — the cloud round trip, and D-8's four sub-checks on the CloudImportMenu.
 *
 * Lane 2 shipped the cloud surface but no worktree could drive a browser, so this was never
 * confirmed end to end. It is genuinely unblocked now: `config.py` reads the repo-root `.env`, the
 * backend resolves `https://nango.swordfish.cfd` with Google Drive and Dropbox enabled, and
 * `deploy/nango/preflight.sh` passes against the live broker with both connections refreshing.
 *
 * THE IMPORT LEG NEEDS A REFERENCE, and finding one taught us the session's biggest product finding:
 * **both providers are sandboxed to files Selom itself created.** Google's connection holds the
 * `drive.file` scope ("only the specific files you use with this app") and Dropbox's is an App
 * Folder — so listing either account returns NOTHING of the user's own data, and the menu's own hint
 * ("Open the file in Drive → Share → Copy link") describes a flow that cannot work. See
 * `docs/cloud-providers-contract/spec.md` and the board's `V-2`.
 *
 * So the refs come from the environment rather than being discovered:
 *   SELOM_BV_GDRIVE_REF   a Drive file id Selom can read (one it created)
 *   SELOM_BV_DROPBOX_REF  a path inside Selom's Dropbox App Folder, e.g. /file.csv
 * Absent, the import legs SKIP LOUDLY and D-8 still runs — a silent skip would read as a pass.
 */

/** Open a project's Data stage, where the drop-zone and the cloud menu sit side by side. */
async function openDataStage(page: import("@playwright/test").Page, projectId: string) {
  await page.goto(`/p/${projectId}`);
  // The project opens on its figure, where `W-2` now collapses the workrail at ≤1700 — so the named
  // stage buttons live behind the spine until it is expanded. Expanding first is the user's own path
  // to Data from here, and it keeps this helper working at any viewport.
  const expandRail = page.getByRole("button", { name: "Expand rail" });
  for (let i = 0; i < 15; i++) {
    if (await expandRail.count()) {
      await expandRail.click().catch(() => {});
      await page.waitForTimeout(200);
    }
    if (await page.getByRole("button", { name: /^Add (another dataset|data)$/i }).count()) break;
    await page.waitForTimeout(300);
  }

  // "Data" alone is the section HEADER — it carries a count badge ("Data 1") and toggles the section
  // open, it does not navigate. The affordance that actually opens the Data stage is Add data /
  // Add another dataset, which is also the one a user reaches for when they want to import.
  const dataBtn = page.getByRole("button", { name: /^Add (another dataset|data)$/i }).first();
  await dataBtn.waitFor({ state: "visible", timeout: 30_000 });
  for (let i = 0; i < 15; i++) {
    await dataBtn.click().catch(() => {});
    if (await page.getByRole("button", { name: /Import from cloud/i }).count()) return;
    await page.waitForTimeout(200);
  }
  throw new Error("never reached the Data stage's cloud menu");
}

test("D-8 — the CloudImportMenu popover at 1280×800", async ({ editor }) => {
  const { page } = editor;
  await editor.viewport(1280, 800);
  await openDataStage(page, editor.projectId);

  const trigger = page.getByRole("button", { name: /Import from cloud/i });
  await expect(trigger).toBeVisible();

  // (c) the trigger must read as a PEER of the drop-zone, not a stray control: same row, same band.
  const peer = await page.evaluate(() => {
    const btns = [...document.querySelectorAll("button")];
    const t = btns.find((b) => /import from cloud/i.test(b.textContent ?? ""));
    const drop = document.querySelector('input[type="file"]')?.closest("label, div");
    if (!t || !drop) return null;
    const tb = t.getBoundingClientRect();
    const db = drop.getBoundingClientRect();
    return {
      triggerTop: Math.round(tb.top),
      dropTop: Math.round(db.top),
      dropBottom: Math.round(db.bottom),
      /** Inside the drop-zone's vertical band, or directly beneath it — either reads as a peer. */
      adjacent: tb.top >= db.top - 24 && tb.top <= db.bottom + 96,
    };
  });

  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Import from cloud" });
  await expect(dialog).toBeVisible();
  await page.waitForTimeout(800); // the menu fetches providers + connections on first open

  const geo = await page.evaluate(() => {
    const pop = document.querySelector('[role="dialog"][aria-label="Import from cloud"]');
    if (!pop) return null;
    const pr = pop.getBoundingClientRect();
    const input = pop.querySelector("#cloud-import-url") as HTMLInputElement | null;

    // (a) does the placeholder FIT, or is it ellipsised? Measured by rendering the same string in a
    // detached span with the input's own font, then comparing to the input's content box.
    let placeholderPx = 0;
    let inputContentPx = 0;
    if (input) {
      const cs = getComputedStyle(input);
      const span = document.createElement("span");
      span.style.cssText = `position:absolute;visibility:hidden;white-space:pre;font:${cs.font}`;
      span.textContent = input.placeholder;
      document.body.appendChild(span);
      placeholderPx = Math.ceil(span.getBoundingClientRect().width);
      span.remove();
      inputContentPx = Math.floor(
        input.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight),
      );
    }

    // (b) what does the popover cover? The drop-zone above and any dataset rows below.
    const drop = document.querySelector('input[type="file"]')?.closest("label, div");
    const dr = drop?.getBoundingClientRect();
    const overlapsDrop = dr ? pr.top < dr.bottom && pr.bottom > dr.top && pr.left < dr.right && pr.right > dr.left : false;

    // (d) does it run past the fold?
    return {
      popTop: Math.round(pr.top),
      popBottom: Math.round(pr.bottom),
      popHeight: Math.round(pr.height),
      viewportH: window.innerHeight,
      belowFold: Math.max(0, Math.round(pr.bottom - window.innerHeight)),
      placeholder: input?.placeholder ?? null,
      placeholderPx,
      inputContentPx,
      overlapsDrop,
      /** A21's ghost: any "coming soon" copy still shipping in this menu. */
      comingSoon: /coming soon/i.test(pop.textContent ?? ""),
      providerRows: pop.querySelectorAll("li").length,
      text: (pop.textContent ?? "").replace(/\s+/g, " ").slice(0, 300),
    };
  });

  await page.screenshot({ path: "test-results/browser-verify/d8-cloud-menu-1280x800.png" });

  console.log(
    `\n[D-8 — CloudImportMenu @1280×800]\n` +
      `  (a) URL placeholder  "${geo!.placeholder}"  needs ${geo!.placeholderPx}px in ` +
      `${geo!.inputContentPx}px → ${geo!.placeholderPx <= geo!.inputContentPx ? "FITS" : "ELLIPSISED"}\n` +
      `  (b) popover ${geo!.popTop}–${geo!.popBottom} (${geo!.popHeight}px); covers the drop-zone: ` +
      `${geo!.overlapsDrop}\n` +
      `  (c) trigger top=${peer?.triggerTop} vs drop-zone ${peer?.dropTop}–${peer?.dropBottom} → ` +
      `${peer?.adjacent ? "reads as a peer" : "DETACHED from the drop-zone"}\n` +
      `  (d) below the fold: ${geo!.belowFold}px (viewport ${geo!.viewportH}); ` +
      `"coming soon" copy present: ${geo!.comingSoon}\n` +
      `  provider rows: ${geo!.providerRows}\n  menu text: ${geo!.text}\n`,
  );

  // (a) an ellipsised placeholder tells the user nothing about what to paste.
  expect(
    geo!.placeholderPx,
    `the URL placeholder "${geo!.placeholder}" needs ${geo!.placeholderPx}px but its input gives ` +
      `${geo!.inputContentPx}px — it is being ellipsised, so the one hint about what to paste is cut off`,
  ).toBeLessThanOrEqual(geo!.inputContentPx);

  // (d) the popover must be fully reachable without scrolling a popover.
  expect(
    geo!.belowFold,
    `the cloud menu runs ${geo!.belowFold}px past the fold at 1280×800 — the bottom rows ` +
      `(the connected accounts) are the part that gets cut`,
  ).toBe(0);

  // A20's regression guard: the server owns provider state; no client-side "coming soon" may return.
  expect(geo!.comingSoon, `"coming soon" copy is back in the cloud menu (A20)`).toBe(false);
  expect(geo!.providerRows, "no OAuth provider rows rendered — the menu is empty").toBeGreaterThan(0);

  expect(editor.pageErrors, `page errors during D-8:\n${editor.pageErrors.join("\n")}`).toEqual([]);
});

for (const p of [
  { id: "google", label: "Google Drive", ref: GDRIVE_REF, env: "SELOM_BV_GDRIVE_REF" },
  { id: "dropbox", label: "Dropbox", ref: DROPBOX_REF, env: "SELOM_BV_DROPBOX_REF" },
]) {
  test(`V-2 — import a real file from ${p.label} through the UI`, async ({ editor }) => {
    test.skip(
      !p.ref,
      `${p.env} is unset. Both providers are sandboxed to files Selom created (Drive = drive.file, ` +
        `Dropbox = App Folder), so there is nothing to discover — a reference must be supplied.`,
    );

    const { page } = editor;
    await editor.viewport(1280, 800);
    await openDataStage(page, editor.projectId);

    await page.getByRole("button", { name: /Import from cloud/i }).click();
    const dialog = page.getByRole("dialog", { name: "Import from cloud" });
    await expect(dialog).toBeVisible();
    await page.waitForTimeout(1200); // providers + connections

    // The provider's row must show a CONNECTED account before its reference box exists — if the
    // broker were down this is where it stops, with a message rather than a dead input.
    const row = dialog.locator("li").filter({ hasText: p.label });
    await expect(row, `no ${p.label} row in the cloud menu`).toHaveCount(1);
    const refBox = row.locator("input");
    await expect(
      refBox,
      `${p.label} shows no reference input — its account is not connected, so the import ` +
        `cannot be driven (check deploy/nango/preflight.sh)`,
    ).toHaveCount(1);

    await refBox.fill(p.ref);
    await row.getByRole("button").last().click();

    // The import streams provider → store → parse, so give it real time.
    await expect(dialog).toBeHidden({ timeout: 180_000 });

    // The dataset must carry visible provenance naming THIS provider — `datasets.source` crossing
    // the boundary through `fromApiDatasetSource` and rendering as the row's SourceChip.
    const chip = page.locator(`[title*="Imported from ${p.label}"]`).first();
    await expect(
      chip,
      `the imported dataset shows no "${p.label}" source chip — provenance did not survive the ` +
        `API → FE mapping (lib/projects/sync.ts::fromApiDatasetSource)`,
    ).toBeVisible({ timeout: 30_000 });

    const title = await chip.getAttribute("title");
    console.log(`\n[V-2 ${p.label}] imported, source chip: ${title}\n`);
    await page.screenshot({
      path: `test-results/browser-verify/v2-cloud-${p.id}-1280x800.png`,
    });

    expect(title, "the chip must name the reference it came from").toContain(p.ref);
    expect(editor.pageErrors, `page errors during the ${p.label} import:\n${editor.pageErrors.join("\n")}`).toEqual([]);
  });
}

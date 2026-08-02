import { expect, test } from "./fixtures";

import { BE_ORIGIN } from "../../scripts/browser-verify/paths.mjs";
import { brokerConfigured, cloudAccount, pngInfo, type CloudFile } from "./cloud-account";

/**
 * A1 — the cloud-export round trip, for real.
 *
 * `E-1`/`E-2`/`E-3` shipped green with every test a mock, and a mock proves the wire, not the
 * product ([[selom-mock-is-wire-only-verify-real]]). This is the spec that makes "a figure can be
 * saved to Drive" a fact instead of a claim, and it is deliberately strict about what counts:
 *
 *   1. drive the REAL affordance — the editor's Export menu, the button a user actually clicks;
 *   2. find the file in the REAL account (list before, diff after — never trust a name);
 *   3. **download it and check the bytes are a PNG of the right size.** A 200 is not proof. Track E
 *      predicted two ways a real call could 200 while writing nothing usable, and one was real: on
 *      Drive's 308, the client re-POSTed the 17-byte *metadata* in a redirect loop and the figure's
 *      bytes never left the box (fixed in `cloud/connectors/google.py`, guarded in
 *      `tests/test_cloud_export.py::test_google_session_uri_on_a_308_is_read_not_followed`);
 *   4. **delete it.** These are the owner's real accounts and this runs on every sweep.
 *
 * SKIPS LOUDLY when the broker is unconfigured or the provider has no connected account — the file
 * cannot be planted for it, so a quiet pass would be a lie. `deploy/nango/preflight.sh` is the
 * one-command check for both.
 */

/** The connected accounts, straight from the app's own API — never hardcoded ids. */
async function connections(): Promise<{ provider: string; connectionId: string }[]> {
  const r = await fetch(`${BE_ORIGIN}/cloud/connections`);
  if (!r.ok) return [];
  const body = (await r.json()) as { connections?: { provider: string; connection_id: string }[] };
  return (body.connections ?? []).map((c) => ({ provider: c.provider, connectionId: c.connection_id }));
}

for (const p of [
  { id: "google", label: "Google Drive" },
  { id: "dropbox", label: "Dropbox" },
]) {
  test(`A1 — save a real figure to ${p.label} through the Export menu`, async ({ editor }) => {
    test.skip(
      !brokerConfigured(),
      "SELOM_NANGO_BASE_URL / SELOM_NANGO_SECRET_KEY are unset in the repo-root .env — there is no " +
        "broker to mint a token from, so the file could not be read back or cleaned up.",
    );

    const conn = (await connections()).find((c) => c.provider === p.id);
    test.skip(
      !conn,
      `no connected ${p.label} account (GET /cloud/connections). Run deploy/nango/preflight.sh.`,
    );

    const { page } = editor;
    const account = cloudAccount(p.id, conn!.connectionId);

    // (1) What is in the account BEFORE. Diffing ids is the only honest way to identify the file:
    //     Dropbox `autorename` may hand back "figure (1).png", so matching on a name we chose would
    //     silently pass on a file from a previous run.
    const before = new Set((await account.list()).map((f) => f.id));

    await editor.viewport(1280, 800);
    await page.getByRole("button", { name: "Export" }).click();
    const dialog = page.getByRole("dialog", { name: "Export figure" });
    await expect(dialog).toBeVisible();
    await page.waitForTimeout(1200); // the menu fetches providers + connections on first open

    // (2) The affordance itself. Disabled means the app cannot see the connection the API just
    //     reported — a wiring break, and exactly the shape of the A20 hardcoded-disabled failure.
    const save = dialog.getByRole("button", { name: new RegExp(`Save to ${p.label}`, "i") });
    await expect(save, `no "Save to ${p.label}" button in the Export menu`).toHaveCount(1);
    await expect(
      save,
      `"Save to ${p.label}" is disabled although GET /cloud/connections reports a connected ` +
        `account — the menu is not seeing the connection`,
    ).toBeEnabled();

    await save.click();

    // The success line names the file that was written; the render + upload is a real round trip.
    const saved = dialog.getByText(new RegExp(`Saved .+ to ${p.label}`, "i"));
    await expect(
      saved,
      `the Export menu never confirmed the save to ${p.label} — check the menu's error line`,
    ).toBeVisible({ timeout: 180_000 });
    const message = (await saved.textContent())?.trim() ?? "";

    // (3) Read it back out of the real account — and delete it whatever the assertions do.
    let landed: CloudFile | undefined;
    try {
      const after = await account.list();
      const fresh = after.filter((f) => !before.has(f.id));
      expect(
        fresh.length,
        `the UI said "${message}" but the ${p.label} account gained ${fresh.length} files — a 200 ` +
          `from /export/cloud is not proof that a file landed`,
      ).toBe(1);
      landed = fresh[0];

      const bytes = await account.download(landed.id);
      const png = pngInfo(bytes);
      console.log(
        `\n[A1 ${p.label}] ${message}\n` +
          `  landed as: ${landed.name} (${landed.size} bytes)\n` +
          `  downloaded ${bytes.length} bytes -> ${png.valid ? `valid PNG ${png.width}x${png.height}` : "NOT A PNG"}\n`,
      );

      expect(
        png.valid,
        `the file in ${p.label} is not a PNG — the bytes that landed are not the figure ` +
          `(first bytes: ${[...bytes.slice(0, 8)].join(",")})`,
      ).toBe(true);
      expect(png.width, "a zero-width PNG means an empty render").toBeGreaterThan(0);
      expect(
        bytes.length,
        `only ${bytes.length} bytes reached ${p.label} — a truncated or metadata-only upload`,
      ).toBeGreaterThan(1024);
    } finally {
      if (landed) await account.remove(landed.id).catch(() => {});
    }

    expect(
      editor.pageErrors,
      `page errors during the ${p.label} export:\n${editor.pageErrors.join("\n")}`,
    ).toEqual([]);
  });
}

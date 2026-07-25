/**
 * Cloud-import provider types + the OFFLINE-DEV fallback list. Pure data — no React, no icons — so
 * it stays in the `lib/` layer; the menu component maps an id to a lucide icon.
 *
 * **This module is no longer a truth table.** The live menu comes from the server
 * (`fetchCloudProviders` → `GET /cloud/providers`, the frozen contract in `./contract.ts`). It used
 * to be a second, hand-maintained registry with a hardcoded `comingSoon: true`, which is exactly why
 * Google Drive and Dropbox stayed unreachable in the UI after both OAuth connections went live —
 * nothing ever told the client a provider had been enabled (review finding A20,
 * [[selom-shipped-not-reachable]]). `enabled` is the server's answer; do not reintroduce a
 * client-side `comingSoon`.
 *
 * What survives is a fallback for when the server cannot be reached AT ALL (offline dev, a dead
 * backend). It is deliberately CONSERVATIVE — every OAuth provider is `enabled: false` — and the
 * menu states out loud that it is degraded, so a client guess is never mistaken for the server's
 * verdict. A fallback may degrade structure; it may never fabricate the answer
 * ([[mock-fallback-never-fabricates-data]]).
 */

export type CloudProviderKind = "url" | "oauth";

export interface CloudProvider {
  /** Matches the backend registry id (sent as `provider` to the import endpoint). */
  id: string;
  label: string;
  kind: CloudProviderKind;
  /** Nango integration id the backend exchanges for a token (OAuth providers only). */
  providerConfigKey: string;
  /** The SERVER's verdict — `url` is always on, an OAuth provider only when its flag is set. */
  enabled: boolean;
}

/** Shown only when `GET /cloud/providers` could not be reached; the menu says so when it is used. */
export const FALLBACK_CLOUD_PROVIDERS: CloudProvider[] = [
  { id: "url", label: "URL / S3 link", kind: "url", providerConfigKey: "", enabled: true },
  { id: "google", label: "Google Drive", kind: "oauth", providerConfigKey: "google-drive", enabled: false },
  { id: "onedrive", label: "OneDrive", kind: "oauth", providerConfigKey: "onedrive", enabled: false },
  { id: "dropbox", label: "Dropbox", kind: "oauth", providerConfigKey: "dropbox", enabled: false },
];

/**
 * A display name for a provider id that arrives on a stamped `datasets.source` — used to say
 * "Imported from Google Drive" instead of "google" on a dataset that is already in hand.
 *
 * COSMETIC ONLY, and that is the whole distinction: what the contract makes server-owned is provider
 * *state* (`enabled`) and menu *order*, never a display string. An unknown id renders as itself
 * rather than being hidden or renamed — an honest "imported from `boxnet`" beats a dataset that
 * looks hand-dropped, which is the bug (B14/B16).
 */
export function providerLabel(id: string): string {
  return FALLBACK_CLOUD_PROVIDERS.find((p) => p.id === id)?.label ?? id;
}

/**
 * Cloud-import provider registry (FE mirror of the backend `cloud.registry`). Pure data — no React,
 * no icons — so it stays in the `lib/` layer; the menu component maps an id to a lucide icon.
 *
 * URL/S3 works today. Google Drive / OneDrive / Dropbox are scaffolded against Nango and stay
 * `comingSoon` until the owner adds their OAuth client IDs to Nango and the backend flag flips on.
 */

export type CloudProviderKind = "url" | "oauth";

export interface CloudProvider {
  /** Matches the backend registry id (sent as `provider` to the import endpoint). */
  id: string;
  label: string;
  kind: CloudProviderKind;
  /** Nango integration id the backend exchanges for a token (OAuth providers only). */
  providerConfigKey: string;
  /** OAuth providers render a Connect button that no-ops until this is false. */
  comingSoon: boolean;
}

export const CLOUD_PROVIDERS: CloudProvider[] = [
  { id: "url", label: "URL / S3 link", kind: "url", providerConfigKey: "", comingSoon: false },
  { id: "google", label: "Google Drive", kind: "oauth", providerConfigKey: "google-drive", comingSoon: true },
  { id: "onedrive", label: "OneDrive", kind: "oauth", providerConfigKey: "onedrive", comingSoon: true },
  { id: "dropbox", label: "Dropbox", kind: "oauth", providerConfigKey: "dropbox", comingSoon: true },
];

export const OAUTH_PROVIDERS: CloudProvider[] = CLOUD_PROVIDERS.filter((p) => p.kind === "oauth");

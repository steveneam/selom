/**
 * The FE half of the FROZEN `GET /cloud/providers` wire contract.
 *
 * Backend source of truth: `app/backend/cloud/contract.py`. The two are kept in lockstep by an
 * executable guard — `app/backend/tests/test_contract_cloud_providers.py` reads
 * {@link CLOUD_PROVIDER_WIRE_KEYS} out of THIS file and fails if either side drifts. So this is not
 * a comment describing the contract; it is one of the two declarations the guard compares.
 *
 * Why the contract exists (review finding A20): the FE used to keep its own provider table with a
 * hardcoded `comingSoon: true`, so Google Drive and Dropbox stayed unreachable in the UI even after
 * both OAuth connections went live — the client had no way to learn a provider was enabled. Provider
 * state is the server's answer now. Do not reintroduce a client-side `comingSoon`.
 *
 * Rules for consumers:
 * - Render the list in the order received. It is the server-owned menu order; do not re-sort.
 * - Derive the disabled affordance from `enabled`, never from a local table.
 * - Ignore unknown keys, so an additive backend field cannot break a deployed client.
 * - `provider_config_key` is a public Nango integration id (e.g. `google-drive`), not a secret.
 */

/**
 * The frozen per-provider wire keys, in wire order. Snake_case because this is the wire; map to
 * camelCase at the boundary like the rest of `lib/cloud` does.
 *
 * The guard test parses this array literally — keep it a flat list of string literals.
 */
export const CLOUD_PROVIDER_WIRE_KEYS = ["id", "label", "kind", "provider_config_key", "enabled"] as const;

/** The response envelope key. An object, not a bare array, so it can gain sibling metadata later. */
export const CLOUD_PROVIDERS_RESPONSE_KEY = "providers";

/** A provider exactly as it arrives on the wire. */
export interface CloudProviderWire {
  /** Registry id, sent back as `provider` to the import/export endpoints. */
  id: string;
  label: string;
  kind: "url" | "oauth";
  /** Nango integration id the backend exchanges for a token; `""` for the `url` provider. */
  provider_config_key: string;
  /** Server's verdict: `url` is always on; an OAuth provider is on only when its flag is set. */
  enabled: boolean;
}

/** The `GET /cloud/providers` response body. */
export interface CloudProvidersResponse {
  providers: CloudProviderWire[];
}

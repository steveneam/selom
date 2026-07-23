"use client";

/**
 * Thin wrapper over the Nango frontend SDK (`@nangohq/frontend`) — the OAuth-popup seam that lets a
 * user connect their Google Drive / OneDrive / Dropbox account. The SDK is **client-only** and
 * lazy-imported (never SSR'd, never in the initial bundle) since it opens a browser popup.
 *
 * In this foundation slice `CLOUD_CONNECT_ENABLED` is false: the Connect buttons render but no-op with
 * a "coming soon" state until the owner adds their OAuth client IDs to Nango. `connectProvider` is the
 * real seam that lights up then — it returns the `connectionId` the backend exchanges for a token via
 * Nango's Connections API.
 */

import type Nango from "@nangohq/frontend";

/** Flip on once the owner's client IDs live in Nango (and a Connect-session endpoint exists). */
export const CLOUD_CONNECT_ENABLED = false;

export interface NangoConnection {
  connectionId: string;
  providerConfigKey: string;
}

async function loadNango(host?: string): Promise<Nango> {
  // Lazy client-only import — keeps the popup SDK out of SSR and the first-load bundle.
  const mod = await import("@nangohq/frontend");
  const Ctor = mod.default;
  return new Ctor(host ? { host } : undefined);
}

/**
 * Open Nango's OAuth flow for `providerConfigKey` and resolve the connection once authorized. Throws
 * while the feature is disabled. `host` targets the self-hosted Nango's public URL (omit → SDK default).
 */
export async function connectProvider(
  providerConfigKey: string,
  connectionId: string,
  host?: string,
): Promise<NangoConnection> {
  if (!CLOUD_CONNECT_ENABLED) {
    throw new Error("Cloud account connection isn't enabled yet — coming soon.");
  }
  const nango = await loadNango(host);
  await nango.auth(providerConfigKey, connectionId);
  return { connectionId, providerConfigKey };
}

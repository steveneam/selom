"use client";

/**
 * Cloud provider/import/export endpoint client.
 *
 * READS: `fetchCloudProviders` (the frozen `GET /cloud/providers` contract — the menu the server
 * owns) and `fetchCloudConnections` (which accounts are actually connected). Together they replace
 * the FE's old hand-maintained provider table; see `./providers.ts` for why that fork existed.
 *
 * Import streams a provider file into Selom's EXISTING
 * intake→confirm→parse pipeline server-side (`POST /uploads/intake/remote`) and returns the ready,
 * server-authoritative {@link Dataset} — the same shape `uploadDataset` returns, so the caller adds it
 * via `projectStore.addUploadedDataset` and it reconciles across reload exactly like a dropped file.
 *
 * Unlike `uploadDataset` (which fails soft to `null`), `importFromCloud` THROWS the {@link ApiError}
 * so a pasted-URL failure (bad link, blocked host, too large) surfaces a real message to the user; the
 * menu catches it. Export (`POST /export/cloud`) is scaffolded (dataset → S3 destination).
 */

import { api } from "@/lib/api/client";
import { fromApiDataset } from "@/lib/projects/sync";
import type { Dataset } from "@/lib/projects/types";
import type { CloudProvidersResponse, CloudProviderWire } from "./contract";
import type { CloudProvider, CloudProviderKind } from "./providers";

/**
 * Map ONE provider off the frozen wire (`./contract.ts`) into the FE shape: snake → camel at the
 * boundary, and **unknown keys are ignored** so an additive backend field cannot break a deployed
 * client. Order is not touched anywhere in this module — the list IS the server-owned menu order.
 */
function fromWireProvider(w: CloudProviderWire): CloudProvider {
  return {
    id: w.id,
    label: w.label,
    kind: w.kind as CloudProviderKind,
    providerConfigKey: w.provider_config_key,
    enabled: Boolean(w.enabled),
  };
}

/**
 * The provider menu — `GET /cloud/providers`, the one frozen cross-lane contract.
 *
 * THROWS on failure rather than falling back here, so the caller decides what a dead server means
 * for its UI (the menu renders the conservative offline list AND says it is degraded). A silent
 * fallback inside the client is how a client-side guess gets mistaken for the server's answer —
 * the A20 failure this endpoint exists to end.
 */
export async function fetchCloudProviders(): Promise<CloudProvider[]> {
  const body = await api.get<CloudProvidersResponse>("/cloud/providers");
  return (body?.providers ?? []).map(fromWireProvider);
}

/** One connected provider account (`GET /cloud/connections`). Names a grant, never carries one. */
export interface CloudConnection {
  /** Registry provider id — `google` | `dropbox` | … (NOT the Nango `provider_config_key`). */
  provider: string;
  /** The Nango connection id the backend exchanges for a live token at import time. */
  connectionId: string;
  /** Human label for the account — "Steven (a@b.com)", so the operator knows which one runs. */
  label: string;
  connectedAt?: string;
}

interface CloudConnectionWire {
  provider: string;
  connection_id: string;
  label: string;
  connected_at?: string | null;
}

/**
 * Which provider accounts are actually connected. `enabled` (above) says the server will accept a
 * provider; this says an account is on the other end of it — an enabled provider with no connection
 * must render an honest empty state, not an import form that cannot succeed.
 *
 * THROWS (like `fetchCloudProviders`): the caller degrades only the account section, so the URL/S3
 * import — which needs no broker at all — keeps working when Nango is down.
 */
export async function fetchCloudConnections(): Promise<CloudConnection[]> {
  const body = await api.get<{ connections: CloudConnectionWire[] }>("/cloud/connections");
  return (body?.connections ?? []).map((c) => ({
    provider: c.provider,
    connectionId: c.connection_id,
    label: c.label,
    connectedAt: c.connected_at ?? undefined,
  }));
}

export interface RemoteImportInput {
  /** A backend provider id: "url" | "google" | "onedrive" | "dropbox". */
  provider: string;
  /** A URL / s3:// URI (url provider), or a provider file id/path (OAuth providers). */
  ref: string;
  /** Nango connection id (OAuth providers only). */
  connectionId?: string;
  /** Optional display name; the backend derives one from a URL when omitted. */
  filename?: string;
}

export async function importFromCloud(projectId: string, input: RemoteImportInput): Promise<Dataset> {
  const row = await api.post<Record<string, unknown>>("/uploads/intake/remote", {
    project_id: projectId,
    provider: input.provider,
    ref: input.ref,
    connection_id: input.connectionId,
    filename: input.filename,
  });
  return fromApiDataset(row);
}

export interface CloudExportInput {
  provider: string;
  /**
   * s3://bucket/key (url provider), a Drive folder id, or a Dropbox folder path.
   * Empty means the provider's default root — My Drive, or the Dropbox App Folder.
   *
   * There is deliberately no folder PICKER in the UI: Google's `drive.file` scope lets Selom see
   * only files it created, so it cannot enumerate the user's folders to offer a choice
   * (docs/cloud-providers-contract/spec.md §Scope). Exports land in the root unless a caller
   * already knows an id.
   */
  dest?: string;
  datasetId: string;
  connectionId?: string;
}

/** Export a RENDERED FIGURE rather than a stored dataset (docs/cloud-export/spec.md D2). */
export interface CloudFigureExportInput {
  provider: string;
  dest?: string;
  figure: unknown;
  format: string;
  /** Journal size preset id; omit to export at the figure's own size. */
  preset?: string;
  filename?: string;
  connectionId?: string;
}

export interface CloudExportResult {
  ok: boolean;
  provider: string;
  dest: string;
  bytes: number;
  /** The name the file was actually written under (extension forced to match the format). */
  filename?: string;
}

export async function exportToCloud(input: CloudExportInput): Promise<CloudExportResult> {
  return api.post<CloudExportResult>("/export/cloud", {
    provider: input.provider,
    dest: input.dest ?? "",
    dataset_id: input.datasetId,
    connection_id: input.connectionId,
  });
}

export async function exportFigureToCloud(input: CloudFigureExportInput): Promise<CloudExportResult> {
  return api.post<CloudExportResult>("/export/cloud", {
    provider: input.provider,
    dest: input.dest ?? "",
    figure: input.figure,
    format: input.format,
    preset: input.preset,
    filename: input.filename,
    connection_id: input.connectionId,
  });
}

"use client";

/**
 * Cloud import/export endpoint client. Import streams a provider file into Selom's EXISTING
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
  /** s3://bucket/key (url provider) or a provider folder id (OAuth providers). */
  dest: string;
  datasetId: string;
  connectionId?: string;
}

export interface CloudExportResult {
  ok: boolean;
  provider: string;
  dest: string;
  bytes: number;
}

export async function exportToCloud(input: CloudExportInput): Promise<CloudExportResult> {
  return api.post<CloudExportResult>("/export/cloud", {
    provider: input.provider,
    dest: input.dest,
    dataset_id: input.datasetId,
    connection_id: input.connectionId,
  });
}

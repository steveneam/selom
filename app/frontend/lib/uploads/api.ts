"use client";

import { api, ApiError } from "@/lib/api/client";
import { fromApiDataset } from "@/lib/projects/sync";
import type { Dataset } from "@/lib/projects/types";

/**
 * The own-data upload handshake (WS2.1 / 7c-sub-spec §5) — puts a dropped file's BYTES in the object
 * store so a skill can run from its `dataset_id` with no multipart re-upload, and so the dataset (and
 * any figure it produces) survives reload independent of this session.
 *
 * The real four-step flow the backend built (`routers/library.py`):
 *   1. `POST /uploads/intake`  → reserve a `pending_upload` dataset row + a presigned upload target.
 *   2. PUT/POST the bytes to that target (dev = an in-app `/uploads/local/{key}` route; S3 = a
 *      presigned POST at step 8 / WS6).
 *   3. `POST /uploads/{id}/confirm` → flip the row to `ready` + stamp the real size.
 *   4. `POST /uploads/{id}/parse`   → server-side ingest → parsed-matrix pointer + the genuine sha256.
 *
 * FAIL-SOFT: any required step throwing returns `null`, so the caller degrades to the metadata-only
 * dataset + a this-session multipart run — the proven path is never broken. `parse` is BEST-EFFORT:
 * an unparseable file (e.g. a DE-results CSV the ingester rejects) still has its RAW bytes stored, and
 * run-from-dataset_id falls back to them, so a failed parse still yields a runnable uploaded dataset.
 */

/** The presigned target the intake step returns (S3 `{url, fields}` shape; the local backend mirrors
 *  it with an in-app route so this client is backend-agnostic — spec §object-store seam). */
interface PresignedUpload {
  url: string;
  fields: Record<string, string | number>;
}

/** PUT/POST the raw bytes to the presigned target. Discriminated by URL scheme: an absolute
 *  `https://…` is an S3 presigned POST (WS6 — the `fields` must precede the `file`); a root-relative
 *  `/uploads/local/…` is the dev LocalObjectStore route, a raw PUT of the body behind the `/api` proxy.
 *  The presigned URL IS the credential (T1), so no auth header is attached. Throws on a non-2xx. */
async function putToPresigned(upload: PresignedUpload, file: File): Promise<void> {
  const { url, fields } = upload;
  if (/^https?:\/\//i.test(url)) {
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.append(k, String(v));
    form.append("file", file);
    const res = await fetch(url, { method: "POST", body: form });
    if (!res.ok) throw new Error(`upload POST failed (${res.status})`);
    return;
  }
  const res = await fetch(`/api${url}`, { method: "PUT", body: file });
  if (!res.ok) throw new Error(`upload PUT failed (${res.status})`);
}

/**
 * Upload a dropped file's bytes and return the server dataset (WS2.1). The returned {@link Dataset}
 * carries the server-authoritative id (7c §2.2) + `uploaded: true`, so runs use `runSkillByDataset`
 * (no re-upload) and it reconciles cleanly across reload. `null` on any failure (fail-soft).
 */
export async function uploadDataset(projectId: string, file: File): Promise<Dataset | null> {
  try {
    const intake = await api.post<{ dataset: Record<string, unknown>; upload: PresignedUpload }>(
      "/uploads/intake",
      // Omit `content_sha256` at intake — the parse recomputes the truth (7c §5). `size_bytes` caps
      // the PUT and must be > 0; a 0-byte file 400s here → null → the caller falls back.
      { project_id: projectId, filename: file.name, size_bytes: file.size },
    );
    const datasetId = String(intake.dataset.id);
    await putToPresigned(intake.upload, file);
    const confirmed = await api.post<Record<string, unknown>>(
      `/uploads/${encodeURIComponent(datasetId)}/confirm`,
      {},
    );
    let row = confirmed;
    try {
      row = await api.post<Record<string, unknown>>(`/uploads/${encodeURIComponent(datasetId)}/parse`);
    } catch {
      // Unparseable — keep the confirmed (ready) row; run-from-dataset_id uses the raw bytes.
    }
    return fromApiDataset(row);
  } catch (e) {
    void (e instanceof ApiError); // fail-soft: degrade to the metadata-only + multipart path
    return null;
  }
}

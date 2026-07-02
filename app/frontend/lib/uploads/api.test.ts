import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the own-data byte-upload handshake (WS2.1) — `uploadDataset` drives the real
 * intake → PUT → confirm → parse flow the backend built, returns a server-authoritative Dataset with
 * `uploaded:true`, and FAILS SOFT to `null` at every step so the caller can degrade to the
 * metadata-only + multipart path. Env is "node" (provides `fetch`/`File`); `@/lib/api/client` is
 * mocked so the JSON steps resolve without a backend, and `fetch` is stubbed for the raw byte PUT.
 */

vi.mock("@/lib/api/client", () => {
  const api = { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() };
  return { api, setAuthHeader: vi.fn(), ApiError: class ApiError extends Error {} };
});

import { api } from "@/lib/api/client";
import { uploadDataset } from "./api";

const post = api.post as ReturnType<typeof vi.fn>;

function file(name = "counts.csv", size = 1234): File {
  return new File([new Uint8Array(size)], name, { type: "text/csv" });
}

const INTAKE = {
  dataset: { id: "srv_ds_1", project_id: "p1", filename: "counts.csv", status: "pending_upload" },
  upload: { url: "/uploads/local/uploads/u1/p1/srv_ds_1/counts.csv", fields: { key: "k", max_bytes: 9_000_000 } },
};
const CONFIRMED = {
  id: "srv_ds_1", project_id: "p1", filename: "counts.csv", status: "ready",
  upload_s3_key: "uploads/u1/p1/srv_ds_1/counts.csv", current_sha256: null,
};
const PARSED = { ...CONFIRMED, parquet_s3_key: "data/abc.csv", current_sha256: "abc123" };

afterEach(() => {
  vi.unstubAllGlobals();
  post.mockReset();
});

describe("uploadDataset — the WS2.1 byte-upload handshake", () => {
  it("intake → PUT → confirm → parse → returns an uploaded Dataset (server id + real sha)", async () => {
    post
      .mockResolvedValueOnce(INTAKE)     // /uploads/intake
      .mockResolvedValueOnce(CONFIRMED)  // /uploads/{id}/confirm
      .mockResolvedValueOnce(PARSED);    // /uploads/{id}/parse
    const fetchSpy = vi.fn(async () => ({ ok: true, status: 200 }) as Response);
    vi.stubGlobal("fetch", fetchSpy);

    const d = await uploadDataset("p1", file());

    expect(d).not.toBeNull();
    expect(d!.id).toBe("srv_ds_1");        // server-authoritative id (7c §2.2)
    expect(d!.uploaded).toBe(true);        // bytes in the store → runs use run-from-dataset_id
    expect(d!.currentSha256).toBe("abc123");
    // intake declares the browser file size (caps the PUT); omits content_sha256 (parse recomputes)
    expect(post).toHaveBeenNthCalledWith(1, "/uploads/intake", {
      project_id: "p1", filename: "counts.csv", size_bytes: 1234,
    });
    // the raw bytes PUT to the proxied local route (dev LocalObjectStore stand-in)
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/uploads/local/uploads/u1/p1/srv_ds_1/counts.csv",
      expect.objectContaining({ method: "PUT" }),
    );
    // confirm + parse target the server id
    expect(post).toHaveBeenNthCalledWith(2, "/uploads/srv_ds_1/confirm", {});
    expect(post).toHaveBeenNthCalledWith(3, "/uploads/srv_ds_1/parse");
  });

  it("parse failing still yields a runnable uploaded dataset off the confirmed (raw-bytes) row", async () => {
    post
      .mockResolvedValueOnce(INTAKE)
      .mockResolvedValueOnce(CONFIRMED)
      .mockRejectedValueOnce(new Error("unparseable")); // parse 400 (best-effort)
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200 }) as Response));

    const d = await uploadDataset("p1", file());

    expect(d).not.toBeNull();
    expect(d!.uploaded).toBe(true); // upload_s3_key present → run-from-dataset_id uses the raw bytes
  });

  it("intake failing (e.g. 402 quota) → null (fail-soft to the metadata-only path)", async () => {
    post.mockRejectedValueOnce(new Error("quota_exceeded"));
    const d = await uploadDataset("p1", file());
    expect(d).toBeNull();
  });

  it("a failed byte PUT → null (the bytes never landed)", async () => {
    post.mockResolvedValueOnce(INTAKE);
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 500 }) as Response));
    const d = await uploadDataset("p1", file());
    expect(d).toBeNull();
  });
});

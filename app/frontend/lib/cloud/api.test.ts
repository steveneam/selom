import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the cloud import/export client. `@/lib/api/client` is mocked so the endpoint calls
 * resolve without a backend; `fromApiDataset` (real) maps the server row. `importFromCloud` returns
 * the ready, server-authoritative Dataset and THROWS on failure (so the menu shows the message).
 */

vi.mock("@/lib/api/client", () => {
  const api = { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() };
  return { api, setAuthHeader: vi.fn(), ApiError: class ApiError extends Error {} };
});

import { api } from "@/lib/api/client";
import { exportToCloud, importFromCloud } from "./api";

const post = api.post as ReturnType<typeof vi.fn>;

const READY = {
  id: "srv_ds_1",
  project_id: "p1",
  filename: "counts.csv",
  status: "ready",
  upload_s3_key: "uploads/A/p1/srv_ds_1/counts.csv",
  parquet_s3_key: "data/abc.csv",
  current_sha256: "abc123",
  source: { provider: "url", ref: "https://example.test/counts.csv" },
};

afterEach(() => post.mockReset());

describe("importFromCloud — the remote-intake client", () => {
  it("maps the ready dataset and posts the remote-intake body", async () => {
    post.mockResolvedValueOnce(READY);
    const d = await importFromCloud("p1", { provider: "url", ref: "https://example.test/counts.csv" });
    expect(d.id).toBe("srv_ds_1");
    expect(d.uploaded).toBe(true); // ready + a stored key → runs use run-from-dataset_id
    expect(d.currentSha256).toBe("abc123");
    expect(post).toHaveBeenCalledWith("/uploads/intake/remote", {
      project_id: "p1",
      provider: "url",
      ref: "https://example.test/counts.csv",
      connection_id: undefined,
      filename: undefined,
    });
  });

  it("throws the error so the menu can surface it (no silent fail-soft here)", async () => {
    post.mockRejectedValueOnce(new Error("host resolves to a non-public address"));
    await expect(
      importFromCloud("p1", { provider: "url", ref: "http://10.0.0.1/x" }),
    ).rejects.toThrow("non-public");
  });
});

describe("exportToCloud — the scaffold export client", () => {
  it("posts the export body", async () => {
    post.mockResolvedValueOnce({ ok: true, provider: "url", dest: "s3://b/k", bytes: 42 });
    const r = await exportToCloud({ provider: "url", dest: "s3://b/k", datasetId: "srv_ds_1" });
    expect(r.ok).toBe(true);
    expect(post).toHaveBeenCalledWith("/export/cloud", {
      provider: "url",
      dest: "s3://b/k",
      dataset_id: "srv_ds_1",
      connection_id: undefined,
    });
  });
});

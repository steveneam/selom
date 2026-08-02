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
import { CLOUD_PROVIDER_WIRE_KEYS } from "./contract";
import {
  exportFigureToCloud,
  exportToCloud,
  fetchCloudConnections,
  fetchCloudProviders,
  importFromCloud,
} from "./api";

const post = api.post as ReturnType<typeof vi.fn>;
const get = api.get as ReturnType<typeof vi.fn>;

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

afterEach(() => {
  post.mockReset();
  get.mockReset();
});

/** A providers body built from the FROZEN key list, so a renamed wire key breaks this fixture. */
const WIRE_PROVIDERS = [
  { id: "url", label: "URL / S3", kind: "url", provider_config_key: "", enabled: true },
  { id: "google", label: "Google Drive", kind: "oauth", provider_config_key: "google-drive", enabled: true },
  { id: "onedrive", label: "OneDrive", kind: "oauth", provider_config_key: "onedrive", enabled: false },
  { id: "dropbox", label: "Dropbox", kind: "oauth", provider_config_key: "dropbox", enabled: true },
];

describe("fetchCloudProviders — the FE half of the frozen contract", () => {
  it("reads the fixture through exactly the frozen wire keys", () => {
    // Guards the fixture itself: if the freeze gains/renames a key, this fails before the mapping
    // assertions below can pass against a stale shape.
    for (const p of WIRE_PROVIDERS) {
      expect(Object.keys(p)).toEqual([...CLOUD_PROVIDER_WIRE_KEYS]);
    }
  });

  it("maps snake_case → camelCase and takes `enabled` from the server", async () => {
    get.mockResolvedValueOnce({ providers: WIRE_PROVIDERS });
    const list = await fetchCloudProviders();
    expect(get).toHaveBeenCalledWith("/cloud/providers");
    const google = list.find((p) => p.id === "google")!;
    expect(google.providerConfigKey).toBe("google-drive");
    expect(google.enabled).toBe(true);
    expect(list.find((p) => p.id === "onedrive")!.enabled).toBe(false);
  });

  it("preserves the SERVER's menu order — the client must not re-sort", async () => {
    get.mockResolvedValueOnce({ providers: WIRE_PROVIDERS });
    expect((await fetchCloudProviders()).map((p) => p.id)).toEqual([
      "url",
      "google",
      "onedrive",
      "dropbox",
    ]);
  });

  it("ignores unknown keys, so an additive backend field can't break a deployed client", async () => {
    get.mockResolvedValueOnce({
      providers: [{ ...WIRE_PROVIDERS[1], beta: true, icon_url: "https://x/y.png" }],
    });
    const [p] = await fetchCloudProviders();
    expect(Object.keys(p).sort()).toEqual(
      ["enabled", "id", "kind", "label", "providerConfigKey"].sort(),
    );
  });

  it("THROWS rather than falling back — the caller decides what a dead server means", async () => {
    get.mockRejectedValueOnce(new Error("network error"));
    await expect(fetchCloudProviders()).rejects.toThrow("network");
  });
});

describe("fetchCloudConnections — which accounts are actually connected", () => {
  it("maps the wire rows and keys them by registry provider id", async () => {
    get.mockResolvedValueOnce({
      connections: [
        {
          provider: "google",
          connection_id: "c878e8db-ab37-40ed-9866-ba458d12a7df",
          label: "Steven (owner@example.test)",
          connected_at: "2026-07-25T05:39:09.594+00:00",
        },
      ],
    });
    const [c] = await fetchCloudConnections();
    expect(get).toHaveBeenCalledWith("/cloud/connections");
    expect(c.provider).toBe("google");
    expect(c.connectionId).toBe("c878e8db-ab37-40ed-9866-ba458d12a7df");
    expect(c.label).toBe("Steven (owner@example.test)");
  });

  it("an absent list is an empty list, never a fabricated connection", async () => {
    get.mockResolvedValueOnce({});
    expect(await fetchCloudConnections()).toEqual([]);
  });
});

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

describe("exportToCloud — the dataset export client", () => {
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

describe("exportFigureToCloud — the figure export client", () => {
  const FIGURE = { data: [{ type: "scatter", x: [1], y: [2] }], layout: {} };

  it("posts the figure, never a dataset_id", async () => {
    post.mockResolvedValueOnce({
      ok: true,
      provider: "google",
      dest: "",
      bytes: 1024,
      filename: "erg.png",
    });
    const r = await exportFigureToCloud({
      provider: "google",
      figure: FIGURE,
      format: "png",
      preset: "nature-single",
      filename: "erg",
      connectionId: "conn-1",
    });

    expect(r.filename).toBe("erg.png");
    const [path, body] = post.mock.calls.at(-1)!;
    expect(path).toBe("/export/cloud");
    // Sending both sources is a 400 on the server -- the figure client must never set dataset_id.
    expect(body).not.toHaveProperty("dataset_id");
    expect(body).toMatchObject({
      provider: "google",
      figure: FIGURE,
      format: "png",
      preset: "nature-single",
      filename: "erg",
      connection_id: "conn-1",
    });
  });

  it("defaults dest to the provider root rather than sending undefined", async () => {
    // `drive.file` means Selom cannot list folders to offer a picker, so an unset destination is
    // the normal case -- it must reach the server as "" (the root), not as undefined.
    post.mockResolvedValueOnce({ ok: true, provider: "dropbox", dest: "", bytes: 1 });
    await exportFigureToCloud({ provider: "dropbox", figure: FIGURE, format: "svg" });
    expect(post.mock.calls.at(-1)![1]).toMatchObject({ dest: "" });
  });
});

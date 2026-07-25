import { describe, expect, it } from "vitest";

import { fromApiDataset } from "./sync";

/**
 * `fromApiDataset` — the wire→FE dataset mapper.
 *
 * The regression under guard (findings B14 · B16): the mapper silently dropped the backend-stamped
 * `datasets.source`, so a file streamed in from Google Drive arrived indistinguishable from one
 * dragged off the desktop. The provenance existed in the database and died at the boundary, which
 * made cloud import look like a feature nobody had used.
 */

const READY_IMPORT = {
  id: "srv_ds_1",
  project_id: "p1",
  filename: "counts.csv",
  status: "ready",
  upload_s3_key: "uploads/A/p1/srv_ds_1/counts.csv",
  parquet_s3_key: "data/abc.csv",
  source: {
    provider: "google",
    ref: "1AbCdEfGhIjKlMnOpQrStUv",
    fetched_at: "2026-07-25T05:39:09.594+00:00",
  },
};

describe("fromApiDataset — cloud-import provenance survives the boundary", () => {
  it("carries the server-stamped source through, snake → camel", () => {
    const d = fromApiDataset(READY_IMPORT);
    expect(d.source).toEqual({
      provider: "google",
      ref: "1AbCdEfGhIjKlMnOpQrStUv",
      fetchedAt: "2026-07-25T05:39:09.594+00:00",
    });
  });

  it("a locally dropped dataset has no source — absence is the signal, not an empty object", () => {
    const { source: _omitted, ...local } = READY_IMPORT;
    expect(fromApiDataset(local).source).toBeUndefined();
  });

  it("discards a source with no provider rather than rendering a half-empty chip", () => {
    // `datasets.source` is a free-form JSON column, so the mapper cannot assume its shape.
    for (const source of [null, {}, { ref: "x" }, [], "google", { provider: "  " }]) {
      expect(fromApiDataset({ ...READY_IMPORT, source }).source).toBeUndefined();
    }
  });

  it("tolerates a source missing its optional fields", () => {
    const d = fromApiDataset({ ...READY_IMPORT, source: { provider: "dropbox" } });
    expect(d.source).toEqual({ provider: "dropbox", ref: "", fetchedAt: undefined });
  });
});

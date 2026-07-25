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

/**
 * `datasets.qc` carries TWO different shapes, and the mapper used to `as`-cast whichever arrived
 * into the FE's `QcReport`.
 *
 * Captured live from a real upload of a real EYG_28 DE export against a real backend (2026-07-25):
 * `POST /uploads/{id}/parse` returns `qc = {ran, ok, flags, stats, blocked}` — the ENGINE's report,
 * with no `nObs`/`nVar`. Every consumer then calls `qc.nObs.toLocaleString()` (`workrail.tsx`
 * DatasetRow, `data-panel.tsx`), so the cast turned Selom's primary flow — drop a file — into a
 * *Cannot read properties of undefined* crash that took the whole app to the error overlay.
 *
 * It survived every gate because `dev:mock` skips `uploadDataset` (`if (!mockMode)`), so no mock
 * run ever produced the engine shape. That is the standing lesson, now executable
 * [[verify-on-real-data-not-mock]].
 */
describe("fromApiDataset — a foreign qc shape must not reach the formatters", () => {
  /** Verbatim from the live `POST /uploads/{dataset_id}/parse` response. */
  const ENGINE_QC = { ran: true, ok: true, flags: [], stats: {}, blocked: false };

  it("drops the engine's QcReport — it has no nObs/nVar to format", () => {
    const d = fromApiDataset({ ...READY_IMPORT, qc: ENGINE_QC });
    expect(d.qc).toBeUndefined();
  });

  it("the dropped shape would otherwise crash the exact call the UI makes", () => {
    const d = fromApiDataset({ ...READY_IMPORT, qc: ENGINE_QC });
    // `workrail.tsx` DatasetRow / `data-panel.tsx` both do `qc.nObs.toLocaleString()` behind a
    // truthiness check on `qc` alone. Undefined keeps them on the `: dataset.modality` branch.
    expect(() => (d.qc ? d.qc.nObs.toLocaleString() : "modality")).not.toThrow();
  });

  it("keeps the FE's own QcReport, which round-trips through POST /datasets", () => {
    const clientQc = { detectedModality: "bulk RNA-seq", nObs: 16760, nVar: 9 };
    const d = fromApiDataset({ ...READY_IMPORT, qc: clientQc });
    expect(d.qc?.nObs).toBe(16760);
    expect(d.qc?.nVar).toBe(9);
  });

  it("discards anything else the free-form column may hold", () => {
    for (const qc of [null, {}, [], "qc", 7, { nObs: 10 }, { nObs: "10", nVar: "9" }]) {
      expect(fromApiDataset({ ...READY_IMPORT, qc }).qc).toBeUndefined();
    }
  });
});

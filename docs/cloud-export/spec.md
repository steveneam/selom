# Spec — export to cloud storage (Track E)

Status: **approved to build** (owner-requested 2026-08-02, scoped **export-only**, queued for
autonomous sessions). Board rows: `E-1` · `E-2` · `E-3` in `docs/next-session-plan/plan.md`.

## What

Let a user send a figure (and a dataset) from Selom **out** to their own Google Drive or Dropbox,
instead of the file only ever reaching them as a browser download.

## Why now

The owner asked whether figures could be saved to Drive "instead of GitHub". They cannot:

- `POST /figures/export` renders PNG/SVG/PDF and returns them as a **browser download**
  (`routers/figures.py`, UI `components/figure/export-menu.tsx`). Good, but local-only.
- `POST /export/cloud` exists but is a scaffold: it takes a **`dataset_id`**, and every OAuth
  connector's `push_from_store` raises `"<provider> export is not available yet"`
  (`cloud/connectors/google.py:29`, `dropbox.py:34`, `onedrive.py:29`). Only the `s3://`
  destination works, and **no UI calls it** — the only references are `lib/cloud/api.ts` and tests.

Everything around the hole already exists and is tested: the endpoint, the provider registry, the
Nango token exchange, the SSRF guards, tenant key resolution, and the FE client wrapper.

## Scope decision — why export before import

`docs/cloud-providers-contract/spec.md` §Scope records an **open founder decision**: Google is
`drive.file`-scoped and Dropbox is an App Folder, so Selom can only read files **it created**. That
cripples import.

**Export is unaffected.** Writing a new file is exactly what `drive.file` permits, and Selom can
always see what it created afterwards. So export needs no scope change and no founder decision —
which is what makes it a coherent thing to build while the owner is away. The §Scope decision stays
open and still blocks import.

## Decisions

### D1 — the connector seam gains `push_path`, and `push_from_store` becomes a wrapper

`push_from_store(key, dest, token)` reads from the **object store**. A rendered figure has no stored
object — it is produced on demand by `export.render`. Three options were considered:

| Option | Verdict |
|---|---|
| Write the render to a scratch object-store key, reuse `push_from_store`, delete after | **Rejected.** Invents a temp-object lifecycle whose cleanup is exactly the failure mode [[cache-owned-temp-lifecycle]] warns about (a naive `finally` leaks on crash). |
| Add a `push_bytes(data, …)` sibling | **Rejected.** Buffers the whole payload in the heap — the streaming design exists precisely so a GB dataset never does that. |
| **Add `push_path(local_path, dest, token, filename)`; `push_from_store` = download + `push_path`** | **Chosen.** |

`push_path` is the honest primitive: every provider upload is "read this file, write it there".
`push_from_store` keeps its signature and becomes a shared helper (download to temp → `push_path`),
so the dataset path is unchanged and the figure path calls `push_path` on the render it already has
in a temp file. One new method on the Protocol, no behaviour change for existing callers.

### D2 — a figure exports by **render-then-push**, not by persisting an artifact

`POST /export/cloud` gains an optional `figure` (plus `format`/`preset`/`filename`), **mutually
exclusive** with `dataset_id`. The handler renders via the same `export.render` the download path
uses, into a temp file, then calls `push_path`.

No new persistence. Rejected the alternative (persist the render as an artifact, export by id)
because it would ship a storage lifecycle nobody has asked for yet.

**Watch `R-04`.** That row wants artifacts fetchable by id, and it and this share a need for "a
rendered thing addressable later". If `R-04` lands first, this endpoint can switch its source from
an inline figure to an artifact id **without touching the connector seam** — that is the point of
D1. Whichever lands first, the other must not duplicate it.

### D3 — `dest` semantics per provider

`dest` is already free-form per provider (the URL connector reads it as an `s3://` URI). Extend that
table rather than adding fields:

| Provider | `dest` | Empty `dest` |
|---|---|---|
| `url` | `s3://bucket/key` or `s3://bucket/prefix/` | error (unchanged) |
| `google` | a Drive **folder id** | `root` — the user's My Drive |
| `dropbox` | a **folder path**, `/Reports` | `""` — the App Folder root |

A trailing-slash / folder `dest` keeps the source basename, matching the URL connector's existing
rule. Filename always carries the correct extension for the format.

### D4 — upload size: correct for figures, honest about datasets

Figures are small (the ERG grid is ~400 KB); datasets are not.

- **Dropbox** — simple upload is capped at 150 MB by the API. Implement the **upload-session**
  (chunked) path above that threshold so a large dataset still works.
- **Google Drive** — implement the **resumable** upload; it is the documented path for anything
  non-trivial and streams from the file handle rather than buffering.

Neither buffers the payload in memory. `SELOM_CLOUD_IMPORT_MAX_BYTES` governs import; export is
bounded by what is already in the store, so no new cap is introduced.

### D5 — flags and reachability

The OAuth providers stay behind their existing flags (`SELOM_CLOUD_GOOGLE` /
`SELOM_CLOUD_DROPBOX`); the registry already refuses a disabled provider before a connector is
reached, and `_not_configured` is the existing error path. **OneDrive stays scaffolded** — it is on
the DEFERRED list pending a machine that logs into Azure cleanly.

`E-3` wires the FE, which **deletes a reachability waiver**. Per the ratchet's rule, the waiver is
removed by the change that wires the surface up, never banked ahead — so `E-1`/`E-2` must not touch
`docs/reachability/backlog.md`.

## Requirements

- **R1** `push_path(local_path, dest, token, *, filename)` on the `CloudConnector` Protocol.
  Returns bytes written. Raises `CloudFetchError` on a provider error or a missing token.
- **R2** `push_from_store` for every connector = download to temp → `push_path`, preserving the
  current URL/S3 behaviour byte-for-byte.
- **R3** Google Drive `push_path` — resumable upload; `dest` is a folder id (`root` when empty);
  the created file is named `filename`.
- **R4** Dropbox `push_path` — simple upload under 150 MB, upload session above; `dest` is a folder
  path; `mode=add` with `autorename` so an export never silently overwrites a user's file.
- **R5** `POST /export/cloud` accepts **either** `dataset_id` **or** `figure` (+ `format`,
  `preset`, `filename`), and rejects a request carrying both or neither with a 400.
- **R6** No payload is buffered whole in memory, in either direction.
- **R7** An export never overwrites an existing user file without being asked to (`autorename` on
  Dropbox; Drive create, not update).
- **R8** Tests use `httpx.MockTransport`, matching the import-side tests. A mock proves the wire,
  not the product ([[selom-mock-is-wire-only-verify-real]]) — so `E-3` owes a **real-browser round
  trip against the live broker**, and it is not done until that passes.

## Verify

- `scripts/verify.sh` (the gate of record — raw, exit-code gated, never piped).
- New backend tests alongside `app/backend/tests/test_cloud_*.py`.
- **`E-3` only:** a `scripts/browser-verify.sh` spec driving editor → export menu → Drive against
  the live broker, then deleting the file it created (as the `V-2` round trip did).

## Out of scope

- OneDrive (DEFERRED).
- Import scope / Google Picker — blocked on the §Scope founder decision.
- Scheduled or automatic export, and any write back to a file Selom did not create.

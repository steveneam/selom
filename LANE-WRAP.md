# LANE 2 WRAP — Cloud reachability across the FE↔BE seam

Branch `agent/cloud-reachability/l2` · worktree `/home/deploy/work/selom-lane2` · 2026-07-25 16:20 (+10:00)
**7 commits, not merged / not pushed / not rebased.** Merge-train position: last (after Lane 1, Lane 3).

## Status per ID

| ID | Status | One line |
|---|---|---|
| L2-01 | **DONE** | `GET /cloud/providers` through `contract.providers_payload`; FE consumes it; three client-side truth tables deleted. |
| L2-02 | **DONE — the row named the wrong file** | The backend never read `app/backend/.env`. See "The L2-02 finding" below — **this one needs an action from you.** |
| L2-03 | **DONE** | `datasets.source` mapped in `fromApiDataset` and rendered in two places. |
| L2-04 | **DONE** | Both fabricated `File` stand-ins deleted; cloud import is by reference. |
| L2-05 | **DONE** | Multi-file drop routes a per-sample 10x/`.h5ad` deposit to `/data/assemble-scrna`. |
| L2-06 | **DONE** | Import button says "Importing…" + `aria-busy`; ratcheted. |
| L2-07 | **BLOCKED (swordfish, not mine)** | Unchanged. Its consequence is now visible in the UI — see "What L2-07 still costs". |

Both reachability waivers deleted (`/cloud/providers`, `/data/assemble-scrna`). The guard fails on a
stale waiver, so that is enforced, not remembered. Backlog: **17 unreachable paths → 15.**

## Verify ledger

`export SELOM_DATASETS_DIR=/home/deploy/migration/selom-migration-staging/selom-data; export SELOM_PYTEST_WORKERS=2; ./scripts/verify.sh --fast`

```
PASS hygiene · PASS be-lint · PASS be-test · PASS fe-lint · PASS fe-types · PASS fe-test
SKIP fe-build (--fast; Turbopack cannot run in a worktree — merge-train gate on your checkout)
RESULT: PASS
```
Run raw, never piped. 1330 backend tests, 565 FE tests. Also `bash deploy/nango/preflight.sh` → **PASSED**
(exit 0), both connections refresh.

### End-to-end gate — MET on real data, real OAuth, real bytes

Ran against a live backend (`uvicorn` on :8021, SQLite + local object store) and the **live** Nango at
`nango.swordfish.cfd`. Both accounts were **empty**, so a real omics file from the corpus was staged in
each, imported back through Selom, then **deleted from both accounts** (verified empty again afterwards).

| Provider | Real file | Result |
|---|---|---|
| Google Drive | `jev/proteome_de.csv` (249,498 B) | `status=ready`, parsed **2180 × 7**, `source={provider: google, ref: 1A36MaS…, fetched_at: …}` |
| Dropbox | `rpgr/rpgr_irpe_rawcounts.csv` (1,242,426 B) | `status=ready`, parsed **36,601 × 7**, `source={provider: dropbox, ref: /selom-e2e-…, fetched_at: …}` |

**sha256 of the stored object == sha256 of the local original, for both.** Byte-identical round trip
through Nango → provider API → SSRF-guarded stream → object store.

`GET /datasets` serves both `source` objects in exactly the `{provider, ref, fetched_at}` shape
`lib/projects/sync.test.ts` asserts against — so the mapper is covered on the live payload's shape, not
an invented one.

`POST /data/assemble-scrna` (L2-05) also verified against the **real Hani GSE201356 deposit** — 2 GSM
samples, 6 triplet members, 150 MB in → **48,923 cells × 64,591 genes**, `obs_columns [sample_id, sample]`,
per-sample counts, artifact id. Filenames match `looksLikeScrnaDeposit`'s unit fixtures exactly.

Everything I started is stopped: uvicorn killed, port 8021 closed, scratch object store deleted. (A
`next dev -p 3111` is running — it is **thalon's**, from Jul 19, not mine.)

---

## ⚠️ The L2-02 finding — one action needed on your checkout

**The row's premise was wrong and, followed literally, would have flipped it DONE with the gate shut.**

`app/backend/config.py` sets pydantic-settings `env_file = <repo root>/.env`. It **never loads
`app/backend/.env`** — where every cloud credential had been staged. So:

- `settings.nango_secret_key` was empty and `settings.nango_base_url` silently fell back to its default,
  `http://localhost:3003` — the **dead** dev instance;
- `deploy/nango/preflight.sh` read that same unused file, so it passed all five checks against the live
  broker **while the server was pointed at a corpse**. A green preflight and a misconfigured server.

Fixed here: `SELOM_NANGO_BASE_URL` / `SELOM_NANGO_SECRET_KEY` / `SELOM_CLOUD_GOOGLE` /
`SELOM_CLOUD_DROPBOX` moved into the repo-root `.env`; `preflight.sh` points at the same file;
`.env.example` + `deploy/nango/README.md` document it; **`app/backend/tests/test_cloud_env_home.py`
binds the two homes together and is verified to FAIL when they diverge.**

**`.env` is gitignored, so that half did not travel.** On your checkout, append to
`/home/deploy/work/selom/.env` and remove the same four lines from `app/backend/.env`:

```
SELOM_NANGO_BASE_URL=https://nango.swordfish.cfd
SELOM_NANGO_SECRET_KEY=<the key currently in app/backend/.env line 21>
SELOM_CLOUD_GOOGLE=true
SELOM_CLOUD_DROPBOX=true
```

Until you do, `test_cloud_env_home.py` still passes (it checks the *paths* agree, not the contents), but
`GET /cloud/providers` will report `enabled: false` and the browser check below will show "Not enabled".
`bash deploy/nango/preflight.sh` is the one-command tell: exit 0 means done.

Leave `app/backend/.env`'s `GOOGLE_*` / `DROPBOX_*` / `MS_*` alone — those are for pasting into Nango's
dashboard and are read by nothing in this repo.

---

## Browser check for you — I could not run one

Turbopack fatals on the out-of-root `node_modules` symlink, so no dev server here. Repro:

1. `.env` per above, then `uv run uvicorn main:app --reload` in `app/backend` (port 8000) and
   `npm run dev` in `app/frontend` (port 3000). **Not `dev:mock`** — the mock reports `enabled: false`
   and an empty connections list on purpose, so it exercises the wire, never the live state.
2. Open a project → **Data** tab → **"Import from cloud ▾"**.
   - **Expect:** "Loading import options…" briefly, then URL/S3 on top; under "Your connected accounts",
     Google Drive and Dropbox each with a green **Connected** chip and `Steven (mactechdish@gmail.com)`;
     OneDrive with a grey **Not enabled** chip and no form.
   - **If Google/Dropbox show "Not enabled":** the `.env` action above hasn't been done.
   - **If they show "No account":** `GET /cloud/connections` failed — a warn strip below names why.
3. Put a file in Drive, copy its share link, take the `/d/<id>/` segment, paste as the Drive reference →
   **Import**. Button must read a spinner **plus "Importing…"** (that is L2-06). Dropbox takes a path
   like `/folder/file.csv`.
   - **Expect:** the dataset appears in "Your data" with a blue **`Imported · Google Drive`** chip; the
     right-hand card opens with an "Imported from Google Drive" block above the data-type strip.
4. Reload the page. The chip must survive (it comes from the server on reconcile, not session state).
5. **L2-05:** drop several per-sample 10x files (e.g. 6 members of two GSMs from
   `…/selom-data/hani/geo/`) on the Data drop-zone → "Assembling per-sample matrices into one
   single-cell cohort…", then a note like *"Assembled 2 samples · 48,923 cells × 64,591 genes."* and one
   dataset. Dropping ERG recordings must still hit the old combine path.
6. **L2-04 regression to look for:** open a project from a previous session (bytes not in this browser),
   pick a dataset, run a skill. It must either run from `dataset_id` or say it needs a re-upload. It
   must **never** silently run on a 4-byte file called "mock".

### Known limits, stated rather than discovered later

- **Google's grant is `drive.file` only** (confirmed on the live connection). That scope reaches only
  files the app created or the user explicitly picked — so **a scientist's existing Drive file is
  invisible to Selom today**. Importing by file id works (proven above) only because the file was
  app-created. Making "import my existing Drive file" real needs either the Google Picker (which grants
  `drive.file` per file) or the restricted `drive.readonly` scope + Google verification. **This is a
  product gap, not a bug in this lane**, and it is not in any row — worth a plan entry.
- **The assemble path is memory-bound in the browser.** 6 input files (~150 MB) produced a **320 MB**
  h5ad, which the FE holds as a Blob → File → re-uploads. Fine for 2–3 samples; a full 9-sample deposit
  will not survive a browser tab. The honest fix is server-side assembly that lands straight in the
  object store — worth a row, deliberately not built here.
- **`/cloud/providers` is unauthenticated** — by design (public config, no tenant data, and the menu must
  render before a user does anything), and asserted so a later hardening sweep cannot quietly re-close
  the feature. `/cloud/connections` **is** auth-gated because its label names a real account.

### What L2-07 still costs

An enabled provider with **no** connected account renders an honest
*"Enabled, but no … account is connected yet. Connecting one from here needs the Nango Connect UI host
(tracked as L2-07)."* — not a Connect button that dies on click. Nothing is blocked today (both accounts
are already connected); a **new** user cannot self-serve a connection until L2-07 lands.

---

## Territory: what I touched outside the declared glob, and why

Declared and deliberate — each is additive, in a directory no other lane owns, and unavoidable for its row:

| File | Why |
|---|---|
| `app/frontend/lib/projects/types.ts` | One additive optional field (`Dataset.source`) + the `DatasetSource` interface. L2-03 is a mapper change; the mapper's output type lives here. |
| `app/frontend/mocks/handlers.ts` | Required by this lane's own DoD ("the MSW mock is updated in the SAME change as the contract"). |
| `app/frontend/lib/intake/assemble.ts` (new) | L2-05's transport. `components/intake/**` is in-glob but CLAUDE.md's structure rule puts a feature endpoint at `lib/<feature>/api.ts`; transport inside a component would have broken the guard-backed convention to satisfy a glob. |
| `deploy/nango/preflight.sh`, `deploy/nango/README.md`, `.env.example` | The L2-02 finding. Unowned by any lane. |
| `app/frontend/lib/projects/sync.test.ts`, `lib/intake/assemble.test.ts`, `lib/cloud/import-surface.guard.test.ts` (new) | Tests for the above. |

**Not touched:** `test_contract_cloud_providers.py` (untouched — the freeze held; its dormant
route-conformance test self-activated and passes). `test_reachability_guard.py` — **waiver deletions
only**, exactly the one edit permitted.

The frozen contract was **not changed** and did not need to be.

## Follow-ups for whoever picks this up

1. **`test_reachability_guard.py::test_waivers_reference_only_real_routes`** still carries
   `allowed_pending = {"/cloud/providers"}`. That route now exists and has no waiver, so the allowance is
   dead weight. I left it — deleting a waiver was the only edit I was permitted in that file.
2. The `@nangohq/frontend` dependency is now **unused** (`lib/cloud/nango.ts` deleted with its
   `CLOUD_CONNECT_ENABLED` kill-switch — a third client-side truth table). It comes back with L2-07;
   `git show e0c6689^:app/frontend/lib/cloud/nango.ts` has it. I did not run `npm uninstall` (forbidden —
   shared symlink).
3. The two product gaps above (`drive.file` scope; browser-side assembly memory) want plan rows.

## Commits

```
e0c6689 feat(cloud): L2-01 — GET /cloud/providers, and the FE stops guessing
6694c64 fix(cloud):  L2-02 — put the cloud settings in the file the backend actually reads
28ace7e fix(intake): L2-03 — carry datasets.source across the FE boundary and show it
4a96ea9 fix(intake): L2-04 — import by reference; no fabricated File reaches a run
8aab935 feat(intake): L2-05 — a reachable surface for scRNA cohort assembly
e2ca939 test(intake): L2-06 — ratchet the labelled Import busy state
a474f2e test(cloud):  don't inherit flag state from whoever's .env is on the box
```

The last one is not a row: L2-02 turned `test_cloud_intake.py`'s "the flag is off by default" assumption
red. The test read the real settings singleton, so it depended on whichever `.env` was on the box. Flag
state is now an explicit input, and the complementary flag-ON case was added — that one is what proves
L2-02 opened something, since the flag-OFF assertion passes just as well with the feature sealed.

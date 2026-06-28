# Selom — Step 7c sub-spec: FE state → Postgres (the store swap)

Status: **APPROVED — building (owner sign-off 2026-06-29).** The four rulings (§2.2 / §3.2 / §4 / §5)
and the open questions Q1–Q4 (§9) are all accepted **as recommended**: Q1 add `users.local_import_at`
(Alembic `0004`) · Q2 widen `uid()` to a full `randomUUID()` hex (keep the prefix) · Q3 last-write-wins
per row for 7c (defer multi-device concurrency) · Q4 dataset_id is the project-flow run path, multipart
kept for `/extract` + back-compat. Created 2026-06-28; approved 2026-06-29.

Companion to `docs/aws-materialization/{plan,spec}.md` (this deepens **spec §10**, which is a
half-page sketch). Builds on step 6's shipped `uploads/` package (`UploadRepo` / `TenantQuery` /
the short-tx pattern) and step 7b's auth seam (`auth/context.py` `require_user`).

---

## 0. Why a sub-spec (not just "do step 7c")

Spec §10 reads as "swap the store impl behind the interface — no FE rewrite, the types are already
DB-shaped." That promise is true for the *types* but **not literally true for the runtime**: the FE
store is a **synchronous** `useSyncExternalStore` whose mutators **return values the caller uses on
the next line**, and an API is asynchronous. Four things must be designed before code:

- **(a)** the sync/async impedance — how a synchronous, value-returning store sits on an async API.
- **(b)** the ~6 missing tenant repos + endpoints (the tables exist in `db/schema.py`; the HTTP
  surface + repos do not), incl. real route-naming collisions with existing read endpoints.
- **(c)** the one-time localStorage → Postgres import (so dogfood work isn't stranded).
- **(d)** the run-from-`dataset_id` endpoint (closes the upload→run loop without re-uploading bytes).

---

## 1. Scope & non-goals

**In scope (7c, all dogfoodable on SQLite + `LocalObjectStore` + dev auth — no AWS):**
- An API client layer + the optimistic-cache rewrite of `projectStore` and `workspaceStore`,
  **behind their existing interfaces** (`lib/projects/store.ts`, `lib/workspace/store.ts`).
- The missing tenant repos + endpoints: `figures`, `workspaces`, `gene_sets`, `papers`(+`supplements`),
  `skill_installs`, `cleaning_recipes`, `reproduction_runs`.
- `POST /import/local-state` (idempotent bulk import).
- `POST /skills/{id}/run-dataset` + the jobs variant (run from `dataset_id`).

**Non-goals (deferred to step 8 / later):**
- Aurora provisioning, live Clerk keys, S3-event/EventBridge triggers, the `API_PROXY_TARGET` flip,
  CORS — all step 8.
- `param-spec-cache` (`lib/catalog`, key `selom.paramSpecs.v1`) — **stays client-side**, it is an
  immutable per-version accelerator, not user state (spec §10). No change.
- Moving the figure's large rendered bundle to `figures.result_s3_key` — the FE inlines the (small)
  editable `spec` today; keep inline, leave `result_s3_key` null until it's a measured problem.
- Parquet (`datasets.parquet_s3_key` keeps the `.csv` key, owner gate Q5).

---

## 2. (a) The sync/async impedance — optimistic local cache + background reconcile

### 2.1 The impedance, stated precisely

`lib/projects/store.ts` is a synchronous module-level cache (`let state: ProjectState`) exposed via
`useSyncExternalStore`. Its mutators **mutate in place + return a value the caller uses immediately**:

| Mutator | Returns | Caller uses the return **synchronously** |
|---|---|---|
| `createProject(name)` | the new `Project` | `app/page.tsx:35`, `sidebar.tsx:30`, `command-palette.tsx:135` → `router.push('/project/'+p.id)` |
| `addFigure(pid, …)` | the new `Figure` | `project-workspace.tsx:351/410/461/519` → selects/opens `saved.id` |
| `forkFigure(id, …)` | the fork | `project-workspace.tsx:622` → opens the fork |
| `deleteProject(id)` | a snapshot of what was removed | `project-workspace.tsx:800` → offers Undo (`restoreProject(snap)`) |
| `saveGeneSet` / `savePaper` | the saved row | `gene-set-browser.tsx`, `skill-match*.tsx` |

So you **cannot** make these `async` and you **cannot** wait for a server id: the component routes
to / opens the new id on the very next line. This is the real reason "swap the impl" is not a
literal drop-in.

### 2.2 ⚑ DECISION (owner gate D-7c-1) — sync-read / async-write optimistic cache + client ids

Keep the in-memory `ProjectState` as the **synchronous source of truth for reads** (exactly as
today). Make every mutator:
1. apply the change to the in-memory cache + `emit()` **synchronously** and **return its value**
   (unchanged signatures — zero component edits), and
2. **write-through to localStorage** (instant offline mirror), and
3. **enqueue a background API call** (a write queue, §2.4) that persists to Postgres.

Reads on reload render instantly from the localStorage mirror, then a background `GET` **reconciles**
the cache from the server (the authority). The store flips from "localStorage is the database" to
"**localStorage is an offline write-through cache in front of the API**".

**Id authority — the keystone ruling:**
- **Projects, figures, gene sets, papers, supplements, skill installs → client-authoritative ids.**
  The FE already mints ids (`uid("p")` etc., `store.ts:23`); the backend `TenantQuery.insert` already
  honors an explicit `id` and only generates one when omitted (`db/tenant.py:111-113`). So the FE
  POSTs its id; the server stores it verbatim. **No id remap, no dangling references, no route
  rewrite** during the in-flight window — and the import (§4) and Undo become trivial idempotent
  upserts. *(One required FE change: widen `uid()` from 8 hex to a full `crypto.randomUUID()` hex so
  per-tenant collision is negligible at scale; keep the `p_`/`f_` prefix for readability. Fits the
  `String(36)` PK.)*
- **Datasets → keep the server handshake (already built).** The upload flow (`/uploads/intake` →
  presigned PUT → `/uploads/{id}/confirm`) *already* returns the server-minted `dataset_id`
  (`UploadRepo.intake`, `main.py:942`), and uploading is inherently async (no sync-return contract to
  honor — you can't render a dataset before its bytes exist). Leave it; do **not** retrofit a client
  id onto datasets.

**Alternative rejected — server-authoritative ids + temp-id remap.** Optimistic create returns a temp
id, the server returns the real one, and every reference (route URL, figure→project FK, in-flight
child creates) must be remapped. The `router.push('/project/'+p.id)` callers make this a live-URL
rewrite mid-navigation; linked creates (project→figure before either settles) must serialize on the
parent's real id. Strictly more moving parts for no benefit once client ids are accepted.

### 2.3 The new store shape (interface unchanged)

```
lib/projects/store.ts  (rewritten internals, same exports)
  state: ProjectState                 // in-memory cache — synchronous reads (unchanged)
  getSnapshot/getServerSnapshot       // unchanged (SSR: empty/seed, §2.5)
  hydrate()                           // CHANGED: read localStorage mirror → emit, THEN GET /projects
                                      //          + /datasets + /figures + … to reconcile (async)
  mutators                            // SAME signatures; now: apply+emit+mirror (sync) → enqueue write
  + (internal) writeQueue             // §2.4 — not exported; no caller sees it
```

`lib/api/client.ts` (NEW): a thin typed fetch wrapper over `/api/*` (the Vercel rewrite → backend).
Centralizes JSON, error mapping (reuse the read-body-once discipline, `skills-api.ts:194-225`
[[fetch-body-read-once-browser-verify]]), and a **pluggable `authHeader()` hook** that returns `{}` in
dev and the Clerk `Authorization: Bearer` in prod — so step 8 is a one-liner, not a sweep.

### 2.4 The write queue — ordering, debounce, reconcile, conflict, offline

- **FIFO per entity, dependency-ordered:** a child write (figure) never flushes before its parent
  (project) create has been enqueued. With client ids the parent id is known immediately, so the only
  ordering requirement is "parent POST enqueued before child POST" — trivially true (the component
  creates the project first). No id-wait.
- **Debounced/coalesced figure-spec writes (the live-edit story):** `updateFigureSpec` (`store.ts:262`)
  fires on every in-canvas edit (already debounced in the editor, but still chatty). The queue
  **coalesces by `(figureId, field=spec)`** — a newer spec replaces the pending one; one
  `PATCH /figures/{id}` carries the latest. An in-flight PATCH that is superseded is allowed to land
  (last-write-wins) and the newer one re-fires after. This is the §3 "debounced-write story for live
  figure-spec edits." ⚠ Note [[selom-fe-probe-autopersist-gotcha]]: the store auto-persists — verify
  probes must snapshot/restore, now doubly so (a probe write would hit the API too).
- **Reconcile (server = authority):** `hydrate()` GETs on first mount; a lightweight refresh runs on
  window `focus` and after the write queue drains. Merge policy: **server rows replace cache rows by
  id**; a cache row with a still-pending write is **not** clobbered (the pending write wins until it
  settles). Last-write-wins per row is acceptable for a single-user-multi-tab dogfood; cross-device
  concurrent edits are out of scope for 7c (flag for later if it matters).
- **Errors / offline:** a failed write retries with backoff (reuse the backend's transient story in
  spirit). On a **permanent** failure: `402 quota_exceeded` and `404 unknown project` **roll back**
  the optimistic change + surface a toast (the create can't stand); a transient/network failure
  **keeps** the optimistic state + a non-blocking "saving…/offline" indicator and retries. The store
  exposes a tiny `useSyncStatus()` (idle | saving | offline | error) for a status chip — additive,
  no existing caller touched.

### 2.5 SSR / hydration

Unchanged pattern: `getServerSnapshot()` returns the deterministic empty/seed state (no user data on
the server — these pages render client-side behind auth), so SSR markup matches the first client
render. `hydrate()` then (i) loads the localStorage mirror and emits, (ii) kicks the reconcile GET.
This is exactly today's seed→hydrate flow, with a GET appended.

---

## 3. (b) The missing tenant repos + endpoints

### 3.1 The surface (reuse the `UploadRepo` short-tx + `TenantQuery` pattern verbatim)

Each repo mirrors `UploadRepo` (`uploads/repo.py`): one short transaction per method,
`set_tenant` + `TenantQuery`, tenant = `ctx.user_id` only (never a body param, spec §6.2), behind a
`get_*_repo()` lazy singleton + a `set_*_repo()` test seam. Endpoints `Depends(require_user)`.

| Resource | Table (`db/schema.py`) | Routes | Maps from (FE) |
|---|---|---|---|
| figures | `figures` (215) | `GET /figures?project_id=` · `POST /figures` · `GET/PATCH/DELETE /figures/{id}` | `Figure` (`projects/types.ts:131`) — `addFigure`/`updateFigureSpec`/`freezeFigure`/`removeFigure`/`forkFigure` |
| workspaces | `workspaces` (114) | `GET /workspace` (the account container; auto-created by `_ensure_workspace`, `repo.py:127`) | `WorkspaceState` root |
| gene sets | `gene_sets` (306) | `GET/POST /workspace/gene-sets` · `DELETE /workspace/gene-sets/{id}` | `GeneSet` (`projects/types.ts:108`) — `workspaceStore.saveGeneSet`/`removeGeneSet` |
| papers | `papers` (244) | `GET/POST /workspace/papers` · `GET/PATCH/DELETE /workspace/papers/{id}` | `SavedPaper` (`workspace/types.ts`) — `savePaper`/`removePaper`/`setPaperDataMap`/… |
| supplements | `supplements` (275) | `POST/DELETE /workspace/papers/{id}/supplements` | `SavedSupplement` — `addPaperSupplements`/`removePaperSupplement` |
| skill installs | `skill_installs` (325) | `POST /skill-installs` · `DELETE /skill-installs` (by scope+skill) | `SkillInstall`/`WorkspaceSkill` — `installSkill`/`uninstallSkill` (project- **and** workspace-scoped; the `COALESCE(project_id,workspace_id)` unique already models both) |
| cleaning recipes | `cleaning_recipes` (292) | `GET/PUT /datasets/{id}/cleaning-recipe` | `CleaningStep[]` (`projects/types.ts:25`) |
| reproduction runs | `reproduction_runs` (196) | `GET/POST /workspace/reproduction-runs` · `GET /workspace/reproduction-runs/{id}` | the durable Ledger pointer; FE `setPaperReproductionRun` |

### 3.2 ⚑ DECISION (owner gate D-7c-2) — resolve the route-naming collisions

Three existing **read** endpoints would collide if the tenant CRUD reused the obvious path. Namespace
the account-library writes under **`/workspace/*`** and keep the existing catalog/live routes intact:

- **`/papers`** is the *staged reproduction-paper catalog* (read-only, `main.py:139`). The user's
  **saved** papers are different → **`/workspace/papers`**.
- **`/gene-sets`** is the *license-clean gene catalog* (`main.py:105`, + `POST /gene-sets/compile`).
  Saved sets are user state → **`/workspace/gene-sets`**.
- **`/reproduction-runs/{id}`** (`main.py:317`) returns the **live in-memory drive status**. The
  durable pointer row is a different lifetime → **`/workspace/reproduction-runs`**. (At step 8 the
  live drive can stamp the durable row on completion; out of 7c scope — note it.)
- **`/figures` route order (FastAPI first-match):** `/figures/styles` (`main.py:1069`) is one segment
  under `/figures`, the same shape as `GET /figures/{id}`. **Declare the new `/figures/{figure_id}`
  route AFTER all the static `/figures/export*` + `/figures/styles*` routes** (or it captures
  `"styles"` as an id). Cheapest: add the figure CRUD block immediately after `/figures/style/apply`.

### 3.3 The figure PATCH contract

`PATCH /figures/{id}` accepts a partial body — any of `{title, spec, frozen, variant_label}` — and
updates only present fields via `TenantQuery.update` (which already refuses `user_id` reassignment,
`db/tenant.py:119`). `spec` is the JSONB column (small editable Plotly spec, inline). This is the
endpoint the coalesced live-edit writes (§2.4) target.

---

## 4. (c) ⚑ DECISION (owner gate D-7c-3) — the one-time localStorage → Postgres import

`POST /import/local-state` — accepts the decoded `selom.projects.v1` + `selom.workspace.v1` blobs and
**upserts in FK-dependency order inside ONE tenant transaction** (workspace → projects → datasets*
→ figures → gene_sets → papers → supplements → skill_installs). Because ids are client-authoritative
(§2.2), every upsert is `INSERT … ON CONFLICT (id) DO NOTHING/UPDATE` — **idempotent**, so a retry
or a re-run is harmless. Returns per-table counts.

- ***datasets in the import are metadata-only** (the mock never had real bytes — `currentSha256` is a
  stand-in, `store.ts:35-48`). Import the row as `status='ready'` with a null `upload_s3_key` and a
  `legacy_no_bytes` marker; a run on it will 409 "re-upload to materialize" (honest — the bytes were
  never in the mock). New uploads go through the real intake flow.*
- **Trigger + marker:** on first authenticated load, if a localStorage blob exists and no marker is
  set, the FE offers "Import your local projects?" (non-silent — the user opts in). On success, set
  `selom.import.v1 = {at}` locally. **Open Q1:** also persist a server-side marker
  (`users.local_import_at`, a 1-column Alembic `0004`) so the prompt doesn't reappear on another
  device? Recommended (cheap, cross-device-correct) — confirm at the gate.
- The localStorage blobs are **read, never deleted** (non-destructive — same discipline as
  `workspace/store.ts:57-90`'s project→workspace migration); the store simply stops treating them as
  authoritative once reconciled.

---

## 5. (d) ⚑ DECISION (owner gate D-7c-4) — run from `dataset_id` (close the upload→run loop)

Today `/skills/{id}/run` + `/skills/{id}/jobs` take a multipart `matrix: UploadFile` (`main.py:554`,
`:823`). After step 6 the bytes already live in S3 (`upload_s3_key`) and the parsed matrix at
`parquet_s3_key` (CSV). Re-uploading them per run is wasteful and breaks staleness coherence.

**Add (additive — the multipart routes stay for `/extract` and ad-hoc one-shots):**
- `POST /skills/{skill_id}/run-dataset` — body `{dataset_id, params, override}` → loads the
  tenant-scoped dataset row, fetches the object (`parquet_s3_key` if parsed, else `upload_s3_key`)
  via the `ObjectStore`, writes it to the **C3 content-addressed managed temp**
  (`engine/ingest.py` `_materialize_csv`, the step-6 leak-free path), then runs the **identical**
  pipeline (the QC / D1 data-contract / D2 frame gates, theme, table synthesis).
- `POST /skills/{skill_id}/jobs-dataset` — same, async (the heavy lane).
- **Refactor, don't fork:** extract `_resolve_run_input(...) -> (path, filename, declared_sha)` used
  by both the multipart and dataset-id entrypoints, so there is one run body. Provenance
  `input.sha256` = `dataset.current_sha256` (the genuine hash once parsed), making the figure's
  staleness check (`Dataset.currentSha256` vs `provenance.input.sha256`) finally real, not a mock
  stand-in.
- **FE:** `runSkill` gains a `bySha`/`byDataset` variant in `lib/skills-api.ts`; the project flow
  (upload → dataset → run) calls it. The `File`-based `runSkill` stays for `/extract`.

---

## 6. Local dogfood config (no AWS)

```
SELOM_JOB_STORE=sql
SELOM_DATABASE_URL=sqlite:///dev.db
SELOM_DB_AUTO_CREATE=true        # create_all on first boot (dev only; prod = Alembic)
# object store stays Local → /uploads/local/{key} serves the upload; auth stays dev (fixed tenant, no header)
```
FE dev: `npx next dev --webpack` [[selom-turbopack-webpack-workaround]]. ⚠ eamos holds `:8000` — run
the Selom backend on another port + point `next.config` at it for the session (revert after), **never
kill :8000**. Verify on real data + the live FE+BE, not `dev:mock` [[verify-on-real-data-not-mock]].

---

## 7. Build slices (ordered, each independently shippable + green-gated)

1. **BE-1 — client ids + figures CRUD.** Accept optional client `id` on `POST /projects` (back-compat:
   omit → server mints, step-6 behavior unchanged). New `figures/repo.py` + the 5 figure routes
   (after the static `/figures/*`, §3.2). Tests: figure CRUD + tenant isolation + client-id round-trip.
2. **BE-2 — the rest of the library repos/endpoints** (workspaces/gene_sets/papers+supplements/
   skill_installs/cleaning_recipes/reproduction_runs), `/workspace/*` namespaced (§3.2). Tests per repo
   + isolation.
3. **BE-3 — `POST /import/local-state`** (idempotent bulk upsert, atomic) + **run-from-dataset_id**
   (the `_resolve_run_input` refactor + the two routes). Tests: import idempotency; run-dataset reads
   S3/local bytes and hits the same gates as multipart.
4. **FE-1 — `lib/api/client.ts`** + rewrite `projectStore` to the optimistic-cache shape (§2.3/§2.4)
   behind the unchanged interface; widen `uid()`. vitest: mutators stay sync + return values; queue
   coalesces spec writes; reconcile merge policy; offline keeps optimistic state.
5. **FE-2 — `workspaceStore`** swap (same shape) + the one-time import opt-in + wire
   run-from-dataset_id into the project run flow.
6. **VERIFY — live FE+BE dogfood** [[full-app-smoke-test-before-handoff]]: upload a real file → run →
   edit the figure → **reload** (persists from Postgres, not just localStorage) → fork → delete+Undo →
   import a pre-existing localStorage blob → confirm rows in `dev.db`. Browser-verify in a **named**
   project [[selom-name-test-projects]].

---

## 8. Acceptance criteria

- **Zero component edits** beyond the additive `useSyncStatus()` chip — every existing
  `createProject/addFigure/forkFigure/deleteProject/saveGeneSet/savePaper` call site compiles &
  behaves unchanged (the sync return contract holds).
- A created project/figure is **persisted to Postgres** and **survives a hard reload with
  localStorage cleared** (proves the API path, not the mirror).
- **Cross-tenant isolation** holds for every new endpoint (extend `tests/test_tenant_isolation.py`
  over figures + the `/workspace/*` resources — same acceptance gate as 7b).
- **Import is idempotent** (run twice → identical DB, no dup rows).
- **run-from-dataset_id** produces a byte-identical figure to the multipart path on the same data, and
  stamps a real `input.sha256` (staleness becomes live).
- Fast gate green (`pytest -m "not slow"`) + ruff clean + FE tsc/eslint/vitest green.

---

## 9. Open questions for the owner gate

- **Q1 (import marker):** add `users.local_import_at` (Alembic `0004`) for a cross-device "already
  imported" marker, or client-only marker? *(Recommend: add the column — cheap, correct.)*
- **Q2 (id width):** OK to widen `uid()` to a full `randomUUID()` hex (keeping the prefix)? *(Recommend
  yes — required for safe client-authoritative ids at scale.)*
- **Q3 (conflict policy):** last-write-wins per row for 7c (single-user, multi-tab), defer real
  multi-device concurrency? *(Recommend yes — out of dogfood scope.)*
- **Q4 (run path):** make run-from-dataset_id the **only** project-flow run path (multipart kept only
  for `/extract`), or keep both wired in the project flow during transition? *(Recommend: dataset_id
  for the project flow; multipart for `/extract` + back-compat.)*

---

## 10. Risks

- **R1 — silent divergence cache vs server.** Mitigation: server-authoritative reconcile on
  focus/after-drain; pending-write rows protected; `useSyncStatus()` surfaces saving/offline/error.
- **R2 — the figure-spec write storm.** Mitigation: coalesce by `(figureId, spec)`; one PATCH carries
  the latest (§2.4). Watch the network tab in VERIFY.
- **R3 — partial import.** Mitigation: one transaction, dependency-ordered, idempotent upserts — a
  failed import leaves nothing half-written and is safe to retry.
- **R4 — route-order regression** (a new `{id}` route shadowing a static one). Mitigation: §3.2
  ordering rule + a route-resolution test.

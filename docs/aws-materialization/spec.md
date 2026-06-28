# Selom — AWS Materialization Foundation (M-001) — Implementation Spec

Status: **Amended in place as we build.** M-001 **steps 1–5 BUILT** — all four content-addressed
stores ride the one `ObjectStore` seam (plan §6): result store (`storage/results.py`), result-cache
durable tier (`skills/_result_cache.py`), artifact/lineage store (`engine/lineage.py`), and the
reproduction Ledger via the new `LedgerStore` seam (`reproduction.py`); behind `SELOM_OBJECT_STORE`
(local default unchanged; `s3` flips all four), verified on the live dev bucket + moto parity.
**Step 2 (statelessness) BUILT** — `SqlJobStore` on the `analysis_jobs` table behind
`make_job_store` (`SELOM_JOB_STORE=memory|sql`), SQLAlchemy-portable (SQLite dev/test · Aurora
Postgres prod) + Alembic; **Aurora provisioning deferred** to the prod-deploy step (owner
2026-06-28 — build now, provision later), validated on SQLite incl. a cross-instance read.
**Step 7a (the tenant schema) BUILT** — the remaining 12 tables (§2.3) added to `db/schema.py` +
Alembic `0002_create_tenant_schema` (RLS Postgres-only, dialect-gated; SQLite-validated; the
Alembic and `create_all` paths proven drift-free), `tests/test_tenant_schema.py`. **Reorder
(owner 2026-06-28):** the step-6/step-7 fork resolved to **schema+auth-first** — the upload
*endpoints* are structurally inseparable from the `datasets`/`users` tables + JWT `user_id`, and
the temp-leak rework is entangled with the C3 parsed-input cache; with a Clerk account now
available there's no reason to build step 6 against a stub. Remaining order: **7b** (Clerk auth →
`TenantQuery` + RLS enforcement + isolation test) · **6b** (upload intake/confirm + parsed-parquet
+ temp redesign + T1/T2, on the real schema) · **7c** (FE → API) · **8** (split deploy). The one
order-independent step-6 sliver — `presign_put` on the seam — folds in next. Created 2026-06-28.

Parent / source of truth: `docs/aws-materialization/plan.md` (locked decisions §1, topology §2,
schema §4, S3 layout §5, migration order §6, QR-hardened must-cover §3). This spec implements the
M-001 foundation row of that plan and treats its locked decisions + must-cover items as **binding
requirements**. Companion inventory: `docs/architecture-consistency-gate/inventory.md`.

> Scope boundary: this doc designs the **materialization foundation** — the Postgres schema, the
> S3 object layout, the store-swap seam, statelessness, presigned upload, auth/tenancy, the deploy
> split, and FE state migration. It does **not** design M-002 (AI-chat serialization) or M-003
> (AI-skills safe slice), which get their own specs.

---

## 0. The core invariant (threaded through every section)

Selom's backend was built **content-addressed + interface-swapped**, so most of this foundation is
a *backend swap behind an existing seam*, not a rewrite. The invariant the whole design rests on
(plan §2):

> content SHA = cache key = ETag = idempotency key = S3 object key = Postgres pointer.
> **Bytes live in S3; rows/pointers live in Postgres; the dev path never requires AWS.**

Evidence the codebase already honours this:

| Store | File | What it proves |
|---|---|---|
| Result store | `storage/results.py:24` (`ResultStore` Protocol) · `:110` (`make_result_store` Local↔R2) | already a Protocol with an S3-API twin; AWS = a third backend |
| Result cache | `skills/_result_cache.py:184` (`_disk_read`) · `:193` (`_disk_write`) · `:202` (`fetch`) · `:228` (`put`) | a clean disk-IO boundary; the docstring already names "a future durable R2 tier (C4)" |
| Lineage | `engine/lineage.py:138` (`ArtifactStore`) · `:161` (`put`) · `:177` (`get_table`) · `:184` (`get_meta`); `artifact_id` = sha at `:270`/`:280` | content-hash PK; docstring names "the D4 object-store tier swaps the backend behind this interface" |
| Ledger | `reproduction.py` `LedgerStore` / `ObjectStoreLedgerStore` + `save_ledger`/`load_ledger` | was the **only** store with no abstraction (direct `path.write_text`); step 5 gave it the `LedgerStore` seam over the ObjectStore (the `root=` arg still writes a direct filesystem path for back-compat). |

Three things are **genuinely new** (no seam exists): statelessness (`jobs/store.py:81` in-memory
singleton), presigned upload (`main.py:158`/`:343` buffer whole files; `engine/ingest.py:177`/`:351`
leak `delete=False` temps), and users/auth/tenancy (no `user_id` anywhere today).

---

## 1. The unified store-swap seam (config seam, all four stores)

### 1.1 Decision — converge the four stores onto ONE `ObjectStore` protocol

The plan asks for a per-store swap "mirroring `make_result_store` Local↔R2". Four parallel swaps
would be four near-identical boto3 wrappers. Instead, **converge** (memory rule
`unify-on-superior-framework`): define **one** `ObjectStore` Protocol with two backends, selected
**once** by config; the four content-addressed stores become thin adapters over it.

```python
# storage/object_store.py  (NEW)
class ObjectStore(Protocol):
    def get_bytes(self, key: str) -> bytes | None: ...
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def head(self, key: str) -> bool: ...                       # existence probe (cross-process completion)
    def delete(self, key: str) -> None: ...
    def presign_get(self, key: str, ttl: int) -> str: ...        # S3: real URL; Local: /jobs/{k}/result-style route
    def presign_put(self, key: str, ttl: int, max_bytes: int) -> dict: ...  # {url, fields} for the upload PUT
```

Two implementations, selected by config exactly as `make_result_store` selects today
(`storage/results.py:110`):

- `LocalObjectStore(root=settings.data_dir)` — filesystem; `presign_*` return the in-app
  `GET /jobs/{id}/result`-style local routes (dev never needs AWS — plan D6).
- `S3ObjectStore(settings)` — boto3 `s3` client. Reuse the R2 hardening verbatim
  (`storage/results.py:65-74`: `request_checksum_calculation="when_required"`, RISKS #5). For AWS,
  `endpoint_url=None` (regional) and IAM-role creds instead of R2 keys.

```python
# config.py addition (mirrors use_r2 at config.py:94)
object_store: str = Field(default="local", validation_alias="SELOM_OBJECT_STORE")  # local | s3
# + s3_bucket, s3_region, s3_presign_ttl; AWS creds come from the Lambda execution role, not env keys.

def make_object_store(settings) -> ObjectStore:
    return S3ObjectStore(settings) if settings.object_store == "s3" else LocalObjectStore(settings.data_dir)
```

### 1.2 The four adapters (names the methods to swap)

| Store | Today (local) | After (adapter over `ObjectStore`) | Methods swapped |
|---|---|---|---|
| **Result store** | `LocalResultStore` / `R2ResultStore` (`results.py:38`/`58`) | `ResultStore.put/get/url_if_exists` delegate to `object_store.put_bytes("results/{key}.json")` / `get_bytes` / `presign_get` | `put`, `get`, `url_if_exists` (Protocol already at `results.py:24`) |
| **Result cache** (C4) | `ResultCache._disk_read/_disk_write` (`_result_cache.py:184`/`193`) | keep the in-proc LRU tier; the disk tier delegates to `object_store.get_bytes/put_bytes("cache/result/{key}.json")` | `_disk_read` → `_obj_read`, `_disk_write` → `_obj_write` (the only two methods that touch the filesystem; `fetch`/`put`/`get`/`set` unchanged) |
| **Lineage** (D4) | `ArtifactStore.put/get_table/get_meta` (`lineage.py:161`/`177`/`184`) | same three methods, body delegates to `object_store` keyed `artifacts/{aid}.csv` + `artifacts/{aid}.meta.json` | `put`, `get_table`, `get_meta` (the `_atomic_write`/`_table_path`/`_meta_path` helpers become key builders) |
| **Ledger** (NEW seam) | `save_ledger`/`load_ledger` direct file IO (`reproduction.py:971`/`980`) | introduce a `LedgerStore` Protocol `{save(ledger)->key, load(slug)->Ledger, exists(slug)->bool}`; `save_ledger`/`load_ledger` become thin wrappers over `get_ledger_store()`; backend delegates to `object_store` key `repro/{slug}/ledger.json` | new `LedgerStore.save/load/exists` |

Each store keeps its existing lazy process-default + test-seam pair (`get_cache`/`set_cache`
`_result_cache.py:270`/`285`; `get_store`/`set_store` `lineage.py:217`/`229`) — add the same
`get_ledger_store`/`set_ledger_store` pair for the Ledger so tests inject an in-memory backend.

**Why converge rather than four swaps:** one boto3 surface to harden (checksums, retries, SSE,
prefix), one place to add the S3 retry/backoff (T3), one IAM surface. The content-hash key scheme
(§4 invariant) already makes every store's payload immutable + dedupable, so a single object store
is correct for all four.

### 1.3 Migration ordering note

The Ledger seam (write the backend the other three already have) is step 5 of plan §6 and is the
**only** store needing new abstraction work — the other three are adapter refits over code that was
designed for exactly this swap. Steps 1–5 ship behind the config flag with the local backend as the
default, so nothing changes for dev until `SELOM_OBJECT_STORE=s3`.

---

## 2. Postgres DDL — the tenant tables

### 2.1 Tenancy model (denormalized tenant key + dual-layer RLS)

Every row-owning table carries a **direct** `user_id text NOT NULL` (the Clerk id), even when it
also has `project_id`. Rationale: a uniform single-column tenant predicate on *every* table makes
both the application `TenantQuery` wrapper (§6) and the Postgres RLS policy identical and
join-free — a forgotten or wrong join can't widen the predicate. The small denormalization cost is
worth the structural guarantee (this is the headline production risk, plan R-3).

Two enforcement layers (defense in depth):

1. **Application layer (primary, §6):** `TenantQuery` — every query is scoped by the JWT-derived
   `user_id` *structurally*; you cannot construct a query without it.
2. **Database layer (backstop):** native Postgres RLS. Each transaction runs
   `SET LOCAL app.user_id = '<jwt user_id>'`; every table has
   `USING (user_id = current_setting('app.user_id', true))`. Even if a future code path bypasses
   `TenantQuery`, the DB refuses cross-tenant rows. Aurora Serverless v2 supports native RLS.

> The plan §1 D2 says "in-app RLS"; this spec keeps the in-app wrapper as primary **and** adds DB
> RLS as a cheap backstop. If the owner wants app-only, the policies below are commented out — but
> R-3 argues for keeping both.

### 2.2 Shared conventions

- PK: `id uuid DEFAULT gen_random_uuid()` except `users.user_id` (Clerk id, text PK) and
  `intermediate_tables.artifact_id` (sha-256, text PK — mirrors `lineage.py:270`).
- `created_at timestamptz DEFAULT now()`, `updated_at timestamptz DEFAULT now()`.
- Every tenant table ends with the RLS enable + policy block (shown once below, applied to all).
- Bytes are **never** stored in Postgres — only S3 keys + content hashes + small JSON the FE reads
  directly (Plotly spec). A `*_s3_key` column is the pointer; an `*_sha256` is the content hash.

```sql
-- Applied to EVERY tenant table <T> below:
ALTER TABLE <T> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <T> FORCE ROW LEVEL SECURITY;   -- applies even to the table owner role
CREATE POLICY tenant_isolation ON <T>
  USING       (user_id = current_setting('app.user_id', true))
  WITH CHECK  (user_id = current_setting('app.user_id', true));
```

### 2.3 DDL

```sql
-- 1. users — the tenant root. Net-new (the inventory was single-tenant: inventory.md §3 "never
--    modeled users/auth/billing"). Clerk user_id is the PK and the tenant key everywhere.
CREATE TABLE users (
  user_id            text PRIMARY KEY,                 -- Clerk user id (sub claim)
  email              text NOT NULL,
  stripe_customer_id text,
  is_subscribed      boolean NOT NULL DEFAULT false,
  tier               text NOT NULL DEFAULT 'free',     -- free | pro (LAUNCH-GATES: schema now, gate later)
  max_projects       integer NOT NULL DEFAULT 3,       -- quota fields carried now, enforced at launch
  max_datasets       integer NOT NULL DEFAULT 10,
  max_storage_bytes  bigint  NOT NULL DEFAULT 1073741824,  -- 1 GiB free tier (placeholder)
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
-- users RLS predicate is self-referential: user_id = current_setting('app.user_id')

-- 2. workspaces — the account-level container (lib/workspace is account-scoped, not project-scoped).
CREATE TABLE workspaces (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  name       text NOT NULL DEFAULT 'My workspace',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_workspaces_user ON workspaces(user_id);

-- 3. projects — the sidebar folders (lib/projects/types.ts:156 Project).
CREATE TABLE projects (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  name         text NOT NULL,
  color        text NOT NULL DEFAULT 'blue',           -- chart token hue (types.ts:159)
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_projects_user ON projects(user_id);

-- 4. datasets — one uploaded file (lib/projects/types.ts:75 Dataset). Bytes in S3; row is the pointer.
CREATE TABLE datasets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  filename        text NOT NULL,
  label           text,                                -- optional display name (types.ts:80)
  modality        text,                                -- detected modality (types.ts:14 Modality)
  upload_s3_key   text,                                -- uploads/{user_id}/{project_id}/{id}/{filename}
  current_sha256  text,                                -- live bytes hash → staleness (types.ts:90)
  parquet_s3_key  text,                                -- data/{sha256}.parquet (parsed/cleaned)
  size_bytes      bigint NOT NULL DEFAULT 0,           -- for the quota check
  qc              jsonb,                               -- QcReport (types.ts:38) — small, FE reads inline
  status          text NOT NULL DEFAULT 'pending_upload', -- pending_upload | ready | failed (T2)
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_datasets_project ON datasets(project_id);
CREATE INDEX idx_datasets_user    ON datasets(user_id);
CREATE INDEX idx_datasets_sha     ON datasets(current_sha256);

-- 5. figures — the durable produced figure (lib/projects/types.ts:131 Figure).
--    Small editable Plotly spec inlined as jsonb (FE reads it directly); a large rendered figure
--    bundle points at S3. parent_figure_id = the fork/variant self-FK; frozen = the "paper" tag.
CREATE TABLE figures (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  project_id       uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  dataset_id       uuid REFERENCES datasets(id) ON DELETE SET NULL,
  skill_id         text,                               -- catalog id
  job_id           uuid REFERENCES analysis_jobs(id) ON DELETE SET NULL,
  title            text NOT NULL DEFAULT 'Untitled figure',
  spec             jsonb,                              -- editable Plotly spec (small → inline)
  result_s3_key    text,                               -- results/{job_id}.json (large bundle in S3)
  provenance       jsonb,                              -- staleness trigger-set (types.ts:138)
  methods          jsonb,
  legend           jsonb,
  table_stats      jsonb,                              -- the Statistics StatsTable (types.ts:142)
  data_check       jsonb,
  data_fit         jsonb,
  parent_figure_id uuid REFERENCES figures(id) ON DELETE SET NULL,  -- variants/forks
  variant_label    text,
  frozen           boolean NOT NULL DEFAULT false,     -- the "paper" tag (types.ts:148)
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_figures_project ON figures(project_id);
CREATE INDEX idx_figures_user    ON figures(user_id);
CREATE INDEX idx_figures_parent  ON figures(parent_figure_id);

-- 6. analysis_jobs — REPLACES the in-memory JobStore (jobs/store.py:51-81). Poll-safe across Lambda
--    instances (any instance reads the row, not a local dict). Mirrors Job (store.py:26) + the
--    content-addressed pointers from _result_cache / lineage.
CREATE TABLE analysis_jobs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  project_id        uuid REFERENCES projects(id) ON DELETE CASCADE,
  dataset_id        uuid REFERENCES datasets(id) ON DELETE SET NULL,
  skill_id          text NOT NULL,
  skill_version     text,                              -- part of the cache key (_result_cache.py:129)
  status            text NOT NULL DEFAULT 'queued',    -- queued|running|succeeded|failed (store.py:16)
  params            jsonb NOT NULL DEFAULT '{}'::jsonb,
  filename          text,                              -- original upload name (store.py:34)
  input_sha256      text,                              -- the input content hash (idempotency)
  result_cache_key  text,                              -- _result_cache.cache_key (_result_cache.py:129)
  result_json_s3_key text,                             -- results/{id}.json pointer
  artifact_id       text REFERENCES intermediate_tables(artifact_id) ON DELETE SET NULL,  -- the matrix the skill saw
  result_url        text,                              -- presigned GET (store.py:35 result_url)
  error             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_user   ON analysis_jobs(user_id);
CREATE INDEX idx_jobs_status ON analysis_jobs(status);
CREATE INDEX idx_jobs_cachekey ON analysis_jobs(result_cache_key);  -- idempotent reuse probe

-- 7. intermediate_tables — content-addressed lineage (engine/lineage.py ArtifactMeta:65).
--    artifact_id = the sha PK (lineage.py:270/280). Bytes (the CSV) live at artifacts/{id}.csv in S3.
CREATE TABLE intermediate_tables (
  artifact_id   text PRIMARY KEY,                      -- sha-256 of the table bytes / matrix descriptor
  user_id       text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  kind          text NOT NULL DEFAULT 'ingested',      -- ingested|combined|cleaned|matrix (lineage.py:43-46)
  filename      text NOT NULL DEFAULT '',
  materialized  boolean NOT NULL DEFAULT true,         -- false for a meta-only matrix (lineage.py:75)
  n_rows        integer NOT NULL DEFAULT 0,
  n_cols        integer NOT NULL DEFAULT 0,
  columns       jsonb NOT NULL DEFAULT '[]'::jsonb,
  csv_s3_key    text,                                  -- artifacts/{artifact_id}.csv (null if meta-only)
  recipe        jsonb NOT NULL DEFAULT '[]'::jsonb,    -- RecipeStep[] (lineage.py:57)
  recipe_note   text NOT NULL DEFAULT '',
  note          text NOT NULL DEFAULT '',
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_intermediate_user ON intermediate_tables(user_id);

-- 8. artifact_parents — the D3 lineage DAG edges (lineage.py:49 ParentRef; lineage.lineage() at :324
--    walks them). A child artifact → its source-file or parent-artifact ancestors.
CREATE TABLE artifact_parents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  child_id      text NOT NULL REFERENCES intermediate_tables(artifact_id) ON DELETE CASCADE,
  parent_kind   text NOT NULL DEFAULT 'source',        -- source | artifact (lineage.py:53)
  parent_id     text NOT NULL,                         -- sha of a source file, or a parent artifact_id
  label         text NOT NULL DEFAULT '',
  UNIQUE (child_id, parent_kind, parent_id)
);
CREATE INDEX idx_artifact_parents_child ON artifact_parents(child_id);

-- 9. cleaning_recipes — the persisted cleaning plan (inventory.md §"Cleaning is advisory": today
--    CleaningStep[] is display-only; this makes a cleaned re-run reproducible).
CREATE TABLE cleaning_recipes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  dataset_id  uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  steps       jsonb NOT NULL DEFAULT '[]'::jsonb,      -- CleaningStep[] (types.ts:25)
  applied     boolean NOT NULL DEFAULT false,
  produces_artifact_id text REFERENCES intermediate_tables(artifact_id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_cleaning_dataset ON cleaning_recipes(dataset_id);

-- 10. gene_sets — provenance-stamped gene set (lib/projects/types.ts:108 GeneSet). Account-level →
--     promoted to workspace scope (lib/workspace/types.ts:99 notes projectId becomes vestigial).
CREATE TABLE gene_sets (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  name         text NOT NULL,
  genes        jsonb NOT NULL DEFAULT '[]'::jsonb,
  source       text NOT NULL DEFAULT '',               -- go | wikipathways | curated | compiled
  source_label text NOT NULL DEFAULT '',
  license      text NOT NULL DEFAULT '',
  created_from text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_gene_sets_user ON gene_sets(user_id);

-- 11a. papers — the saved Skill-Match / Reproduction anchor (lib/workspace/types.ts:50 SavedPaper +
--      reproduction.py:370 Paper). Bibliographic metadata kept structured.
CREATE TABLE papers (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  workspace_id        uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  filename            text NOT NULL,
  doi                 text,
  pmid                text,
  title               text,
  authors             jsonb NOT NULL DEFAULT '[]'::jsonb,
  venue               text,
  year                integer,
  volume              text,
  issue               text,
  pages               text,
  is_preprint         boolean NOT NULL DEFAULT false,
  url                 text,
  modality            text,                            -- scrna|bulk|proteomics (reproduction.py:388)
  skills              jsonb NOT NULL DEFAULT '[]'::jsonb,   -- routed slugs (types.ts:67)
  out_of_scope        jsonb NOT NULL DEFAULT '[]'::jsonb,
  figure_count        integer NOT NULL DEFAULT 0,
  tier_summary        jsonb,
  reproduction_run_id uuid REFERENCES reproduction_runs(id) ON DELETE SET NULL,
  data_map            jsonb,                           -- per-panel picker overrides (types.ts:83)
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_papers_user ON papers(user_id);

-- 11b. supplements — files attached to a saved paper (lib/workspace/types.ts:32 SavedSupplement).
--      Bytes (xlsx/csv/pdf) live in S3 at uploads/{user_id}/supplements/{sha256}.{ext}; row = pointer.
CREATE TABLE supplements (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  paper_id    uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  filename    text NOT NULL,
  kind        text NOT NULL,                           -- pdf | xlsx | csv (types.ts:23)
  size_bytes  bigint NOT NULL DEFAULT 0,
  sha256      text,
  s3_key      text,                                    -- uploads/{user_id}/supplements/{sha256}.{ext}
  status      text NOT NULL DEFAULT 'pending_upload',  -- T2 reconciliation
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_supplements_paper ON supplements(paper_id);

-- 12. reproduction_runs — the Ledger pointer (reproduction.py:397 Ledger; save_ledger:971). The full
--     typed ledger JSON lives in S3 (repro/{slug}/ledger.json); this row is the queryable handle +
--     the headline score so a list view doesn't fetch every blob.
CREATE TABLE reproduction_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  paper_slug      text NOT NULL,
  ledger_s3_key   text,                                -- repro/{slug}/ledger.json
  reproducibility integer,                             -- PaperScore.reproducibility (reproduction.py:336)
  selom_confidence integer,
  tier            text,
  n_panels        integer NOT NULL DEFAULT 0,
  status          text NOT NULL DEFAULT 'pending',     -- pending | driven | failed
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_repro_user ON reproduction_runs(user_id);
CREATE INDEX idx_repro_slug ON reproduction_runs(paper_slug);

-- 13. skill_installs — a skill added to a project/workspace (types.ts:96 SkillInstall;
--     workspace/types.ts:90 WorkspaceSkill — the account-wide promotion).
CREATE TABLE skill_installs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  project_id   uuid REFERENCES projects(id) ON DELETE CASCADE,   -- null ⇒ workspace-wide install
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  skill_id     text NOT NULL,
  installed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (COALESCE(project_id::text, workspace_id::text), skill_id)
);
CREATE INDEX idx_skill_installs_user ON skill_installs(user_id);
```

> Table count note: the plan §4 says "12 tenant tables". This DDL has 13 row-owning tables +
> `supplements` (a child of `papers`) + `artifact_parents` (a join/edge table). Counting
> papers+supplements and intermediate_tables+artifact_parents as one logical entity each gives the
> plan's 12 core entities. All carry `user_id` + RLS. No silent omissions.

### 2.4 Forward-ordering caveat

`figures.job_id → analysis_jobs(id)`, `analysis_jobs.artifact_id → intermediate_tables`, and
`papers.reproduction_run_id → reproduction_runs(id)` are forward references. The migration creates
tables in dependency order (users → workspaces → projects → datasets → intermediate_tables →
artifact_parents → reproduction_runs → analysis_jobs → figures → papers → supplements →
cleaning_recipes → gene_sets → skill_installs), or adds the cross-FKs in a second `ALTER TABLE` pass.

---

## 3. S3 object key layout + ETag/304 reuse

Exactly the plan §5 layout (content-hash keyed, so disk→S3 is a prefix change, not a re-architecture):

```
uploads/{user_id}/{project_id}/{dataset_id}/{filename}   raw drop (presigned PUT) — tenant-prefixed
uploads/{user_id}/supplements/{sha256}.{ext}             paper supplements (presigned PUT)
data/{sha256}.parquet                                    parsed/cleaned matrix (D8 substrate, deferred adopt)
artifacts/{artifact_id}.csv  +  artifacts/{artifact_id}.meta.json   D3 lineage (artifact_id = sha, lineage.py:270)
results/{job_id}.json                                    figure bundle (results.py:_obj "results/{key}.json")
cache/result/{cache_key}.json   ·   cache/render/{key}.json   C1/C2 caches (_result_cache.py keys)
repro/{slug}/ledger.json                                 reproduction Ledger (reproduction.py:975)
```

**Key construction rule (T1 — load-bearing):** every `uploads/...` key's `{user_id}` segment is the
**JWT-verified** user id derived server-side, **never** a request parameter. The dataset/supplement
row is created first (status `pending_upload`); its ids fill the key; the server then presigns that
exact key. A client cannot influence the prefix.

**ETag / 304 reuse:** content-addressed keys (`{sha256}`, `{cache_key}`, `{artifact_id}`) are
immutable — the same content always self-identifies (lineage.py docstring: "the same table always
self-identifies"). So:

- S3 returns the object's ETag (= MD5 for non-multipart, or the content sha we set as metadata).
- The figure-result endpoint sets `Cache-Control: public, max-age=…, immutable` and serves
  `ETag: "<sha>"`. A repeat fetch sends `If-None-Match`; S3 / the API answers **304 Not Modified**.
- An identical re-run hits `result_cache_key` (idempotency) → no recompute (the C1 contract,
  `_result_cache.py:1`), and the rendered envelope reuses on a cosmetic/theme change (the C2 split,
  `_result_cache.py:144 render_key`). The invariant "content SHA = ETag = idempotency key" is what
  makes all of this one mechanism.

---

## 4. The three genuinely-new seams

### 4.1 Statelessness — `analysis_jobs` table replaces the in-memory `JobStore` ✅ BUILT

> **BUILT (step 2, SQLite-validated; Aurora deferred).** Implemented as `SqlJobStore`
> (`jobs/sql_store.py`) — generalized from "PgJobStore" to a **SQLAlchemy-portable** store so the
> dev/test path runs on stdlib SQLite and prod on Aurora Postgres behind the SAME code (plan D6),
> selected by `make_job_store(settings)` (`SELOM_JOB_STORE=memory|sql`). The `analysis_jobs` table
> lives in `db/schema.py`; Alembic owns the migration (`alembic/versions/0001_create_analysis_jobs.py`,
> verified via the CLI + `command.upgrade` on SQLite). Step-2 scope is this table only — the
> cross-table FKs (users/intermediate_tables) + RLS land in step 7; `user_id` ships now as a
> nullable forward-compatible column. The cross-instance guarantee + the config-driven app path are
> covered by `tests/test_job_store.py`. **Aurora is provisioned at the prod-deploy step** (owner
> 2026-06-28: build now, provision later) — no AWS DB cost yet.

**Problem (cited):** `jobs/store.py:81` is a **process-wide singleton dict**
(`job_store = JobStore()`); `jobs/queue.py:24` builds one `result_store` per process. On Lambda, a
poll (`GET /jobs/{id}`) can land on a **cold instance** that has never seen the job → 404, even
though another instance ran it. `jobs/queue.py:71 get_job` already probes the shared result store
cross-process for arq — that pattern generalizes.

**Design:** a `PgJobStore` implementing the same `JobStore` surface (`create`/`get`/`update`,
`store.py:55-77`) against the `analysis_jobs` table. The singleton in `queue.py` is replaced by
`make_job_store(settings)` (in-memory for local-inline dev, Postgres for prod) — the same
config-seam shape as `make_object_store`.

- `submit` (`queue.py:61`) inserts a `queued` row, runs inline (dev) or enqueues to the heavy
  Lambda (prod), returns the row.
- The worker `UPDATE`s `status`/`result_url`/`error` (`queue.py:37`/`51`/`53`) on the row.
- `get_job` (`queue.py:71`) reads the row — **any** Lambda instance sees the same state. The
  existing arq cross-process completion probe (`url_if_exists`) stays as a belt-and-braces check.
- Idempotency: before running, look up `result_cache_key`; on a hit, mark `succeeded` and point at
  the existing `results/{job_id}.json` — no recompute (the C1 cache promoted to a DB-visible probe).
- Polling stays HTTP poll (`GET /jobs/{id}` — inventory.md route table) — SSE is replaced by polling
  for the Lambda deploy (plan §6 step 8: "SSE → polling/WS").

### 4.2 Presigned S3 PUT upload — replaces direct multipart

**Problem (cited):**
- `main.py:158 _save_capped` does `data = await upload.read()` (whole file buffered in memory) and
  checks the cap **after** (`:165`) — inventory.md confirms "size cap checked *after* the file is
  buffered in memory".
- `main.py:343 _save_upload` does `shutil.copyfileobj(matrix.file, f)` into a temp dir.
- API Gateway caps request bodies at ~6–10 MB (plan R-2), so multipart through the API breaks for
  real omics files.
- `engine/ingest.py:177` and `:351` create `NamedTemporaryFile(delete=False)` temps that are
  **never cleaned** (the materialized decoded-CSV + the combined-frame CSV leak) — on Lambda's
  ephemeral disk this is a per-invocation leak.

**Design — three-step presigned PUT (client → S3 direct, bypassing API Gateway):**

1. `POST /uploads/intake` `{project_id, filename, content_sha256, size_bytes}` → server:
   - verifies the tenant (JWT), checks the **quota** (`max_datasets`, `max_storage_bytes`),
   - inserts a `datasets` row `status='pending_upload'` (gets `dataset_id`),
   - builds the key `uploads/{jwt_user_id}/{project_id}/{dataset_id}/{filename}`,
   - returns `object_store.presign_put(key, ttl, max_bytes)` — a presigned PUT URL with a
     `Content-Length-Range` condition (server-enforced size ceiling; replaces the post-read cap).
2. Client PUTs the bytes **directly to S3** (no API Gateway body limit).
3. Confirm: `POST /uploads/{dataset_id}/confirm` → server `head`s the key, flips `status='ready'`,
   stamps `current_sha256` + `size_bytes`. (T2 covers the failure path below.)

**Parsing moves server-side, leak-free:** the heavy Lambda reads the S3 object via a **streamed**
download to a `tempfile` it owns and deletes in a `finally` (matching `queue.py:54`'s existing
`data_path.unlink` discipline), then ingests. The `delete=False` temps in `ingest.py:177`/`:351`
must be wrapped so the caller deletes them, or rewritten to stream the parsed parquet to
`data/{sha256}.parquet` and drop the local temp — **stop leaking temps** is an explicit acceptance
criterion (§10). Parsed output is written content-addressed to `data/{sha256}.parquet` (the D8
substrate, adopted as an extra per plan §7 deferral — pyarrow/duckdb only when the substrate lands).

### 4.3 Auth / users / tenancy — Clerk JWT → Lambda authorizer

**Problem (cited):** there is **no `user_id` anywhere today** (inventory.md §3). All state is
single-tenant.

**Design (plan §2 topology):**
- Clerk issues a JWT to the Next.js frontend (best Next/Vercel DX, plan D3).
- API Gateway → a **Lambda authorizer** verifies the Clerk JWT (issuer + JWKS), extracts the `sub`
  claim → `user_id`, and injects it into the request context. **The Lambda derives the tenant from
  this verified claim — never from a request param or body** (T1).
- On first request for a new `sub`, upsert the `users` row (email from the verified claim; default
  `free` tier + default quotas).
- Stripe webhooks update `users.is_subscribed` / `tier` / `stripe_customer_id` (carried now, gated
  at launch per LAUNCH-GATES).
- Every handler opens a transaction, runs `SET LOCAL app.user_id = <ctx.user_id>` (DB RLS backstop),
  and uses the `TenantQuery` wrapper (§6) for all data access.

---

## 5. Light zip Lambda vs heavy Docker/ECR Lambda — the deploy split

Plan §2 + R-4. The split is by **dependency weight**, not by domain:

| Lane | Package | Endpoints | Why |
|---|---|---|---|
| **Light zip** (FastAPI + Mangum, ≤250 MB zip) | router/catalog/text only | `/skills`, `/gene-sets`, `/papers/route`, `/papers/extract`, `/methods/compose`, `/citations/*`, `/describe` | no scverse/Kaleido import → fast cold start; the deterministic router is pure-Python |
| **Heavy Docker/ECR** (≤10 GB image) | scverse stack + Kaleido (headless Chrome) | `/skills/{id}/run`, `/skills/{id}/jobs`, `/data/inspect`, `/data/combine`, `/papers/{id}/reproduce`, `/figures/export` | scanpy/anndata + Kaleido blow past the 250 MB zip cap (inventory.md: `/figures/export` = headless Chrome) |

- **Docker is for the AWS/ECR image only** — owner-approved 2026-06-28. **Local Docker is NOT used**
  (dev runs `uvicorn` directly per CLAUDE.md; the `ask-before-docker-wsl` memory rule is satisfied —
  this is the approved exception, scoped to the ECR build).
- Both lanes share the **same FastAPI app**; the split is the deploy artifact + the API Gateway
  route → integration mapping, not a code fork. The lazy-import discipline already in the codebase
  (every loader in `ingest.py:45-86` lazy-imports its dep; `queue.py:32` lazy-imports the runners)
  is what lets the light lane avoid pulling the heavy deps at import time.
- The light lane's import graph must be audited so a stray top-level `import scanpy` doesn't bloat
  the zip (an acceptance check — mirrors the existing "raw `import('plotly.js')` 500'd SSR" lesson,
  inventory.md known-crash history).

---

## 6. T1 — Structural tenant isolation (acceptance-gating)

Four mechanisms; **all four** required (this is plan R-3, the headline production risk).

### 6.1 `TenantQuery` — a forgotten `user_id` filter is *impossible*

Not a convention ("remember to filter") — a wrapper that **cannot** issue an unscoped query.

```python
# db/tenant.py  (NEW)
class TenantQuery:
    """Every data-access call is bound to ONE tenant at construction. There is no method that
    returns rows without the user_id predicate — the predicate is injected by the wrapper, not the
    caller, so it can't be forgotten."""
    def __init__(self, conn, user_id: str):
        self._conn = conn
        self._uid = user_id                  # the JWT-derived tenant — set ONCE, never from a param

    def select(self, table, **filters): ...  # always appends WHERE user_id = self._uid
    def insert(self, table, **values):       # always forces values["user_id"] = self._uid
        values["user_id"] = self._uid        # caller-supplied user_id is overwritten, never trusted
    def update(self, table, id, **changes): ...  # WHERE id = %s AND user_id = self._uid
    def delete(self, table, id): ...             # WHERE id = %s AND user_id = self._uid
```

- The request handler receives `tq = TenantQuery(conn, ctx.user_id)` from the auth middleware; no
  handler ever sees a raw connection. A code review / lint rule forbids importing the raw DB client
  outside `db/`.
- `insert` **overwrites** any caller-supplied `user_id` with the JWT one — a malicious body
  `{"user_id": "victim"}` is silently corrected, never honoured.

### 6.2 Tenant derived from the verified claim, never a param

The only source of `user_id` is `ctx.user_id` from the Lambda authorizer (§4.3). No endpoint accepts
`user_id` / `owner` / `tenant` in its path, query, or body. A request that includes one is ignored
(and optionally 400'd). This is enforced by §6.1 (`TenantQuery` never reads a body `user_id`) + a
schema rule (no Pydantic request model has a `user_id` field).

### 6.3 S3 prefix isolation — a presigned URL can't touch another tenant's prefix

- **Server-side key derivation (primary):** the `uploads/{user_id}/...` key is built from the JWT
  `user_id` (§3). A presigned URL's signature **covers the exact key** — the client cannot change
  the key without invalidating the signature. So a presigned PUT/GET is *single-object scoped* and
  the object is, by construction, under the tenant's own prefix.
- **Bucket policy / IAM condition (backstop):** the upload role's policy scopes `s3:PutObject` /
  `s3:GetObject` to `arn:aws:s3:::selom-bucket/uploads/*` and `data/*`/`artifacts/*`/`results/*`/
  `cache/*`/`repro/*` (the known prefixes only); `Deny` on anything outside; enforce
  `aws:SecureTransport=true` and `s3:x-amz-server-side-encryption=aws:kms`. Per-tenant IAM roles are
  **not** used (one role per Clerk user doesn't scale); isolation comes from server-side key
  construction + signature scoping, with the bucket policy denying public access + non-TLS + the
  wrong prefix shape.
- **GET path:** a presigned GET is only ever generated for a key the `TenantQuery` first confirmed
  belongs to the user (the row carries the key + `user_id`), so a tenant can never be handed a URL
  to another tenant's object.

### 6.4 Automated cross-tenant isolation test (acceptance gate)

A test (`tests/test_tenant_isolation.py`, runs in the fast CI lane per Task E2) that:

1. seeds two users A and B, each with a project + dataset + figure + job + paper + gene set;
2. authenticates as A (mock authorizer context `user_id=A`);
3. asserts every read endpoint returns **only** A's rows (count + ids);
4. attempts to read/update/delete **B's** ids by guessing them → asserts 404/empty (never B's data);
5. POSTs a body containing `{"user_id": "B"}` → asserts the created row is owned by **A** (the
   wrapper overwrote it);
6. (DB-RLS layer) runs a raw query with `SET LOCAL app.user_id = A` → asserts B's rows are invisible
   even to a hand-written SQL bypass of `TenantQuery`.

This test is **green = a hard merge gate**. It is the acceptance proof for R-3.

---

## 7. T2 — Presigned upload failure path (orphan reconciliation)

**The orphan:** client PUTs to S3 successfully, but the `POST /uploads/{id}/confirm` fails (network
drop, client crash) → an object exists with no `ready` row; or a `pending_upload` row exists with no
object (PUT never happened). Silent data loss / dangling state. Must not be silent (plan T2).

**Design — the row is created before the object, and S3 is the source of truth for "did it land":**

1. **Row-first ordering** (§4.2): the `datasets` / `supplements` row is inserted `pending_upload`
   *before* the presigned URL is issued. So there is never an object whose ids aren't already a row
   (the key is built *from* the row).
2. **S3 Event Notification → confirm Lambda (authoritative):** an `s3:ObjectCreated:Put` event on
   the `uploads/` prefix triggers a small Lambda that parses `{user_id}/{project_id}/{dataset_id}`
   out of the key, finds the matching `pending_upload` row, and flips it to `ready` (stamping size +
   sha from object metadata). **This heals the failed-confirm orphan** — the explicit confirm POST
   becomes a latency optimization, not the only path to `ready`.
3. **Sweep job (the reverse orphan):** a scheduled Lambda (e.g. hourly) :
   - deletes `pending_upload` rows older than `UPLOAD_TTL` (e.g. 24 h) that still have no object
     (PUT never happened), and
   - lists `uploads/` objects with no matching `ready`/`pending` row and deletes them (object
     without a row — e.g. a duplicate or a deleted-row leftover).
4. **Idempotency:** the event handler is safe to run twice (flipping `ready`→`ready` is a no-op); the
   sweep checks both directions, so neither orphan class survives a cycle.

Acceptance: a test that simulates "PUT ok, confirm POST never sent" and asserts the S3-event path
brings the row to `ready`; and "row pending, no PUT" asserts the sweep removes it.

---

## 8. T3 — Aurora Serverless v2 cold-start

**The risk (plan T3 / R-1):** Aurora Serverless v2 scaling **from 0 ACU** adds 10–30 s of latency to
the first query after idle. A user's first request after a quiet period would hang or time out.

**Design:**
- **Min-ACU floor:** set the cluster `min_capacity` to a **non-zero** floor (e.g. **0.5 ACU**) so
  the DB never fully pauses; the first query is warm. This is the recommended default.
- **Cost trade (must be flagged):** 0.5 ACU running 24/7 is a continuous idle cost (~0.5 × ACU-hour
  rate, on the order of a low-double-digit USD/month) versus scale-to-0's zero idle. The plan's D2
  rationale (scale-to-zero) is in **tension** with T3 (cold-start latency) — this is a real
  trade-off the owner must rule on at the gate (Open Question Q1). Options:
  - **(a)** min 0.5 ACU floor — pay idle, no cold-start (recommended for a user-facing product);
  - **(b)** scale-to-0 + **client retry/backoff** — free idle, but the first request after idle
    needs a retry wrapper (see below) and a UI "warming up…" state;
  - **(c)** RDS Proxy in front to smooth connection storms from concurrent Lambda cold starts
    (a separate concern — connection pooling — but worth pairing with either).
- **Client retry/backoff (required regardless):** the DB access layer wraps the connect/first-query
  in a bounded exponential backoff (e.g. 3 retries, 2 s → 4 s → 8 s) catching the
  "database resuming" error class, so even with a floor a scaling event degrades to a short delay,
  not a 500. This belongs in `db/` next to `TenantQuery`.

---

## 9. T4 — Cloudflare rationale (logged)

Why Cloudflare fronts Vercel rather than Vercel-native WAF or AWS CloudFront (plan D4 / T4):

| Factor | Cloudflare | Vercel-native WAF | AWS CloudFront |
|---|---|---|---|
| WAF + DDoS | **free** tier covers it | paid add-on | AWS WAF is metered per-rule/request |
| Owner preference / existing bundle | **DNS already on Cloudflare** (one dashboard) | — | new surface to manage |
| Caching boundary | **edge security only** — Cloudflare does **not** cache app assets | Vercel owns assets | would double-cache vs Vercel |
| SSL | **Full (Strict)** end-to-end to Vercel | n/a | n/a |

**Decision:** Cloudflare = DNS + WAF + DDoS + SSL Full(Strict) at the edge; **Vercel owns asset
caching** (avoid the double-cache that CloudFront-in-front would create — plan D4). The caching
boundary is explicit: **Cloudflare = edge security, Vercel = assets, S3 = bytes.** Logged here so the
choice isn't re-litigated; the driver is free WAF/DDoS + owner's existing DNS bundle, not a technical
superiority claim over Vercel's WAF.

---

## 10. FE state migration — localStorage → Postgres behind the existing store interfaces

The FE types were **deliberately shaped DB-ready** so this is "an impl change, not a FE rewrite"
(`lib/projects/types.ts:1-8`: "shaped to match the planned schema … the swap … is a backend-impl
change, not a FE rewrite"; `lib/workspace/types.ts:9-13` says the same).

| FE store | Today | After | Maps to |
|---|---|---|---|
| `ProjectStore` (`lib/projects`, key `selom.projects.v1`) | localStorage single-key blob | a `ProjectStore` impl calling the API (`GET/POST /projects`, `/datasets`, `/figures`, …) | tables 3,4,5,13 |
| `workspaceStore` (`lib/workspace`, key `selom.workspace.v1`) | localStorage | API-backed `WorkspaceStore` | tables 2,10,11,11b |
| `param-spec-cache` (`lib/catalog`, key `selom.paramSpecs.v1`) | localStorage cache of immutable specs | **stays client-side** — it's an *immutable per-version accelerator* (`param-spec-cache.ts:1-17`), not user state. No migration; optionally seed from the figure's stamped provenance (part B, `param-spec-cache.ts:11`). |

- **No component changes:** the docstrings promise "no component imports Supabase directly —
  everything goes through `ProjectStore`" (`projects/types.ts:8`) / `workspaceStore`
  (`workspace/types.ts:12`). The migration swaps the store *implementation* behind that interface.
  Field-by-field the types already line up with §2's DDL (the table column comments cite the exact
  `types.ts` line each maps from).
- **One-time import:** on first authenticated load, an optional "import your local projects" reads
  the three localStorage keys and POSTs them to the API (so a dogfood user's existing work isn't
  stranded), then marks localStorage migrated.
- **`param_spec` cache:** unchanged — it is correctly client-side (immutable, version-keyed) and the
  Postgres move would be a regression (an extra round-trip for data that never changes per version).

---

## 11. IAM least-privilege policy (DRAFT)

One **execution role** for the Lambdas, scoped to exactly the resources the foundation touches
(plan §8 — "least-privilege IAM credential, not root"). DRAFT — tighten ARNs at build time.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3BucketObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::selom-prod/*",
      "Condition": {
        "Bool": { "aws:SecureTransport": "true" },
        "StringEquals": { "s3:x-amz-server-side-encryption": "aws:kms" }
      }
    },
    {
      "Sid": "S3ListScoped",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::selom-prod",
      "Condition": { "StringLike": { "s3:prefix": [
        "uploads/*", "data/*", "artifacts/*", "results/*", "cache/*", "repro/*" ] } }
    },
    {
      "Sid": "PresignOnly",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::selom-prod/uploads/*"
    },
    {
      "Sid": "SecretsRead",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:*:*:secret:selom/*"
    },
    {
      "Sid": "AuroraConnect",
      "Effect": "Allow",
      "Action": "rds-db:connect",
      "Resource": "arn:aws:rds-db:*:*:dbuser:*/selom_app"
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/selom-*"
    }
  ]
}
```

Notes: no `s3:*`, no `rds:*` admin, no root; SSE-KMS + TLS enforced on every object write; the DB
user `selom_app` is a **non-superuser** role bound by RLS (it cannot bypass policies — `FORCE ROW
LEVEL SECURITY` in §2.2 applies even to the table owner). A **separate**, narrower role for the
sweep/event Lambdas (S3 list/delete + DB update only) is recommended but deferred to the build.

---

## 12. Tier / quota / retention mechanism

Schema carries the fields now; numbers are gated at launch (plan §7 deferral; LAUNCH-GATES
"build now, gate later").

- **Quota check (write path):** `POST /uploads/intake` (§4.2) checks `count(datasets) <
  max_datasets` and `sum(size_bytes) + new < max_storage_bytes` *before* presigning. A
  project-create checks `max_projects`. Over-quota → 402/409 with an upgrade prompt (Stripe).
- **Retention (free vs pro) via S3 Lifecycle:**
  - **Free tier:** an S3 **Lifecycle rule** expires objects under `uploads/` (raw drops) after N
    days (e.g. 30) — the *uploads* prune. Derived artifacts (`results/`, `artifacts/`, `cache/`,
    `data/`) are content-addressed and cheap to regenerate, so a separate, longer rule (or
    keep-while-referenced) applies.
  - **Pro tier:** **retain** — pro users' `uploads/` are excluded from the expiry rule.
  - Because S3 Lifecycle is prefix-based, the tier split is implemented either by **two prefixes**
    (`uploads/free/{user_id}/...` vs `uploads/pro/{user_id}/...`) chosen at presign time from
    `users.tier`, **or** by an **object tag** (`tier=free|pro`) + a tag-filtered lifecycle rule.
    Tag-based is preferred (a tier upgrade re-tags rather than re-keys; no object move). **Open
    Question Q2** on which.
- A nightly reconcile keeps `datasets.status`/`size_bytes` consistent with S3 after a lifecycle
  expiry (an expired object → mark the row `expired`, surfaced as "re-upload to regenerate").

---

## 13. Migration order (follows plan §6)

Build-phase order; each step is independently shippable behind the config flag (local default
unchanged until flipped):

1. ✅ **Result store → S3** — adapter over `ObjectStore`; near config-only. Proves the seam. **BUILT.**
2. ✅ **Jobs → SQL `analysis_jobs`** — `SqlJobStore` (§4.1), SQLAlchemy-portable + Alembic;
   `SELOM_JOB_STORE=memory|sql`. **BUILT** (SQLite-validated incl. cross-instance + the app path);
   **Aurora provisioning deferred** to the prod-deploy step.
3. ✅ **Result-cache durable tier → S3** — `_disk_read/_disk_write` → `_obj_read/_obj_write` over the
   `ObjectStore` (key `cache/result/{key}.json`; the named C4). **BUILT.**
4. ✅ **Artifact/lineage store → S3** — `ArtifactStore` over `ObjectStore` (keys
   `artifacts/{id}.csv` + `.meta.json`; the named D4). **BUILT.**
5. ✅ **Reproduction Ledger → S3** — new `LedgerStore` seam (`ObjectStoreLedgerStore`, key
   `repro/{slug}/ledger.json`). **BUILT** on the S3 side; the `reproduction_runs` pointer row is
   part of step 2's Postgres schema (still pending).
7a. ✅ **Tenant schema** — the 12 tables (§2.3) in `db/schema.py` + Alembic `0002`; RLS Postgres-
   only; SQLite-validated. **BUILT** (pulled ahead of step 6 — see the reorder note below).
6. **Presigned S3 upload + parsed-parquet** — the one genuine flow rewrite (§4.2). Now lands
   **after** 7a/7b, on the real `datasets`/`users` tables + JWT `user_id` (the intake/confirm
   endpoints are structurally inseparable from them; the temp-leak rework is entangled with the C3
   parsed-input cache). The order-independent `presign_put` seam method is the next small slice.
7b. **Clerk auth → `TenantQuery` + RLS enforcement + isolation test** (§4.3, §6) — Aurora is
   provisioned here; `analysis_jobs` gains its users FK + RLS + a non-null tenant.
7c. **FE localStorage → Postgres** behind the existing store interfaces (§10) — types pre-shaped.
8. **Split deploy** (light zip + heavy Docker/ECR Lambda, §5); secrets → Secrets Manager; SSE →
   polling.

Steps 1–5 are backend swaps the code was built to absorb; **7a is the schema (built)**; 7b is the
auth/tenancy enforcement; 6 is the upload rewrite (reordered to ride on the real schema); 7c is the
FE swap; 8 is the deploy. **Reorder rationale (owner 2026-06-28):** the original §6 put step 6
before step 7, but step 6's *value* (the upload endpoints) can't exist without step 7's schema +
`user_id`, and a Clerk account is now available — so schema+auth come first and step 6 is built once
on the real foundation rather than against a stub.

---

## 14. Local ↔ S3 parity test

A single test suite run **twice** — once with `SELOM_OBJECT_STORE=local`, once with `=s3` (against a
local S3 mock such as MinIO/moto in CI) — asserting **identical behaviour** across the seam:

- `put_bytes`/`get_bytes` round-trip equality for every store (result, cache disk tier, artifact,
  ledger): write payload → read back → byte-identical.
- `head` returns the same existence verdict on both backends.
- Content-addressed idempotency: writing the same `{artifact_id}` / `{cache_key}` twice is a no-op
  on both (mirrors `lineage.py:167` "skip if the id already exists").
- A full skill run produces the **same** `results/{job_id}.json` content on both backends (the C1
  cache key is backend-independent — `_result_cache.cache_key` hashes content, not location).
- `presign_get`/`presign_put` return a usable URL on both (local = an in-app route, S3 = a real
  presigned URL) and a GET/PUT through each URL succeeds.

Green on both backends = the seam is transparent and the dev path (`local`) is a faithful stand-in
for prod (`s3`). This is the structural guarantee behind plan D6 ("the dev path never requires AWS").

---

## 15. Acceptance criteria

A — **Store seam** ✅ (steps 1–5)
- [x] One `ObjectStore` Protocol with `Local`/`S3` backends, selected by `settings.object_store`
      (mirrors `make_result_store`). `LocalObjectStore.put_bytes` is atomic (write-temp + replace) so
      the cache/artifact torn-read guarantee survives the seam.
- [x] All four stores (result, result-cache durable tier, lineage, **Ledger**) route bytes through
      it; the Ledger gained the `LedgerStore` seam (`ObjectStoreLedgerStore`, key
      `repro/{slug}/ledger.json`) it lacked. `save_ledger`/`load_ledger` keep their `root=` direct-
      filesystem path (back-compat); only the no-`root` default flows through the seam.
- [x] §14 parity suite green on both backends + the **real boto3 path** (moto) for all four stores;
      live round-trip on the dev bucket `selom-dev-objectstore-apse2` passed for steps 1–5.

B — **Schema** ✅ (step 7a; RLS verified-on-real-Postgres when Aurora lands in 7b)
- [x] All tenant tables from §2.3 created with FKs, indexes, and the RLS enable+policy block on every
      one (RLS emitted **Postgres-only**, dialect-gated — SQLite has none); `user_id` present +
      `NOT NULL` on every net-new row-owning table (`analysis_jobs.user_id` stays nullable + FK/RLS-
      free until 7b backfills the tenant). PKs are app-supplied uuid hex (the `analysis_jobs`
      precedent), not a `gen_random_uuid()` server default — one portable schema, no dialect-divergent
      defaults. SQLite-validated (`tests/test_tenant_schema.py`); the Alembic + `create_all` paths are
      proven drift-free. RLS *enforcement* is exercised by the 7b isolation test on real Postgres.
- [x] `intermediate_tables.artifact_id` is the sha PK (matches `lineage.py:270`);
      `analysis_jobs` carries `result_cache_key` + `result_json_s3_key` + `artifact_id` (from step 2).

C — **Statelessness** ✅ (code; Aurora deferred)
- [x] `SqlJobStore` (SQLAlchemy-portable) replaces the in-memory singleton behind `make_job_store`;
      a job created on one instance is readable from another (cross-instance test + the config-driven
      app path, `tests/test_job_store.py`). Validated on SQLite; Aurora provisioned at prod-deploy.
      Polling, not SSE, in prod (unchanged). Step 7 adds the users FK + RLS + the JWT `user_id`.

D — **Presigned upload**
- [ ] Upload bypasses API Gateway (presigned PUT direct to S3); no whole-file buffer in a handler
      (replaces `main.py:164 _save_capped`); the size cap is enforced *before* bytes land
      (`Content-Length-Range`), not after.
- [ ] **No leaked temp files** — the `delete=False` temps (`ingest.py:177`, `:351`) are owned +
      deleted, or replaced by streamed `data/{sha256}.parquet`.

E — **Tenancy (T1, hard gate)**
- [ ] `TenantQuery` makes an unscoped query unconstructable; the tenant comes only from the verified
      Clerk claim; no endpoint accepts a `user_id` param.
- [ ] `tests/test_tenant_isolation.py` (§6.4) green — cross-tenant read/write/delete all denied; a
      body-supplied `user_id` is overwritten; the DB-RLS layer blocks a raw-SQL bypass.
- [ ] S3 keys are JWT-derived; the bucket policy denies non-TLS / non-KMS / wrong-prefix access.

F — **Resilience (T2/T3)**
- [ ] Orphan reconciliation: the S3-event path brings a `pending_upload` row to `ready` even when
      the confirm POST never arrives; the sweep removes both orphan classes.
- [ ] Aurora min-ACU floor set (or scale-to-0 + retry/backoff) with the cost trade documented; the
      DB layer retries the "resuming" error class.

G — **Deploy + FE + cost**
- [ ] Light zip vs heavy Docker/ECR split (§5); light lane import-audited (no scverse/Kaleido at
      import). Docker = ECR image only; no local Docker.
- [ ] FE `ProjectStore`/`WorkspaceStore` swapped to API backends with **zero component edits**;
      `param-spec-cache` stays client-side.
- [ ] IAM policy is least-privilege (§11); tier/quota/retention wired (§12).

---

## 16. Open questions (for the owner gate)

> **RESOLVED at the gate (owner, 2026-06-28):** Q1 → **scale-to-zero now** (retry/backoff + a
> "warming up" state) + a **0.5-ACU floor at launch**. Q3 → **keep both** app-`TenantQuery` + DB RLS.
> Q4 → **yes**, denormalized `user_id` on every table. Q5 → parsed output **stays CSV** now; adopt
> pyarrow/duckdb only when the D4/D8 substrate lands. Q6 → **wire the mechanism now**, numbers at
> launch. Q7 → **Alembic**. Plus: **fold M-003's `skill_requests` into this unified schema** at build,
> and LLM-context PII redaction lives in **M-002** (queue redaction in M-003).

- **Q1 — Aurora floor vs scale-to-0 (T3).** Plan D2 chose Aurora *for* scale-to-zero, but T3's
  cold-start (10–30 s) argues for a non-zero min-ACU floor for a user-facing product. Which:
  (a) 0.5 ACU floor (pay idle, no cold-start), (b) scale-to-0 + retry/backoff + a "warming up" UI,
  or (c) add RDS Proxy? This is a cost-vs-latency policy call only the owner can make.
- **Q2 — Tier retention implementation.** Two S3 prefixes (`uploads/free|pro/...`) vs an object tag
  (`tier=…`) + tag-filtered lifecycle. Tag-based avoids re-keying on upgrade (recommended) but adds
  a tagging step on every presign. Confirm.
- **Q3 — DB RLS: app-only or app + DB policies?** Plan D2 says "in-app RLS"; this spec adds native
  Postgres RLS as a cheap backstop (defense in depth for R-3). Keep both, or app-`TenantQuery` only?
- **Q4 — Denormalized `user_id` on every table.** This spec puts a direct `user_id` on every table
  (uniform, join-free RLS predicate) rather than deriving it via `project_id`. Confirm the small
  denormalization is acceptable (it is the cheapest path to "forgotten filter impossible").
- **Q5 — Parsed-parquet now or later?** §4.2 writes `data/{sha256}.parquet`. Plan §7 defers
  pyarrow/duckdb "until the substrate lands". Adopt pyarrow as an extra in step 6, or keep parsed
  output as CSV (`artifacts/{id}.csv`, already the lineage format) until the D8 substrate work?
- **Q6 — Stripe + quota numbers.** Schema carries `tier`/`max_*`/`stripe_customer_id`; the actual
  free/pro limits + price are LAUNCH-GATES-deferred. Confirm we wire the *mechanism* now and leave
  the numbers as placeholders.
- **Q7 — Migration tooling.** Alembic vs raw SQL migrations for the Aurora schema? (Not specified in
  the plan; recommend Alembic for the FK/RLS ordering in §2.4.)

---

*End of DRAFT M-001 spec. No code, install, migration, or commit performed. Awaiting owner review at
the discussion gate before authoring M-002 / M-003 or connecting AWS access (plan §8, §10).*

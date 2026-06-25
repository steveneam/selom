# Selom Architecture Consistency Gate

Last updated: 2026-06-25 19:30 +10:00 — Claude (acting FE+BE).
Status: **Review gate for Steven.** No code, deploy, Supabase/DB mutation, Parquet
materialization, or refactor is implied by this document. This is the read-only
architecture assessment + integration plan the owner asked for ("see what can be
applicable or integratable to Selom"), grounded in the actual Selom codebase and in
the EAMOS architecture-consistency gate it was modelled on.

> **Provenance of this gate.** Adapted from the EAMOS gate (`D:\eamos\docs\architecture-consistency-gate\{plan,inventory}.md`)
> and the upstream Forj vault spine the EAMOS plan distilled from:
> `…\Forj\Wiki\reference\{infrastructure-spine, data-architecture-spine, edge-infrastructure-distillation}.md`.
> Those vault decisions (DuckDB/Parquet/no-Spark, the dual OLTP+OLAP endpoint, the
> services spine, the adopt-now-5 security lifts) are **ratified ADRs** — this gate
> **adopts** them for Selom, it does not re-derive them. Backfilled with current
> (2025–26) best-practice research (cited inline in the gate tasks).

---

## The owner's thesis (the organizing principle)

> *"Each filter/editor/parameter is dynamic to each data/skill set — which is good, it's
> what makes Selom unique; we don't want a generalised filter that does nothing. But there
> are a lot of edge cases, and switching between datasets and skills can cause crashes,
> because the pane/filter/parameter/editor is bespoke for each data/skill combination. So
> we need a consistent skeleton (robust tables, intermediate tables) for smooth input→output.
> Each data input will always be consistent (table, rows, columns) — only the format, style,
> layout and labelling differ. The architecture must be robust enough to handle that,
> especially the downstream stuff, scaling to a web server with a database and many users."*

This gate takes that thesis literally and turns it into a testable architecture. The
**bespoke-per-skill surface is preserved** (it is the moat); what changes is that it must
ride on **one consistent spine** so a bespoke pane can never receive a shape it doesn't
expect, go stale on a switch, or take the editor down with it.

## Goal

Before the next feature slice, verify Selom uses **one robust skeleton** across ingest,
analysis, lookup, figure sections, editor panes, caches, the (future) database, API
routes, UI loading states, and metrics. The target skeleton:

```text
dropped file (any format)
  -> ingest + classify (one modality taxonomy)
  -> CANONICAL TABLE contract  (rows × columns; tidy long-form + typed metadata)
  -> cleaning / intermediate tables  (bronze -> silver, content-addressed lineage)
  -> skill run (declares: param schema · capabilities · table contract)
  -> RESULT cache row  (skill+version+params+input-hash -> stats table + numeric series)
  -> figure-spec envelope  (data/layout/meta.selom.* — the declared contract)
  -> RENDERED-section cache  (theme/style envelope, separate from the compute)
  -> FE SECTION REGISTRY slot  (one contract drives render + nav + export + preflight)
  -> stable skeleton state  (idle|loading|empty|partial|stale|error|ready) + error isolation
  -> telemetry  (timing, payload size, memory, cache-hit, freshness)
```

Any section, page, pane, or metric that **cannot be described by this path** is either a
legacy compatibility path or an architecture gap — the same drift test EAMOS uses.

## Current read (honest)

The backbone is **sound and unusually consistent for its stage** — much of the spine the
owner wants already exists in seed form:

- **One ingest/classify spine** (`engine/ingest.py`, `engine/databundle.py`): a `DataBundle`
  wraps every input (AnnData / DataFrame) with a single modality taxonomy (`SC_COUNTS`,
  `BULK_COUNTS`, `DE_RESULTS`, `PROTEOMICS`, `METABOLOMICS`, `GENERIC_TABLE`) — the owner's
  "always a table" insight is already half-built here.
- **One capability contract** (`skills/_capabilities.py` → `meta.selom.capabilities`,
  resolved by `lib/figure-model.ts deriveFigureModel`): the FE reads a *resolved model*, not
  raw spec, and gates editor tools off declared flags — the generic-spine + flagged-plug-in
  pattern is already the rule for the figure editor.
- **One theming pass** (`skills/theme.py apply`) and **one provenance/methods/result bundle**
  (`jobs/queue.py`, `storage/results.py`) per run.
- **The data-substrate decision is already correct**: pandas in-memory now; Parquet+DuckDB
  held for the web/DB launch (matches the ratified vault three-plane exactly).

It is **not yet consistent end-to-end**, and the gaps are precisely where the owner reports
crashes and where multi-user/DB scale will bite:

1. **No canonical table contract between ingest and the skills.** Each skill re-opens
   `bundle.path` and re-parses; there is no one normalized table every downstream stage
   consumes. Intermediate tables (cleaned matrix, design sheet, long-form metrics) are
   ephemeral and unversioned. (`skills/contract.py` `run_bundle_with_table`; the three maps
   in `inventory.md §3–4`.)
2. **The FE panes are registry-*driven* but not registry-*complete*, and lack stable states.**
   `lib/catalog/params.ts` is a real per-skill registry, but capability declarations cover
   only 2 skills, panels assume their data is present, there are **no per-pane error
   boundaries**, no contract validation at the spec→component seam, and staged params are not
   scoped to the active skill — the exact recipe for the switch-crashes. (`inventory.md §5`.)
3. **No cache boundary.** Every run recomputes from disk; there is no result cache keyed by
   (skill, params, input-hash) and no source/render split. (`inventory.md §4`.)
4. **No database, no server-side source of truth.** Projects/datasets/figures live in FE
   `localStorage`; results are JSON blobs; job state is in-memory. None of this survives
   multi-user. (`inventory.md §3`.)
5. **"No performance issues / no memory leaks" is unproven** — it needs measured gates
   (render timing, payload-size ceilings, heap-snapshot leak hunts across switches), not code
   inspection. (Task E.)

## The central fix — a four-part contract spine

Everything below hangs off **one idea**: a single **content hash** (`input_sha256` +
`skill_version` + canonical params) is simultaneously the **table lineage address**, the
**cache key**, the **ETag**, and the **idempotency key**. Build the spine once; every
consistency property falls out of it.

### Spine 1 — the Canonical Table contract (the owner's "always rows × columns")

- **One internal table shape every stage/skill consumes**, regardless of input format:
  **tidy long-form** carried as a typed frame with **embedded semantic metadata** (schema
  version, modality, units, source tags, content hash). AnnData/MuData stay as the *native
  container for single-cell/multimodal lanes only* — a modality plug-in behind the spine, not
  the spine itself (matches `[[generalize-via-flagged-plugins-over-shared-spine]]`). The
  bespoke-per-dataset part is **only** the format adapter + the labels/units — exactly the
  owner's "format/style/labelling differ, the table doesn't."
  *(Best-practice basis: Arrow/Parquet embedded key-value metadata travels losslessly with
  the bytes; AnnData/MuData layered `X/obs/var/layers/obsm` for sc; tidy-data for the rest —
  research report B1.)*
- **Intermediate tables get medallion lineage, content-addressed**: bronze (raw upload =
  `input_sha256`) → silver (cleaned/normalized = `hash(bronze + cleaning_version + params)`)
  → gold (skill result = the run key). Each immutable; the lineage edge "this gold number came
  from this silver table came from this bronze upload" is just the hash chain. This is the
  **robust intermediate-table skeleton** the owner asked for. *(Research B2.)*
- **Validate every stage boundary with a named frame contract** (one schema per stage output:
  `CleanedTableSchema`, a per-skill result schema). A broken bronze→silver or skill→figure
  handoff fails at the seam → HTTP 400, not a silent mid-render crash downstream. *(Use a
  lightweight frame-validation layer over the dataframes; keep request/response JSON
  validation where it is — research B3.)*

### Spine 2 — the Skill/Section Registry (one contract drives everything)

- **Every skill declares, as DATA, its full surface**: param schema (have: `param_spec`),
  capabilities (have: `_capabilities._PROFILES` — but only 2 skills), its **table contract**
  (input column groups it needs; missing), and its **editor/section surfaces**. The generic FE
  renders render + nav + export + preflight from this ONE contract — never branches on skill id.
  This generalises the EAMOS `REPORT_SECTION_REGISTRY` to Selom's *dynamic* panes.
- **Close the declaration gaps**: extend capability profiles to every interactive skill; add a
  **boot-time / test-time audit** that every `params.ts` overlay key and every declared
  capability exists in a live `skill.json` (today drift only surfaces as a dev console warn —
  `params.ts warnDeadKnob`). *(Registry/schema-driven rendering with a default unknown-type
  renderer — research A1.)*
- **The skill-table-contract guard already exists in spirit** (the native/L3/L4 split memory);
  formalise it so a skill cannot ship without declaring the columns it consumes, and the FE can
  show "this data is missing column X for this skill" *before* a run instead of a runtime fail.

### Spine 3 — Stable skeleton states + crash isolation (the direct switch-crash fix)

- **Model each pane/section/metric as a discriminated-union state machine**
  (`idle | loading | empty | partial | stale | error | ready`), not parallel booleans; render a
  **stable skeleton from the state tag**, so every section always renders the same outer shape
  independent of data arrival. *(Research A2.)*
- **Wrap each dynamically-generated pane in its own error boundary** with
  `resetKeys=[datasetId, skillId]` — one bespoke pane that still throws fails *alone*; the
  editor and siblings stay up, and switching data/skill auto-clears a stuck error. *(react-error-boundary,
  research A3.)*
- **Validate the spec shape at the data→component boundary** (the seam, not deep in render);
  on mismatch, return a safe `error`/`partial` state with an unknown-type fallback. This is the
  direct guard against "panes receive shapes they don't expect." *(Research A4.)*
- **Reset pane state on switch via `key={datasetId:skillId}` remount** and **derive-don't-sync**
  (compute from props/spec during render; stop copying spec into state). Scope staged `fdParams`
  to the active skill id, not just the active figure id. This kills the leftover-state class
  (`project-workspace.tsx` `fdParams` lifecycle, `inventory.md §5.4`). *(Research A5.)*

### Spine 4 — Cache/source boundary + the analytical lane

- **Content-addressed result cache**: key = `(skill_id + skill_version, canonical(params),
  input_sha256)`. Canonicalize params properly (stable serialization, sorted keys, float/precision
  coercion, drop-defaults) so equal runs hit and `1` vs `1.0` can't false-miss. Immutable →
  **invalidate by bumping `skill_version`**, never a TTL. Layered: in-process LRU → local disk →
  object store; the object store *is* the durable artifact (Parquet result table + JSON spec under
  the hash). *(Research A1–A3, A6.)*
- **Split the SOURCE/RESULT cache from the RENDERED-figure cache** — result cache owns the compute
  (`(skill_version, params, input_hash)`); render cache owns the display envelope
  (`(result_hash, theme_version, render_params)`). A theme/label/journal-style change reuses the
  compute and only re-renders. This is the cache-layer twin of Selom's existing **Figure-data
  (amber) vs Figure-styling (cyan)** boundary. *(Research A4 — directly mirrors the shipped UX.)*
- **The content hash is also the ETag and the idempotency key**: `If-None-Match → 304` on figure
  GETs; `Idempotency-Key` (scoped per user+op) on run submission so a retried submit never
  double-computes. Derive both from the same canonical key. *(Research A5.)*
- **Analytical lane (ratified vault three-plane — adopt as-is)**: keep pandas/in-memory for the
  single-file hot path; the combine/multi-file/cohort/freshness path (the 516-file ERG tree, batch
  reproduction) is the **DuckDB-over-Parquet** lane. Offline build → chrom/condition-partitioned,
  sorted, zstd Parquet silver → embedded read-only DuckDB for scans. **No Spark, no MotherDuck, no
  lakehouse format** until the documented triggers fire (`data-architecture-spine.md`).

## Gate Matrix (Selom)

| Area | Required invariant | Current status | Gate before production |
| --- | --- | --- | --- |
| **File system** | Source, results, scratch, generated assets have clear homes; no runtime writes outside an approved data dir. | Temp upload dirs cleaned after run; `data/results/*.json`; scratch under the session dir. | Confirm artifact layout; results/intermediates go to object store (R2) not the repo; no generated blobs in Git. |
| **API routes** | Every expensive route has input bounds, a timeout, and an explicit failure contract. | Upload size cap (`_save_capped`, 512 MB default); QC gate → 422; **no per-route rate limit, no skill-execution timeout**. | Route × {auth, rate, max-payload, timeout, cache-path, failure-contract} matrix; add execution timeout + app-level rate limit on run/ingest. |
| **Data substrate / schema** | One canonical table contract; intermediate tables versioned + content-addressed; param ranges validated at the API. | DataBundle taxonomy ✓; **no normalized table contract; intermediates ephemeral; param min/max are metadata-only (no 400 on out-of-range)**. | Canonical-table contract (Spine 1) + frame-validation at stage seams + param-range enforcement in `resolved_params`. |
| **Lookup / read path** | Repeated reads hit a cache; no re-parse of the same input across routes. | `/data/inspect` then `/skills/{id}/run` re-parse the same file; **no input or result cache**. | Result cache (Spine 4) + an input-payload cache keyed by `input_sha256`; record p50/p95 cold/warm per skill. |
| **Analysis path** | Batch/combine/cohort use the analytical lane, not point-path loops. | Multi-file combine is pandas in-memory, ephemeral, unrecorded. | Promote combine/cohort onto the DuckDB/Parquet lane with a tiny-fixture preflight first (Task D). |
| **UI sections / panes** | Every pane has a stable slot + state machine + error isolation, independent of data arrival. | Registry-driven params ✓; **no per-pane error boundary, no spec-boundary validation, panels assume data present, staged params not skill-scoped**. | Spine 2 + Spine 3: registry completeness audit; state machines + error boundaries + boundary validation; `key`-remount on switch. |
| **Metrics** | Timing, payload size, memory, cache-hit, freshness are observable + bounded. | A run returns provenance; **no timing header, no payload-size ceiling, no memory/cache telemetry**. | Add opt-in, sanitized diagnostics + a perf-audit script (Task E). |
| **Caching** | Result cache owns compute; render cache owns the envelope; legacy stores are compatibility-only. | **None** (every run recomputes). | Build Spine 4; never let the figure JSON blob become the long-term query store. |
| **Database / persistence** | Projects/datasets/figures/runs in a server DB with RLS; bytes in object storage. | **All in FE localStorage + JSON files + in-memory job store.** | Supabase schema (Task F) — projects/datasets/figures/runs/intermediate_tables/cleaning_recipes + RLS + FK/composite indexes; bytes/Parquet in R2. |
| **Security** | Secrets server-only; `service_role` never on the hot path; JWT verified at the boundary; degrade-don't-cascade. | Pre-auth single-user dev; R2 keys server-side. | The vault **adopt-now-5**: key hygiene (RLS + anon hot path), JWT-verify FastAPI middleware, circuit-breaker the httpx client, pin Supabase region + front Render through Vercel, rate-limit auth/AI routes (`edge-infrastructure-distillation.md`). |
| **Operations** | No startup/request-time downloads; materialize offline → storage → disk; no unapproved DB mutation. | Skills run locally; no remote infra yet. | Keep the materialization doctrine when the DB/lane lands; every materialization has dry-run + checksum + rollback. |

## Gate Tasks (do read-only / design first; build only on owner pick)

Mirrors the EAMOS A–F, retargeted to Selom and to lane ownership (FE = Claude, BE = Codex;
Claude covers both while Codex is away).

- **Task A — Architecture inventory checklist (this gate's `inventory.md`).** Already drafted
  here: routes × bounds, the de-facto schema, the FE bespoke machinery + switch/crash seams,
  cache boundaries, the substrate. *Acceptance: the inventory + a findings list (done below).*
- **Task B — Stable-skeleton + registry consistency (FE, highest-leverage for the crashes).**
  The Spine-2 + Spine-3 work: per-pane state machines + error boundaries + spec-boundary
  validation + `key`-remount + skill-scoped staged params + a registry-completeness audit test.
  *Acceptance: switching any dataset/skill never crashes the editor; an unknown/partial spec
  renders a stable fallback, not a throw; a CI test fails when a `params.ts`/capability key has
  no backing `skill.json`.* **This is the recommended first build** — it directly closes the
  reported failure mode, is FE-only, and needs no DB.
- **Task C — Cache/source boundary (BE).** Spine-4 result cache (content-addressed) + the
  source/render split + ETag/304 + an input-payload cache. *Acceptance: an identical re-run is a
  cache hit (no recompute); a theme/label change re-renders without re-running the skill; figure
  GET honors `If-None-Match`.*
- **Task D — Canonical table contract + DuckDB/Parquet lane, tiny-fixture first (BE).** Spine-1:
  the normalized table contract + frame-validation at seams + medallion intermediate lineage;
  then the DuckDB/Parquet analytical lane with **only** the artifact layout + manifest + checksum
  + read-only health (no multi-GB build). *Acceptance: every skill consumes one declared table
  contract; disabled/missing/ready lane health is sanitized; tests pass without real corpora.*
- **Task E — Performance + memory proof (FE+BE).** Render-timing + payload-size ceiling +
  heap-snapshot leak hunt across dataset/skill switches + `Plotly.purge` on unmount + `useMemo`'d
  data/layout + a fast-vs-slow test split. *Acceptance: p50/p95 + peak heap recorded for cold/warm
  paths; no detached-canvas/listener growth across 20 switches; a fast named contract-test target
  separate from slow integration cases.*
- **Task F — Database / production readiness (BE, at the web launch).** The Supabase schema
  (Task F table set in `inventory.md §7`), RLS, FK/composite indexes, R2 object boundary, and the
  adopt-now-5 security lifts. *Acceptance: a migration/runbook with verification SQL + sanitized
  health; no remote mutation without explicit owner approval.*

## Test hygiene (the EAMOS fast/slow lesson, applied)

Selom already has the split *as a discipline* (focused subsets vs the full suite, the
real-engine opt-in tests). Formalise it: **a fast, named contract-gate** (param/capability
registry audit, table-contract guard, golden byte-identity, figure-model resolution) that every
feature commit runs in seconds, and **a slow gate** (real-engine skill runs, browser preflight,
perf/leak audits) behind an explicit target. Normal commits must never depend on a multi-minute
run.

## Boundaries / what NOT to do (re-litigation guard)

- **Do not generalise the bespoke panes away.** The dynamic-per-skill surface is the moat; the
  fix is a consistent *spine under* it, not a generic filter. (Owner-stated.)
- **Do not move the single-file hot path onto DuckDB** — pandas/in-memory wins there; DuckDB is
  the scan/combine/cohort lane only. (`data-architecture-spine.md`.)
- **Do not stand up Spark, MotherDuck, a lakehouse format, Redis, or a second host before the
  documented trigger fires.** Infra only when load-bearing. (Vault.)
- **Do not put large per-user tables or the figure blobs into Postgres** — Parquet-on-R2 for
  artifacts, Postgres rows for metadata/lineage/pointers. (Research B4.)
- **Do not claim "no perf issues / no leaks" from code review** — only measured gates (Task E)
  earn that.
- **No DB/Supabase/Render/Parquet mutation without explicit owner approval.**

## Recommended first move

**Task B (FE stable-skeleton + registry consistency)** — it is the direct fix for the reported
switch-crashes, is FE-only (Claude's lane), needs no database, and hardens the moat (the bespoke
panes) rather than diluting it. Then Task C (cache boundary) for the "faster / cleaner execution"
ask, and Task D's canonical-table contract as the substrate for the DB launch. Tasks E/F gate the
production web launch. **Pick with the owner at the meeting; nothing here is built yet.**

## References

- EAMOS gate: `D:\eamos\docs\architecture-consistency-gate\{plan,inventory,session-prompts}.md` ·
  `D:\eamos\docs\architecture-consistency-gate\selom-message.md`.
- Vault spine (ratified ADRs): `…\Forj\Wiki\reference\{infrastructure-spine, data-architecture-spine,
  edge-infrastructure-distillation}.md`.
- Selom inventory: `docs/architecture-consistency-gate/inventory.md` (companion to this plan).
- Memory: `[[selom-data-substrate-decision]]` · `[[selom-engine-spine-pillars]]` ·
  `[[generalize-via-flagged-plugins-over-shared-spine]]` · `[[selom-figure-edit-ux-pattern]]` ·
  `[[full-app-smoke-test-before-handoff]]`.
- Best-practice research (2025–26), cited inline in the spine sections: registry/schema-driven
  rendering, discriminated-union state machines, `react-error-boundary` + `resetKeys`, boundary
  schema validation, `key`-remount/derive-don't-sync; `Plotly.purge`/`useMemo`/WebGL-context budget,
  ~100k-point decimation, heap-snapshot leak hunting; RFC 8785 param canonicalization,
  version-in-key invalidation, `diskcache` L2, source/render cache split, ETag/304 + idempotency,
  tidy-Arrow canonical table, medallion-per-user lineage, pandera frame contracts, Parquet-vs-Postgres
  split.

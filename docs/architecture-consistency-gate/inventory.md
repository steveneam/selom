# Selom Architecture Inventory

Last updated: 2026-06-25 19:45 +10:00 — Claude (acting FE+BE).
Status: Static inventory for the architecture consistency gate (companion to `plan.md`).
Read-only mapping of the current Selom skeleton. **Not** a production sign-off, a DB
migration, or a deploy approval; where a property needs a live DB, a browser pass, or a
load test, it is marked **unproven** rather than inferred from code shape.

## Scope + the four consistency lenses

The owner asked the architecture to be robust across **four** dimensions, not just speed.
Every finding below is tagged against them:

- **SCALE** — survives a web server + a real database + many concurrent users.
- **MAINTAIN** — one place to change a behaviour; no shotgun edits across N skills.
- **IMPLEMENT** — adding the *next* skill/dataset/feature is fast and low-risk.
- **FUTURE-PROOF** — new features/upgrades slot into the spine without touching the generic
  renderer/canvas/cache/router (the extensibility / "fill-in-the-blanks" test).

The headline: Selom's spine is **already strong on MAINTAIN/IMPLEMENT for the figure editor**
(the capability contract + the per-skill registry make most chart features a plug-in). The
gaps cluster on **SCALE** (no DB, no cache, localStorage state) and on **FUTURE-PROOF at the
pane boundary** (no stable states / error isolation / contract validation → the switch-crashes).

## Canonical flow (as-is)

```text
dropped file
  -> _save_upload/_save_capped (temp dir, original name preserved)            [main.py:152,337]
  -> engine.ingest -> DataBundle{payload: AnnData|DataFrame, kind, source, path, meta}  [engine/ingest.py]
  -> classify (L1 payload type -> L2 column signature -> GENERIC_TABLE|UNKNOWN)  [engine/databundle.py]
  -> run_qc -> QCReport{flags(block|warn|info), stats}                          [engine/qc.py]
  -> profile_data + plan_cleaning (advisory; not persisted, not enforced)       [engine/cleaning.py]
  -> route_profile / route_data -> suggested skills                             [engine/route.py]
  -> [422 gate if qc.blocked and not override]                                  [main.py:499]
  -> run_bundle_with_table(skill_id, bundle.path, params)  ## skill RE-OPENS the file  [skills/contract.py:106]
  -> theme.apply -> capabilities.stamp (meta.selom.capabilities)                [skills/theme.py, _capabilities.py]
  -> {figure, table} -> bundle{figure, provenance, methods, guardrails, table}  [jobs/queue.py:43]
  -> result_store.put(job_id) -> data/results/{job_id}.json | R2               [storage/results.py]
  -> FE: localStorage Figure{spec, provenance, table, ...}                      [lib/projects/store.ts]
  -> FE: deriveFigureModel(spec) -> resolved model -> editor panes              [lib/figure-model.ts]
```

The same skeleton should apply to lookup, analysis, combine, and reproduction. A route or pane
that cannot be mapped to this chain is a drift candidate.

## Backend route inventory + bounds

Source: `app/backend/main.py` (+ routers). Cap `max_bytes = settings.max_upload_mb*1MB`
(default 512), checked **after** `UploadFile.read()` in `_save_capped` (main.py:152).

| Route | Purpose | Bounds today | Expensive | Gate |
| --- | --- | --- | --- | --- |
| `GET /health`, `/skills`, `/skills/{id}` | Liveness, live skill catalog | — | No | — |
| `GET /gene-sets`, `POST /gene-sets/compile`, `GET /gene-sets/{id}` | Gene-set catalog/compile | q ≤ 50; compile set_ids unbounded | No | Bound compile input |
| `POST /data/inspect` | ingest+classify+QC+plan+route | size cap | **Yes** | p50/p95; reuse via input cache |
| `POST /data/combine` | ERG multi-file merge | size cap per file | **Yes** | Move to analytical lane; record the merge |
| `POST /skills/{id}/run` | single skill, sync | size cap; **no exec timeout; param ranges not enforced** | **Yes** | timeout + range-validate + result cache |
| `POST /skills/{id}/jobs`, `GET /jobs/{id}`, `/events`, `/result` | async skill (inline\|arq) | SSE ≤ 600 ticks @0.5s | **Yes** | persist job state (in-memory today) |
| `POST /papers/{id}/assess-data`, `/reproduce`, `GET /papers/{id}`, `/scorecard` | reproduction drive | size cap per file | **Yes** | per-panel run records; ownership checks (future) |
| `POST /papers/route`, `/papers/extract`, `/extract/chart` | routing, PDF/chart extract | text unbounded; image unbounded | route No / extract **Yes** | bound text + image inputs |
| `POST /methods/compose`, `GET /citations/*`, `/papers/metadata/by-doi` | methods + citation lookup | runs list unbounded; cached/throttled | Low–Mod | bound list; verify cache TTLs |
| `POST /figures/export` | Kaleido PNG/SVG/PDF | spec JSON | **Yes** (headless Chrome) | timeout + payload ceiling |
| `POST /figures/style/apply`, `GET /figures/styles`, `/export/presets` | live style preview, catalogs | spec JSON | Mod | — |

**Bounds gaps (SCALE):** no app-level rate limiting; no skill-execution timeout (a hung skill
blocks a worker forever); size cap checked *after* the file is buffered in memory; param
`min/max/options` in `param_spec` are **metadata only** — a caller can pass `fc_threshold=100`
on a `max:5` param and the skill runs (no 400). (`skills/contract.py resolved_params`.)

## De-facto schema (entities today, + the table set for the DB launch)

**FE-owned (localStorage, keys `selom.projects.v1` / `selom.workspace.v1`):**

| Entity | Where | Key fields | Relations |
| --- | --- | --- | --- |
| `Project` | `lib/projects/types.ts` | id, name, color, createdAt | 1:N datasets/figures/installs |
| `Dataset` | same | id, projectId, filename, modality, currentSha256, qc | N:1 project; N:1 (ephemeral bytes) |
| `SkillInstall` | same | id, projectId, skillId | N:1 project; N:1 skill |
| `Figure` | same | id, projectId, datasetId?, skillId?, spec, provenance, methods, table, dataCheck, dataFit, parentFigureId?, variantLabel?, frozen | N:1 project/dataset/skill; self-FK (variants) |
| `GeneSet` | same | id, name, genes[], source, license, createdFrom | account-level (workspace) |
| `SavedPaper` / `SavedSupplement` / `WorkspaceSkill` | `lib/workspace/types.ts` | paper metadata + reproductionRunId + supplements[] | workspace-scoped |

**BE-owned (in-memory / ephemeral):**

| Entity | Where | Persistence |
| --- | --- | --- |
| `DataBundle{payload, kind, source, design, qc, meta, path}` | `engine/databundle.py` | in-memory; deleted post-run |
| `SourceRef`, `Design`, `QCReport`, `QCFlag` | `engine/models.py` | embedded; QC optionally returned to FE |
| `Job{id, skill_id, status, params, result_url, error}` | `jobs/store.py` | **in-memory dict** (Redis in arq mode) |
| Result bundle `{figure, provenance, methods, guardrails, table}` | `storage/results.py` | `data/results/{id}.json` or R2 (one blob) |
| `Golden`/`Panel`/Ledger (reproduction) | `reproduction.py` | one JSON per paper |

**Missing / undermodeled entities (the intermediate-table skeleton the owner wants):**
`CleaningRecipe` (steps are display-only, never persisted), `IntermediateTable` (cleaned/
normalized matrices are ephemeral — no `post_qc`/`post_normalization` artifact, no lineage),
`Run` (implicit in Job+result; no queryable record), a normalized result schema (results are
JSON blobs → "which skills best on modality X?" needs a full scan), `MergedDataset` (combine is
ephemeral; "merged from {A,B,C}" is lost), and `skill_version` in a queryable place.

**The DB-launch table set** (Task F; FE types are already shaped for this — "impl change, not FE
rewrite"): `workspaces · projects · datasets · intermediate_tables · cleaning_recipes ·
skill_runs · figures · gene_sets · papers · supplements`, each with FKs + RLS; **bytes/Parquet in
R2**, **rows/metadata/lineage in Postgres** (research B4).

## FE bespoke machinery + the switch/crash seams

**The spine that already works (MAINTAIN/IMPLEMENT — keep + extend):**

- **Per-skill param registry** `lib/catalog/params.ts` — `PRESENTATION[skillId]` overlays
  (label/help/widget/showWhen) merged with the backend `param_spec` by `paramFieldsFromSpec`;
  `visibleParamFields` does conditional reveal; `warnDeadKnob` flags overlay drift (dev only).
  Adding a skill's controls = a data entry. ✅ extensible.
- **Capability/figure-model resolution** `lib/figure-model.ts` — `deriveFigureModel(spec)` →
  resolved `model.capabilities`/`model.gesture` from `meta.selom.capabilities` (declared) +
  inferred floor; panes read the resolved model, never raw spec. ✅ the generic-spine rule.
- **Figure store** `hooks/use-figure-store.ts` — JSON-Patch present/past/future + checkpoint
  (live preview vs one undo entry); 60-entry history.
- **Per-chart plug-ins behind capability flags** — `lib/{volcano,heatmap,erg}/*` +
  `components/figure/{mark,threshold,colorbar,dendrogram}-drag.ts`, each gated on a declared
  capability, not a skill-id branch. ✅ the `[[generalize-via-flagged-plugins-over-shared-spine]]`
  pattern.

**The seams where it breaks (FUTURE-PROOF / SCALE — the switch-crashes):**

| Seam | Where | Risk | Lens |
| --- | --- | --- | --- |
| **No per-pane error boundary** | inspector panels, `property-panel.tsx`, `panels/*` | one bespoke pane throwing unmounts the whole editor | FUTURE-PROOF |
| **No spec-boundary validation** | store `init` / panel render | a pane built for skill A receiving skill B's spec reads undefined → crash (e.g. `ColorscaleControls` on a spec with no heatmap trace → `tone.zmin` on null) | FUTURE-PROOF |
| **Staged `fdParams` scoped to figure, not skill** | `project-workspace.tsx` (reset on `activeFigureId`) | params from skill A persist; on a failed re-run / same-skill switch the next run silently uses stale values | MAINTAIN |
| **Panels assume data present** | `style-panel.tsx`, `data-panel.tsx`, threshold/marks editors | `cap.thresholds=true` but no points → empty/undefined readout; no "no data yet" state | FUTURE-PROOF |
| **No stable skeleton states** | most panes | only ad-hoc booleans; no `idle/empty/partial/stale/error/ready`; `property-panel` returns `null` (sidebar vanishes) instead of a slot | FUTURE-PROOF |
| **Capability declared but unmatched** | `figure-model.ts` | a figure can declare `thresholds:true` with no up/down traces; `landmarkMarks` falls back to `meta.selom.marks` → a new ERG skill that forgets the declaration still renders dots but the editor doesn't gate the panel | MAINTAIN |
| **Registry drift only warns** | `params.ts warnDeadKnob` | an overlay/capability key with no backing `skill.json` is dropped silently (dev console only) — no CI gate | IMPLEMENT |
| **Param-spec fetch fail-soft + no timeout** | `use-skill-params.ts` | backend slow/down → "Loading inputs…" forever or zero controls with no error | SCALE |
| **WebGL/listener leaks across switches** | `figure-canvas.tsx` (react-plotly.js) | no `Plotly.purge` on unmount; data/layout rebuilt each render can re-init the plot; mounting many `scattergl` panes hits the ~8–16 context cap | SCALE |

**Known crash history (the edge cases the owner means), all real:** Radix `SelectItem` empty-string
value → runtime crash (fixed with a `__none__` sentinel); `NaN` is invalid JSON → spacer/sparse
cells must be Python `None` (`skills/_plotly.jsonable` doesn't sanitise); title-less furniture axes
→ Plotly "Click to enter axis title" placeholders → drop `axisTitleText` when secondary axes
present; a raw `import("plotly.js")` 500'd SSR → keep WebGL behind `dynamic(ssr:false)`. Each was a
*bespoke-pane-meets-unexpected-shape* failure — the class Spine 3 closes structurally.

## Cache / source boundary inventory

| Cache / artifact | Today | Should be |
| --- | --- | --- |
| Input payload | **none** — same file re-parsed across `/data/inspect` + `/skills/{id}/run` | input cache keyed by `input_sha256` |
| Result (compute) | **none** — every run recomputes | content-addressed `(skill+version, params, input_hash)` → stats table + numeric series |
| Rendered figure (envelope) | **none** | `(result_hash, theme_version, render_params)` — reuse compute on a cosmetic/theme change |
| Result store | `data/results/{id}.json` (one blob) or R2 | the durable artifact = Parquet result + JSON spec under the content hash on R2 |
| Job state | in-memory dict | a `skill_runs` row (survives restart, queryable) |
| Analytical lane | pandas in-memory for combine | DuckDB-over-Parquet for combine/cohort/freshness (ratified) |

The content hash is the spine: **cache key = ETag = idempotency key = medallion address** —
one object-store of content-addressed artifacts, indexed by Postgres rows, scanned read-only by
DuckDB.

## Data substrate + intermediate-table gaps

- **No canonical table contract**: skills re-open `bundle.path` and re-parse; only 3 skills have
  named-column schemas (`engine/compat.py _SCHEMA`); a skill needing a `gene` column when the file
  has `symbol` fails *at runtime*, not at a pre-run check. (SCALE/MAINTAIN.)
- **Intermediates ephemeral**: post-QC / post-cleaning / post-normalization matrices live only in
  `DataBundle.payload` during a run and are discarded; no `IntermediateTable`, no lineage, no
  "inspect the matrix the skill actually saw." (SCALE/FUTURE-PROOF.)
- **Cleaning is advisory**: `plan_cleaning` proposes steps; the FE `CleaningStep[]` is display-only;
  no "commit cleaning" → figures aren't reproducible from a *cleaned* table. (MAINTAIN.)
- **Combine is ephemeral**: `ingest_many` merges in memory and returns a CSV; the "merged from"
  receipt is never stored. (SCALE.)
- **Provenance is incomplete**: records skill/params/input.sha256/env but **not** the engine
  (stub vs real), the accepted cleaning, the overridden QC flags, or the design used. (MAINTAIN.)

## The extensibility test (FUTURE-PROOF — "adding the next feature")

The owner wants new skills/features/upgrades to slot in cheaply. Score each addition against the
**fill-in-the-blanks** test — does it touch only declared data + a thin plug-in, or does it edit
the generic spine?

| Adding… | Today | After the gate |
| --- | --- | --- |
| A new skill's **params** | ✅ data entry in `params.ts` + `skill.json` | same (+ CI audit so a typo'd key fails the build, not just warns) |
| A new skill's **editor tools** | ⚠️ a capability profile (only 2 skills have one) + a plug-in | ✅ every interactive skill declares a profile; the generic canvas/inspector unchanged |
| A new **chart kind** | ✅ pure transform + drag plug-in behind a flag (heatmap/volcano/ERG done) | same + a declared table contract + an auto stable-skeleton state |
| A new **input format** | ✅ a loader/recognizer in the ingest registry | ✅ + it emits the canonical table contract, so all downstream stages work unchanged |
| A new **section/page/metric** | ⚠️ bespoke wiring (render + nav + export each hand-edited) | ✅ one registry entry drives render + nav + export + preflight + its state machine |
| A new **analysis stage** (e.g. enforced cleaning) | ❌ no intermediate-table slot to hang it on | ✅ a bronze→silver→gold tier with a content-addressed artifact + a frame contract |

The first three rows are already good (the moat). The gate's job is to make the **last three** the
same fill-in-the-blanks shape — that is the future-proofing.

## Findings requiring action (prioritized)

1. **Stable-skeleton + error isolation at the pane boundary is the next consistency fix and the
   direct switch-crash fix.** State machines + per-pane error boundaries + spec-boundary validation
   + `key`-remount + skill-scoped staged params. FE-only, no DB. *(Plan Task B — recommended first.)*
2. **No cache boundary.** Content-addressed result cache + source/render split + ETag/304; an
   identical re-run must not recompute, a theme change must not re-run the skill. *(Task C.)*
3. **No canonical table contract / intermediate-table lineage.** One declared table contract every
   skill consumes; medallion intermediates; frame-validation at seams. The substrate for the DB
   launch. *(Task D.)*
4. **No server-side source of truth.** localStorage + JSON blobs + in-memory jobs won't survive
   multi-user; needs the Supabase schema + RLS + the R2 object boundary. *(Task F.)*
5. **"No perf issues / no leaks" is unproven.** Needs render-timing, payload ceilings, heap-snapshot
   leak hunts across switches, `Plotly.purge`/`useMemo`, and a fast/slow test split. *(Task E.)*
6. **Bounds + validation gaps at the API.** Param-range enforcement, skill-execution timeout,
   app-level rate limiting, input-size cap before buffering. *(Task C/F.)*
7. **Registry drift only warns.** Promote `warnDeadKnob` + capability-vs-`skill.json` checks to a
   CI gate so a missing/renamed param can't ship silently. *(Task B.)*

## Read-only verification checklist (before any "production-ready" claim)

- Fast contract gate green: param/capability registry audit, table-contract guard, golden
  byte-identity, figure-model resolution, vitest/pytest focused subsets.
- Browser preflight: open every skill's figure, switch dataset↔skill 20×, assert no crash + no
  heap growth (detached canvases/listeners) + stable skeletons.
- p50/p95 + peak heap recorded for cold/warm run, lazy section, full editor.
- Secret/env scan for client-bundle exposure; (at DB launch) Supabase advisors + RLS + index review.
- DuckDB/Parquet lane disabled/missing/ready health is sanitized; no startup/request downloads.
- No remote DB/Render/Supabase mutation without explicit owner approval.

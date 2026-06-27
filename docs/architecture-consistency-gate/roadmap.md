# Selom Architecture Gate — Agile Roadmap

Last updated: 2026-06-27 22:52 +10:00 — Claude.
Status: **Active lane.** Owner greenlit the gate (2026-06-25): "stick with this plan…
go with your recommended task… this is the lane until it is mostly complete; other
tasks/plans/pillars on hold." Companion to `plan.md` (why) + `inventory.md` (current state).

This file answers: *is the plan robust and broken into agile buckets completable across
sessions?* — **Yes.** Each bucket below is one ship-and-verify slice (≈ a session),
independently shippable, with its own acceptance gate, mirroring how the heatmap slices
ran. Buckets within a task are ordered; tasks run B → C → D → E, with F at the web launch.

## The database-materialization line (read first — owner's flag)

> Owner: *"let me know if it needs database materialisation at some point… don't let it be
> the blocker."*
>
> **⚠ DISCUSSION GATE (owner 2026-06-27):** *"prior to reaching the database work we need to
> discuss something as there may be a change of plans in that regard, but complete all the work
> prior until then."* → **Complete every DB-free bucket first** (B5 · Task B exit · C1–C3 · C5 ·
> D1–D3 · E1–E2), then **STOP and raise it with the owner before starting ANY materialization
> bucket (C4 · D4 · F1–F3)** — the DB approach itself may change, so do not begin that work or
> pre-commit to the Supabase/R2/DuckDB shape until the discussion happens.

**Everything in Tasks B, C, D1–D3, and E is database-free and can complete now.** They use
the existing in-process / local-disk substrate. The DB/object-store materialization line is:

| Needs materialization? | Buckets | Status |
| --- | --- | --- |
| **No — do now** | B1–B5 · C1–C3 · D1–D3 · E1–E2 | the lane |
| **Yes — DEFERRED, flagged, NOT a blocker** | **C4** (R2 cache tier) · **D4** (DuckDB/Parquet lane) · **F1–F3** (Supabase schema, FE-state migration) | on hold until the web/DB launch; the upstream buckets are designed so the local version drops into the materialized one with no rework (content-addressed local dir → R2 object; declared table contract → Parquet schema; FE types → SQL rows) |

When a bucket starts to *want* materialization (it'll be D3 hardening, then D4), stop and
flag it — the gate is built so the work in front of it never waits on it. Per the discussion
gate above, that flag is now a **hard stop for an owner conversation**, not just a heads-up.

## Definition of done (every bucket)

A bucket is done when: scope shipped · `tsc`/`eslint`/`vitest` (FE) or `pytest`/`ruff` (BE)
green · the named **acceptance** holds · live full-app verify on real data where it touches the
running app (`[[full-app-smoke-test-before-handoff]]`) · committed (owner pushes) · `CURRENT.md`
+ this roadmap's checkbox updated. Same ratchet as the figure-editor slices.

---

## Task B — FE stable-skeleton + registry consistency  ·  lane: FE (Claude)  ·  DB-free

The direct fix for the dataset/skill **switch-crashes**. Hardens the bespoke panes; builds no
new surface — it makes the existing surface unbreakable.

| # | Bucket | Scope | Acceptance | Size |
| --- | --- | --- | --- | --- |
| **B1** | Per-pane crash isolation | A granular error boundary around each inspector panel · the figure-data panel · the canvas · the stats table, with `resetKeys=[datasetId, skillId, figureId]` + a friendly fallback. | Force a bad spec into one pane → only that pane shows the fallback; editor + siblings stay live; switching data/skill auto-resets the boundary. | ~1 |
| **B2** | Fail-safe at the spec→component seam | One `validateFigureContract(spec)` guard at store `init` + null-safe `readTones`/`readThresholds`/`readSeededMarks`; an unknown/partial spec routes to an `empty`/`error` state, never a throw; an unknown section type hits a default fallback renderer. | A heatmap-less spec with `cap.colorscale` set renders "no heatmap trace", not a crash; a volcano with no points renders "no points yet". | ~1 |
| **B3** | Pane state machine + stable skeletons | A `PaneState` discriminated union (`idle\|loading\|empty\|partial\|stale\|error\|ready`) + a shared `<PaneShell>`; convert the panes that return `null` / assume data (property-panel, figure-data-panel, colorscale/threshold/marks editors) to render a stable slot from the state tag; param-spec fetch gets a timeout + error state. | Every pane always renders the same outer shape; "loading inputs" vs "no inputs" are distinct; a slow/failed param-spec fetch shows an error, not an infinite spinner. | ~1–2 |
| **B4** | Skill-scoped staged params + switch hygiene | Scope `fdParams` to the active **skill** (reset on skill change, not just figure); `key={dataset:skill}` remount where stale state leaks; derive-don't-sync cleanup in `project-workspace`. | Run volcano fc=2, fail the re-run, switch to heatmap and back → no stale fc; a switch never carries another skill's params into a run. | ~1 |
| **B5** | Registry-completeness CI gate | A test asserting every `params.ts` overlay key **and** every declared `_capabilities` tool has a backing `skill.json`; promote `warnDeadKnob` drift from a dev console warn to a failing audit. | A typo'd/renamed param or capability fails CI, not just a console warn. | ~0.5 |

**Task B exit:** open every skill's figure, switch dataset↔skill 20× → zero crashes, every pane a
stable slot, no stale-param leak, a heap snapshot flat across switches (overlaps E1). **✅ PASSED
2026-06-27** — see the Progress entry below.

## Task C — Cache / source boundary  ·  lane: BE (Codex; Claude covers while away)  ·  DB-free (R2 tier deferred)

The "faster / cleaner execution / caching strategy" ask. Content hash from `plan.md` Spine 4.

| # | Bucket | Scope | Acceptance | Size |
| --- | --- | --- | --- | --- |
| **C1** | Content-addressed result cache (L1+L2) | Key = `(skill_id+version, canonical(params), input_sha256)`; canonicalize params (stable serialize · sorted keys · float/precision coercion · drop-defaults); in-proc LRU + a **local-disk JSON tier** (dependency-free — content-addressing makes `diskcache`'s eviction/concurrency machinery unneeded for an immutable cache, and avoids a venv dep; a future R2 tier (C4) swaps the disk backend behind the same interface); invalidate by `skill_version` bump (no TTL — the version is in the key). | An identical re-run is a measured cache hit (no recompute); a `skill_version` bump misses cleanly. | ~1 |
| **C2** | Source/render split + ETag/304 | Separate the compute cache (above) from the figure-envelope cache `(result_hash, theme_version, render_params)`; `ETag` = content hash on figure GET, honor `If-None-Match` → 304. | A theme/style/label change re-renders **without** re-running the skill; a repeat GET is a 304. | ~1 |
| **C3** | Input cache + param-range + exec timeout | Cache the parsed input by `input_sha256`; enforce `param_spec` min/max/options at the API (400 on out-of-range); add a per-skill execution timeout. | `fc_threshold=100` on a `max:5` param → 400; a hung skill times out instead of pinning a worker; the same file isn't re-parsed across `/data/inspect` + `/run`. | ~1 |
| **C4** | R2 object-store tier ⚑ | Promote the durable cache layer to R2 (Parquet result + JSON spec under the content hash). | — | **DEFERRED (materialization)** |
| **C5** | Param-spec caching (don't re-fetch the immutable) | The `param_spec` is immutable per `skill_version`, yet the Figure-data Inputs re-fetch it on every open (so the "renders with no backend" figures can't show their inputs, and B3 must show an error there). Cache it: **(A, FE-only)** persist fetched specs to localStorage keyed by `skill_id`+version and seed `useSkillParams` from it (instant + offline after first fetch); **(B, cross-lane)** stamp `param_spec` into each figure's provenance at run so the figure is self-describing forever. B3's error/Retry stays as the floor. *(Owner 2026-06-26: file for Task C, not B3. Surfaced during B3 verify — the "no backend → /api/skills/{id} fails" question.)* | A re-opened figure shows its inputs with **no** describe round-trip; an offline already-run figure shows tunable inputs (re-run still needs the backend). | ~1 |

## Task D — Canonical table contract + analytical lane  ·  lane: BE  ·  D1–D3 DB-free, D4 deferred

Spine 1 — the owner's "always a table; intermediate tables." The substrate for the DB launch.

| # | Bucket | Scope | Acceptance | Size |
| --- | --- | --- | --- | --- |
| **D1** | Declared table contract per skill | Each skill declares the input column groups it needs (extends the existing skill-table-contract guard); a pre-run validator surfaces "missing column X for this skill" before running; FE shows it on the data-fit/intake surface. | A DE skill dropped on a counts table gets a clear pre-run message, not a runtime stack trace. | ~1–2 |
| **D2** | Frame-validation at stage seams | A named frame schema per stage output (`CleanedTableSchema`, a per-skill result schema); validate ingest→clean→skill boundaries `lazy=True`; failure → 400 (mirrors the existing ValueError→400 path). | A malformed clean→skill handoff fails at the seam with a clear 400, not a downstream crash. | ~1 |
| **D3** | Intermediate-table lineage (local) | Materialize cleaned/normalized tables as **content-addressed** artifacts (local dir now) with parent-hash lineage in embedded metadata; record the cleaning recipe + the merge receipt. | "Inspect the matrix the skill actually saw" works; a cleaned re-run is reproducible; combine records "merged from {A,B,C}". | ~1–2 |
| **D4** | DuckDB/Parquet lane, tiny-fixture preflight ⚑ | Artifact layout + manifest + checksum + read-only health only; no multi-GB build. | — | **DEFERRED (materialization)** |

## Task E — Performance + memory proof  ·  lane: FE+BE  ·  DB-free

| # | Bucket | Scope | Acceptance | Size |
| --- | --- | --- | --- | --- |
| **E1** | Plotly leak hardening | `Plotly.purge` on unmount; `useMemo` the data/layout refs; audit `dynamic(ssr:false)`; cap simultaneous `scattergl` panes (WebGL context budget). | 20 dataset/skill switches → no detached-canvas/listener growth in a heap-snapshot diff. | ~1 |
| **E2** | Telemetry + test hygiene | Render-timing + payload-size ceiling + a perf-audit script; formalize the fast (named contract gate) vs slow (real-engine/browser/perf) test split. | p50/p95 + peak heap recorded cold/warm; a feature commit runs the fast gate in seconds. | ~1 |

## Task F — Database / production readiness ⚑  ·  lane: BE  ·  DEFERRED (web/DB launch)

**On hold until the web/DB launch — flagged, not a blocker.** F1 Supabase schema + RLS + FK/composite
indexes (the `inventory.md §3` table set) · F2 migrate FE state localStorage→server · F3 the vault
**adopt-now-5** security lifts (JWT-verify middleware + key hygiene can be brought forward partially).
Nothing here gates Tasks B–E; the upstream buckets are shaped so F is a wiring step, not a rewrite.

---

## Sequencing across sessions

```
NOW ───────────────────────────────────────────────────────────────▶ web/DB launch
 Task B (crash fix, FE)      Task C (cache, BE)      Task D1–D3 (table contract)   E1–E2 (proof)
 B1 ▸ B2 ▸ B3 ▸ B4 ▸ B5  ──▶ C1 ▸ C2 ▸ C3       ──▶ D1 ▸ D2 ▸ D3            ──▶  E1 ▸ E2
                                                                                      │
                          (deferred, owner-gated, needs materialization) ────────────┘
                              C4 · D4 · F1 · F2 · F3
```

B is first (closes the crashes, FE-only, no DB). C and D1–D3 can interleave once B lands. E runs
alongside/after as the proof. The deferred buckets wait for the explicit data-architecture greenlight.

## Progress

- [x] B1 (impl + tsc/eslint/vitest green, commit `322228c`; **browser live-verified 2026-06-25** on
  real B5 iRPE clustermap — a `?b1throw` probe forced a StylePanel throw: the Style pane showed its
  local fallback while the 11-trace canvas + Axes/Legend/Data/Page tabs + toolbar + skill card stayed
  live [console: "handled by the <ErrorBoundary>"], and switching to a plain heatmap auto-cleared the
  boundary [resetKeys=[spec]] → Style re-rendered. Probe reverted, tree clean. ⚠ Turbopack
  `0xc0000142` recurred even in a fresh shell → ran the dev server on **`npx next dev --webpack`** as
  the env workaround)
- [x] B2 (fail-safe at the spec→component seam; tsc/eslint green, vitest **284** [+15]; **browser
  live-verified 2026-06-25** on the B5 iRPE project). New pure `lib/figure/contract.ts`:
  `validateFigureContract` coerces ANY input (null/string/array/partial) to a render-safe
  `{data,layout}` so the figure-store `init` NEVER throws (wired in `use-figure-store.ts`;
  `normalizeSpec` also hardened as defense-in-depth); `heatmapColorscaleState` resolves the heatmap
  colour-scale section to `ready|empty|hidden` so a non-heatmap colorscale (trajectory/markers) stays
  hidden as before. The 3 named readers (`readTones`/`readThresholds`/`readSeededMarks`) confirmed
  null-safe + locked with seam tests. **Both acceptance cases verified live** via a `?b2probe`-gated
  contrived spec (declares heatmapTones+thresholds, no heatmap trace, empty volcano buckets): the Style
  tab rendered **"No heatmap trace in this figure."** and the Figure-data ThresholdEditor rendered
  **"No points yet…"** — editor + siblings stayed live, console clean. No-regression confirmed (a real
  iRPE clustermap still shows the full Colour-scale controls, state `ready`). Probe reverted,
  `project-workspace.tsx` byte-identical to HEAD.
- [x] B3 (pane state machine + stable skeletons; tsc/eslint green, vitest **288** [+4]; **browser
  live-verified 2026-06-26** on the B5 iRPE project). New pure `lib/ui/pane-state.ts` — the
  `PaneState` discriminated union (`idle|loading|empty|partial|stale|error|ready`) + predicates
  (`hasData`/`isPending`/`isDegraded`); new `components/ui/pane-shell.tsx` `<PaneShell>` renders a
  stable outer shape per tag (loading→skeleton · empty→note · error→message+Retry · partial/stale→
  content+note). `useSkillParams` gained an **8s fetch timeout + AbortController + an `error` status +
  `retry()`** (cache entry evicted on failure so Retry re-fetches) — the fix for the infinite "Loading
  inputs…" spinner; `{fields,loading}` kept back-compatible for sweep-form/workbench-panel. The
  Figure-data **Inputs** pane renders loading/empty/error/ready through `<PaneShell>`; `property-panel`'s
  `!spec` `return null` became a stable empty shell. **Verified live**: a dead-backend proxy gave the
  error state + Retry (no infinite spinner), in the same Inputs card; starting the backend + Retry
  rendered the real param controls (`ready`). No store-mutating probe this pass → B5 fixture untouched
  (8 figures intact). **Filed C5** (param-spec caching) per owner — the "no backend → fetch fails"
  dependency is reducible (cache the immutable spec); B3's error/Retry is the floor.
- [x] B4 (skill-scoped staged params + switch hygiene; tsc clean · eslint **0-err** [27 warns, **−1 vs
  HEAD** — the removed effect's setState-in-effect warning] · vitest **288**; commit `f77e0c1`; **browser
  live-verified 2026-06-26** on real localStorage fixtures, webpack dev, **no backend**). The reset-from-
  figure `useEffect` (`project-workspace.tsx`, keyed only on `activeFigureId`, eslint-disabled, one-frame
  flash) → a **derive-don't-sync during-render reset** keyed on `fdScope = dataset:skill:figure` (React's
  "store info from previous renders" pattern); `key={fdScope}` remounts the bespoke `FigureDataPanel` on
  any switch + the preview/inputs `PaneBoundary` resetKeys widen to `[datasetId, skillId, figureId]`.
  **Acceptance verified live** in the two-version volcano project `p_3384a01f`: staged **fc 1→2** (counts
  re-bucketed live 607/334→142/53) → **Re-run FAILED** (no session bytes → re-upload halt, staged fc=2
  KEPT, **no new version** — 2 in store) → switched to the **fc=3** version (reset to 3, no banner) →
  **back** to the fc=1 version (**reset to 1 — no stale fc=2/3**, counts back to 607/334). Plus a genuine
  **cross-skill** switch in `p_7821cab4` (`erg_intensity_response` ↔ `erg_traces`): the Figure-data pane
  remounted to the correct skill, **no crash / no boundary trip**, console clean (only the expected
  param-spec 404 = B3's error state). **No store-mutating probe** (drove the real UI) → fixtures intact
  (22 figures, volcano fc=[1,3] unchanged).
- [x] B5 (registry-completeness CI gate; **cross-lane — FE vitest + BE pytest**; tsc/eslint 0-err, vitest
  **293** [+5], BE `test_capabilities` **8** [+2]; **red-then-green verified, no browser needed**). Promotes
  the `warnDeadKnob` dev console warning to a FAILING test. **The spine** = the backend `skill.json` param_spec
  + `list_skill_ids()`; two FE/BE mirrors are each validated against it in their own lane's fast gate
  (reachability picks the home): **FE** `lib/catalog/registry-completeness.test.ts` reads the REAL skill.json
  via `node:fs` (the cross-lane read IS the point — the test exists to catch FE↔BE contract drift) → every
  `params.ts` PRESENTATION overlay key backs a real param_spec entry · every overlay skill has a backing
  skill.json · the `dev:mock` fixture renders the same controls as live · no stale fixture key; **BE**
  `tests/test_capabilities.py` → every `_capabilities._PROFILES` skill id ∈ the registry · every declared
  capability tool ∈ the FE-known allow-list (mirrors `figure-model.ts` `SelomCapabilities.tools`). New export
  `params.ts::overlayParamKeys()`. **Drift FIXED en route** (the gate's first catch): the `SKILL_PARAM_SPECS`
  dev:mock fixture was stale — missing the heatmap clustermap controls (`cut_k`/`annotations`/`quant_track`/
  `split_by`/`split_by_cut`) and the ERG mean/spread (`central`/`spread`/`error`/`band_*`/`boundary_lines`/
  `error_every`), bar-significance (`wave`/`show_error`/`error`/`bar_fill`/`legend`/`comparisons`/`sig_test`/
  `hline`/`hline_label`) + flicker `marks` controls → brought current so dev:mock matches live. **Red proof:**
  `volcano.highlight`→`highlightz` → FE red ("overlay keys absent from the backend param_spec: volcano.highlightz");
  volcano tool `thresholds`→`thresholdz` → BE red ("declares capability tool(s) {'thresholdz'} the FE can't
  resolve") — both reverted, green. ruff **clean** (`-m ruff` / direct `.venv/Scripts/ruff.exe` are
  EDR-blocked → ran via the documented copy-to-TEMP workaround `cp .venv/Scripts/ruff.exe $TEMP && $TEMP/ruff.exe`
  [[selom-backend-python-exec]]). **Task B code COMPLETE
  (B1–B5); NEXT = Task B EXIT smoke** (open every skill's figure, switch dataset↔skill 20× → zero crashes,
  stable slots, no stale-param leak, flat heap — overlaps E1; needs a browser pass).
- [x] **Task B EXIT smoke** (capstone; **browser-driven via chrome-devtools MCP, 2026-06-27** on the
  cleaned localStorage fixtures, webpack dev, **no backend** — so every analysis-input pane correctly
  shows B3's `error` slot [param-spec describe 404], the floor, not a crash). **~150 dataset/skill/view
  switches** driven through the REAL UI (programmatic clicks → real React handlers) across **all 5
  skills**: `erg_traces` + `erg_intensity_response` (p_7821cab4, SVG, 2 skills × multiple datasets),
  `volcano` (p_3384a01f, **WebGL scattergl**), `heatmap`/clustermap (p_fb5166e1, SVG + dendrogram +
  annotation strips), and the legacy no-spec `umap` (demo-pbmc → B2 "Figure spec not stored" empty
  state). **Acceptance, all four met:** (a) **zero crashes / zero boundary trips** — `role=alert`
  "rest of the editor is fine" never appeared; console carried only the expected param-spec 404s, **no
  `[error-boundary]`, no React/Plotly/WebGL errors, no "too many active WebGL contexts"**; (b) **every
  pane a stable slot** — `data-pane-status` resolved to loading→error→ready, empty states rendered
  ("Figure spec not stored", "Re-run to generate", "No points yet"), never `null`; (c) **no stale-param
  leak (B4)** — staged a distinctive `fc=5` on the volcano fc=1 version, switched to the fc=3 version →
  it showed its **own** base (3) with **no pending banner**, and returning to v1 reset to 1 (the
  abandoned stage discarded; `fdScope` reset + `key={fdScope}` remount confirmed); (d) **heap flat
  across switches (E1 overlap)** — measured the delta between TWO post-GC measurements *after* Plotly's
  one-time module load (the 87→190 MB jump is that load, permanent, not a leak): **SVG/ERG 190.65 →
  189.53 MB** over 60 switches, **WebGL/volcano 195.52 → 195.68 MB** over 48 switches; canvas count
  capped at 3 for scattergl and returned to **0 at home** every time (react-plotly purges on unmount),
  snapshot files flat (76.2 → 74.4 MB). Fixtures intact afterward (7 projects / 18 figures / 16
  datasets, no re-runs since no backend). **⚑ Task B fully COMPLETE (B1–B5 + exit). NEXT = Task C
  C1–C3 + C5** (cache/source boundary, BE/cross-lane; all DB-free — see the discussion-gate stop before
  any materialization bucket).
- [x] C1 (content-addressed result cache; **BE; pytest-verified, no browser**; ruff clean). New pure
  **`skills/_result_cache.py`** — a two-tier (in-proc LRU + local-disk JSON under `data/result_cache/`)
  content-addressed store keyed by `(skill_id+version, canonical(params), input_sha256)`. `canonical_params`
  overlays caller params on skill defaults, coerces each to its `param_spec` type (so a string query arg
  hash-equals the typed default), **drops any param equal to its default**, rounds floats to a stable
  precision, and hashes reserved `_`-prefixed **file** params by content (so two runs with different
  `_design_path` sheets don't collide). Wired into `skills/contract.py::_execute` (the one chokepoint every
  `run_skill*`/`run_bundle*` funnels through) — it caches the **pre-theme compute output** and re-applies
  `theme.apply` on every hit (cheap, deterministic; `theme.apply` deep-copies its input → no mutation), which
  is forward-compatible with C2's source/render split. **Invalidation is automatic** (the version is in the
  key → a bump is a clean miss; no TTL). Cache entries are isolated from callers in both directions
  (deep-copy on `set` and `get`). Two config knobs (`SELOM_RESULT_CACHE=on|off`, `SELOM_RESULT_CACHE_MEM_MAX`).
  **Dependency-free deviation from the roadmap's named `diskcache`** (owner asked "should it be installed?" —
  no: content-addressing makes its eviction/concurrency machinery unnecessary for an immutable cache and it'd
  mutate the EDR-fragile venv; a future R2 tier (C4) swaps the disk backend behind the same interface).
  **Gates:** `tests/test_result_cache.py` **15** (canonicalization · key stability/version-sensitivity ·
  input-byte tracking · two-tier round-trip + disk-survives-restart + LRU eviction + caller-isolation +
  disabled-flag · **acceptance**: an identical re-run is a measured `mem_hits` with the runner **not**
  re-entered (a call-counter proves no recompute), a non-default param and a `skill_version` bump each miss
  cleanly · a real stub-engine skill caches end-to-end through the genuine `_execute`/`theme.apply`/stamp path);
  contract+capabilities **58**, golden+integration **67** all green. New **`tests/conftest.py`** disables the
  cache suite-wide (autouse) so the golden tests still recompute — a content-addressed cache surviving on disk
  would otherwise serve a stale figure (false green) when a skill changes without a version bump; the cache's
  own tests opt back in. ⚠ a missing input path (the golden harness's `"unused"`) is unhashable → the cache is
  skipped entirely (no spurious collisions). · [x] C2 (source/render split + ETag/304;
  **BE; pytest-verified, no browser**; ruff clean). The split is realized by C1 caching the **pre-theme**
  compute (the *source*) and theming being a separable *render* step. C2 adds the **figure-envelope
  cache**: new `skills/theme.py::render(spec, skill_id, style, source_key=None)` wraps `apply` and caches
  the themed figure keyed by `(source identity, skill_id, style, THEME_VERSION)` — so a theme/style change
  re-renders from the cached source **without re-running the skill**, and a repeat render of the same
  source+style is a cache hit. `source_key` lets `_execute` reuse the compute key it already holds (no
  re-hash of a large source figure); `/figures/style/apply` omits it and hashes the figure by content.
  New `THEME_VERSION` constant (bump on any theme/style-token change → every envelope misses cleanly, the
  same discipline as a skill `version`). The render cache reuses the C1 store via new generic `put`/`fetch`
  primitives (`get`/`set` are now thin wrappers); envelope keys are `render-…` prefixed (filename-safe — a
  `:` would silently break the NTFS disk tier, **a bug the cold-disk test caught**). Wired into
  `_execute` (compute tier → render tier) and `POST /figures/style/apply`. **ETag/304:** `GET
  /jobs/{job_id}/result` now emits a strong content-hash `ETag` and honors `If-None-Match` → **304** (an FE
  that already holds the figure skips the re-download). **Gates:** `test_result_cache.py` **+3** render-cache
  tests (envelope hit on repeat · style change & THEME_VERSION bump each miss · **acceptance**: a style
  change does NOT re-enter the runner [call-counter] · the end-to-end test now asserts BOTH tiers hit +
  `errors==0`), `test_jobs.py` **+1** (ETag present · matching `If-None-Match` → 304 no-body · stale
  validator → 200), full file **22**, contract/capabilities/export/legends/data_inspect/guardrails **110**,
  golden+integration green; ruff clean. ⚠ the export/rasterize path's `theme.apply` is intentionally left
  (a terminal raster, not an editable re-render). · [x] C3 (input cache + param-range 400 + exec
  timeout; **BE; pytest-verified, no browser**; ruff clean). Three guards on the run path:
  **(1) parsed-input cache** — new `engine.ingest_cached(src, hint, sheet, sep)` memoizes `engine.ingest`
  in-process keyed by the input **content hash** (+hint/sheet/sep), so the same bytes aren't re-parsed
  across `/data/inspect` + `/run` (each uploads to its own temp path, but the bytes — hence the key —
  match). In-process only (the payload is a live AnnData/DataFrame). On a hit the heavy payload+kind are
  **shared read-only** (QC/profile read them; the skill run reads from `path`, a file), while
  `source`/`qc`/`path` are **rebound per request** so one caller's metadata/file lifecycle can't corrupt
  the shared entry — a materialized parse keeps its persistent decoded temp; a direct file rebinds to the
  current upload. Wired into `/data/inspect` + `_inspect_for_run`. **(2) param-range validation** — new
  `contract.validate_param_ranges(spec, params)` enforces each `param_spec`'s type / `[min,max]` /
  `options` at the API → **400** with a clear `param_out_of_range` message (e.g. `fc_threshold=100` on a
  `max:5` param), on both `/run` and `/skills/{id}/jobs`, **before** any heavy work; unknown/reserved
  (`_`) keys ignored. **(3) exec timeout** — `/run` runs the skill in a worker thread under
  `SELOM_SKILL_TIMEOUT_S` (default 120s) via `asyncio.wait_for(run_in_executor)` → a hung skill returns
  **504** promptly and the event loop stays live instead of the whole server freezing (this also fixes the
  prior sync-call event-loop block). ⚠ a true kill needs a subprocess worker (deferred infra) — the
  abandoned thread finishes on its own; documented. New config `SELOM_INPUT_CACHE`/`_MAX` +
  `SELOM_SKILL_TIMEOUT_S`; the conftest disables the input cache suite-wide (settings singleton is built at
  import → flip the attribute, not the env). **Gates:** `test_input_cache.py` **3** (same bytes parse once ·
  distinct input/hint miss · disabled bypass), `test_run_guards.py` **7** (range unit: numeric/option/type +
  ignore unknown; endpoint: `/run` & jobs **400** out-of-range · happy-path **200** · hung skill **504**),
  engine+endpoint+cache regression **124**, golden+integration green, ruff clean. · [x] C5
  (param-spec caching — the last DB-free Task C bucket; **cross-lane: BE pytest + FE vitest + browser**;
  ruff/tsc/eslint clean). Two complementary fixes so the Figure-data Inputs no longer depend on a live
  describe round-trip. **(B, cross-lane — self-describing figure):** `provenance.build` now stamps the
  immutable `param_spec` into the figure's `skill` block (`bundle["skill"]["param_spec"]`, grouped with
  id+version the FE keys by) — every run's figure carries its own spec forever. FE `SkillProvenance.skill`
  gained an optional `param_spec`; `useSkillParams(skillId, seed?)` takes that provenance spec as a `seed`
  and renders the inputs from it **synchronously with NO fetch** (the spec is immutable per skill_version).
  **(A, FE-only — local cache):** new pure `lib/catalog/param-spec-cache.ts` (single key
  `selom.paramSpecs.v1` → `{[slug]:{version,spec}}`, SSR-safe, fail-soft); `fetchParamSpec` persists every
  successful describe and, on failure/offline, **falls back to the cached spec** (ok:true) so an
  already-run skill stays tunable offline — B3's loading→error/Retry floor only applies when nothing is
  seeded/cached. `useSkillParams` also seeds instantly from the cache (no loading flash) and warms it from
  the provenance seed. Wired through `FigureDataPanel` (`specSeed` prop) from the open figure's provenance.
  **Gates:** BE `test_provenance.py` updated (+param_spec asserts on `build` + the `/run` bundle),
  provenance/jobs/run-design/run-guardrail/contract/capabilities **60** green, golden **66** unaffected
  (provenance is outside `_execute`/theme), ruff clean; FE new `param-spec-cache.test.ts` (round-trip ·
  version-overwrite · SSR/corrupt/quota fail-soft) + `use-skill-params.test.ts` (persist-on-success ·
  offline cache-fallback · B3 floor when nothing cached) → tsc clean · eslint 0-err · **vitest 309** (+11).
  **BROWSER-VERIFIED (live BE :8010 + FE webpack, real eyg28 PDE6B_FS d210 DE CSV):** a fresh volcano run
  stamped `provenance.skill.param_spec` (keys fc/fdr/top_n/highlight); opening Figure-data rendered the
  INPUTS (thresholds 607↑/334↓ + Highlight genes) with **zero `GET /api/skills/volcano` describe calls**
  (network log) and warmed `selom.paramSpecs.v1`; then **backend killed + full page reload** → the figure
  still showed tunable inputs offline (no error slot, no spinner), Re-run present (still needs the backend).
  Verified in a NAMED throwaway project ("C5 verify — volcano param-spec cache …"); curated fixtures
  untouched. · [ ] C4 ⚑
- [x] D1 (declared table contract per skill → enforced pre-run gate; **cross-lane: BE pytest + FE vitest +
  browser**; ruff/tsc/eslint clean). The per-skill INPUT contract already existed in `engine/compat.py`
  (s52 data-fit scorer): `_REQS` (modality class) + `_SCHEMA` (named column groups — fold-change /
  significance / gene, matched by the classifier's synonym sets). **It was advisory** (a 0-100 score on
  the data-fit/intake surface + the reproduction matcher) — the own-data `POST /run` path did NOT gate on
  it, so a certain mismatch fell through to the runner (a `KeyError` → 500, or a misleading figure). **D1
  promotes it to an enforced pre-run gate + guards the declarations from drift.** **The gate** (`main.py`
  /run, after the QC gate, before the runner): compute `compat.fit(skill, bundle)` once; if `gated and not
  override` → **422 `data_contract_failed`** with `compat.contract_message` (names the missing columns +
  the next step) + the `data_fit` dump + routing; reuse the same fit for the response (single load/score).
  Honest (only `compatible is False` blocks; unreadable/unclear stays optimistic) · overridable (the QC
  gate's `override=true` escape hatch) · complementary (an uncontracted skill — e.g. ERG — is never gated
  here; its runner's `ValueError→400` covers it). **FE:** `runSkill` now surfaces a typed gate's
  `detail.message` as-is (self-framed, no "Couldn't run…try again" wrapper) — **and reads the 422 body
  ONCE** (a double `res.json()` threw → silently fell back to the generic "rejected (422)"; the fetch mock
  hid it, the browser caught it → [[fetch-body-read-once-browser-verify]]). **The guard (ratchet):**
  `test_skill_input_contract.py` — every `_REQS`/`_SCHEMA` skill ships (no drift), a column contract
  declares something checkable, a contracted skill's modality admits a table class (mirrors the OUTPUT
  `test_skill_table_contract.py`). **Gates:** BE `test_data_contract.py` (counts→422 naming the columns ·
  DE table→200 no false block · override bypasses · uncontracted not gated) + `test_skill_input_contract.py`
  + the run-path regression **76** green, contract/inspect/capabilities/table-contract **70**, golden **66**,
  ruff clean; FE tsc/eslint clean · **vitest 309** (+1 skills-api typed-message case; net 309 — the +1
  replaced a count reshuffle). **BROWSER-VERIFIED** (live BE :8010 + FE webpack): a real 6×6 bulk-counts CSV
  → volcano → **blocked pre-run, NO figure, NO stack trace**, the clear message rendered in the UI ("This
  data doesn't fit volcano: missing a fold-change column… Swap in a file…"); the eyg28 DE table → volcano →
  200 (no false block). Doc `docs/architecture-consistency-gate/skill-input-contract.md`. · [x] D2
  (frame-validation at stage seams; **BE; pytest + live-HTTP + BROWSER**; ruff clean, dependency-free — NO
  pandera). New pure **`engine/frame_schema.py`** = a lightweight `lazy`-style frame-schema collector (the
  pandera shape without the venv dep — C1 "no diskcache" precedent + [[selom-uv-sync-footgun]]). **The clean
  3-layer story, one source of truth each:** QC = is-the-data-clean (coarse, whole-frame) · **D1** = are the
  *named* columns/modality present (presence → 422) · **D2** = do those *present, required* columns carry
  *usable* data (depth → **400 `frame_validation_failed`**). The seam check (`main.py` /run, after D1, before
  the runner) flags a **positively-determined** structural defect among the columns D1 already confirmed
  present: `empty_column` (all-null / all-blank), `non_numeric_column` (a required fc/sig column with no
  parseable number — a column with ≥1 number is NOT flagged, the runner coerces it), `duplicate_column`.
  Lazy (every defect in one 400) · honest (only inspects D1-present columns, never re-reports a missing one) ·
  overridable (same escape hatch). The per-skill rules are **derived from D1's `compat._SCHEMA`** + the
  classifier synonym sets (single-sourced — D1 reads presence, D2 reads usability of the same resolved
  column). Also a named **result-seam** schema (`validate_result_table`: rectangular StatsTable) guarded by a
  test over the native-table skills (the output-seam ratchet) — NOT a raising hot-path gate (a malformed
  *output* is a runner bug, not a user 400). FE = ZERO change (rides D1's already-fixed `runSkill`
  `detail.message` read-once path, which is status-agnostic → a 400 surfaces verbatim). **Gates:**
  `test_frame_schema.py` (19: empty/non-numeric/duplicate, lazy-vs-strict, missing-is-D1, single-sourced
  numeric-group derivation, result-seam + native-table ratchet) + `test_frame_validation.py` (5 endpoint:
  empty fc → 400 at the seam · good DE → 200 no false block · override bypasses · missing cols = D1's 422 ·
  uncontracted not seam-checked); run-path + golden regression unaffected; **full suite 1051 pass**. **LIVE
  (BE :8010 real engine):** an empty-fold-change DE table → volcano → **400** naming `log2FoldChange`,
  override → 200. **BROWSER:** dropped the same file in a named project, applied Volcano → the exact message
  rendered as a `role=alert` ("…a fold-change column ('log2FoldChange') is empty — every value is missing…"),
  **NO figure, NO crash**, console clean (only the expected 400 log). Doc
  `docs/architecture-consistency-gate/frame-validation.md`. · [x] D3 (intermediate-table lineage, local;
  **BE; pytest + live-HTTP**; ruff clean, dependency-free). New pure **`engine/lineage.py`** = a
  content-addressed, immutable local artifact store (the C1-cache discipline; the **D4 precursor** — the
  local-dir backend swaps for DuckDB/Parquet behind one `materialize`/`get_table`/`get_meta`/`lineage`
  interface, exactly as C1's disk tier swaps for R2). A stage's table is written under its own SHA-256
  (`data/artifacts/<id>.csv`) + a `<id>.meta.json` sidecar carrying **parent-hash lineage** (`ParentRef` —
  a source file by SHA, or a prior artifact by id), the **cleaning recipe** (the plan steps), and a computed
  **`receipt`** ("merged from {A, B, C}" / "derived from X"). Immutable + idempotent (a re-materialize of the
  same bytes returns the existing record → the reproducibility guarantee); a single-cell **matrix** is
  recorded **meta-only** (shape + lineage, no multi-GB CSV). Wired: `/run` stamps the ingested table's
  `artifact` into the response (fail-soft) · `/data/combine` materializes the merged cohort + its
  merge-receipt (input SHAs captured before the temp uploads are cleaned) · new `GET /artifacts/{id}` (meta +
  lineage walk) + `GET /artifacts/{id}/table` (inspect the matrix the skill saw). Config `SELOM_ARTIFACTS`;
  conftest disables it suite-wide (tests opt back in). **Gates:** `test_lineage.py` (11: shape/hash ·
  reproducible+immutable · round-trip the bytes · disk survives a new store · "merged from {…}" receipt ·
  artifact-parent lineage walk · matrix meta-only · disabled-store · 3 endpoint: /run stamp + inspect
  round-trip + combine receipt); **full suite 1051 pass**. **LIVE (BE :8010 real engine):** a volcano run
  stamped `artifact` (kind ingested, recipe "used as-is", receipt "derived from de_good.csv"); `GET
  /artifacts/{id}/table` returned the exact CSV the skill saw; `/data/combine` of 2 files → receipt **"merged
  from {wt.csv, ko.csv}"**. Doc `docs/architecture-consistency-gate/intermediate-table-lineage.md`. · [ ] D4 ⚑
- [ ] E1 · [ ] E2
- [ ] F1 ⚑ · [ ] F2 ⚑ · [ ] F3 ⚑

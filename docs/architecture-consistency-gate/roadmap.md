# Selom Architecture Gate — Agile Roadmap

Last updated: 2026-06-27 18:03 +10:00 — Claude.
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
stable slot, no stale-param leak, a heap snapshot flat across switches (overlaps E1).

## Task C — Cache / source boundary  ·  lane: BE (Codex; Claude covers while away)  ·  DB-free (R2 tier deferred)

The "faster / cleaner execution / caching strategy" ask. Content hash from `plan.md` Spine 4.

| # | Bucket | Scope | Acceptance | Size |
| --- | --- | --- | --- | --- |
| **C1** | Content-addressed result cache (L1+L2) | Key = `(skill_id+version, canonical(params), input_sha256)`; canonicalize params (stable serialize · sorted keys · float/precision coercion · drop-defaults); in-proc LRU + `diskcache`; invalidate by `skill_version` bump (no TTL). | An identical re-run is a measured cache hit (no recompute); a `skill_version` bump misses cleanly. | ~1 |
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
  resolve") — both reverted, green. ⚠ ruff binary EDR-blocked this session (only the blocked
  `.venv/Scripts/ruff.exe` resolves) → hand-verified the BE test vs the project's ruff config (no `[tool.ruff]`
  → default select E4/E7/E9/F; E501 not selected; all new imports + `_KNOWN_TOOLS` used). **Task B code COMPLETE
  (B1–B5); NEXT = Task B EXIT smoke** (open every skill's figure, switch dataset↔skill 20× → zero crashes,
  stable slots, no stale-param leak, flat heap — overlaps E1; needs a browser pass).
- [ ] C1 · [ ] C2 · [ ] C3 · [ ] C4 ⚑ · [ ] C5
- [ ] D1 · [ ] D2 · [ ] D3 · [ ] D4 ⚑
- [ ] E1 · [ ] E2
- [ ] F1 ⚑ · [ ] F2 ⚑ · [ ] F3 ⚑

# Selom Architecture Gate — Agile Roadmap

Last updated: 2026-06-25 20:10 +10:00 — Claude.
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

**Everything in Tasks B, C, D1–D3, and E is database-free and can complete now.** They use
the existing in-process / local-disk substrate. The DB/object-store materialization line is:

| Needs materialization? | Buckets | Status |
| --- | --- | --- |
| **No — do now** | B1–B5 · C1–C3 · D1–D3 · E1–E2 | the lane |
| **Yes — DEFERRED, flagged, NOT a blocker** | **C4** (R2 cache tier) · **D4** (DuckDB/Parquet lane) · **F1–F3** (Supabase schema, FE-state migration) | on hold until the web/DB launch; the upstream buckets are designed so the local version drops into the materialized one with no rework (content-addressed local dir → R2 object; declared table contract → Parquet schema; FE types → SQL rows) |

When a bucket starts to *want* materialization (it'll be D3 hardening, then D4), I'll stop and
flag it — the gate is built so the work in front of it never waits on it.

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

- [ ] B1 · [ ] B2 · [ ] B3 · [ ] B4 · [ ] B5
- [ ] C1 · [ ] C2 · [ ] C3 · [ ] C4 ⚑
- [ ] D1 · [ ] D2 · [ ] D3 · [ ] D4 ⚑
- [ ] E1 · [ ] E2
- [ ] F1 ⚑ · [ ] F2 ⚑ · [ ] F3 ⚑

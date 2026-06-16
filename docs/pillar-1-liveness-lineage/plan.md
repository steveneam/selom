# Plan — Pillar 1: Liveness & Lineage

> Task breakdown of the approved `spec.md` (final process step before build). Ordered by
> slice; each task names the files and its done-check. Lane tags: `[FE]` / `[BE]` /
> `[FE+BE]`. Build proceeds slice by slice — each slice is independently shippable + verified
> (tsc + build + e2e/browser, backend pytest where touched). _Filed 2026-06-16._

Legend: ⬜ todo · 🔜 next · ✅ done.

> **BUILD STATUS — ✅ COMPLETE (S1–S4), 2026-06-16.** All four slices shipped + verified. The
> per-task ⬜ marks below are the *original* plan record (kept as filed); the authoritative
> delivered state is here:
> - **S1 — Persistence + staleness** ✅ shipped `4fe15d0`/`b1d9ff6` (session 6).
> - **S2 — Workrail + Statistics node** ✅ shipped `af03583` (BE `table`) + `e7da4c9` (Stats panel)
>   + `e31d347` (workrail) (sessions 6–7).
> - **S3 — Versioning: sweep, compare, freeze** ✅ shipped `e7f8294` + `c8c8ded` (session 8).
> - **S4 — Durable Supabase mapping** ✅ this note (design-only, no code).
>
> Verified end-to-end: `tsc` + `next build` (5 routes) + 32 vitest + 2 e2e + browser at desktop;
> backend pytest 171 + ruff (S2.1 only); console clean. **All on `origin/main`.**

---

## S1 — Persistence + staleness  *(foundation; the trigger data already exists)*

⬜ **1.1 [FE] Durable `Figure` type.** Extend `FigureRef` → `Figure` in `lib/projects/types.ts`:
add `spec`, `provenance?`, `methods?`, `guardrails?`, `table?`, `parentFigureId?`,
`variantLabel?`, `frozen?`. Keep back-compat (all new fields optional).
*Done:* `tsc` clean; type maps to design §5 `figures`.

⬜ **1.2 [FE] Persist figures through `ProjectStore`.** Update `lib/projects/store.ts`:
`addFigure` accepts + stores the full record (spec+bundle+table); add `updateFigureSpec(id, spec)`
and `forkFigure(parentId, patch)`; `hydrate()` tolerates legacy figures (missing `spec` →
flagged, no crash, like the `geneSets` back-compat).
*Done:* run → reload → figure + bundle intact; legacy state loads.

⬜ **1.3 [FE] Wire the editor to the persisted spec.** In `project-workspace.tsx`: on run, persist
the full figure; load the editor from the stored `spec`; persist in-canvas edits back
(`updateFigureSpec`, debounced/on-commit via the figure store).
*Done:* edit legend → reload → edit survives; `bundle` no longer transient.

⬜ **1.4 [FE] Staleness engine (pure + tested).** New `lib/lineage/staleness.ts`:
`figureStaleness(fig, live) → {stale, reasons[]}` per Decision D1 (data+params gate; skill minor+
gates, patch ignored; env info-only). Unit tests = the factor truth table.
*Done:* unit tests green across all four factors + no-change.

⬜ **1.5 [FE] Staleness badge + Re-run.** Surface a non-blocking "Stale — *X* changed" badge on the
figure header (and later the rail node); **Re-run** replays `(skillId, provenance.params)` against
the dataset's current bytes via `runSkill`, persisting a **new** version (`parentFigureId`).
Disabled w/ tooltip when the dataset file is unavailable.
*Done:* force stale → badge + Re-run → new fresh version, prior retained.

**S1 verify:** `tsc` + `next build`; staleness unit tests; e2e (run → reload persists; stale →
re-run → new version); browser-verify badge at desktop, console clean.

---

## S2 — Sectioned workrail + Statistics node  *(the IA + the contract addition)*

⬜ **2.1 [BE] Skills emit a result `table`.** *(Cross-lane, additive — Decision D7.)* Each runner
that computes a table returns `table: {columns, rows, title?}`; assemble centrally in `run_skill`
alongside the bundle. Wire shape → `{figure, provenance, methods, guardrails, table?}`. Start with
volcano / deg / enrichment / markers; purely-visual skills return none.
*Done:* golden test — volcano+enrichment return a well-formed table; existing goldens unchanged;
pytest + ruff green.

⬜ **2.2 [FE] `runSkill` carries `table`; `StatsPanel` renders it.** Add `table?` to
`SkillRunResponse`; new `components/project/stats-panel.tsx` = sortable grid + CSV export. FE
fallback derives a minimal table from figure traces when absent; omit node when neither (D3).
*Done:* volcano → DE table node, sortable, CSV export; visual-only skill → no node.

⬜ **2.3 [FE] The workrail replaces the tabs.** New `components/project/workrail.tsx` (sections
**Data → Statistics → Figure**); `project-workspace.tsx` swaps `Tabs` for it. Items listed per
**figure** (D4) with Stats+Dataset lineage shown on select; Workbench becomes a "Run a skill"
action in the flow. Reuse `--stage-*` colours. Staleness badges render on figure nodes.
*Done:* four tabs gone; three sections drive the main pane; lineage + stale state visible on nodes.

**S2 verify:** `tsc` + `next build`; backend pytest (table goldens); browser-verify the workrail IA
+ a Statistics table + a stale badge on a rail node; console clean.

---

## S3 — Versioning: sweep, compare, freeze

⬜ **3.1 [FE] Parameter sweep.** A small form (pick param + N values) loops `runSkill` per value →
N sibling figures sharing `parentFigureId` + `variantLabel`.
*Done:* sweep resolution {0.5, 1.0} → 2 siblings under one parent.

⬜ **3.2 [FE] Compare view.** Select ≥2 versions → side-by-side figures + a **diff** (params
highlighted; `StatsTable` row/column deltas aligned on the first column). New
`lib/lineage/diff.ts` (pure, tested) + a compare surface.
*Done:* compare the two resolutions → params diff + table-delta (cluster count) shown; diff unit
tests green.

⬜ **3.3 [FE] Freeze = tag.** `frozen` flag + UI marker; the editor blocks in-place edits on a
frozen figure and offers "Edit a copy" → `forkFigure`.
*Done:* freeze v1 → editing forks v2; v1 immutable + marked.

**S3 verify:** `tsc` + `next build`; diff unit tests; e2e (sweep → compare → freeze→fork);
browser-verify, console clean.

---

## S4 — Durable Supabase mapping  *(design-only; not dogfood-blocking)*

✅ **4.1 [doc] §5 mapping confirmed.** `Figure` (spec/provenance/table/parentFigureId/frozen) maps
onto `figures`; variants-as-rows + `figure_history` (patch trail) compose cleanly; schema deltas
filed for B7 below. No runtime change. _Note filed 2026-06-16._

### Mapping note — `Figure` → Supabase §5

**`Figure` (FE, `lib/projects/types.ts`) → `figures` (Supabase, `docs/command-center/design.md §5`).**

| FE field (`Figure`) | `figures` column | vs §5 |
|---|---|---|
| `id` | `id` (uuid pk) | in §5 |
| `projectId` | `project_id` (fk→projects) | in §5 |
| `datasetId?` | `dataset_id` (fk→datasets, null) | in §5 |
| `skillId?` | `skill_id` (text / fk→skill_catalog, null) | in §5 |
| `spec?` | `spec` (jsonb) | in §5 |
| `provenance?` | `provenance` (jsonb) | in §5 — **the staleness trigger-set** (`input.sha256` / `params` / `skill.version` / `environment`) |
| `createdAt` | `created_at` (timestamptz) | in §5 |
| `title` | `title` (text) | **Δ add** |
| `methods?` | `methods` (jsonb, null) | **Δ add** |
| `guardrails?` | `guardrails` (jsonb, null) | **Δ add** |
| `table?` | `result_table` (jsonb, null) | **Δ add** (D7 Statistics contract; **not** `table` — SQL reserved word) |
| `parentFigureId?` | `parent_figure_id` (self-fk→figures.id, null) | **Δ add** (D5 version tree) |
| `variantLabel?` | `variant_label` (text, null) | **Δ add** |
| `frozen?` | `frozen` (bool not null default false) | **Δ add** (D6 paper tag) |

**`Dataset` deltas (`datasets`):** add `current_sha256` (text — the live data version staleness
diffs against; FE `Dataset.currentSha256`) and `label` (text, null — the Pillar-1 family rename).
Both additive.

**Verdict — composes cleanly; no structural rework.** Findings:

1. **Versions-as-rows (D5) need no new table.** A sweep sibling, a re-run, and a freeze-fork are
   all ordinary `figures` rows with `parent_figure_id` set. The family tree is *derived* by walking
   the self-FK — already pure + tested in `lib/lineage/versions.ts` (`rootFigureId` /
   `versionFamily` / `groupFamilies`). The DB needs only the self-referential FK + an index on
   `parent_figure_id`. The rejected alternative (`figure_versions` table) stays rejected; §5 needs
   no version table.
2. **Staleness is computed, never stored — no `stale` column.** `figureStaleness(fig, live)` (pure
   FE) diffs `figures.provenance` against `datasets.current_sha256` + the live skill version at read
   time. The DB stays normalized; nothing to keep in sync; the "honest" property survives the swap
   unchanged. Propagation is free (D2) — each figure carries its own input hash, so a changed
   dataset flags every figure built on it with no cascade engine. Add an index on
   `figures(dataset_id)` for that fan-out.
3. **`figure_history` stays orthogonal and composes.** §5's `figure_history(figure_id, patch,
   actor, ts)` is the RFC-6902 *within-a-figure* edit audit (the in-canvas editor's JSON-Patch
   trail, shared with the future Pillar-3 copilot). **Versions** (this pillar) are *coarse named
   snapshots* = sibling `figures` rows; **history** is *fine within-figure edits* = patch rows.
   They never overlap: freezing v1 stops its history at the freeze; "Edit a copy" mints a new
   `figures` row (new id) that begins its own history trail. (Decision D5.)
4. **RLS unchanged.** Every new column lives on `figures`/`datasets`, already owner-scoped via
   `project_id → projects.owner` (§5). `parent_figure_id` never crosses a project (invariant: a fork
   copies `projectId`), so the existing "RLS by owner" policy covers the whole version tree with no
   new policy surface.

**Schema delta to file for B7 (Codex lane):**
- `ALTER TABLE figures ADD` → `title text`, `methods jsonb`, `guardrails jsonb`, `result_table
  jsonb`, `parent_figure_id uuid references figures(id)`, `variant_label text`, `frozen boolean not
  null default false`.
- `ALTER TABLE datasets ADD` → `current_sha256 text`, `label text`.
- Indexes: `figures(parent_figure_id)`, `figures(dataset_id)`.
- The Supabase `ProjectStore` impl maps FE `table` ⇄ column `result_table` (reserved-word avoidance)
  and is the only place that translation lives.
- *(Optional later normalization: collapse `methods`+`guardrails`+`result_table` into one `bundle
  jsonb`; kept as discrete columns here to mirror the FE `Figure` 1:1 and keep `provenance`
  independently queryable for staleness.)*

**No runtime change.** This note + the delta are the whole S4 deliverable. The FE already persists
through `ProjectStore` shaped to this mapping (req 13), so the future swap is a `ProjectStore` impl
change, not a caller rewrite. **→ Pillar 1 build is complete (S1–S4).**

---

## Notes
- **Lane discipline:** 2.1 is the only BE task — explicit `feat(backend:)` commit, keep the Codex
  handoff section accurate; everything else `feat(frontend:)`. Never `git add -A`.
- **Sequencing:** S1 → S2 → S3. S1 unblocks everything (staleness + persisted versions). 2.1 (BE
  table) can land in parallel with 2.2/2.3 since the FE fallback degrades gracefully.
- **Open defaults to confirm during build** (owner may still steer): D1 gating thresholds, D3
  show-when-substantive, D4 per-figure granularity — all reversible.

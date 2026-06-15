# Plan — Pillar 1: Liveness & Lineage

> Task breakdown of the approved `spec.md` (final process step before build). Ordered by
> slice; each task names the files and its done-check. Lane tags: `[FE]` / `[BE]` /
> `[FE+BE]`. Build proceeds slice by slice — each slice is independently shippable + verified
> (tsc + build + e2e/browser, backend pytest where touched). _Filed 2026-06-16._

Legend: ⬜ todo · 🔜 next · ✅ done.

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

## S4 — Durable Supabase mapping  *(design-only now; not dogfood-blocking)*

⬜ **4.1 [doc] Confirm the §5 mapping.** Verify `Figure` (spec/provenance/table/parentFigureId/
frozen) maps onto `figures` + that variants-as-rows + `figure_history` (patch trail) compose
cleanly; note any schema delta for the future B7 Supabase swap. No runtime change.
*Done:* a short mapping note appended here / to `design.md`; no code.

---

## Notes
- **Lane discipline:** 2.1 is the only BE task — explicit `feat(backend:)` commit, keep the Codex
  handoff section accurate; everything else `feat(frontend:)`. Never `git add -A`.
- **Sequencing:** S1 → S2 → S3. S1 unblocks everything (staleness + persisted versions). 2.1 (BE
  table) can land in parallel with 2.2/2.3 since the FE fallback degrades gracefully.
- **Open defaults to confirm during build** (owner may still steer): D1 gating thresholds, D3
  show-when-substantive, D4 per-figure granularity — all reversible.

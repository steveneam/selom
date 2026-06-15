# Spec — Pillar 1: Liveness & Lineage

> **Status:** DRAFT for owner review (phase process: research ✓ → interview ✓ → **spec** →
> plan → build). Sources of truth for the *why/decisions*: `research.md` + `interview.md` in
> this folder. This document is the *how*. _Filed 2026-06-16 · Claude (FE+BE acting)._

---

## What

Turn Selom's project workspace into a **Prism-style lineage tool that is honest about
recompute cost.** Replace the four tabs with a sectioned left **workrail — Data → Statistics →
Figure** — that makes the raw-data→output chain the navigation itself. Persist each figure's
spec + provenance bundle so we can compute **staleness** (the figure's stored trigger-set — input
hash, params, skill version, env — diffed against the current one → "stale, because *params*
changed", with an explicit **Re-run**). Add a single **version-history** primitive
(parameter-sweep-led) that subsumes branch & compare and turns **freeze** into a "tag this version
as the paper one". Surface the **Statistics** result table each skill already computes.

## Context

- **Product thesis** (`docs/build-charter.md`): "is THIS the right, reproducible figure for my
  paper?" A stale figure is a *wrong* figure; an un-retraceable one is *indefensible*. Pillar 1
  makes both states visible.
- **What exists today:**
  - `ProjectState = {projects, datasets, installs, figures, geneSets}` — `lib/projects/store.ts`
    (localStorage mock, Supabase-schema-aligned). `FigureRef` (`lib/projects/types.ts`) carries
    `{id, projectId, datasetId?, skillId?, title, createdAt}` — **no spec, no provenance, no
    version.**
  - The editable spec lives only in `useFigureStore` (`hooks/use-figure-store.ts`, in-memory,
    lost on reload). The provenance bundle lives only in transient `bundle` state in
    `components/project/project-workspace.tsx`.
  - `runSkill` (`lib/skills-api.ts`) returns `{figure, provenance, methods, guardrails}`. The
    **provenance bundle** (`SkillProvenance`: `input.sha256`, `params`, `skill.id+version`,
    `environment`) is exactly the multi-factor staleness trigger-set (`provenance.py`).
  - Navigation = four tabs in `project-workspace.tsx` (Overview / Data / Workbench / Figure).
  - `components/pipeline.tsx` = a 4-stage **static** tracker (data/skill/figure/publish); reusable
    colour system (`--stage-*`), not the workrail.
  - Planned schema (`docs/command-center/design.md §5`): `figures(…, spec, provenance, …)` +
    `figure_history(figure_id, patch, actor, ts)` — **speced, unrealized.**
- **Why now:** owner closed the figure-editor track (session 4) and chose Pillar 1 first.

## Requirements

Each is testable. Tagged by delivery **slice** (S1–S4; see Design §"Slicing").

**Persistence & lineage (S1)**
1. A figure produced by a run is **persisted durably** with its full Plotly `spec`, its
   `provenance` bundle, and its `methods`/`guardrails`, surviving reload. *(Test: run → reload →
   figure + bundle still present and editable.)*
2. Each persisted figure records its **lineage edges**: `datasetId`, `skillId`, and (for variants)
   a `parentFigureId`. *(Test: a forked variant points at its parent; a re-run points at the same
   dataset.)*
3. In-canvas edits persist to the figure's stored spec (the working spec is durable, not just
   in-memory). *(Test: edit legend → reload → edit survives.)*

**Staleness engine (S1)**
4. A pure `figureStaleness(figure, liveTriggerSet)` returns `{stale: boolean, reasons:
   StaleReason[]}`, where each reason names which factor diverged: `data` (input sha256), `params`,
   `skill` (version), or `env`. *(Test: change a param on the dataset's current run config → the
   stored figure reports `stale` with reason `params`.)*
5. A stale figure shows a **non-blocking badge** ("Stale — params changed") in the workrail and on
   the figure, with a **Re-run** action that replays the figure's `(skillId, resolved params)`
   against the dataset's current bytes via the existing `runSkill` path, producing a **new
   version** (does not mutate the prior). *(Test: Re-run → new version appears, prior retained, new
   one is fresh.)*

**Sectioned workrail (S2)**
6. The project workspace navigation is a **left workrail with three sections — Data, Statistics,
   Figure** — replacing the Overview/Data/Workbench/Figure tabs. Each section lists its artifacts;
   selecting one shows it in the main pane. *(Test: the four tabs are gone; the three sections
   render and switch the main pane.)*
7. The rail visibly links artifacts along the chain (a Figure shows its source Statistics +
   Dataset; staleness badges appear on the rail node). *(Test: a figure node shows its lineage and
   stale state inline.)*

**Statistics node (S2 — contract addition)**
8. A skill run that computes a tabular result returns it as a structured `table`
   (`{columns: string[], rows: (string|number)[][], title?}`); the FE renders it as a **Statistics
   artifact** that is viewable, sortable, and exportable to CSV. *(Test: volcano run → a DE table
   node appears with the gene/log2FC/padj columns, exportable.)*
9. When the backend returns no `table`, the Statistics node is **omitted** (not shown empty) —
   *recommended default, Decision D3*. *(Test: a purely-visual skill shows Data→Figure with no
   Statistics node.)*

**Version history, compare, freeze (S3)**
10. From any figure the user can **fork a parameter sweep**: pick a param, give N values, get N
    linked sibling versions (each its own run). *(Test: sweep clustering resolution {0.5, 1.0} →
    two sibling figures sharing a parent.)*
11. A **compare view** shows ≥2 selected versions **side-by-side (figures)** *and* a **diff** of
    their params + Statistics tables (changed params highlighted; table row/column deltas). *(Test:
    compare the two resolutions → params diff shows `resolution 0.5→1.0`; table diff shows cluster
    count change.)*
12. A version can be **tagged "frozen / paper"**; a frozen version is immutable (edits to it fork a
    new unfrozen version) and visually marked. *(Test: freeze v1 → editing it creates v2; v1
    unchanged.)*

**Durability posture (all slices)**
13. All new state goes **through the `ProjectStore` interface**, schema-shaped to design §5
    (`figures.spec/provenance`, variants via `parentFigureId`), so the later Supabase swap is an
    impl change, not a caller rewrite. *(Test: no component imports storage directly; types map to
    §5.)*

## Design

### Data model (extend, don't replace)

Extend `FigureRef` → a durable **`Figure`** record (still the `figures` table, design §5):

```ts
interface Figure {
  id: string;
  projectId: string;
  datasetId?: string;
  skillId?: string;            // catalog id
  title: string;
  spec: FigureSpec;            // NEW — the editable Plotly spec (was transient)
  provenance?: SkillProvenance;// NEW — the staleness trigger-set (was transient)
  methods?: SkillMethods;      // NEW
  guardrails?: SkillGuardrail[];
  table?: StatsTable;          // NEW — the Statistics result (contract addition)
  // lineage / versioning
  parentFigureId?: string;     // NEW — set on a fork/variant/re-run
  variantLabel?: string;       // NEW — e.g. "resolution = 1.0"
  frozen?: boolean;            // NEW — the "paper" tag
  createdAt: number;
}
interface StatsTable { columns: string[]; rows: (string | number)[][]; title?: string }
```

The dataset gains the live trigger inputs needed to diff against a figure's stored bundle:
`Dataset` already has `filename`/`modality`; add `currentSha256?` + the project's current run
config is reconstructed from the figure's own `provenance.params` (we re-run with the *same*
params, against the *current* data).

`figure_history` (design §5, RFC-6902 patch trail) stays as the **fine-grained edit audit**;
**versions** (this spec) are **coarse named snapshots** (sibling `Figure` rows via
`parentFigureId`). They are complementary — history = within-a-figure edits; versions = the
branch/compare/freeze tree. (Decision D5.)

### Staleness engine (pure, FE)

`lib/lineage/staleness.ts`:
```ts
type StaleFactor = "data" | "params" | "skill" | "env";
interface StaleReason { factor: StaleFactor; was: string; now: string }
function figureStaleness(fig: Figure, live: { sha256?: string; skillVersion?: string; env?: ... }):
  { stale: boolean; reasons: StaleReason[] }
```
Diffs `fig.provenance` against the live trigger-set. **Recommended gating defaults (D1):**
`data` (sha256 ≠) and `params` (≠) → stale; `skill` major/minor version bump → stale, patch →
ignore; `env` → **info only**, never gates (too noisy on a dev box). Replace-vs-append (D2): any
input sha256 change = stale (we cannot cheaply tell append from replace; honest over-flagging
beats silent drift). Propagation (D2): staleness is computed **per figure** from its own bundle;
because each figure stores its own input hash, a changed dataset naturally flags **every** figure
built on it — no explicit cascade engine needed; the rail shows each flagged node (no animated
cascade).

### Sectioned workrail (FE IA change)

New `components/project/workrail.tsx` replaces the `Tabs` in `project-workspace.tsx`:
- Three sections, top→bottom: **Data** (datasets + intake/QC), **Statistics** (result tables),
  **Figure** (the editable figures). Items are listed under each section; selecting drives the
  main pane (the existing `DataPanel`, a new `StatsPanel`, and the existing `EditorWorkspace`).
- **Rail item granularity (D4, recommended):** list per **figure** (the unit the scientist names),
  with its source Statistics + Dataset shown as its lineage on selection. (Not per-analysis or
  per-dataset grouping — simplest, matches how figures are produced one-at-a-time today.)
- Reuse the `--stage-*` colour system from `pipeline.tsx`. The Workbench (skill-apply) becomes an
  **action within the Data/Statistics flow** (a "Run a skill" affordance), not a top-level tab.
- Staleness badges + the Re-run action render on figure nodes and in the figure header.

### Statistics node (contract addition — backend-led, additive)

- **Backend:** each skill's runner additionally returns `table: StatsTable | None` (the DE /
  enrichment / marker / correlation / cluster-summary table it already computes). Wire shape
  becomes `{figure, provenance, methods, guardrails, table?}` — additive; existing readers ignore
  it. Centralize in `run_skill` where the bundle is assembled.
- **FE:** `runSkill` returns `table?`; the new `StatsPanel` renders it (sortable grid + CSV
  export). **Fallback (D3):** when `table` is absent but the figure clearly carries the data
  (e.g. a volcano's x/y/text), derive a minimal table FE-side; otherwise omit the node.

### Re-run & versioning flow

- **Re-run** (stale figure): `runSkill(skillId, currentDatasetFile, fig.provenance.params)` →
  persist a **new `Figure`** with `parentFigureId = fig.id`, fresh bundle. Prior retained.
- **Parameter sweep:** a small form (pick param + values) loops `runSkill` per value, persisting N
  siblings sharing a `parentFigureId`. Leads the primitive; "vary dataset"/"vary skill" reuse the
  same loop with a different varied axis (future, same mechanism).
- **Compare:** select ≥2 figures → a compare view: figures side-by-side + a params diff + a
  `StatsTable` diff (align on first column; mark added/removed/changed rows).
- **Freeze:** set `frozen=true`; the editor blocks in-place edits on a frozen figure and offers
  "Edit a copy" → fork.

### Slicing (the smallest shippable steps; the plan details tasks)

- **S1 — Persistence + staleness** *(foundation, highest value/lowest cost — the bundle already
  exists, we just store + diff it).* Realizes req 1–5, 13.
- **S2 — Workrail + Statistics node** *(the IA + the contract addition).* Req 6–9.
- **S3 — Versioning: sweep, compare, freeze.** Req 10–12.
- **S4 — Durable Supabase mapping** *(when the web stack lands; not dogfood-blocking).*

## Decisions

- **D1 — Staleness gating factors.** *Choice:* `data` + `params` gate; `skill` minor+ gates, patch
  ignored; `env` is info-only. *Alt:* gate on all four (noisy on dev), or data-only (misses param
  drift). *Why:* matches Snakemake's trigger spirit while staying quiet on a single-box dogfood.
  *Reversible:* yes (a config map). **Recommended default — owner may overrule.**
- **D2 — Replace-vs-append & propagation.** *Choice:* any input-hash change = stale; per-figure
  computation (no cascade engine); rail shows each flagged node. *Alt:* diff append vs replace
  (can't do cheaply), animated cascade (cost, little value). *Why:* honest over-flagging > silent
  drift; per-figure hashing gives propagation for free. *Reversible:* yes.
- **D3 — Statistics node shown only when substantive.** *Choice:* omit the node when no `table`
  (and no derivable one). *Alt:* always show (empty nodes clutter the honest rail). *Why:* the rail
  must stay honest — no empty receipts. *Reversible:* yes. **Recommended default — owner flagged
  this open.**
- **D4 — Rail item granularity = per figure.** *Choice:* list figures; show their Stats+Dataset
  lineage on select. *Alt:* group per analysis or per dataset. *Why:* the figure is the named unit;
  simplest. *Reversible:* yes. **Recommended default — owner flagged this open.**
- **D5 — Versions = sibling `Figure` rows (not a new table).** *Choice:* model variants/freeze as
  `Figure` rows linked by `parentFigureId` + flags; keep `figure_history` for patch audit. *Alt:* a
  dedicated `figure_versions` table. *Why:* surgical, reuses the `figures` table + design §5; fork
  = copy a row. *Reversible:* yes (can normalize later).
- **D6 — Freeze = a tag, not immutability machinery.** *Choice:* `frozen` flag; edits to a frozen
  figure fork. *Alt:* a separate immutable-snapshot store. *Why:* with explicit re-run nothing
  silently drifts, so a flag + fork is enough (owner's rethink). *Reversible:* yes.
- **D7 — Statistics `table` is a backend contract addition (additive).** *Choice:* skills return
  `table?` alongside the figure; FE fallback derives when absent. *Alt:* derive everything FE-side
  from Plotly traces (fragile for proper columns). *Why:* the backend has the clean table; additive
  keeps every existing reader working. *Reversible:* yes. **Cross-lane (BE-led) — flag in handoff.**

## Invariants

- The editable figure remains a pure Plotly `{data, layout}` spec; lineage/version metadata lives
  **outside** the spec (on the `Figure` record), never injected into `data`/`layout`. *(The style
  stamp in `layout.meta.selomStyle` is the one sanctioned exception, already shipped.)*
- No component imports a storage backend directly — everything goes through `ProjectStore`.
- A re-run or fork **never mutates** an existing figure record; it creates a new one.
- Staleness is **advisory** — it never blocks editing, export, or viewing.

## Error Behavior

- **Re-run with the dataset file unavailable** (mock has no real bytes / file gone): the Re-run
  action is disabled with a tooltip ("re-attach the dataset to re-run"); staleness badge still
  shows. Never silently no-op.
- **Backend omits `table`:** Statistics node falls back to FE-derived, else is omitted — never an
  error.
- **Corrupt/old persisted state** (figures without `spec`): tolerated like the existing `geneSets`
  back-compat in `hydrate()` — missing fields default; the figure shows as "spec not stored
  (legacy)" rather than crashing.

## Testing Strategy

- **Unit (FE):** `figureStaleness` truth table across each factor (data/params/skill/env) +
  no-change = fresh; `StatsTable` CSV export; the params/table **diff** function.
- **Store:** persist a figure (spec+provenance) → reload (re-hydrate) → intact; fork → parent link;
  freeze → edit forks.
- **Backend:** a golden test that a representative skill (volcano / enrichment) returns a
  well-formed `table` alongside the figure; existing golden figures unchanged.
- **e2e (Playwright, extends `e2e/figure-gestures.spec.ts` harness + `?demo=`):** run → reload →
  figure persists; force a stale state → badge + Re-run → new fresh version; sweep → 2 siblings →
  compare shows the diff; freeze → edit forks.
- **Browser-verify** at desktop (chrome-devtools MCP): the workrail IA, a stale badge, a compare
  view; console clean.

## Out of Scope

- **Layout / multi-panel composition** (Fig 1A–F) — dropped from Pillar 1 (owner uses
  PowerPoint/Photoshop; feed via existing SVG/PDF export). A future standalone feature; tech noted
  in `interview.md` (figurefirst / svgutils / Konva).
- **Auto-recompute / reactive cascade** — explicitly rejected (omics cost); re-run is always
  explicit.
- **Multi-user auth / RLS / real Supabase tables** — S4 is design-only here; the real swap is a
  later backend bucket (charter B7). This spec only keeps the model swap-ready.
- **PROV export / FAIR interop** — noted in research as a stretch; not built now.
- **Pillar 2 (direct-manip editor) & Pillar 3 (guided trust)** — separate phases; the Statistics
  node merely *sets up* Pillar 3's checklist home.

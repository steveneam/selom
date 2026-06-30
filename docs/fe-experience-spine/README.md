# FE Experience Spine — the organizing framework for the figure/AI front-end

_2026-06-30 22:05 +10:00 (Australia/Sydney). The single index that routes every front-end experience
workstream onto one backbone, so nothing is orphaned and every surface obeys the same invariants. Owner
directive (2026-06-30): fold all figure-styling work into the Prism pillar; fold the quick FE wins and the
AI-explain backlog in too; give the whole thing a solid spine. This is that spine._

## The backbone — one horizontal axis, two FE layers, one polish lane

The **engine spine** (`docs/pillars/plan.md`) is the horizontal axis — the stages every dataset flows
through:

```
  INGEST → JOIN → ROUTE → ANALYZE → GRADE → OUTPUT (figure + table + methods)
   (Data)         (Run-   (Figure-  (Stats)  (the editor / canvas)
                   skill)   data)
```

Two FE **experience layers** ride that axis, plus a thin deterministic polish lane:

- **Layer A — AI Assist (`L-AI`)** — *horizontal*. A uniform "Ask AI" affordance at **each** stage,
  governed by one apply-discipline contract. Home: **`docs/ai-cross-stage-entry-points/spec.md`**.
- **Layer E — Direct Manipulation (`L-EDIT`, Prism phase 2)** — *vertical*, concentrated on **OUTPUT**
  (with the editable table reaching into GRADE). The canvas figure editor: rulers/guides/gridlines/snap,
  the color board, the editable Prism-style table, the methods/legend stage, styling-AI. Home:
  **`docs/pillar-2-direct-manipulation/spec.md`**. Foundation: `docs/figure-editor-contract/spec.md`.
- **Lane P — Deterministic polish** — small, no-AI, no-canvas fixes at specific stages (white table,
  tooltips, suggested-skill tags, empty-space). Companions to A and E; tracked in §4 below.

The Prism track runs phase 1 (liveness/lineage — `docs/pillar-1-liveness-lineage/`, **shipped**) → phase 2
(this, direct-manipulation) → phase 3 (guided trust — Ask-Selom chat, on-hold). `L-AI` is the assist
fabric that all three phases share.

## The seven invariants (the framework both layers obey — this is what makes it robust)

Every surface in A, E, and P holds **all seven**. A change that can't is out of architecture.

1. **Render = f(spec).** Every figure is a pure function of its Plotly `FigureSpec` (`{data, layout}`).
   *All* edits — manual, AI, canvas-gesture — are JSON-Patch through the **one** store
   (`hooks/use-figure-store.ts`). No edit path bypasses it. (Already true; the canvas extends it.)
2. **AI compiles away.** Every AI action resolves to a deterministic param/override the engine runs;
   re-running from recorded params **with the gateway off reproduces the result**.
3. **One provenance chokepoint.** Every figure-producing write (human *or* AI) stamps attribution via the
   server-controlled `provenance.stamp_ai_actions` (`47d492b`). No parallel attribution path — ever.
4. **Apply-discipline by stage consequence.** `live`(cosmetic) · `staged`(data/params) · `advisory`
   (statistics). **Statistics is advisory-only** (propose-never-auto). The editable table's
   **hybrid-by-column** rule is this same dial: plotted-value columns = live (marked override),
   input/data columns = staged re-run.
5. **Deterministic path primary.** Everything works with the gateway off and the AI untouched; the manual
   controls stay fully usable; AI is assistive and renders its output *into those same controls* (a param
   diff), never as a separate artifact.
6. **One pending queue.** Staged changes (ingest + analyze) share **one** stage-partitioned pending-changes
   banner; **one** explicit re-run commits them through the chokepoint.
7. **Inference-first editor contract.** The editor adapts to *any* skill's figure via `FigureModel`
   inference (`lib/figure/figure-model.ts`); skill hints (`layout.meta.selom`) are optional refinement,
   never required. (figure-editor-contract §3.1.)

## The shared technical backbone (the code spine both layers extend — do not fork it)

| Backbone piece | File | Role |
|---|---|---|
| Canonical figure model | `lib/figure/figure-spec.ts` (`FigureSpec`) | Plotly `{data, layout}` — the one source of truth |
| The mutation funnel | `hooks/use-figure-store.ts` (`init/set/commit/flush/undo`) | every edit goes through here; undo/redo; 60-deep history |
| Patch engine + classifier | `lib/figure/patch.ts` (`applyPatches`, `classifyPatch`) | RFC-6902 JSON-Patch; `client`(live) vs `server`(recompute) split |
| Figure inference | `lib/figure/figure-model.ts` (`deriveFigureModel`) | capabilities/series/colorPaths; extend → `derivePlotTable` (editable table) |
| Plotly gesture → patch | `lib/figure/plotly-edits.ts` (`relayoutToOps`/`restyleToOps`) | granular on-chart edits → ops |
| The DOM-overlay drag layer | `components/figure/*-drag.ts` (`mark`/`threshold`/`colorbar`/`dendrogram`) | pixel-mapped overlay; **the rulers/guides reuse this exact technique** |
| The AI composer | `components/ai/ai-propose-composer.tsx` → generalize to `<AskAi stage=…>` | the L-AI entry point; backend `proposeActions(req.stage)` is already stage-aware |
| AI action registry | `app/backend/ai/registry.py` + `ai/models.py ACTION_TYPES` | the stage-typed actions the gateway may emit |
| The provenance chokepoint | `app/backend/companions/provenance.py::stamp_ai_actions` | the one server-trusted write-attribution (invariant 3) |

**Rule:** new work *extends* these; it never forks a second figure model, a second store, or a second
attribution path. That single backbone is why the "Prism + Inkscape + Photoshop" vision is an incremental
build, not a rewrite (canvas research, 2026-06-30).

## 1. Layer A — AI Assist (`docs/ai-cross-stage-entry-points/spec.md`)

A uniform `<AskAi>` at each stage; one surface (the one-click default *flows into* chat, never two modes);
apply-discipline per invariant 4. **Figure-styling AI moved OUT of here → pillar-2** (it's intrinsic to the
editor surface). Stages owned here: **route · ingest · analyze (shipped) · grade (advisory) · methods
(draft)**. The **AI-explain enhancement backlog** (`docs/ai-helpers/s5-followups.md` #11–14, + #1–7) folds
in here as the "AI-helper polish" slice.

## 2. Layer E — Direct Manipulation / Prism phase 2 (`docs/pillar-2-direct-manipulation/spec.md`)

The OUTPUT stage becomes a canvas figure editor. Owns **all figure-styling**: canvas chrome
(rulers/guides/gridlines/snap), the reactbits color board, the editable Prism-style table
(hybrid-by-column), the **white** (not dark) stats table (the cheap precursor of "editable"), the
methods/legend **stage split** (IA), styling-AI (the LIVE `restyle_figure` composer, conducted via L-AI's
`<AskAi mode="live">`), and the journal-styles phase-2 hookup. Architecture: **overlay-on-Plotly** (the
DOM-overlay layer) + Plotly-native gridlines; the multi-panel **compositing artboard** is a deferred epic.

## 3. The split of responsibility (where coupled items live)

| Item | Stage | Owned by | Note |
|---|---|---|---|
| Figure-styling AI (LIVE restyle) | OUTPUT | **pillar-2** | conducted via L-AI's `<AskAi mode="live">`, but the surface + presets are the editor's |
| Editable stats table (hybrid-by-column) | GRADE (renders) / OUTPUT (edits) | **pillar-2** | direct-manipulation; the white-table restyle is its precursor |
| Methods/legend **stage** (the IA split) | OUTPUT→methods | **pillar-2** | frees the figure view to become the canvas |
| Methods **AI draft + polish** (content) | methods | **L-AI** | fills the stage pillar-2 creates; uses `methods.build_body` |
| Suggested-skill tags (repoint at Skill Match) | ROUTE | **Lane P** + **L-AI** | the deterministic substrate the route-AI chip sits on |

## 4. Lane P — the deterministic polish backlog (the "quick FE wins", routed)

Small, no-spec, no-AI fixes. Owner deprioritized them *behind* cross-stage AI but asked they be captured
here so none are lost. Each is routed to its stage + nearest owning workstream:

| # | Quick win | Stage | Routed to | Evidence (FE reality-map, 2026-06-30) |
|---|---|---|---|---|
| P1 | **White (not dark) stats table** | GRADE | pillar-2 (precursor of editable table) | `stats-panel.tsx` renders `bg-card` (dark); confirmed |
| P2 | **Hover tooltips on truncated skill names** | ROUTE | Lane P (standalone, 1-liner) | `workbench-panel.tsx:314` `.truncate`, no `title`; confirmed |
| P3 | **Suggested-skill tags** (not popularity-ranked) | ROUTE | L-AI route phase (substrate) | `workbench-panel.tsx:93-97` sorts by `popularity`; repoint at Skill-Match `route_data` |
| P4 | **Fill the empty skill-list space** | ROUTE | Lane P / L-AI route phase | `workbench-panel.tsx:282` `max-h-[34rem]`, empty when few skills; confirmed |
| P5 | **reactbits color board** (vs native `<input type=color>`) | OUTPUT | pillar-2 (slice 2) | `panels/data-panel.tsx` uses native picker; confirmed |

P1 and P5 ride their pillar-2 slices; P3 rides the L-AI route phase; P2 and P4 are standalone Lane-P
one-offs that can ship any time (they need no spec). **Note** (FE reality-map): the data-intake pane is
*not* sparse — its "incompleteness" is the on-hold static intake questionnaire
([[selom-intake-questionnaire-rethink]]), a redesign, not a missing-controls gap.

## 5. Build order (owner: cross-stage AI first)

1. **L-AI** — extract `<AskAi>` → route → ingest → grade (advisory + reachability) → methods (draft);
   AI-helper polish slice (explain backlog) folds in. *(cross-stage-AI spec.)*
2. **Lane P standalone** — P2/P4 any time (trivial); P3 lands inside the L-AI route phase.
3. **Pillar-2** — its own research→interview→design→spec→plan (Prism discipline); slices
   gridlines → color board → rulers → guides → editable table → methods split → styling-AI. Runs after /
   alongside L-AI design once owner greenlights the pillar.

## Reading order

This README → `docs/ai-cross-stage-entry-points/spec.md` (Layer A) → `docs/pillar-2-direct-manipulation/spec.md`
(Layer E) → `docs/figure-editor-contract/spec.md` (the editor foundation) → `docs/pillars/plan.md` (the
engine spine). Memory anchors: [[selom-figure-editor-architecture]] · [[selom-figure-edit-ux-pattern]] ·
[[selom-prism-pillar-phases]] · [[selom-ai-helpers]] · [[selom-provenance-stamping-chokepoint]].

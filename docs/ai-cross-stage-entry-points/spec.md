# Cross-stage AI entry points (Layer A — AI Assist) — build spec

_2026-06-30 22:05 +10:00 (Australia/Sydney) · revised from the build-spec draft per owner directive
(2026-06-30): **figure-styling AI moves to pillar-2** (the editor surface owns it); the **AI-explain
enhancement backlog folds in here**. This is **Layer A** of the FE Experience Spine
(`docs/fe-experience-spine/README.md`) — the horizontal AI-assist fabric over the engine spine.
Build-approved (owner picked "cross-stage AI first"); each phase gets a thin build note +
review-gauntlet + fe-review before code._

## What the owner locked (2026-06-30)

1. **Sequence — cross-stage AI first**, ahead of the quick FE wins and the Prism pillar.
2. **AI interaction model — adopted in full**: **one surface** (the one-click default *flows into* chat;
   never two disjoint modes), apply-discipline keyed to stage stakes (`live`/`staged`/`advisory`/`select`/
   `draft`), **statistics advisory-only** (propose-never-auto).
3. **Figure-styling AI → pillar-2.** The OUTPUT-stage `restyle_figure`/`relabel` composer is *conducted*
   via this layer's `<AskAi mode="live">` but its surface + presets live in the editor; it ships as
   pillar-2 slice 7 (`docs/pillar-2-direct-manipulation/spec.md`), not as a phase here.
4. **Editable Prism table = hybrid by column** — a pillar-2 decision (the editor surface), cross-referenced
   only.

## Goal

An "Ask AI" affordance at the engine-spine stages this layer owns, under one interaction model, preserving
the seven spine invariants — especially: **AI compiles away** (every suggestion → a deterministic
param/override; gateway-off re-run reproduces it) and **server-trusted provenance** (every figure-producing
write stamped by the one chokepoint `provenance.stamp_ai_actions`; the FE posts the delta, never the
attribution).

## The apply-discipline contract (the spine of every stage)

One reusable composer, one rule-set, parameterized per stage by **default affordance** + **apply-discipline**
(both scale with consequence × reversibility).

| Stage | Surface | Actions | Default affordance | **Apply-discipline** | Owner |
|---|---|---|---|---|---|
| **route** (Run-skill) | skill picker / Skill Match | `select_skill` | suggested-skill **chips** (+ rationale/confidence) | **SELECT** — pre-selects in picker; user confirms + runs | Layer A |
| **ingest** (Data) | intake / data-check pane | `set_profile`·`set_design`·`map_columns`·`apply_cleaning_step` | one-click auto-detect (column/control mapping) | **STAGED** — auto-propose, human-confirm; joins the shared queue | Layer A |
| **analyze** (Figure-data) | Ask-AI composer + pending banner | `set_param`·`add_filter`·`remove_filter` | goal box + chat | **STAGED** — pending queue, one explicit re-run | Layer A — ✅ shipped (S5; the template) |
| **grade** (Statistics) | the Score / Stats stage | `explain_score` (informational) | **conversational / advisory** | **ADVISORY** — propose-only; never auto-apply | Layer A |
| **methods** | the methods/legend card | `methods.build_body` (not a gateway action) | one-click ledger draft + chat polish | **DRAFT** — inline, AI-marked, user-editable | Layer A |
| **output** (Styling) | figure styling controls | `restyle_figure`·`relabel` | one-click presets + chat | **LIVE** — JSON-Patch, instant + undoable | **pillar-2** (conducted via this composer) |

**Apply-discipline definitions:** **LIVE** (immediate JSON-Patch, undoable; cosmetic only) · **STAGED**
(shared pending banner → one explicit re-run via the chokepoint) · **ADVISORY** (proposed with
rationale/assumptions, *never* auto-applied; a separate deliberate apply) · **SELECT** (pre-selection; the
*run* carries the decision into provenance) · **DRAFT** (AI-marked, fully editable prose on a deterministic
ledger draft).

**Net:** the "magic button" never returns a black box — it returns a reviewable param diff (OLD→NEW + why)
a human could have typed, with undo + the ✨ provenance marker. The literature's *fix* for the magic-button
trust problem, free from Selom's invariants.

## Phase 0 — the reusable `<AskAi>` composer (precursor, no behaviour change)

Generalize `components/ai/ai-propose-composer.tsx` (today hardcoded to analyze — "Ask AI to tune these
inputs") into a stage-parameterized composer. The backend is **already ready**: `proposeActions(req)`
(`lib/ai/api.ts`) accepts `req.stage` and only defaults it to `"analyze"`.

```tsx
<AskAi
  stage="route" | "ingest" | "analyze" | "grade" | "output"
  label={…} placeholder={…}
  context={{ skillId, params, figureSpec?, capabilitySurface? }}
  mode="staged" | "live" | "advisory" | "select" | "draft"
  onStaged | onLive | onAdvice | onSelect | onDraft={…}
/>
```

- Keep `proposeActions` → `proposalsFromTurn` for `staged`.
- Add the **live cosmetic apply path** the composer notes is *not wired yet* (`ai-propose-composer.tsx`
  lines 57–63) — map `restyle_figure`/`relabel` from `turn.figure_spec` to JSON-Patch via
  `useFigureStore().commit`. **This path is consumed by pillar-2's styling-AI**, but it lives in the shared
  composer so every `mode="live"` caller reuses it.
- The S5 analyze composer becomes `<AskAi stage="analyze" mode="staged">` — **byte-identical** (regression
  guard the analyze path).
- Gateway-off (locked): always renders (discoverable) but states honestly it's off and changes nothing.

## Per-stage loop design

### Phase 1 — route (Run-skill) · SELECT
- **Surface:** `<AskAi stage="route" mode="select">` on the skill picker / Skill Match results.
- **Substrate:** the deterministic **Skill Match** keyword router stays *primary*
  ([[selom-skill-keyword-index]]); `select_skill` is the AI **verifier/ranker** over it. The Lane-P quick
  win **P3 — repoint the "top tags" from `popularity` to Skill-Match `route_data` suggestions** lands here
  (it's the deterministic substrate the AI chip sits on); P2 (skill-name tooltips) + P4 (fill empty space)
  ride along opportunistically.
- **Effect:** the proposal **pre-selects** a registry-validated `skill_id` (like the sweep `Suggest`
  pre-select); user confirms + runs. Unfitting intent → a `no_fitting_skill` gap, never a registry widen.
- **Provenance (locked):** record only the **resulting run** (AI-routed), not the bare selection.

### Phase 2 — ingest (Data) · STAGED · most entangled
- **Surface:** `<AskAi stage="ingest" mode="staged">` on the data-check / intake pane. Default = one-click
  auto-detect (gene-ID column, control/treatment mapping).
- **Context:** the bundle's `data_columns` (on `ActionContext`), profile + cleaning plan, candidate
  `skill_id`.
- **Effects:** `map_columns`→`_column_override` (P1-HOOKS) · `set_design`→design sheet · `apply_cleaning_step`
  →cleaning toggle · `set_profile`→data-type label. All **stage** into the next run's params; high
  consequence → the mapping is **always shown for confirmation**, never silent.
- **Apply (locked):** enters the **shared** pending queue (below), tagged by stage; one re-run carries it.
- **Provenance:** on the eventual run's `provenance.actions[]` via the chokepoint (how the data was read is
  reproduction-critical).
- **Note:** intersects the on-hold intake-questionnaire rethink ([[selom-intake-questionnaire-rethink]]) —
  the AI auto-detect is the dynamic counterpart; sequence after/alongside deciding that form's fate.

### Phase 3 — grade (Statistics) · ADVISORY · the deliberate-friction stage
- **Surface:** `<AskAi stage="grade" mode="advisory">` on the Statistics / scorecard stage + the
  reachability fix below.
- **Near-term (no new backend actions):**
  - Wire the **already-built-but-unreachable** `explain_score` onto the scorecard + `propose_sweep` onto the
    sweep UI (`s5-followups.md` #2 — both tested + MSW-mocked, no UI today).
  - The advisory composer answers "which test/correction?" with rationale + **assumptions + citations**,
    *propose-only* — it does **not** mutate the analysis.
- **Deferred (new grade-stage actions — own backend spec):** a true "apply a different test/correction"
  needs registered actions (`grade` has only the informational `explain_score` today). When built, apply
  stays **advisory** (a separate click after an assumptions checklist, GraphPad-style), never one-click.
- **The owner's "AI = general change of the dataset"** lands in the **editable table (hybrid-by-column)**,
  pillar-2 — cross-referenced, not built here.

### Phase 4 — methods · DRAFT
- **Surface (near-term):** a one-click "Draft methods/legend" + chat-polish `<AskAi stage="methods"
  mode="draft">` on the **current** methods/legend card (`PublishConfidence`) — ships without waiting on
  the IA split.
- **Effect:** a deterministic draft from the run ledger via `methods.build_body` + `legends.py`
  ([[selom-lit-synthesizer]]); chat refines ("match Nature's format", "add the FDR threshold").
- **Migration:** when pillar-2 splits out the **Methods & Legend** stage (pillar-2 slice 6), this composer
  moves there unchanged. (Pillar-2 owns the stage/IA; this layer owns the content generation.)

### Phase 5 — AI-helper polish (the AI-explain enhancement backlog)
Fold in the deferred AI-explain enhancements from `docs/ai-helpers/s5-followups.md` — they are L-AI surface
quality, not new stages:
- **#11** sweep AI-prose Copy (carry `[AI-generated]`, symmetry with the explain Copy).
- **#12** `approved_by` UI surface — NEXT#1 derives a server-trusted approver on every AI run; surface it in
  the ✨ marker tooltip (`ai-marker.tsx`, cheap) and later the Activity feed.
- **#13** staged-vs-committed model cue — label the staged preview's model "proposed by" (the documented
  propose→apply drift, `docs/provenance-chokepoint/spec.md`).
- **#14** "updated for the re-scored run" cue — a brief signal when an open explanation auto-swaps on
  rescore (today only the spinner flashes).
- Plus the still-open S5 enhancements where cheap: **#1** bulk "Accept all / Dismiss all" in the banner ·
  **#5** re-ask dedup (replace previous suggestions for a param) · **#6** changed-control highlight on the
  Marks/Threshold editors. (#2 explain/sweep reachability is built in Phase 3; #3/#4/#7 tracked separately.)

## The pending-changes queue (one shared, stage-partitioned)

One banner, partitioned by stage (already partitions by author). Holds **STAGED** changes only (`ingest` +
`analyze`/params); one explicit re-run applies them together via the chokepoint. **LIVE** (output) applies
immediately (no queue); **ADVISORY** (grade) is advisory cards (never auto-applied); **SELECT** (route) is a
pre-selection; **DRAFT** (methods) is inline prose.

## Phasing (build order)

0. **Extract `<AskAi>`** (no behaviour change; analyze byte-identical).
1. **route** — SELECT; folds Lane-P P3 (suggested tags) + P2/P4.
2. **ingest** — STAGED auto-detect-confirm; the shared queue; most careful (data-contract gates).
3. **grade** — ADVISORY; `explain_score`/`propose_sweep` reachability first, then the advisory composer.
4. **methods** — DRAFT on the current card; migrates to the dedicated stage later.
5. **AI-helper polish** — the explain backlog (#11–14 + cheap #1/#5/#6).

Each phase = its own build note + `review-gauntlet` (correctness) + `fe-review` (V·R·D·A·R·N) + verify on
real data + live backend (NOT dev:mock) + commit (named paths, no AI sign-off).

## Invariants (the seven spine invariants — all hold)

Render = f(spec) · AI compiles away · one provenance chokepoint (no parallel path) · apply-discipline by
consequence (statistics advisory-only) · deterministic path primary (one surface per stage; manual controls
primary; AI output renders *in those controls*, never a separate artifact) · one pending queue ·
inference-first editor contract. Plus: `tier` always registry-derived, never trusted from a proposal;
unfulfillable-but-coherent intents → gaps (review-only), never auto-widen the registry.

## Cross-references (not built here)

Pillar-2 (`docs/pillar-2-direct-manipulation/spec.md`) owns: figure-styling AI (slice 7), the editable
table (hybrid-by-column), the methods/legend stage split, the color board, canvas chrome. The FE Experience
Spine (`docs/fe-experience-spine/README.md`) is the index. The provenance chokepoint
([[selom-provenance-stamping-chokepoint]]) is the one write-attribution every phase routes through.

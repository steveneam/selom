# Cross-stage AI entry points — design spec (build deferred)

_2026-06-30 · NEXT#2, `s5-followups.md` #0. **Design-first / Prism-level** — the gateway spine (S1–S4)
already supports stage-typed actions everywhere, but the "Ask AI" composer is wired ONLY at the figure-
data (analyze) stage. This spec maps each stage's loop so the per-stage composers can be built against an
agreed design rather than ad hoc. **This is a design deliverable; nothing is built from it yet** — the
open questions at the end are for owner review._

## Goal

Give the user an "Ask AI" affordance at each engine-spine stage where the gateway can already act, so the
AI assists across the whole pipeline — not just figure-data tuning — while preserving the two invariants
that make the write-path trustworthy:

1. **AI compiles away** — every AI suggestion resolves to a deterministic param/override the engine runs;
   re-running from recorded params with no gateway reproduces the result.
2. **Server-trusted provenance** — every AI write is stamped by the one chokepoint (NEXT#1,
   `docs/provenance-chokepoint/spec.md`); the FE posts the delta, never the attribution tag.

## The spine stages and what the gateway already supports

`ActionContext.stage ∈ {ingest, join, route, analyze, grade, output}`. Registered actions per stage
(`ai/registry.py`, `ai/models.py ACTION_TYPES`):

| Stage | Surface today | Actions available | Wired? |
|---|---|---|---|
| **ingest** (Data) | the intake / data-check pane | `set_profile`, `set_design`, `map_columns`, `apply_cleaning_step` | ❌ no entry point |
| **join** | (multi-file combine) | — (no actions yet) | n/a |
| **route** (Run-skill) | the skill picker / Skill Match | `select_skill` | ❌ no entry point |
| **analyze** (Figure-data) | the Ask-AI composer + pending-changes banner | `set_param`, `add_filter`, `remove_filter` | ✅ shipped (S5) |
| **grade** (Score) | the Score stage | `explain_score` (informational) | ✅ shipped (AI-EXPLAIN) |
| **output** (Styling) | the figure styling controls | `restyle_figure`, `relabel` (cosmetic) | ❌ no entry point |

So three stages need entry points (**ingest**, **route**, **output**); **analyze** + **grade** are done.

## The unifying pattern (reuse, don't re-invent)

The analyze loop is the template. Generalize it into one reusable composer, parameterized per stage:

- **One `<AskAi stage=… context=…>` composer** — a text input + submit that calls
  `proposeActions({ stage, skill_id, params, goal, figure_spec?, capability_surface? })`, maps the
  `HelperTurn` via `proposalsFromTurn`, and routes the proposals to the stage's surface. The composer
  itself is stage-agnostic; what differs is **(a)** the context it posts and **(b)** where the proposals
  land + how they apply.
- **Two action tiers drive two surfaces** (already true in analyze, generalize):
  - **cosmetic** (applied live, JSON-Patch) → the change is immediate + undoable. Used by `output`
    (`restyle_figure`/`relabel`) and any live-preview ingest tweak.
  - **recompute** (staged) → enters a pending-changes queue and applies on ONE explicit re-run through
    the #1 chokepoint. Used by `analyze` and by `ingest`/`route` (they change what the next run computes).
- **Every write goes through the NEXT#1 chokepoint.** Ingest/route/output writes that produce a new
  figure must stamp provenance via `stamp_ai_actions` — no stage gets its own attribution path.

## Per-stage loop design

### ingest (Data stage) — `set_profile` · `set_design` · `map_columns` · `apply_cleaning_step`

- **Surface:** an "Ask AI about this data" composer on the data-check / intake pane (next to the
  layered data-type label + cleaning plan).
- **Context posted:** `stage:"ingest"`, the bundle's `data_columns` (already on `ActionContext`), the
  profile + cleaning plan, the candidate `skill_id` if one is selected.
- **Actions → effects:** `map_columns` → the `_column_override` reserved param (P1-HOOKS); `set_design`
  → the design sheet selection; `apply_cleaning_step` → the cleaning toggle param; `set_profile` → the
  data-type label override. None execute on their own — they **stage** into the next run's params.
- **Apply mechanism:** these are *pre-run* settings. Two design choices (open question Q1): either they
  feed the **same** analyze-stage staged-params queue (so the run that eventually fires carries them), or
  the Data stage gets its own "apply to next run" affordance. Recommendation: stage into the shared run
  params; surface in the pending-changes banner tagged by stage.
- **Provenance:** recorded on the eventual run's `provenance.actions[]` via the chokepoint (these are the
  AI's contribution to *how the data was read*, which is reproduction-critical).

### route (Run-skill stage) — `select_skill`

- **Surface:** an "Ask AI which analysis" composer on the skill picker / Skill Match results.
- **Context posted:** `stage:"route"`, the data profile + columns, the user's goal.
- **Action → effect:** `select_skill` proposes a `skill_id` (validated against the registry — the gateway
  cannot invent a skill; an unfitting one becomes a `no_fitting_skill` gap).
- **Apply mechanism:** selecting a skill is a navigation/selection act, not a figure write. Recommendation:
  the proposal pre-selects the skill in the picker (like the sweep `Suggest` pre-select), the user
  confirms + runs. The **run** itself then carries the route decision into provenance via the chokepoint
  (the run was AI-routed). Open question Q2: does a route suggestion alone (no run yet) need a provenance
  record, or only the resulting run? Recommendation: only the run (no figure exists until then).
- **Overlap:** Skill Match already deterministically routes papers→skills ([[selom-skill-keyword-index]]).
  `select_skill` is the AI verifier over that, not a replacement — keep the deterministic router primary.

### output (Styling stage) — `restyle_figure` · `relabel` (cosmetic)

- **Surface:** an "Ask AI" composer in the figure styling controls.
- **Context posted:** `stage:"output"`, the current `figure_spec`, the goal.
- **Actions → effects:** cosmetic JSON-Patch applied **live** to the figure spec (no recompute).
- **Apply mechanism:** immediate + undoable (the analyze cosmetic path already exists). Cosmetic changes
  don't alter the data/result, so the provenance question is lighter — open question Q3: do cosmetic AI
  restyles get a `provenance.actions[]` entry (for "this figure's styling was AI-assisted") or are they
  styling-only and uncredited? Recommendation: record them (consistency + honesty), tier `cosmetic`.

## Cross-cutting UX decisions (the Prism-level calls — for review)

- **Q1 — one pending queue or per-stage queues?** Recommendation: ONE pending-changes banner that
  partitions by stage (the banner already partitions by author). Ingest + analyze recompute proposals
  share the queue; the single explicit re-run applies them together. Avoids N banners.
- **Q2 — route suggestion provenance.** Recommendation: record only the resulting run, not a bare
  selection.
- **Q3 — cosmetic-restyle provenance.** Recommendation: record (tier cosmetic) for honesty.
- **Q4 — composer placement / density.** Each stage's composer must not crowd the deterministic controls
  (the manual path stays primary; AI is assistive). fe-review (V·R·D·A·R·N) gates each.
- **Q5 — gateway-off posture.** With the gateway off (default) every composer proposes nothing (empty
  plan). The entry point should still render (discoverable, "lights up" when a key lands) but say so
  honestly — same lit/unlit pattern as the explain helpers.

## Recommended phasing (when build is approved)

1. **Extract the reusable `AskAi` composer** from the analyze stage (no behaviour change) — the precursor.
2. **output (styling)** first — cosmetic-only, lowest risk (no recompute, no data-contract gates), proves
   the generalized composer.
3. **route** next — pre-select + confirm, overlaps the existing sweep-suggest pattern.
4. **ingest** last — highest value but most entangled (it changes how the data is read → the run params →
   the data-contract gates); needs the most careful staged-vs-applied design.

Each phase = its own build spec + review-gauntlet + fe-review.

## Invariants any build must hold

- The deterministic/manual path stays primary and fully usable with the gateway off.
- Every figure-producing AI write stamps provenance via the NEXT#1 chokepoint — no parallel path.
- `tier` is always registry-derived, never trusted from a proposal.
- Unfulfillable-but-coherent intents become gaps (review-only), never auto-widen the registry.

## Open questions for review

Q1 (shared vs per-stage pending queue) · Q2 (route provenance) · Q3 (cosmetic-restyle provenance) ·
Q4 (composer placement per stage) · Q5 (gateway-off entry-point posture). Resolving these unblocks the
phase-1 build spec.

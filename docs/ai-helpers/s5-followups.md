# AI-Helpers S5 — deferred follow-ups

_2026-06-30 · the enhancement backlog surfaced by the `review-gauntlet` + `fe-review` (V·R·D·A·R·N)
passes over the S5 diff. The **bugs** they found are fixed in the S5 commit; these are **enhancements**
(missing affordances / nice-to-haves), deliberately deferred. The retro consumes this list._

## Fixed in the S5 commit (not deferred)
- **Gauntlet:** design-sheet dropped on the AI re-run (BE+FE) · `reconcile()` clobbering `aiProposals`
  (`mergeFigures`) · the panel's own Re-run bypassing `/ai/apply` · false AI attribution after a manual
  override (`approvedActions` gated on `authorOf`) · cosmetic-plan misreport · panel over-painting the header.
- **fe-review:** the ✨ marker occluding the control value readout (ParamControl `badge` slot) · the
  editing toolbar overflowing under the panel at ≤1400px (`flex-wrap`) · Reset not restoring the a/b-label
  toggle · the staged marker saying "applied"/dropping the model (new `staged` marker state) · proposed
  suggestions uncounted (header + tab badge now count all outstanding) · mock duplicate proposal id ·
  header badge missing `aria-label`.

> **REORG 2026-06-30 — these now have homes (FE Experience Spine).** This backlog is no longer the
> task-of-record; it is the source list. Routing: **#0** → `docs/ai-cross-stage-entry-points/spec.md`
> (Layer A; figure-styling split to `docs/pillar-2-direct-manipulation/spec.md`). **#11–14** (+ cheap
> #1/#5/#6) → that spec's **Phase 5 "AI-helper polish"**. **#2** reachability → its **Phase 3 (grade)**.
> Index: `docs/fe-experience-spine/README.md`. Items below stay as the detailed evidence the specs cite.

## Deferred — enhancements (route through the retro)
0. **Cross-stage AI entry points (owner-flagged 2026-06-30).** The "Ask AI" composer is wired ONLY at
   the figure-data (analyze) stage — intentional for S5. But the gateway spine (S1–S4) already supports
   stage-typed actions elsewhere, with NO FE entry point yet: **Data/ingest** (`set_profile` /
   `set_design` / `map_columns` / `apply_cleaning_step`) · **Run-skill/route** (`select_skill`) ·
   **Statistics/grade** (`explain_score` — see #2) · **Figure-styling/output** (`restyle_figure` /
   `relabel` — cosmetic, see #3). Sequence the per-stage composers/entry points (this is a Prism /
   pillars-level UX decision, not a one-off; design each stage's loop before building).
1. **Bulk proposal actions** — "Accept all" / "Dismiss all" in the banner (today: per-row only). A
   multi-action plan must be accepted/dismissed one row at a time; Reset un-stages but keeps the rows.
2. **`explain_score` + `propose_sweep` UI entry points** — both endpoints are built, unit-tested, and
   MSW-mocked (`lib/ai/api.ts` `explain()`), but have **no UI surface**: the jobs are unreachable in the
   app. Wire `explain_score` onto the reproducibility scorecard and `propose_sweep` onto the sweep UI.
3. **Committed-figure control attribution** — opening a committed AI-assisted figure's Figure-data shows
   no ✨ on its controls (the markers read the pre-commit `aiProposals` queue, emptied on re-run;
   `provenance.actions[]` is not read there). Attribution survives in the Activity feed + the "AI-assisted"
   lineage label. Optional: derive control markers from `provenance.actions[]` for committed figures.
4. **Activity / Gaps drill-through** — Activity History rows + Gaps entries are inert; no navigate-to-figure
   from a logged run, no drill to the `context_hash` source of a gap, no manual refresh (Retry only on error).
5. **Re-ask dedup** — the composer's `addAiProposals` concatenates; a second Ask targeting the same param
   yields two rows for that key. Add dedup / "replace previous suggestions for this param".
6. **Changed-control highlight on the Marks/Threshold editors** — the amber/fuchsia ring is applied to the
   param grid only, not the bespoke Marks/Threshold figure-data controls; extend for one changed-state language.
7. **Actor-tag forgery hardening** (carried from S5 backlog) — `/ai/apply` trusts the client-stamped
   `approved_by`/`approved_at`; have the FE post the staged delta so the backend re-derives a server-trusted tag.

## Deferred — AI-explain wiring (NEXT#1, 2026-06-30 · gauntlet + fe-review)

_The HIGH source-honesty fix, the sweep top-3 chips, cursor-pointer, the explain Retry, and the
mock/param-type guards shipped in the wiring commit. These are the deliberately-deferred enhancements
(docs/ai-explain-wiring/spec.md is the shipped scope: make the two helpers reachable + the sweep
recommender useful offline)._
8. **Explain — Copy / "add to methods"** — the grounded explanation is prose a reproducer would want to
   capture; there is no Copy control, and the repo has a methods-synth feature it could feed.
9. **Explain — refresh on re-score** — `ExplainScore` caches the result in local state; an open panel
   won't re-run if the scorecard prop updates (a re-scored run). Re-fetch on scorecard change, or stale-flag it.
10. **Sweep — surface live AI prose** — the picks (`suggestions[]`) are ALWAYS deterministic by design
    (grounded + reproducible); when `SELOM_AI_GATEWAY=live`, the `explain` `text` carries the AI's narrative
    reasoning, which the chip panel currently drops. Add an AI-attributed prose line (with the ✨ badge) below
    the chips when `source==="ai"`.

## Deferred — fe-review gaps over the NEXT#1 + NEXT#3 diff (2026-06-30)

_The confirmed A-attributable finding (Copy strips the AI tag) + the Copy false-positive + the stale-Copied-
on-rescore edge shipped in the NEXT#3 commit. The Copy `focus-visible` ring shipped too. These are the
deliberately-deferred enhancements the fe-review G1 (jobs-to-be-done) pass surfaced._
11. **Sweep AI-prose has no Copy** — `ExplainScore` got a Copy button but the new sweep AI-prose line
    (`source==="ai"`) is hand-select-only. Add the same attributed Copy for symmetry (carry `[AI-generated]`).
12. **`approved_by` has no UI surface** — NEXT#1 now derives a server-trusted `approved_by` on every AI run,
    but the applied ✨ marker tooltip (`ai-marker.tsx`) shows only actor·model·approved_at and the Activity
    History row shows none of it. Surface the approver (the audit trail records who the user can't read). Cheap
    in the marker tooltip; the Activity feed is a bigger add.
13. **Staged-vs-committed model cue** — pre-commit the ✨ marker shows the client-held `proposal.model` (the
    proposing model); post-commit it shows the server-stamped `action.model`. With the delta refactor the FE no
    longer sends model, so the staged preview's model is the *proposing* gateway and can differ from the
    apply-time one (the documented propose→apply drift, `docs/provenance-chokepoint/spec.md`). Add a reconciling
    signal at the Re-run step, or label the staged model as "proposed by".
14. **"Updated for the new score" cue** — the auto refresh-on-rescore re-fetches silently (only the spinner
    flashes). Add a brief "updated for the re-scored run" cue when an open explanation swaps.

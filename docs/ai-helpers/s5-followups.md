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

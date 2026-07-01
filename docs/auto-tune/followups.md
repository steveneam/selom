# Auto-tune — follow-ups (review backlog)

> From the dual review over the Phase 1 (analyze) working tree (2026-07-01): `review-gauntlet`
> (3 confirmed / 3 dropped) + `fe-review` (4 confirmed / 3 dropped + a G1 user-task walkthrough + the
> G2 render gate). The confirmed breaches were **fixed in the Phase 1 commit** (below). The remaining
> items are the intentionally-deferred phases + the D4-deferred richer surface — captured so none are
> lost, not owed on Phase 1.

## ✅ FIXED (2026-07-01) — Auto-tune clobbered the design contrast + downgraded the method on a bulk `deg` figure

> Found in the project-workspace-refactor browser smoke (2026-07-01, real backend, a real `deg` figure);
> **fixed the same day** in `lib/skills/api.ts` `stageableRecommendations` (+2 unit tests, +1 empty-fill
> lock). Real-engine confirmed: `recommend_params("deg")` emits every design/method param as
> `scaled=False` (value≡default) → the gate below skips them on a committed contrast → clean no-op;
> `umap_scrna` `n_hvg` stays `scaled=True` → still fills. This was a *correctness* issue (a "best-practice"
> button proposing a scientifically-wrong method + wiping the experimental design), ranked above the
> cosmetic D4 items below. NOT a "look up better numbers" gap — the numbers are already right; the *policy*
> was wrong. **The fix is a one-rule FE staging policy; the backend was left as-is (its curated layer is
> already correctly scoped).**

**Symptom.** On a bulk-RNA-seq `deg` figure whose contrast is set (`reference=CE4_4_iRPE`,
`treatment=CE4_5_iRPE`, `method=pydeseq2`, `mode=bulk`), clicking **Auto-tune inputs** proposes:
`mode bulk→auto · method pydeseq2→wilcoxon · reference CE4_4_iRPE→"" · treatment CE4_5_iRPE→""`.
That would **wipe the design contrast** and **downgrade the method** — `pydeseq2→wilcoxon` is the *wrong
direction* for bulk (DESeq2 is the bulk best practice; Wilcoxon is the single-cell default).

**Root cause.** `engine/recommend.py:recommend_params` builds its baseline from **every** param's
`param_spec` default (`recommend.py:81-83`), then the curated layer only moves `n_hvg` (umap/cluster).
The module's docstring correctly declares design params (`reference/treatment/condition_col/sample_col`)
are **ingest's job, not this recommender's** — but the *raw default baseline* still emits them (as
`scaled=False`, `why="skill default"`), and the FE `stageableRecommendations` (`lib/skills/api.ts`) diffs
those raw defaults against the figure's *committed, design-correct* values → stages the difference. The
scope boundary leaks through the FE staging. (The shipped UMAP verify missed it because that figure's
non-`n_hvg` params already equalled their defaults, so nothing else diffed.)

**Fix (one policy rule, FE `stageableRecommendations`) — SHIPPED.** Stage a rec as a change **only when
it's a curated move (`scaled===true`) OR the figure's current value for that key is empty/unset** — a raw
static default (`scaled=false`) must never *overwrite* a committed non-default. `ParamRec.scaled` already
carries exactly this distinction (curated best-practice move vs. static baseline). Result: Auto-tune on a
well-configured `deg` figure becomes a clean no-op → *"Already at the best-practice settings"*, while it
still fires `n_hvg→2000` on a UMAP figure that needs it and still fills genuinely-empty inputs. Landed as
the gate `if (!rec.scaled && committedIsSet) continue;` after the equality/user-edit checks.

**Test.** `stageableRecommendations` unit: (a) deg recs (all `scaled=false`) + a base with
`reference/treatment/method` set → `applied=[]` (no clobber); (b) a `scaled` `n_hvg` rec + a base with
`n_hvg` unset → `applied=[n_hvg]`; (c) a `scaled` rec whose key the user hand-staged → still `skipped`
(existing behaviour, unchanged). Keep the backend as-is (its curated layer is already correctly scoped)
or add a one-line note; the real fix is the FE staging policy.

**Separate, later (not this fix).** A *cited* expansion of the small curated allowlist (which knobs beyond
`n_hvg` deserve a defensible best-practice default) — additive, literature-backed, its own change.

## Fixed in the Phase 1 commit (2026-07-01)

- **[gauntlet · design, medium] Deterministic path was not the primary CTA.** Auto-tune was `outline`
  while the AI "Ask" was the filled primary — the loudest button pointed at the gateway-off (inert-by-
  default) path, against the "deterministic path primary" invariant. Auto-tune is now `variant=default`
  (neutral `--primary`, never `--stage-ai`/✨ — R8); "Ask" steps back to `outline` **only when Auto-tune
  is present** (the standalone route composer keeps "Ask" primary).
- **[gauntlet · a11y, medium] Outcome not announced.** The Auto-tune outcome rendered into a plain
  `<p>` with no live region and the button had no busy state for AT. Now `role="status"`/`aria-live=
  "polite"` on both notes (Auto-tune + the chat note) + `aria-busy={tuning}` on the button (WCAG 4.1.3).
- **[fe-review · V, medium] Note count vs. visible cue mismatch.** `stageableRecommendations` counted
  changes against the STAGED value while every visible pending signal (amber ring, banner count) is vs.
  the figure BASE — so the note could claim a change with no visible cue (e.g. a rec that reverts a
  user's staged value to default). Now the helper diffs against the committed base and the note counts
  exactly the keys that become visibly pending.
- **[fe-review · R, low] Silent overwrite of a user's hand-edited staged value.** Auto-tune merged over
  any staged value, and only the blunt global Reset (to base) could undo it. Now `stageableRecommendations`
  **skips any user-touched key** (staged ≠ base) and reports it (`skipped[]` → "Left your N edited
  input(s) as-is") — Auto-tune fills only untouched inputs, never clobbers an in-progress edit.
- **[gauntlet + fe-review, low] Contradictory direction ("below" vs "above").** The idle hint said
  "below", the success note said "above"; "above" also misdirected (the pending banner itemizes only AI
  proposals — a non-AI change shows just a count there). Both strings now say "review the changed inputs
  **below**" (where the amber-ringed controls actually render, in the FigureDataPanel under the composer).
- **[fe-review · R, low] Stale outcome note.** The note lived only in `<AskAi>` local state and was
  cleared only on the next click, so it kept asserting pending changes after a Reset/Re-run/figure
  switch. Now cleared on the pending true→false edge (Reset / committed Re-run) and on a `scopeKey`
  change (new figure/skill/dataset).
- **[fe-review · G1, spec-central] "Never a black box" — the OLD→NEW+why diff.** The `why` was dropped
  and the note listed keys only. `stageableRecommendations` now returns `applied[{key, from, to, why}]`;
  the outcome note renders each change as `key old→new (why)` — the reviewable diff the spec headline
  (§What / R9a) promises.

## Deferred — the richer per-control surface (rides the D4 "recommended" actor)

These were **explicitly deferred in the spec (D4)**: v1 stages recommendations as human-authored pending
changes (no distinct provenance actor / banner category), so the per-control affordances below are not
owed on Phase 1. They are the "cleaner-honesty upgrade" D4 flagged.

1. **Per-control `why` marker + OLD→NEW on each changed control (R9b).** v1 shows the full diff+why in
   the outcome note; a per-control tooltip/marker (reuse `s5-followups.md` #6 changed-control affordance)
   and an OLD→NEW row (like `AiProposalRow`) need a "recommended" author category threaded into
   `authorOf`/`pendingCounter`/`FigureDataPanel`. (fe-review G1: "understand WHY / see OLD→NEW per
   control".)
2. **Per-control revert of a single auto-tuned input.** The existing per-control revert
   (`figure-data-panel.tsx`) renders only for `author==='ai'`; an auto-tuned key (author `user`) has no
   per-control undo — only the global Reset. A distinct "recommended" marker would carry its own revert.
   (v1 mitigations already in place: user edits are never overwritten, and the note lists exactly what
   changed so a manual revert is targeted.)
3. **A batch "Undo Auto-tune".** Snapshot `fdParams` before the click and offer a one-click restore of
   the pre-click state (finer than the global Reset-to-base).
4. **Distinguish "recommended" from "you" in the banner counter.** Auto-tuned changes count under "you"
   (correct that they're ✨-free); a neutral "recommended" tally would let the user tell what Auto-tune
   set from what they typed after further editing. (D4-deferred.)

## Deferred — the remaining Auto-tune phases (spec §Phasing 2–4)

5. **route** — "Auto-pick skill" (pre-select `dataFit.fits[0]`; FE reuse, no new BE).
6. **ingest** — "Auto-detect design" (re-apply the persisted `design` prefill; FE reuse). Note: overlaps
   the shipped INTAKE-DESIGN questionnaire prefill — confirm it's additive, not redundant, before building.
7. **methods** — "Draft methods" (`POST /methods/compose`; DRAFT discipline).
8. **grade** — advisory "Recommended stats" card (deterministic, never applied); may collapse to
   surfacing the existing scorecard advice.

## Minor / ambiguous (not blocking)

- **No-context disable + hint (R9).** R9 says "no skill selected / no dataset context → the button is
  disabled with a hint." v1 leaves the button enabled with no dataset (it returns the all-static
  baseline, per the spec's Error Behavior). Decide whether to disable+hint or keep the fail-soft baseline
  (lean: keep the baseline — a skill's defaults ARE best practice, so the button is still meaningful).
- **Generic error copy.** An Auto-tune failure shows "Couldn't fetch recommendations (404)." with no next
  step; nothing is mutated on failure (safe), but the copy could point at a next step.

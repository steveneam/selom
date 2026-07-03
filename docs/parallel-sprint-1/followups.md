# Parallel Sprint 1 — review followups (fixes deferred to next session)

**Stamp:** 2026-07-04 04:10 +10:00 · base `1d76ae7` (local `main`, unpushed at capture).
**Status:** Sprint 1 (ENG · ERG · FIG) **merged + integrated-gates-green + WS2.7 live-verified.** The
milestone **review-gauntlet** (2 confirmed) + **fe-review** (26 agents) ran over the sprint diff
`4215365..1d76ae7`. **Owner directive: apply ALL review fixes NEXT session — no source changes were made
this session.** Main is push-ready as-is; the items below are polish/hardening on the *new* Sprint-1 code,
not regressions to existing features.

Clean bill: **ENG** (vocab single-sourcing, drift-guard, WS2.7/2.8) and **FIG core** drew **zero
correctness/invariant findings** — the behavior-preserving refactor + the frozen-contract invariants held
under adversarial verification. All findings are FE interaction/a11y/affordance, concentrated in the two new
UI surfaces (ERG blind-marking · FIG gridline controls).

---

## P1 — correctness / WYSIWYG (fix)

**1. FIG: minor-gridline style control doesn't match the render.** *(fe-review — CONFIRMED)*
`app/frontend/lib/figure/gridlines.ts` — `minorShowOps()` writes only `{ …minor: { showgrid: true } }` on
toggle-on and **never applies the selected `griddash`**. The "Minor style" `SelectField` shows `Dot` (from
the hardcoded `GRID_DEFAULTS.minorDash` fallback), but the figure renders Plotly's default minor line until
the user manually re-selects the value — the panel's live/WYSIWYG promise fails for this one leaf.
**Fix:** on minor toggle-on, write the current minor dash (and minor color/width if P4#4 is taken) alongside
`showgrid:true`, so the emitted op matches what the control displays. Add a unit test asserting toggle-on
emits the shown dash.

## P2 — accessibility (fix)

**2. ERG: blinded cell label is near-illegible (~2:1 contrast).** *(gauntlet #1 — MEDIUM)*
`app/frontend/components/project/marks-editor.tsx:196` — in blind mode the per-cell header flips to
`italic text-muted-foreground/40` (effective ≈ 2.0:1, fails WCAG 1.4.3 AA 4.5:1, and even the 3:1 large-text
floor). Because blind mode hides the real condition label, this greyed `Cell N` token is the **only** way the
operator tells cells apart while marking — a load-bearing identifier rendered nearly invisible.
**Fix (one-liner):** drop the `/40` on the blind branch → `italic text-muted-foreground` (≈ 6.3:1); keep the
`italic` as the "blinded/anonymized" cue. Non-blind branch (`text-foreground/80`) is fine — leave it.

## P3 — design decision (owner call) — ERG blind-marking scope

**3. "Blind marking" doesn't blind the primary surface, and leaks the condition.** *(gauntlet #2 + fe-review,
both CONFIRMED — same root)*
The toggle blinds the numeric editor list but not the surface the operator actually marks on:
- **The waveform CANVAS stays unblinded.** `blind` is state local to `marks-editor.tsx` and never reaches the
  figure; the canvas ERG facet titles (condition labels, baked into the spec), condition colors, and legend
  stay fully visible — and the editor tells the operator to "drag the dots on the figure". So the hypothesis
  bias the feature exists to prevent is **not** prevented on the surface that matters most.
- **The µV column leaks condition.** Each `MarkRow` still shows `{mark.uv} µV` (marks-editor.tsx:311); b-wave
  amplitude is the canonical genotype discriminator. **Tradeoff:** the µV is *also* a legit marking cue
  (confirms the mark sits on the peak/trough), so masking it may hurt the task — not a clean win.
- **Cell order leaks condition.** Cells are relabelled sequentially `Cell 1..N` in first-seen order; an
  operator who knows the canonical condition ordering can still map position → condition.

**Decide first (product question — what does "blind" promise?), then implement:**
- **(a) True blind** — thread `blind` to the figure canvas and de-identify facet titles / legend / condition
  colors while blind (bigger, cross-component — touches figure rendering near the FIG boundary; coordinate),
  randomize cell order, mask µV. Delivers the stated anti-bias intent.
- **(b) Honest scope** — keep it editor-only and re-frame to "Hide condition labels" (the inline subtext +
  aria-label already say exactly this); document the canvas/µV as out of scope. Cheap + honest.
- **(c) Middle** — de-identify the canvas facet titles (the biggest leak) but keep µV as a marking cue.

*Lead recommendation: pick (a) vs (b) before touching code — it's a product call, not a bug.*

## P4 — FIG gridline affordance polish (minor, optional) *(fe-review "gap"s)*

4. **Minor color/width have no control** — only minor *dash* is exposed; minor `gridcolor`/`gridwidth` fall to
   Plotly defaults, so a user can't make minor lines visually subordinate to major ones. (Add to the minor
   sub-group; pairs with P1#1.)
5. **No per-axis control** — all writers mirror x+y (`bothAxes`/`minorMergeOps`). Not a regression (the removed
   axes-panel toggle was also both-axes), but "grid only X / only Y, or X≠Y" is an unserved task if wanted.
6. **No per-group reset** — color/width/dash/minor have no one-click "restore default"; only global Undo + the
   spacing "Auto". Match the ERG-marks pattern (per-row Reset + "Reset all to auto").
7. **Discoverability breadcrumb** — the Axes-panel section was renamed to "Zero line" with no in-UI pointer to
   the Style-tab's new "Axis gridlines" group (the redirect lives only in a code comment). A returning user who
   knew the old location gets no signpost.
8. **Grid-spacing input** — no unit hint; non-numeric / ≤ 0 is silently coerced to Auto with no validation
   message; on a log axis `dtick` is in log units, unhinted. Add a hint + gentle inline validation.

## Verified working (fe-review "present") — do not re-litigate

Blind editor list · marks + staged overrides survive toggling · "operator-moved" readout + "· auto X ms"
seed · per-row Reset + "Reset all to auto" · staged-vs-applied footer · FIG show/color/width/style toggles ·
grid spacing (clear→auto) · instant live re-render · Undo/Redo. The sprint's features work; the above is
hardening.

---

## RESUME PROMPT (next session)

> # Selom — Sprint 1 review-fix pass (do everything) · 2026-07-04 04:15 +10:00 · Claude
> **Read first:** this file (`docs/parallel-sprint-1/followups.md`) — the ranked findings — then `COORDINATION.md`
> + `agent_handoff/CURRENT.md` (NEXT item **S1**). `git fetch && git status`.
> **State:** Sprint 1 (ENG·ERG·FIG) is merged on local `main` (`7ff02a2` at capture — **14 commits ahead of
> `origin/main`, UNPUSHED**; confirm `git rev-list --count origin/main..HEAD`). The 3 lane worktrees
> `D:/selom-{eng,erg,fig}` + their merged branches still exist. Back to sequential single-session (no lanes).
> **This session = do everything:** apply the review fixes, make the P3 call, verify, commit, get it pushed, clean up.
> **Order:**
>  1. **P3 FIRST — it's a product decision, not a bug.** Before any P3 code, put the forcing question to the owner
>     (`AskUserQuestion`): should "Blind marking" (a) **truly blind** — thread `blind` to the figure canvas +
>     de-identify facet titles/legend/condition-colours while blind, randomise cell order, mask µV (bigger; reaches
>     `components/figure/figure-canvas.tsx`), or (b) **honest scope** — keep it editor-only + rename to "Hide
>     condition labels" (cheap)? Both reviews confirmed the canvas/µV/cell-order leak. Don't code P3 until answered.
>  2. **P1 (fix)** — FIG minor-gridline WYSIWYG bug: `lib/figure/gridlines.ts` `minorShowOps()` must write the
>     *shown* minor dash (+ minor colour/width if you take P4#4) on toggle-on so the control matches the render. Add a unit test.
>  3. **P2 (fix)** — ERG a11y one-liner: `components/project/marks-editor.tsx:196`, drop the `/40` on the blind
>     branch → `italic text-muted-foreground` (keep the italic as the blinded cue).
>  4. **P3 (implement per the decision).**
>  5. **P4 (optional polish)** — FIG gridline affordances as prioritised (minor colour/width · per-axis · per-group
>     reset · axes→style breadcrumb · spacing unit hint/validation).
> **Verify:** FE tsc + eslint(0) + vitest; live-verify P1 + P3 in the running editor (`npx next dev --webpack`; FIG
> gridlines are client-side → `dev:mock` fine; if P3(a) touches the canvas, drive a real ERG figure). Anything
> backend → real data + a live uvicorn.
> **Close out:** commit the fixes (named paths, no AI sign-off) → get `main` **pushed** (owner's gate; origin was
> 14 behind) → remove the 3 worktrees (`git worktree remove D:/selom-eng` ×3, `--force` if dirty) + delete the
> merged branches (`git branch -d agent/{eng/consistency,erg/marks-v2,fig/gridlines}`).
> **Landmines:** BE via the uv-3.12 PY + `PYTHONPATH=…\.venv\Lib\site-packages` (NOT `uv run` — EDR) · `npx next
> dev --webpack` (plain `next dev`/Turbopack panics 0xc0000142) · verify on real data not `dev:mock` for anything
> data-bearing · git `user.email` = the Vercel noreply · **no AI sign-off** on commits/PRs.

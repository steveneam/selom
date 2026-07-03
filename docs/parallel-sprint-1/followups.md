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

> # Selom — Sprint 1 review-fix pass · <stamp when you start> · Claude
> Read `docs/parallel-sprint-1/followups.md` (this file) + `COORDINATION.md` first. `git fetch && git status`.
> Sprint 1 is merged on `main` (`1d76ae7` at capture; may be pushed/advanced — check). **Apply the review
> fixes here.** Suggested order: **P1** (FIG `minorShowOps` writes the shown dash — WYSIWYG bug, `gridlines.ts`
> + a unit test) → **P2** (ERG contrast one-liner, `marks-editor.tsx:196`) → **P3** (get the owner's blind-scope
> decision **before** coding: true-blind vs honest-rename — it's a product call) → **P4** FIG gridline polish
> (optional, as prioritized). Mostly FE (`marks-editor.tsx`, `lib/figure/gridlines.ts` + `style-panel.tsx`);
> P3(a) may reach the figure canvas (`components/figure/figure-canvas.tsx`) — that crosses the ERG↔FIG line, so
> scope it deliberately. Landmines unchanged: BE via uv-3.12 PY + PYTHONPATH (not `uv run`), `npx next dev
> --webpack`, verify on real data + live backend (FIG gridlines are client-side → `dev:mock` ok), git email =
> the Vercel noreply, no AI sign-off. After the fixes: FE tsc/eslint/vitest (+ a targeted re-verify), then
> commit + hand back for push. The 3 Sprint-1 worktrees (`D:/selom-{eng,erg,fig}`) + branches are merged and
> can be removed (`git worktree remove …` + delete branch) once you're sure nothing else needs them.

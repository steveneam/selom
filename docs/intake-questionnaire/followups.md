# Intake questionnaire — follow-ups (review backlog)

> From the dual review over `99bd6e4` (2026-07-01): `review-gauntlet` (4 confirmed) + `fe-review`
> (2 confirmed V·R·D·A·R·N + a G1 user-task walkthrough). The **confirmed breaches were fixed in the
> follow-up commit** (see below). The items here are the G1 **affordance gaps** the walkthrough
> surfaced — the deterministic skeleton computes/persists the design richness but does not yet let the
> user *correct* it. Most are the **intentionally-deferred** AI/edit layer (Layer A ingest `<AskAi>`
> L4 refiner + an edit affordance); they are captured so none are lost, not owed on this slice.

## Fixed in the review-close commit (2026-07-01)

- **[repro] Bulk detection == the deg run** — `suggest_design_hints` selected bulk sample columns by
  *dtype*; the `deg` runner selects *positionally* (`_read_counts` reads `index_col=0`). A numeric
  gene-id (Entrez / unnamed integer index — common in GEO) became a phantom sample → a spurious
  condition level + a `treatment` the runner 400s on. Now selects `df.columns[1:]` (mirrors the run);
  regression test added (`test_bulk_numeric_gene_id_not_counted_as_a_sample`).
- **[spine] No shadow copy of the deg label constants** — `_rep_regex` / `_obs_aliases` wrapped the
  reuse import in `try/except` with hard-coded fallback copies (a silent parallel path that would drift
  and emit a *confident stale* hint, against the module's E4 fail-to-empty policy). Now imported
  directly; a rename raises → honest empty hint, and a drift guard
  (`test_reuses_the_deg_runner_label_constants`) fails loudly.
- **[design/D/N] Dangling "→ chips" pointer** — the confirm-card's "· or pick another from the chips →"
  pointed at the "Recommended for your data" chips, which live on the **Skills** view, not the Data
  stage where the card renders (triple-confirmed). Reworded to "· or choose another below" (points at
  the co-located **Skip** button).
- **[design] AI-context Sparkles axis** — the "Add context for the AI" fold's Sparkles used cyan
  (`--primary`) instead of the fuchsia AI axis (`--stage-ai`). Aligned to `text-stage-ai` (the control
  is explicitly "for the AI"; matches `ask-ai.tsx`). *(Split call — the sibling "Recommended" Sparkles
  is cyan; revisit if the color vocabulary is unified.)*

## Shipped — the "correct the detection" affordances (WS2.2, verified live 2026-07-02)

> These landed as part of the Layer A ingest build (**`6b84834`** reproducible design-edit
> affordances · **`3743878`** honest inspect states · **`79db701`** reset/override) — *before* the
> restructure tracker (`e9edf44`) was written, so the audit inherited them from the stale Deferred
> list below and minted WS2.2 as a phantom `TODO`. RESTRUCTURE-04 verified each on a **live backend
> + real data** (see `docs/restructure/plan.md` Progress log) and reconciled this doc — no re-build.
> Evidence: real bulk `rpgr_irpe_rawcounts.csv` (2-cond) + `+ rpgr_irpe_design.csv` (design-sheet,
> `ref=Control`) + `EYG_29…St7…rawCounts.csv` (6-cond → #2 fires); real scRNA assembled from Hani
> GSE201356 10x (`line` = 3 iPSC lines → #2 fires, `sample_id` = replicate → #6). Backend-dependent
> render conditions confirmed present on real `/data/inspect` `design`/`routing`.

2. **✅ SHIPPED — non-selected levels marked EXCLUDED on a >2-condition design.** A level that is
   neither `reference` nor `treatment` shows a muted "not compared" badge when `levels.length > 2`
   (`intake-questionnaire.tsx`). Verified: eyg29 (6 conditions) + Hani (3 lines) both render the badge
   for the non-contrast levels. (`deg` contrasts are inherently pairwise — this surfaces the exclusion,
   it does not queue further contrasts.)
3. **✅ SHIPPED — WHY the engine prefilled this design is shown.** The confirm-card renders
   `design.note` ("inferred N condition(s) from the sample column names" / "replicates counted as
   distinct samples" / "read the design sheet → …") and appends "'<ref>' guessed as the control —
   confirm below" when `candidate.reference_guess` is set. Verified live: rpgr note; rpgr + sheet →
   `reference_guess='Control'` renders the control-guess line.
4. **✅ SHIPPED — source column shown even with one candidate.** When `group_candidates.length === 1`
   the card shows "Conditions from **<label>**" read-only (the dropdown only appears for >1 candidate).
   Verified live on rpgr / eyg29 (bulk "sample columns" / "condition") + Hani ("line").
6. **✅ SHIPPED — scRNA sample/replicate column picker.** `DesignHints.sample_col_candidates` +
   the "Replicate / sample column" `Select` let the user name the sample-id obs column, so pseudobulk
   aggregates by biological replicate, not cells. Verified live: Hani → detected `sample_id`,
   candidates `['sample_id','line']`, replicate counts per line (not cell counts).
7. **✅ SHIPPED — reset design edits to the engine prefill.** A "Reset to detected" control appears
   once `designEdited` (contrast / sample-col / time-course override / timepoint edit) and restores the
   engine prefill (`resetToDetected`). (Pure FE state; no backend dependency.)
8. **✅ SHIPPED — honest copy when routing didn't resolve.** When `routing` is null the card no longer
   implies a silent run: it shows "no analysis auto-detected. **Skip** below to pick a skill"; when a
   skill resolves it shows "You want to make: **<skill>**". Verified: all four real datasets route to a
   skill (the null branch is the FE fallback else).

## Deferred — still open (NOT part of WS2.2; kept so none are lost)

1. **Correct a mis-parsed condition label (rename / merge / exclude a sample).** `DesignChoice.levels`
   / `LevelHint` are documented "after any rename/remove/add" but no in-place rename/merge UI exists —
   the card accepts-or-Skips the detection (exclusion is *surfaced* by #2, but a true rename/merge is
   not editable). **Deliberately out of WS2.2 scope:** the `deg` runner has no label-rename map (labels
   come from column names / obs / a design sheet), so a display rename wouldn't reproduce — the
   **design sheet is the reproducible correction path** (see #5). Primary target of the L4 refiner
   (messy free-text names → conditions) + a light manual edit affordance.
5. **Auto-feed an attached design/sample sheet into detection from the intake caller.** *Transport is
   shipped* — `suggest_design_hints` accepts `design_path`, `/data/inspect` accepts a `design` file, and
   `inspectData(file, override, design)` sends it (verified: passing the sheet flips `source` to
   `design_sheet` with `ref=Control`). The remaining open piece is the **intake caller auto-passing** an
   attached sheet on inspect so the confirm-card reflects it without a manual step. Not WS2.2.

## G2 render gate — RESOLVED at the root (AI panel is now an overlay)

The fe-review render gate (server was unreachable) flagged a squeeze: the intake card's pills + contrast
selects use `sm:grid-cols-2`, and the **`paddingRight: 376` AI-panel reserve** collapsed the two-column
DataPanel to ~149px columns whenever the panel was open at ≤~1400px — even the *pre-existing* data-type
select clipped to 47px. Measured live (1280 AI-open): main content 330px, columns 149px, contrast selects
31px & overflowing.

**Fix (owner directive): the AI panel is now a fixed OVERLAY, not a push** (`project-workspace.tsx` — the
`paddingRight` reserve removed; the panel was already `fixed` / opaque, so it floats over the content).
Content keeps full width, so nothing is squeezed. Re-measured live: 1280 AI-open now → main 678px, columns
323px, contrast selects 118px, **no overflow, no clip**; 1024 → no overflow/clip. Verified visually at
1440 / 1280 / 1024 (AI-closed) — the confirm-card renders cleanly; AI-open, the panel occludes the
right-column confirm-card (expected overlay behaviour — it's a dock you open/close).

### Residual (minor, NOT from this slice)
- **1024 two-column tightness.** At the desktop floor (1024) with the workrail expanded, the DataPanel's
  right column is ~153px and the contrast selects ~54px (truncated to "C…", still no clip/overflow). This
  is the pre-existing 2-column-at-1024 characteristic (the DataTypeStrip select is equally tight),
  independent of the AI panel. Option if it matters: container-query the intake grids to stack the selects
  below ~16rem card width, and/or auto-collapse the workrail at ≤1024.
- **Radix Select controlled/uncontrolled console warning.** One benign dev warning ("Select is changing
  from uncontrolled to controlled") surfaces in the intake flow (a `<Select value>` that is `undefined`
  on first paint before the async design/answers arrive). Pre-existing in `99bd6e4`, not flagged by either
  review. Track down the offending Select and seed its `value` to a defined string from first render.

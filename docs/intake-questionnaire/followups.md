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

## Deferred — the "let the user correct the detection" follow-on (rides Layer A ingest `<AskAi>` L4)

1. **Correct a mis-parsed condition label (rename / merge / exclude a sample).** `DesignChoice.levels`
   / `LevelHint` are documented "after any rename/remove/add" but no edit UI exists — the card can only
   accept-or-Skip the detection. If the replicate-suffix regex mis-groups a header (`WT` vs `WTb`) or a
   QC-failed sample must be dropped, the user can't fix it in place. **Primary target of the L4 refiner**
   (messy free-text names → conditions) + a light manual edit affordance.
2. **Signal that non-selected levels are EXCLUDED from a >2-condition design.** `designRunParams` sends
   only `reference` + `treatment`; with WT/Het/KO, picking WT vs KO silently drops Het. Add an
   "excluded from this comparison" badge on the unselected level pills (honesty), and/or a way to queue
   further pairwise contrasts. (`deg` contrasts are inherently pairwise — this is a *surfacing* gap.)
3. **Surface WHY the engine prefilled this design.** The backend returns a plain-English `design.note`
   ("inferred 3 conditions from the sample column names", "replicates counted as distinct samples",
   "read the design sheet → …") and `reference_guess` is a keyword *guess* — none is shown. A
   confirm-the-detection card should show what to confirm *against* + that "control" was inferred, not
   certain. Cheap surfacing win (the field is already on the wire).
4. **Show the source column even with one candidate.** The group/condition `Select` renders only when
   `group_candidates.length > 1`, so the single-factor case (most bulk + single-obs scRNA) hides which
   column the conditions came from. Show the source label read-only when there's one candidate.
5. **Feed an attached design/sample sheet into detection.** `suggest_design_hints` already accepts
   `design_path` (sheet = source of truth), but `/data/inspect` passes `bundle` only and
   `inspectData(file, override)` never sends the sheet — so attaching a sample sheet changes nothing
   until run time, with no signal. Thread the sheet through inspect so the confirm-card reflects it.
6. **Let the user designate the scRNA sample/replicate column.** When `sample_col` isn't detected,
   pseudobulk can't aggregate by biological replicate and the grid counts CELLS (inflated n). Add a
   picker to name the sample-id obs column. Directly affects DE validity.
7. **Reset design edits to the engine prefill.** Re-seed fires only on a new file / re-inspect; add a
   "reset to detected" control after the user changes the contrast selects. (LOW.)
8. **Show what will run when routing didn't resolve.** If `routing` is null the "You want to make …"
   line is omitted and the copy degrades to "ready to analyze" — the user confirms a run without seeing
   the skill. Surface the resolved skill (or a "pick one" prompt). (LOW.)

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

# Data-aware routing — follow-ups (fe-review backlog)

> From the `fe-review` G1 user-task walkthrough over the Slice-2 diff (2026-07-01). The review found
> **0 confirmed interaction breaches** (V·R·D·A·R·N clean) and the mechanism JTBD all present
> (one-click apply, override→re-rank, survive-reload, route-composer data context). The items below
> are affordance GAPS — the new data-fit richness is *computed + persisted* but not yet *surfaced*.

## Addressed in the slice (2026-07-01)

- **Honest no-fit (was the sharpest gap).** A *real inspected* dataset whose routed skills are all
  gated / unresolved no longer falls through to the generic modality mock — `recommendedSkills`
  returns the inspected result AS-IS (empty → row hidden = "your data fits none of these"). The mock
  is the fallback ONLY for a NOT-inspected dataset (demo/sample). `quick-apply.ts` + tests.
- **Per-chip "why" (partial).** Each chip now carries a `title` tooltip with the data-fit verdict +
  reason (`confidence_label — reason`) for an inspected dataset (`workbench-panel.tsx` `fitFor`).

## Owner-decided (no change)

- **Real-vs-generic header.** fe-review suggested distinguishing the header when chips come from the
  modality mock vs real data-fit. The owner has decided otherwise: `becf1ff` mandates the single
  "Recommended for your data" header, and this session's D3 says demo/sample data shows the modality
  mock under that same header (a data-type-appropriate list, not a popularity fallback). The
  honest-no-fit fix above removes the only *misleading* case (a real no-fit masked by the mock).

## Shipped — "surface the data-fit verdict & reasons" (WS2.3)

> #1/#2 shipped in **`99bd6e4`** (INTAKE-DESIGN, "data-aware-routing followups #1/#2"); #3 shipped in
> RESTRUCTURE-05 and verified live on real data (`docs/restructure/plan.md` Progress log). #4 remains
> deferred (a distinct AI route-composer surface — see below).

1. **✅ SHIPPED — own-data fit verdict on the intake surface.** `data-panel.tsx` renders
   `DataFitVerdict` (from `components/reproduction/data-fit-panel.tsx`) on the active inspected
   dataset — the fitting analysis's confidence band + verdict, reusing the reproduction component.
2. **✅ SHIPPED — dataset-card fit band.** The dataset cards render a `ConfidenceChip`
   (`BAND_TONE`/`CONFIDENCE_META`) off the persisted `dataFit.confidence` — a glance at which
   datasets are a good fit.
3. **✅ SHIPPED — "not a fit" trace (WS2.3, `f51e0c2`-successor).** `recommendedFromRoute` still drops
   `compatible===false` skills from the chips (correct — they can't run), but they are no longer
   invisible: `quick-apply.notAFitSkills` returns the dropped analyses resolved to catalog skills, and
   `workbench-panel.tsx` renders a muted, struck "Not a fit for your data — <reason>" list with the
   engine's reason **visible** (not tooltip-only). Verified live: real bulk counts
   (`rpgr_irpe_rawcounts.csv`) route `[deg, volcano, enrichment]` → `deg` is a chip, **volcano +
   enrichment are `compatible=false`** ("missing a fold-change column, a significance (p/padj)
   column") → the trace shows both with their reasons. Unit-tested (`quick-apply.test.ts`, incl. the
   complement-of-chips case).

## Deferred — still open (NOT part of WS2.3)

4. **Route-composer transparency (AI surface).** When the `select_skill` compat gate rejects the AI's
   pick, `registry.py` builds a specific reason ("skill X is incompatible with the current data: …")
   but returns only a `no_fitting_skill` gap (`ai/gap_store.py`); `ask-ai.tsx:300` shows the generic
   "No fitting skill for that — recorded as a gap." Thread the reason through the gap/turn so the
   composer shows *why*. And on success add an affirmative "checked against your data" signal (today
   the success note is identical whether the data-aware gate ran or was skipped on a non-inspected
   dataset). **Out of WS2.3's DoD** (a distinct AI route-composer surface + a backend gap-threading
   change, not the own-data verdict surface); tracked in `docs/restructure/plan.md` "Open items".

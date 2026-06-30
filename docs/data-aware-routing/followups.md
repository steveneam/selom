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

## Deferred — a "surface the data-fit verdict & reasons" follow-on slice

1. **Own-data fit verdict on the intake surface.** `DataFitSummary {quality, confidence, fits[]}` is
   persisted but never shown on the own-data intake (`data-panel.tsx` renders only DataTypeStrip /
   CleaningReport / IntakeQuestionnaire). A reusable verdict component already exists
   (`components/reproduction/data-fit-panel.tsx` + `ui/confidence-chip` + `CONFIDENCE_META`/`BAND_TONE`)
   — wired only into the paper-reproduction flow. Wire it (or a lean variant) into own-data intake.
2. **Dataset-card fit band.** The dataset cards (`data-panel.tsx`) show modality/dims/cleaning but
   not the now-persisted `dataFit.confidence`/`quality`. Add the band so a user sees at a glance
   which datasets are a good fit.
3. **"Hidden: not a fit" trace.** `recommendedFromRoute` silently drops `compatible===false` skills
   (e.g. volcano/enrichment on a raw count matrix). Consider a muted/struck "not a fit for your
   data — <reason>" affordance so an expected-but-dropped analysis isn't invisible. (The reason —
   `dataFit.fits[].reason` — is available.)
4. **Route-composer transparency.** When the select_skill compat gate rejects the AI's pick,
   `registry.py` builds a specific reason ("skill X is incompatible with the current data: …") but
   returns only a `no_fitting_skill` gap; `ask-ai.tsx` shows the generic "No fitting skill … recorded
   as a gap." Thread the reason through the gap/turn so the composer can show *why*. And on success,
   add an affirmative "checked against your data" signal (today the success note is identical whether
   the data-aware gate ran or was skipped on a non-inspected dataset).

# Selom skill-gap backlog

> The durable "Selom can't do X yet" backlog, fed by the cold-drive reproduction diagnostic
> (`docs/reproduction-dogfood/spec.md`, Slice 3 / R5). Each dogfooded paper's honest non-graded
> panels accumulate here so dogfooding is a feedback engine, not just a score — the Ratchet.

## Curated capability gaps (hand-authored — the updater preserves this section)

_High-value gaps the panel statuses can't name on their own. The auto-region below classifies a
non-graded panel only from its status, so a real "Selom has no skill for this metric" gap shows up
there as an ambiguous `no_golden` (the paper printed a number, but in a family Selom can't compute)
and is invisible to the heuristic. Those gaps live here, lifted by hand from the findings notes._

### Integration mixing-metrics — LISI / iLISI / kBET / ARI / NMI / silhouette

- **Hit by:** Harmony (Korsunsky 2019), `findings-harmony.md`. Every benchmark figure (Fig 1–6)
  scores batch integration with a **mixing metric**, and those are the only numbers the paper prints.
- **Why it's a gap, not a data problem:** Selom has `integration` + the clean-room **Melody**
  ([[selom-harmony-reimplementation]]) — it can *compute the embedding* — but has **no skill to
  compute the graded mixing metric** from an embedding + batch labels. So the panels route to
  `integration`, run (or would), and read back **nothing to score** → `no_golden`. The auto-region
  can't tell this apart from "the paper printed no number."
- **What would close it:** a `mixing_metrics` skill (LISI / iLISI / kBET, plus ARI / NMI / silhouette)
  over an embedding + a batch/label vector — the engine-sensitive metric type already exists in the
  tolerance grader (`MT_INTEGRATION`, [[selom-gsea-engine-sensitivity]] is the analogous case), so a
  measured Melody↔Harmony delta wouldn't be mislabelled irreproducible.
- **Priority:** high — it's the single lever that makes the entire integration-benchmark paper class
  auto-gradable (the biggest cold-drive recall miss the dogfood phase surfaced).

> _Why the auto-region below is empty so far:_ the two calibration papers (Harmony, Yoshimura) deposit
> their real matrices behind GEO accessions and attach only a QC table, so their non-graded panels are
> **data-availability** gaps (`data_unmatched` / `no_golden`), not buildable skill gaps. That matches
> the phase's strategic insight — the binding constraint for `driven` is data availability, not skill
> coverage ([[selom-live-reproduction-drive]]). The auto-region will populate once a dogfooded paper
> with attached data hits a `needs_recipe` / `no_skill` / unsupported-modality panel.

<!-- skill-gaps:auto:start -->

## Auto-derived gaps

_Maintained by `skill_gaps.update_skill_gaps_doc` from the cold-drive diagnostic — don't hand-edit between the markers. Dogfooded papers: 2 (yoshimura, harmony). Ranked by how many papers hit each gap._

_No buildable skill gaps surfaced yet. The dogfooded papers' non-graded panels were **data-availability** gaps (data cited-not-attached, or no printed number) rather than missing analyses — see the curated section above for the qualitative gaps the statuses can't name._

```json
{
  "gaps": [],
  "papers_seen": [
    "yoshimura",
    "harmony"
  ]
}
```

<!-- skill-gaps:auto:end -->

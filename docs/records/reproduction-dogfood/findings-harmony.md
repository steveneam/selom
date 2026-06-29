# Slice 0 findings — Harmony cold drive (Korsunsky 2019)

> Session 50, 2026-06-22. The first cold-drive diagnostic (`docs/records/reproduction-dogfood/spec.md`
> Slice 0). Tool: `reproduction_diagnose.diagnose_paper`. Inputs: the staged main PDF + supplements
> 3/4 (PDF methods) + supplement-8.xlsx (the only tabular file). Raw report:
> `graphify-out/scratch/s50-harmony-gap.{md,json}` (gitignored scratch).

## Headline

**auto-grade rate: n/a — 0 / 8 panels gradable, 0 driven, 0 goldens extracted.** The honest engine
graded *nothing*, and stayed honest doing it (**0 Selom-confidence defects** — all 8 panels are grey
`run_failed`). Recall is the problem, not credibility. This is exactly the measurement Slice 0 exists
to produce.

| metric | value |
|---|---|
| panels found (routing) | 8 (figs 1–6, 13, 14) |
| in-scope | 8 |
| gradable (in-scope + ≥1 printed golden) | **0** |
| driven (graded) | 0 |
| status rollup | `run_failed` × 8 |

## Why nothing graded (root causes, in priority order)

**1. Zero goldens extracted — the primary blocker.** `build_extracted_spec` read **no printed
numbers** from the Harmony PDF (`goldens_expected` is empty for every panel). Harmony's quantitative
claims are integration-benchmark metrics — **iLISI / kBET / LISI**, ARI/NMI, silhouette, **runtime /
scalability**, cell counts — none of which are in the golden vocabulary. Today `_METRIC_SKILL` knows
only `de_total/de_up/de_down` and `pc1_var/pc2_var` (DE counts + PC variance). So even with perfect
data matching, every panel would be `no_golden`: **there is no number to grade against.** This is the
single biggest lever and a clean Slice 1 (P5b) target.

**2. The matcher forced the lone supplementary table onto all 8 panels → masked `data_unmatched` as
`run_failed`.** `match_data`'s "single tabular supplement → it feeds every panel" rule assigned
`supplement-8.xlsx` to all 8 integration panels. The `integration` skill expects an h5ad/embedding,
got an xlsx, and h5py raised *"file signature not found."* The **honest** status here is
`data_unmatched` (no ingestable analysis input was deposited), not `run_failed`. The heuristic turns a
data-availability gap into a skill failure, which is less honest and noisier. Concrete Slice 2 (P2 2d)
fix: don't feed an obviously-wrong tabular to a skill whose modality it can't be (a small supplementary
*table* ≠ a counts matrix); prefer `data_unmatched` + the per-panel picker.

**3. Routing collapsed every figure to `integration`.** All 8 figures routed to the one skill. For a
single-method paper that is *defensible* (every figure IS about Harmony), but it means no per-figure
discrimination (benchmark scatter vs runtime/scalability vs downstream analysis), and it's why the bad
xlsx match hit all 8. Lower priority than #1/#2; revisit under routing granularity (P3) / the skill-gap
signal (Slice 3).

## Meta-finding (data availability — affects every dogfooded paper)

The Harmony "data" supplements are the **Harmony + LISI R source packages** (`harmony-master`,
`LISI-master`) with bundled `.rda`/`.RData` example objects — **not** the benchmark count matrices
(those are in GEO). So a famous methods paper deposits *code + R objects + accessions*, not
csv/xlsx analysis inputs. The dogfooding loop must either (a) follow a GEO/accession fetch path, or
(b) honestly report "raw data not deposited in an ingestable form" (a data-availability reality, **not
a Selom bug**). This validates choosing a paper with deposited tabular data (e.g. **Yoshimura**,
`sd01.xlsx`) as the next calibration target — to separate the *extractor* gap (#1) from the *data*
gap.

## Top 3 fixes (feed Slice 1+)

1. **Integration/benchmark golden vocabulary** *(Slice 1, P5b — biggest lever).* Teach the golden
   extractor + readers the integration-paper metrics: iLISI/kBET/LISI, ARI/NMI, silhouette, runtime.
   Without goldens, auto-grade is structurally 0 for this whole paper class.
2. **Matcher honesty: lone-tabular ≠ feeds-every-panel** *(Slice 2, P2 2d).* When the only tabular is
   a supplementary table (or the skill needs a modality the file isn't), classify `data_unmatched`,
   not a forced run; add the per-panel data picker for when real data is attached.
3. **Skill-gap signal** *(Slice 3, P3 3c).* Record: "integration-benchmark paper — Selom has
   `integration`/Melody but **no mixing-metric skill** (LISI/kBET) to *compute the graded number*."
   That missing skill is the real gap, and the kind of thing dogfooding should surface paper-over-paper.

## What this validates about the plan

- **Measure-before-build paid off:** without this run we'd likely have started widening DE/PCA readers;
  the real gap is a different metric *family* entirely (integration benchmarks) plus a matcher-honesty
  bug. Slice 0 redirected Slice 1.
- The two-axis credibility guard held: **0 Selom defects** despite 0 recall — a hard paper did not read
  as a Selom failure.
- Next: pick the Slice 1 target from fix #1, and run Slice 0 again on Yoshimura (has deposited tabular
  data) to get a second, data-complete baseline.

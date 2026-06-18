# Hani (Kim 2023) — skill-gap roadmap

The ultimate reproduction target is the Kim/Gonzalez-Cordero/Yang 2023 retinal-organoid
meta-atlas (`GSE201356`). It is the hardest repro class — a **meta-atlas / benchmarking**
paper whose headline figures depend on integrating many external public retinal scRNA-seq
datasets we do not hold (we hold only the 4 organoid samples). The goal (owner, 2026-06-19)
is to reproduce its figures **or at least hold the skills + capability + styling to**.
See memory `selom-hani-figure-reproduction` for the per-figure feasibility map.

This file tracks the **skill gaps** — the buildable half of the goal (blocker type 2). Data
staging (the reference atlas) and out-of-scope panels (schematics, IHC) are the other two
blocker types and are not skills.

## Status

| Skill | Hani fig | What it does | Deps | Status |
|---|---|---|---|---|
| `boxplot` | 2C | grouped box-and-whisker; method/condition concordance (Cepo>Limma>HVG) | pandas | **SHIPPED** `46ebb96` |
| `pvca` | 2B | Principal Variance Component Analysis — variance apportioned across batch/cell-type/dataset | numpy/pandas | **SHIPPED** `7a5171d` |
| `regression` | 4C | OLS scatter + fit (maturation/identity score vs developmental age) | scipy/pandas | **SHIPPED** `7a5171d` |
| `integration` (Harmony) | 1C / 4B / 6 atlas | multi-dataset batch correction as a shipped skill | harmonypy (MIT) + scanpy/anndata | **SHIPPED** — Harmony co-embedding; live on the 4 Hani libraries (iLISI 2.10→3.18) |
| violin + PubMed annotation | 3A / 3B | existing `violin` + a PubMed-count "known vs novel marker" annotation layer | existing `violin` + lit-synth network | **SHIPPED** — `annotate=pubmed`; live RHO→656 hits/retina = known, ZZZ3→0 = novel |

`boxplot` is wired into the live `reproduction_hani` ledger (Fig 2C, replacing the old
`box` placeholder), so lit-synth Phase D now emits its Methods paragraph. **`regression` is
wired as Fig 4C** (developmental-age vs Cepo-statistic scatterplots) with a faithful,
caption-exact directional golden — `age_association="both"` (maturation genes are positively
AND negatively associated with age; not the single "positive" the roadmap first assumed).
**`pvca` is deliberately NOT wired**: on inspection Fig 2B is a *pairwise PVCA batch-effect
heatmap* ("proportion of variance contributed by batch per dataset pair"), not a variance-
fraction bar, and shows no "cell type dominates" claim — so the pvca-bar skill does not
faithfully reproduce it (pvca stays a shipped capability). Curated subset = 7 panels /
6 in-scope; captured scorecard reproducibility 96 / confidence 100, 0 defects. _(The 2B/4C
goldens were corrected after the ★D bridge's figure-rendering surfaced that they had been
wired from assumed descriptions rather than the panels — figure-repro discipline working.)_

## Shipped — multi-dataset integration (Harmony)

The strategically biggest skill gap, now **SHIPPED** (★A, 2026-06-19). It unblocks the
**reference-atlas** figures (1C, 4B) and the organoid fidelity benchmark (6C/6D) once the data
is staged, and gives ★3 (Hani-live) real batch correction across the organoid libraries.

- **Method (as built):** `read → filter → normalize → PCA → Harmony` via scanpy's
  `external.pp.harmony_integrate` (wraps `harmonypy.run_harmony` on the PCA embedding by a
  `batch_key`) `→ neighbors on X_pca_harmony → Leiden → UMAP`. The skill emits the integrated UMAP
  in the same editable Plotly shape `umap_scrna` produces (default colour = batch key, to show the
  mixing). Graceful single-batch fallback: missing / one-level batch key ⇒ plain PCA→UMAP, no error.
- **Dependency — done.** `harmonypy 0.0.10` (MIT, github.com/slowkow/harmonypy) is now declared in
  the `[omics]` extra in `pyproject.toml`. In-env it was promoted from the scratch lib by a plain
  file-copy into `.venv` (the `uv` install path can trip EDR — memory `selom-backend-python-exec`);
  a deploy box gets the identical package via `uv sync --extra omics`.
- **Verified live on the 4 deposited GSE201356 libraries** (10k cells): iLISI (effective #libraries
  among each cell's 30 nearest neighbours, 1 = segregated … 4 = fully mixed) rose **2.10 → 3.18**
  (+1.08) after Harmony — measurable batch correction, not just "it ran". Stub golden-tested;
  real path guarded by a skipif live test (`tests/test_integration_skill.py`).
- **Still the dominant reproduction blocker: data staging** (below) — that is data engineering, not
  this skill. The skill is the prerequisite that makes the atlas work runnable once the data lands.

## Resources & next-session plan (owner, 2026-06-19)

- **Reference-atlas datasets are in hand but on hold.** Cowan, Lu, Lukowski, **Orozco**, and Yan
  are all in the Hani folder — but each is a separate paper + supplement, slow to curate, and
  **Yan is a citation rabbit hole** (its supplement is just references to further papers). So the
  full-Hani data staging (Fig 1C / 4B / 6C-D, which needs these integrated) is a **last pre-launch
  HARDENING task**, not a now-build. This is the dominant blocker and it is data engineering.
- **`integration` / Harmony skill — SHIPPED** (★A, 2026-06-19; see the section above). The
  prerequisite skill for the atlas work is done; what remains for the atlas figures is data staging.
- **NCBI API key — RECEIVED & live** (2026-06-19): `SELOM_NCBI_API_KEY` is set in the gitignored
  `.claude/settings.local.json` (keyed ~10/s, verified). This unblocks the violin+PubMed real counts
  (★B) whenever it's built next.
- **OSCA-source books** (github.com/OSCA-source, ~6 repos) — study next session to tighten Selom's
  scRNA workflow (QC → normalize → integrate → cluster → annotate → DE/markers → trajectory);
  translate the Bioconductor methods to our Python skills, don't ship R. Memory:
  `osca-source-sc-workflow`.

## Shipped — violin + PubMed annotation (★B, 2026-06-19)

Fig 3A/B overlay a "known vs novel marker" split derived from a **PubMed query count** on top
of a scatter/violin of the Cepo statistics. **Now SHIPPED** as the wiring of two existing pieces.

- **As built:** a `violin` param `annotate=pubmed` (+ `context`, `known_min`). After the gene is
  picked, the real engine queries PubMed for `GENE[Title/Abstract]` (optionally `AND
  context[Title/Abstract]`) through lit-synth's cached/throttled seam (`lookup.pubmed_count`,
  built on a new `pubmed.count` reading the esearch `<Count>`), buckets known (hits ≥ `known_min`)
  vs novel, tints every violin by the bucket colour, and adds a corner badge. Pure helpers
  (`pubmed_query`, `annotate_pubmed`) keep query-building + annotation unit-testable; the network
  call is best-effort and **degrades to an unannotated figure** when offline (honest-empty rule).
- **Methods + cite:** `methods._violin` gains the annotation clause + the NCBI Entrez (Sayers)
  citation when `annotate=pubmed`, so lit-synth emits it.
- **Verified live** on the deposited GSE201356 organoid h5ad: RHO → 656 PubMed hits in 'retina'
  ⇒ known (blue) across 19 cluster violins; ZZZ3 → 0 ⇒ novel. Stub golden byte-identical.

## Out of scope (not skills)

Schematics (1A, 4A, 5, 6B) and IHC/micrographs (6E) are correctly excluded by reproduction
guard 7 — no data behind them. The reference-atlas figures (1C, 4B, 6C/6D) are blocked on
**data staging**, not on a missing skill.

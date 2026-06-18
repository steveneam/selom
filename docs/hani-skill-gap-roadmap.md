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
| `integration` (Harmony) | 1C / 4B / 6 atlas | multi-dataset batch correction as a shipped skill | **harmonypy (NEW DEP)** + scanpy/anndata | **DEFERRED** — see below |
| violin + PubMed annotation | 3A / 3B | existing `violin` + a PubMed-count "known vs novel marker" annotation layer | existing `violin` + lit-synth network | **DEFERRED** — see below |

`boxplot` is wired into the live `reproduction_hani` ledger (Fig 2C, replacing the old
`box` placeholder), so lit-synth Phase D now emits its Methods paragraph. `pvca` and
`regression` are shipped **as capabilities** (registered, golden-tested, methods-described)
but are **not yet wired as Hani ledger panels** — Fig 2B and Fig 4C are not in the curated
ledger subset yet, and adding them needs golden targets (directional: cell-type dominates
variance / score rises with age). Wiring them is a ledger-expansion step (★3/★4 territory),
not a skill gap.

## Deferred 1 — multi-dataset integration (Harmony)

The strategically biggest gap: it unblocks the **reference-atlas** figures (1C, 4B) and the
organoid fidelity benchmark (6C/6D), and would give ★3 (Hani-live) real batch correction
across the 4 organoid samples / 3 batches.

- **Method:** scanpy ingest of the per-sample 10x matrices → concat → PCA → Harmony
  (`harmonypy.run_harmony` on the PCA embedding by a batch key) → neighbors/UMAP on the
  corrected embedding. The skill emits the integrated UMAP (colour by dataset/batch/cell type)
  the same editable Plotly shape `umap_scrna` already produces.
- **Blocker — a new dependency.** `harmonypy 0.0.10` lives only in the scratch lib path
  (`D:/tmp-thl/pylibs/`), not in the repo. Shipping the skill means adding `harmonypy` to the
  `[omics]` extra in `pyproject.toml` (lazy real-engine import behind the existing stub/real
  split, exactly like the other heavy skills). An in-env install may be slow and could trip
  EDR (see memory `selom-backend-python-exec`).
- **Decision:** deferred pending an owner go-ahead on the dependency. Not Docker/WSL, so it
  is in-lane, but it is the one ★2 skill that adds a third-party runtime dep, so it is called
  out rather than added silently. The biggest reproduction unlock is still the **data staging**
  (curating + integrating the public fetal/mature retinal sets), which is data engineering, not
  this skill.

## Deferred 2 — violin + PubMed annotation

Fig 3A/B overlay a "known vs novel marker" split derived from a **PubMed query count** on top
of a scatter/violin of the Cepo statistics.

- **Both halves already exist:** the `violin` skill ships, and the PubMed-count half is now
  feasible via lit-synth Phase B/C (`/citations/search`, the NCBI E-utilities `ThrottledFetcher`
  behind one injectable seam). This is therefore an **enhancement/wiring** of two shipped pieces,
  not a from-scratch skill: per gene, query PubMed → bucket as known (hits ≥ k) vs novel → colour
  the violin/scatter points by that bucket.
- **Why deferred:** lower leverage than the variance/regression gaps, and the real annotation is
  network-bound (every gene = an esearch). The clean design is a `violin` param (e.g.
  `annotate=pubmed`) that calls `litsynth.lookup` with the cache, degrading to "unannotated" when
  offline — consistent with the lit-synth honest-empty-over-fabricate rule.

## Out of scope (not skills)

Schematics (1A, 4A, 5, 6B) and IHC/micrographs (6E) are correctly excluded by reproduction
guard 7 — no data behind them. The reference-atlas figures (1C, 4B, 6C/6D) are blocked on
**data staging**, not on a missing skill.

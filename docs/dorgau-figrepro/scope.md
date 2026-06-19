# Dorgau et al. 2024 — figure-reproduction scope (4th ledger)

> Scope-before-build, session 31 (2026-06-20). Owner-greenlit direction: **proceed with
> Dorgau as a focused Fig-1 scRNA ledger** (most figures are out of Selom's current scope —
> see the feasibility map). This doc captures the per-figure feasibility, the Fig-1
> panel → skill → golden-target mapping, the methods recipe, the data-staging plan, and the
> build plan for `reproduction_dorgau.py`. Same discipline as the prior ledgers
> ([[figure-repro-look-at-figures-first]] / [[figure-repro-match-numbers-exactly]]):
> figures → methods → numbers; reproduce the authors' exact thresholds; report engine-deltas
> and structural limits honestly; the two-axis score keeps "paper reproducibility" separate
> from "Selom confidence".

## Paper

| Field | Value |
|---|---|
| Title | *Single-cell analyses reveal transient retinal progenitor cells in the ciliary margin of developing human retina* |
| Authors | Dorgau, Queen, Lako et al. (Newcastle / HDBR) |
| Journal | *Nature Communications* (2024) **15**:3567 |
| DOI | `10.1038/s41467-024-47933-x` (recovered from the PDF XMP via our own `paper_metadata.extract_candidate_ids`) |
| Data | GEO **GSE234971** (all single-cell data — super-series: scRNA + scATAC) |
| Code | GitHub `RachelQueen1/BBSRC_Retina` + Zenodo `10.5281/zenodo.10599556` |
| Reference dataset | Lu et al. GEO `GSE116106` (comparison only) |
| Local staging | PDF + all supplements in the **Dorgau/** Desktop folder (outside the repo). Raw matrices NOT yet staged → GEO pull required. |

This is a **broad multi-omic developmental-retina paper**. The reproducible core for Selom is
**Fig 1 (scRNA-seq)**; the rest is spatial transcriptomics, scATAC-seq, IPA gene-regulatory
networks, and wet-lab validation.

## Per-figure feasibility map

| Fig | Modality / method | Selom fit | Verdict |
|---|---|---|---|
| **1** | **scRNA-seq** — integrated UMAP, marker dotplot, pseudotime density, RPC→T1/T2/T3 trajectory, top-gene heatmap | ✅ **Fully in scope** — every panel maps to a real skill | **REPRODUCE** |
| 2 | Spatial transcriptomics (Visium) — histology, spatial cluster maps, UMAP, subclustering, signature overlays | ⚠️ Spatial out (no Visium coords/H&E support); the **scRNA-derived violin module-scores (2G/I)** are computable | partial / out-of-scope |
| 3 | Spatial transcriptomics — CMZ violins, early/late RPC ratio | ⚠️ **3H ratio** (from scRNA) + violins possible; spatial maps out | partial / out-of-scope |
| 4 | **scATAC-seq** — peak annotation, differential-accessibility heatmap, coverage tracks | ❌ No ATAC support (Signac/CellRanger-ATAC) | out-of-scope |
| 5 | scATAC motif / footprinting (Signac, chromVAR) | ❌ No motif/footprinting support | out-of-scope |
| 6 | Gene regulatory networks — **IPA** (proprietary) + SCENIC+ | ❌ Proprietary tool; eGRN out | out-of-scope |
| 7 | TEAD footprinting + wet-lab IF validation | ❌ Wet-lab + ATAC | out-of-scope |

**Honest framing:** ~1 of 7 figures is squarely in scope. This is exactly what the two-axis
Reproducibility Score is built for — Figs 4–7 go grey (`out-of-scope`, excluded from the
denominator), so the in-scope subset (Fig 1) scores on its own merits and a 6/7-out-of-scope
paper never reads as a Selom failure ([[selom-reproducibility-score]]). Fig 1 is, however,
**deeply** validatable (numeric goldens below) — narrow but deep.

## Fig 1 — panel → skill → golden target

scRNA recipe (Methods, verbatim): CellRanger count → GRCh38; QC remove cells with **<1000 reads
OR <500 genes OR >10% mito**, remove hemoglobin-expressing cells, DoubletFinder doublets;
Seurat v4.3.0 normalize → **FindVariableFeatures 2000 HVG** → ScaleData regressing
`percent.mt`/`nCount_RNA`/`nFeature_RNA` → PCA on 2000 HVG → **Harmony v0.1.1** batch removal →
UMAP on the **first 10 harmony components** → graph-based clustering (resolutions 0.2–2.2;
**43 clusters at res 2.2**, clusters 36/40/41/42 = fibroblast/lens removed) → FindMarkers cluster
markers → cell-type assignment. Pseudotime: **Monocle 3** on 4 branches → FindAllMarkers → top-10
genes/cell-type heatmap ordered by pseudotime.

| Panel | Content | Selom skill | Golden target | Notes / expected verdict |
|---|---|---|---|---|
| **1A** | Integrated UMAP, cell types | `umap_scrna` + **`integration`/Melody** | 43 clusters → ~15–17 retinal cell types (Supp Data 2 `cell fate`) | **Melody dogfood** — paper used Harmony, so direct method match |
| **1B** | Marker dotplot per cell type | `markers` (dotplot form) | FindMarkers top genes (Supp Data 2: e.g. cluster 0 RPC → CCND1, TF) | numeric marker overlap |
| **1C** | RPC + T1/T2/T3 subset UMAP | `umap_scrna` (subset) | 4 branch atlases (Supp Data 2 branch sheets) | re-cluster of the progenitor subset |
| **1D** | Pseudotime density (bimodal: early/late RPC) | `trajectory` (DPT) | bimodal distribution | derive density from DPT |
| **1E/F** | RPC→T1→T2/T3 trajectory | `trajectory` (DPT+PAGA) | lineage topology RPC→T1→{T2,T3} | **engine-delta** Monocle3 → DPT/PAGA (expected, scorer handles it) |
| **1G** | Top-gene heatmap along pseudotime | `pseudotime_genes` | top-10 genes/cell-type per branch (Supp Data 2) | **form-delta**: our smoothed curves vs their heatmap |

### Golden numeric targets (from the deposited supplements)

- **Per-sample QC** (Supp Data 1 `Sample_Overview`, 24 samples 7.5–21 PCW): cells before/after QC
  (e.g. `15046` 8073→4713, `15278` 9651→5668, `14556` 14734→1100 [the noted low-yield sample],
  `15184` 14794→11384) — lets us validate the QC step numerically per sample.
- **Integrated atlas** (Supp Data 2 `integrated UMAP`): 43 clusters; cell fates =
  Proliferating RPC, RPC, T1, T2, T3, RGC, Amacrine, Horizontal, Bipolar, Cone PR, Rod PR,
  Photoreceptor precursors, Muller glia, Microglia, Fibroblasts, Mixed.
- **Marker tables** (Supp Data 2, 11,365 rows): `p_val, avg_log2FC, pct.1, pct.2, p_val_adj,
  cluster, gene, cell fate` for the integrated UMAP + all 4 pseudotime branches = the Fig 1B/G genes.
- **Note**: `Source Data.xlsx` holds only the IF/wet-lab quantifications (VSX2/Ki67/Recoverin/CRX/
  SNCG/Casp3) — Fig 7 / supplementary, NOT Fig 1. Fig 1 goldens are GEO + the marker supplements.

## Data staging plan (the blocker)

GSE234971 raw 10x matrices are NOT staged. Plan (same shape as the Hani GSE201356 pull):
1. Inspect GSE234971 supplementary file list (formats/sizes) — confirm 10x mtx vs processed objects.
2. Stage to `D:/selom-data/dorgau/` (gitignored; outside the repo per D12 + the data-license gate).
3. **Subset for the live drive** (24 samples × ~10k cells is large): a representative set of
   developmental stages, downsampled, sufficient to recover the cluster topology + the
   RPC→T1→T2/T3 lineage. The supplements give the **full** goldens regardless of subset.
4. The DATA license is a separate gate from CODE ([[license-decision-framework]]) — HDBR/GEO terms
   to confirm at decision time; no Docker/WSL involved (plain HTTP).

## Build plan — `reproduction_dorgau.py`

Follows the established ledger API (`reproduction.py`: `Paper`, `Panel`, `Golden`, `MethodSub`,
`Ledger`; `build_ledger` → `drive_captured` → `Scorecard`; `drive_live_*` for the real-data path).

- `build_ledger()` — 7 figures encoded; Fig 1 panels A–G in-scope; Figs 2–7 panels tagged
  `out-of-scope` (spatial / scATAC / IPA / wet-lab) so they grey out and leave the denominator.
- `drive_captured()` — the engine reproduces the by-hand verdicts from the supplement goldens
  (cell-type list, marker overlap, lineage topology); 0 expected Selom defects.
- `drive_live_fig1()` — stage GSE234971 subset → run the real Selom scRNA stack
  (`normalization_qc` → HVG 2000 → `pca` → **Melody** → `umap_scrna` → `markers` → `trajectory` →
  `pseudotime_genes`) and match the goldens. Mirrors `drive_live_organoid` (Hani).
- Expected scorecard: Fig 1 = Reproduced/Verified on its in-scope panels with engine-deltas
  (Monocle3→DPT) and a form-delta (1G) flagged; Figs 2–7 out-of-scope (grey). High Selom
  confidence, modest in-scope reproducibility denominator — the honest narrow-but-deep profile.

## Compounding wins (why this ledger pays for itself)

1. **Dogfoods Selom Melody** (clean-room Harmony) on a *new* real human-retina dataset — the paper
   itself used Harmony, so it's a direct method match, not an approximation ([[selom-harmony-reimplementation]]).
   Naturally exercises the parked **`n_hvg`→2000** Melody fast-follow (paper used 2000 Seurat HVG).
2. First ledger to exercise the **`trajectory` (DPT+PAGA)** + **`pseudotime_genes`** skills against a
   real published trajectory figure (Monocle3→DPT = an expected, scorer-handled engine-delta).
3. Likely surfaces one small, high-reuse skill gap: **module-score** (Seurat `AddModuleScore`,
   pervasive in this field; needed for the Fig 2/3 violins if scope later widens).
4. New GEO ingest (GSE234971) for the catalog + real-datasets record ([[selom-real-datasets]]).

## Open questions for the owner (before the live drive)

- **Subset size** for `drive_live_fig1` — how many samples / cells (cost vs fidelity). Default: a
  representative ~4–6 stage subset, ≤10k cells/sample, enough to recover the RPC→T1→T2/T3 lineage.
- Whether to **widen scope** to the scRNA-derived Fig 2/3 violins later (needs a `module_score` skill).

---

## Reproduction record (session 31, 2026-06-20) — BUILT + VALIDATED

`reproduction_dorgau.py` shipped: `build_ledger()` (13 panels) + `drive_captured()` + three live
drives. Engine extension: new scope **`MODALITY_UNSUPPORTED`** (scATAC/spatial/IPA — data deposited,
no Selom skill; added to `OUT_OF_SCOPE_SCOPES`).

**Scorecard (the engine's output): Reproducibility 94/100 (Reproduced) · Selom-confidence 100/100 ·
7 scored / 7 in-scope · 6 out-of-scope · 0 Selom defects.** The 6 spatial/scATAC/IPA/wet-lab reps
grey out (excluded from the denominator); engine-substituted panels (Harmony→Melody, Monocle3→DPT,
Seurat→scanpy markers) correctly cap at *Reproduced (92)*; the two un-substituted exact panels
(1C, 3H) hit *Verified (100)*.

**Three live validations (all PASS):**
1. **Deposit re-derivation — Supp Data 2** (`drive_live_markers`): re-derived **43 clusters · 17
   cell-fate labels · CCND1 (proliferating-RPC top marker) · 4 pseudotime branches** straight from
   the deposited marker tables → `captured_matches_live: True`.
2. **Cohort QC — Supp Data 1** (`drive_live_qc`): **24 samples**, spot-check 15046 **8073 → 4713**,
   66.4% cells retained.
3. **Raw-data Melody dogfood — GSE234963** (`drive_live_fig1`, staged 5-sample stage-spanning subset,
   7,500 cells, 7.5→21 PCW Eye+Retina): **Melody batch-mixing 0.146 → 0.490** (kNN entropy, 1=fully
   mixed; the paper used Harmony → direct method match) · **9 canonical retinal lineages recovered**
   (Proliferating RPC, Rod, Cone, RGC, Amacrine, Horizontal, Bipolar, Müller glia, Microglia) · 25
   live Leiden clusters (correctly *not* forced to the res-2.2 deposit count of 43) · the `integration`
   skill rendered the editable Melody UMAP (23 traces).

**The score spectrum across the four real ledgers:** RPGRIP1 63 / JEV 86 / Hani 96 / **Dorgau 94**
(narrow-but-deep: the in-scope scRNA core reproduces cleanly; 6/7 figures grey out honestly).

**Compounding wins realised:** (1) Melody dogfooded on a *new* real dataset (mixing number proves it);
(2) first ledger to exercise `trajectory`/`pseudotime_genes` against a real published trajectory
figure; (3) the `MODALITY_UNSUPPORTED` scope is reusable for any future multi-omic paper; (4)
GSE234963 ingested (24-sample CSV cohort + the authors' per-cell DoubletFinder calls in the metadata).

**Staging recipe:** `scripts/stage_dorgau_subset.py` (DEV-only) extracts a stage-spanning subset from
`GSE234963_RAW.tar` → `D:/selom-data/dorgau/processed/dorgau_subset.h5ad` (gitignored data).

**Deferred (next, owner-sequenced):** the **Skill Keyword Index** — a deterministic keyword→skill
routing layer (AI verifies, not the backbone) that would have auto-produced this feasibility map;
spec-before-code next session.

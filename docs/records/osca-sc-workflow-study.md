# OSCA Study — Tightening Selom's single-cell workflow

> Study/distill pass over **OSCA — "Orchestrating Single-Cell Analysis with Bioconductor"**
> (Amezquita, Lun, Hicks, et al.), the owner-supplied reference. Goal: mine the *what* and
> *why* of the canonical scRNA workflow and turn it into concrete, scoped improvements to
> Selom's Python skills. **Reference-only — we reimplement license-clean in Python; R is
> validation-only (ADR 0002), never shipped.**
>
> _Authored 2026-06-19 (session 25), Claude (acting FE+BE). Originally a SCOPING doc; now
> also the running tracker. **SHIPPED so far: C, A, B, G (session 25) + D, I, H, F (session
> 26).** Only **E** remains (scoped below, owner decision pending). Each shipped item is its
> own scoped `feat(backend)` commit, verified live on real data, defaults OFF where applicable._

## 0. Sources

The OSCA project is six GitHub repos under `github.com/OSCA-source`, published as the
Bioconductor "books". The sixth repo (`OSCA`) is just the build wrapper; the five
content volumes are what was studied:

| Volume | Covers | Read from |
|---|---|---|
| `OSCA.intro` | R/Bioconductor setup, `SingleCellExperiment` (≈ AnnData), getting data | release |
| `OSCA.basic` | **QC · normalization · feature selection · dim-reduction · clustering · marker detection · annotation** | release |
| `OSCA.advanced` | droplet processing · doublets · cell cycle · trajectory · CITE-seq · big data | 3.20 |
| `OSCA.multisample` | **batch correction/integration · multi-sample DE · differential abundance** | release |
| `OSCA.workflows` | 14 end-to-end copy-paste case studies (no new method) | release |

Canonical combined edition (owner-supplied): <https://bioconductor.org/books/3.23/OSCA/>.
Methodology is stable across 3.20→3.23.

---

## 1. The canonical OSCA scRNA workflow (reference)

Each stage: OSCA's recommended method + function, the load-bearing *why*, and the
license-clean Python/scanpy route. This table is the durable takeaway — keep it as the
reference for any scRNA skill work.

| Stage | OSCA method (Bioconductor fn) | Why it matters | Python/scanpy route |
|---|---|---|---|
| **Droplet cell-calling** | `emptyDrops()` — test each barcode vs the **ambient RNA profile** (Monte-Carlo p, FDR≈0.001); `barcodeRanks()` knee is the *inferior* fallback | A fixed total-count knee discards real **low-RNA cells**; the ambient test keeps them | No direct scanpy fn; CellRanger already calls cells for 10x. `scanpy`/`scar`/`cellbender` for ambient removal. Low priority (our 10x dogfood is pre-called) |
| **Per-cell QC + filtering** | `perCellQCMetrics()` + `perCellQCFilters()` — **adaptive MAD outliers, `nmads=3`**, log-transform library size & gene count, proportions on raw right-tail; per-batch via `batch=` | Adaptive thresholds adapt to depth/capture/mito **without manual cutoffs**; fixed cutoffs are brittle across batches | `sc.pp.calculate_qc_metrics` (have it) **+ a MAD filter** (`scipy.stats.median_abs_deviation`, log1p the size/genes) + `sc.pp.filter_cells`. **Gap A** |
| **Doublet detection** | `scDblFinder()` / `computeDoubletDensity()` (simulate doublets, score local density); `findDoubletClusters()` | Doublets form spurious "intermediate" clusters; flag within a capture | `sc.pp.scrublet` (built into scanpy). **Gap I** |
| **Normalization** | `computeSumFactors()` (scran **deconvolution**: pool within `quickCluster`, deconvolve) → `logNormCounts`; `multiBatchNorm()` across batches | Pooling beats library-size on sparse counts — but the book says this **mostly affects per-gene stats, not clustering** | `sc.pp.normalize_total(target_sum=1e4)→log1p` (have it). Deconvolution needs scran (R). Optional modern alt: `sc.experimental.pp.normalize_pearson_residuals`. **Low priority** (see §3) |
| **Feature selection (HVG)** | `modelGeneVar()` → decompose variance into **technical (fitted trend) + biological**; `getTopHVGs()` selects on the **biological** component (`n=`/`prop=`); per-batch via `block=`/`combineVar()` | Log-variance is driven by abundance, not biology; selecting on the biological component (≈2000) sharpens clusters. **Selom does no HVG at all today.** | `sc.pp.highly_variable_genes(flavor="seurat_v3", n_top_genes=2000)` (closest to variance modeling) on counts, or `flavor="seurat"` on log data; subset before PCA. **Gap B** |
| **Dimensionality reduction** | PCA on log-HVGs (`fixedPCA`, ~50 PCs); choose d by `denoisePCA`/elbow/`getClusteredPCs` (book default: just pick 10–50); t-SNE/UMAP **for viz only** | Top PCs concentrate coordinated biology; later PCs ≈ noise. Don't quantify on the 2-D embedding | `sc.pp.pca` + `sc.pp.neighbors` + `sc.tl.umap` (have it). PC-count auto-selection optional |
| **Clustering** | `clusterCells()` + `SNNGraphParam()` — graph-based, **`k=10`** default, Walktrap; `k` controls granularity; eval via modularity/`approxSilhouette`/`bootstrapStability` | Graph-based scales + makes no shape assumption; "true #clusters" is meaningless | `sc.pp.neighbors` + `sc.tl.leiden` (have it). Could expose resolution + a stability/silhouette diagnostic |
| **Marker detection** | `scoreMarkers()` — **effect sizes (Cohen's d, AUC, Δdetected)** from pairwise comparisons, ranked by min/mean/median/rank; **p-values dropped** | p-values from data-derived clusters are **circular/invalid**; effect sizes are honest and rankable | scanpy has no `scoreMarkers`; compute Cohen's d + AUC from the matrix (we already compute per-group mean & fraction in `markers`). **Gap D** |
| **Cell-type annotation** | `SingleR()` (per-cell **correlation to a reference**, `celldex`); `AUCell` marker-set scoring; cluster voting | Reference-based catches subtypes a marker panel misses | `sc.tl.score_genes` marker-set (have it, Mode A); reference route = `celltypist` or a correlation scorer. **Gap E** |
| **Batch integration** | `fastMNN()` (MNN pairs, `d=50,k=20`) after `multiBatchNorm()` + `combineVar()`; **diagnose over-correction** (cluster×batch table, `lost.var`); **correct for embedding ONLY — DE/markers use UNcorrected data + batch as a blocking factor** | Correction can erase real biology; it's a viz/clustering tool, not a DE input | We ship **Harmony** (`sc.external.pp.harmony_integrate`) — a fine Python-native equivalent. Missing: a **mixing diagnostic** + the **uncorrected-for-DE** principle. **Gap G** (+ ties to **Gap C**) |
| **Multi-sample DE (across conditions)** | **Pseudo-bulk**: `aggregateAcrossCells()` per (label × sample) → edgeR (`filterByExpr`→`calcNormFactors` TMM→`estimateDisp`→`glmQLFit/Test`) per cluster; `pseudoBulkDGE()` wraps it | **Cells are NOT biological replicates** — per-cell tests are pseudoreplication and inflate false positives. Replication is at the **sample** level | We have **no pseudobulk path**; `deg` scRNA mode is per-cell Wilcoxon. But `deg._bulk_deseq` (pyDESeq2 + TMM) is exactly the engine to reuse on the aggregated table. **Gap C (highest value)** |
| **Differential abundance** | edgeR on the **cells-per-(cluster×sample)** count table (TMM on abundances; watch composition effects; test vs an LFC threshold) | Cluster proportions are compositional — one cluster growing shrinks others spuriously | Reuse the same DESeq2/edgeR-TMM machinery on the abundance matrix; `composition` is plotting-only today. **Gap F** |
| **Trajectory / pseudotime** | `TSCAN::quickPseudotime` (MST on cluster centroids) or `slingshot` (principal curves); **`testPseudotime()`** fits a natural spline per gene vs pseudotime | Pseudotime ≠ real time; gene-vs-pseudotime testing is what makes a trajectory *useful* | `sc.tl.diffmap→paga→dpt` + simpleppt curves (have it). Missing: the **genes-along-pseudotime** test. **Gap H** |
| **Cell cycle** | `cyclone()` (pair-sign classifier); caution: **only remove cycle when it's a confounder**, else it's real biology | Over-correcting cycle injects spurious signal | `sc.tl.score_genes_cell_cycle` (scanpy). Low priority for current dogfood |

---

## 2. Selom today (verified from the skill code, not the names)

The shipped real engines (`app/backend/skills/<id>/run_real.py`):

- **`normalization_qc`** — `sc.pp.calculate_qc_metrics` (total counts, genes/cell, mito %),
  grouped by sample. **Computes metrics only; does not filter any cells.**
- **`umap_scrna`** — `filter_genes(min_cells=3)` → `normalize_total(1e4)`→`log1p` →
  `pca(n_pcs)` → `neighbors` → `leiden` → `umap`. **No HVG selection; PCA on all genes.**
  (Fast path: replot a precomputed embedding from `obsm`.)
- **`integration`** — same pipeline but `harmony_integrate(batch_key, theta=2.0)` →
  neighbors on `X_pca_harmony`. Single-batch fallback. **No multiBatchNorm/HVG; no mixing
  metric in the output** (iLISI was measured by hand in session 23, not surfaced).
- **`markers`** — `rank_genes_groups(method="wilcoxon", pts=True)` → top-N/group →
  dendrogram-ordered dotplot (mean expr + fraction). **Ranks by Wilcoxon, not effect size.**
- **`deg`** — `auto` mode: scRNA=`.h5ad` → per-cell `rank_genes_groups` Wilcoxon (top-N bar
  for one group); **bulk** = pyDESeq2 Wald (+ optional edgeR-identical TMM via rnanorm);
  **time-course** = pyDESeq2 continuous-time Wald. **No pseudobulk for scRNA condition contrasts.**
- **`annotate`** — marker-set scoring (`sc.tl.score_genes` per type → per-cluster argmax).
  **Marker-panel only (Mode A); no reference-based annotation.**
- **`composition`** — reads a category×condition table → grouped/stacked bars.
  **Plotting only; no abundance test.**
- **`trajectory`** — `diffmap`→`paga`→`dpt` + simpleppt principal-curve lineages.
  **No genes-vs-pseudotime test.**
- Supporting: `pca`, `cluster`, `heatmap`, `violin`, `volcano`, `boxplot`, `corr_heatmap`,
  `pvca`, `regression`, `gsea`/`enrichment`/`go_graph`/`pathway`, `cepo` (proprietary).

Selom's spine (`QC → normalize → PCA → integrate → cluster → UMAP → markers/annotate →
composition → DEG → trajectory`) is the right shape and matches OSCA stage-for-stage. The
gaps are in **rigor at specific stages**, not in the overall architecture.

---

## 3. Gap analysis → prioritized backlog

Severity = impact on correctness/credibility (esp. for the figure-reproduction mission,
where a methods-faithful pipeline is the product). Each is scoped, not built.

### Tier 1 — methodological correctness (recommend building)

**C — Pseudobulk DE between conditions** *(highest value)*
- **Gap:** Comparing a condition (e.g. mutant vs control) on scRNA via per-cell tests is
  **pseudoreplication** — OSCA's strongest warning. Selom's `deg` scRNA path does exactly
  this (per-cell Wilcoxon). Many target papers (RPGRIP1 6F, Hani) do pseudobulk.
- **Build:** `deg` `mode="pseudobulk"` (or a `pseudobulk_de` skill): aggregate counts per
  (cell-type × sample) from an `.h5ad` with `sample`+`label` obs → feed the **existing**
  `_bulk_deseq` (pyDESeq2 + TMM). Pure reuse of shipped machinery.
- **Compounds:** reuses `deg._bulk_deseq`; satisfies OSCA's "DE uses uncorrected data + batch
  as covariate" principle; strengthens the reproduction engine on multi-sample papers.
- **Effort:** S–M (aggregation + obs-column plumbing; engine exists).

**A — Adaptive (MAD) cell QC filtering**
- **Gap:** `normalization_qc` computes metrics but never removes low-quality cells, so every
  downstream skill runs on unfiltered raw data when the input isn't pre-cleaned.
- **Build:** add an opt-in filter (`filter=true`, `nmads=3`) to `normalization_qc` (or a
  small `qc_filter` step): MAD outliers on log library size & genes + raw mito %, per
  `groupby`, returning the filtered matrix + a kept/removed summary.
- **Compounds:** improves UMAP/clusters/markers on real raw drops; reusable MAD helper.
- **Effort:** S.

### Tier 2 — rigor & trust (recommend, cheaper wins)

**B — HVG feature selection before PCA**
- **Gap:** `umap_scrna`/`integration` run PCA on all genes — no HVG step. OSCA selects on the
  biological-variance component (~2000 genes), which sharpens structure.
- **Build:** `n_hvg` param (default 2000) → `sc.pp.highly_variable_genes(flavor="seurat_v3")`
  on counts (or `"seurat"` on log) → subset before PCA, in both skills + a shared helper.
- **Compounds:** one helper used by every embedding skill; closer to authors' pipelines.
- **Effort:** S–M (will shift golden fixtures — regen).

**G — Integration over-correction diagnostic**
- **Gap:** `integration` reports no mixing number; OSCA insists you *check* correction.
- **Build:** surface a batch-mixing metric in the output (iLISI / per-cluster batch entropy,
  before vs after) — the exact number session 23 computed by hand. Matches the memory rule
  "verify integration by a before/after mixing number."
- **Effort:** S.

**D — Effect-size marker ranking** — ✅ SHIPPED (session 26, `baed4f0`)
- **Gap:** `markers` ranks by Wilcoxon p; OSCA ranks by Cohen's d / AUC (cluster p-values are
  circular).
- **Built:** `rank_by ∈ {wilcoxon (default), cohens_d, auc}` on `markers` — one-vs-rest
  effect size per (cluster, gene) from the matrix; effect-size value on the Pillar-1 table.
  Default `wilcoxon` keeps golden + outputs byte-identical.
- **Verified:** real RPGRIP1 scRNA — effect-size ranking surfaces canonical markers
  (NRL/RHO/GNAT1/RCVRN for rods; VIM/CLU/SOX2 for Müller) where Wilcoxon-by-p returns
  obscure genes. The OSCA rationale, demonstrated.

**F — Differential abundance test** — ✅ SHIPPED (session 26, `f657048`)
- **Gap:** `composition` only plots. OSCA tests cluster-count changes with edgeR + TMM.
- **Built:** new `diff_abundance` skill — cells-per-(cluster×sample) → DESeq2 (TMM default =
  edgeR-DA convention), sample-level replication, compositional caveat surfaced; per-cluster
  log2FC/padj table. Promote-not-rebuild: extracted shared `deg.deseq_results` (full frame
  incl. padj) reused by `_bulk_deseq` (output unchanged) + the new skill.
- **Verified:** real RPGRIP1 scRNA (MS-VUS n=3 vs LCA-1 n=2) — Cone photoreceptors
  significantly shrinking (log2FC −1.32, adj p 5.9e-4).

### Tier 3 — coverage

- **H — genes-along-pseudotime** — ✅ SHIPPED (session 26, `20b77c5`): new
  `pseudotime_genes` skill — per-gene Spearman vs `dpt_pseudotime`, BH-corrected, top-N
  drawn as binned expression curves. Reusable `_scrna.compute_pseudotime` helper.
  Verified: real RPGRIP1 — rod-rooted pseudotime's top trends are the rod identity program
  (ROM1/NRL/RHO/GNAT1/PDE6G/…).
- **I — doublet detection** — ✅ SHIPPED (session 26, `8bba291`): opt-in `doublets=true` on
  `normalization_qc` via `sc.pp.scrublet` (per-capture `batch_key`; explicit threshold keeps
  it dep-free as skimage is absent). Default OFF; per-group rate on the table (merges with
  the MAD-filter summary). Verified: Hani subset 84/10000 doublets.
- **E — reference-based annotation** (SingleR-style) — ⏳ SCOPED, owner decision pending.
  Two routes:
  - **(E1, recommended) clean-room correlation-to-reference** (SingleR-style): given a
    reference (a labelled h5ad, or a precomputed cell-type × gene mean-expression table),
    correlate each query cluster's mean profile (Spearman, over shared genes) to each
    reference profile and assign the argmax + a confidence. **No new dependency, no remote
    download** — pure scipy/numpy, fits the library-only/license-clean policy (D12). Reuses
    the markers per-group means + the chunked-rank Spearman from `pseudotime_genes`. Likely
    a Mode B on `annotate` (Mode A = marker-set scoring today). Effort **M**.
  - **(E2) celltypist** — pretrained logistic-regression classifier. Adds a pip dep AND
    downloads remote models; pretrained models are immune/gut-centric (may not match the
    retinal dogfood); custom models need a labelled reference anyway. Heavier, and the
    remote-download pattern is exactly what D12 / the ask-before-remote rule guard. Effort
    **L**. Recommend deferring unless a pretrained model genuinely fits the domain.
- **Cell cycle** (`sc.tl.score_genes_cell_cycle`) — only if a target dataset needs it. Effort S.

### Deliberate non-goals

- **scran deconvolution normalization** (`computeSumFactors`) — R-only and, by OSCA's own
  statement, mostly matters for *per-gene stats*, which Selom already does correctly via the
  pseudobulk/DESeq2 path (Gap C). `normalize_total` is acceptable for clustering. Skip;
  revisit `normalize_pearson_residuals` only if embeddings look abundance-driven.
- **emptyDrops cell-calling** — our 10x dogfood is CellRanger-pre-called; low value now.
- **fastMNN** — Harmony is the shipped Python-native integrator and is widely accepted; the
  OSCA *principles* (multiBatchNorm/HVG/diagnostics/uncorrected-for-DE) are what to adopt
  (Gaps B/C/G), not the specific MNN algorithm.

---

## 4. Build status

The recommended order — **C → A → B/G** (session 25), then **D → I → H → F** (session 26) —
is now **complete except E**. Eight of the nine gaps shipped, each its own scoped
`feat(backend)` commit, verified live on real data, with new behavior opt-in/default-OFF
where it would otherwise shift existing outputs (the verified Hani ledger stays byte-identical).

Compounding wins banked along the way (per the "get more powerful each task" steer):
- **promote-not-rebuild** — pseudobulk (C) and differential abundance (F) both reuse the
  bulk DESeq2 engine; F's need for padj drove extracting a shared `deg.deseq_results` that
  `_bulk_deseq` now also uses (its output unchanged).
- **one shared helper per stage** — `_scrna.select_hvg` (B), `_scrna.compute_pseudotime`
  (H, adoptable by `trajectory`); the chunked column-ranking pattern (markers AUC →
  pseudotime Spearman) is now an established idiom.
- **dependency-free diagnostics** — integration mixing entropy (G), Scrublet via explicit
  threshold (I), vectorized BH everywhere.
- **opt-in defaults protect verified reproductions** — every new knob defaults to the prior
  behavior, so goldens and the driven ledgers are unaffected until deliberately flipped.

**Remaining:** E (reference annotation) — owner to pick route E1 (clean-room correlation, no
dep; recommended) vs E2 (celltypist, dep + download). Then the cross-cutting follow-ups from
the session-25 plan: re-verify the Hani live-organoid ledger, and consider flipping
`n_hvg`→2000 as the `umap_scrna`/`integration` default (the target papers use Seurat HVG, so
it should improve fidelity — gate behind a ledger re-verify).

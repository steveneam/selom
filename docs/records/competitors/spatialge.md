# Selom vs spatialGE (Ospina Lab / Moffitt) — Competitor Figure & Viz Teardown

> **What this is.** A figure/skill-coverage teardown of **spatialGE Web** — an
> academic no-code **spatial-transcriptomics** web app (Ospina Lab, Moffitt Cancer
> Center; R/Bioconductor `spatialGE` behind a Shiny-style web front end). It walks
> every analysis module + figure type the app exposes, its parameter/UX surface, and
> a **coverage map vs Selom** (HAVE / GAP / SELOM-EDGE per figure type), ending in a
> P1→P4 backlog focused on the one place spatialGE clearly beats us: **native spatial
> transcriptomics**. Companion to `docs/records/competitors/omicsbox.md` (the broad
> NGS-suite teardown) — that doc covers analysis *breadth*; this one covers the
> *spatial* lane Selom is weak/absent in. Sibling angle (intake/questionnaire) is
> already in `docs/intake-questionnaire/spec.md` — **not** re-covered here.
>
> _Filed 2026-06-30 · source: owner's logged-in spatialGE Web session, a guided walk
> through modules 1–9 (25 screenshots; **all now read** — 14 in the first pass + the
> 8-shot `2313xx`/`2314xx` batch + the 2-shot `2335xx` module-9 batch, since hydrated
> locally — see §0). Project =
> a 4-sample 10x **Visium** breast-cancer set (`sample_093d/396a/396c/397d`; metadata
> `patient` + `therapy` ∈ {none, pembrolizumab, adriamycin, taxotere})._

---

## 0. Source coverage & one caveat

The session is the app's own module order (left nav, `230800`): **1 Import data ·
2 QC & data transformation · 3 Visualization · 4 Spatially variable genes ·
5 Spatial gene set enrichment · 6 Spatial domain detection · 7 Phenotyping ·
8 Differential expression · 9 Spatial gradients.** I have figure-level screenshots
for **modules 1–8**, plus **module 9's parameter pane + results-column legend**
(`233514`/`233524`, captured 2026-06-30 — see §1.9). The final `2313xx`/`2314xx` batch was OneDrive on-demand
placeholders in the first pass; it is now **hydrated and read** (`231223`, `231315`,
`231322`, `231340`, `231351`, `231413`, `231421`, `231431`). Contrary to the first
pass's guess, that batch is **not** the missing spatial result-renders — it is a
**deeper dive into module 2 (QC & data transformation)**: the QC **violin/boxplot**
distribution renders (`231413`/`231431` interactive Plotly · `231421` static ggplot),
the **pseudo-bulk PCA/UMAP** sub-analysis (`231315`), and the **Normalize** (`231322`)
/ **Filter** (`231340`/`231351`) parameter panes — plus the app's **async-job modal**
(`231223`). So the genuinely **still-uncaptured** items remain the ones the first pass
inferred from the nav label + the app's known method set: the DE **Volcano** render,
**Expression surface**, **SpaGCN** / **MILWRM** domain results, **SPARK-X** results,
and **module 9's populated result render** (its STgradient **Heatmap** tab + results
table) — these were never screenshotted (they are *not* in the hydrated batch).
**Module 9's parameter/UX surface and results schema are now captured** (`233514`/
`233524`); only its *rendered* output remains unseen. Every claim below is tagged with the screenshot
timestamp it came from so the owner can cross-reference; label-only items are marked
**(nav/label only)**.

**The competitor in one line:** a *narrow-but-deep* spatial-transcriptomics app —
Visium-native ingest, tissue-image overlays, and a stack of spatial-statistics
methods (Moran's I, STclust, STenrich, STdeconvolve) — with mostly **static
R/ggplot raster** outputs and **zero non-spatial / multi-omics breadth**.

---

## 1. Module-by-module figure inventory

Wedge tag per figure type: **⭐ SELOM-EDGE** (we render it better / it's our moat) ·
**✅ HAVE** (Selom already does this, spatial caveat aside) · **⛔ GAP** (spatial-native;
Selom absent/weak).

### 1.1 Import data — `230818`
Spatial-native ingest. Per-sample table with four required inputs, each green-checked:
**Expression · Coordinates · Scaling factors · Tissue image** — i.e. the full 10x
Visium quadruple (count matrix + spot coordinates + image scale factors for
registration + the H&E image). Below it a **sample-level metadata** table (`patient`,
`therapy`). Note in-app: re-importing forces a full re-run. → **⛔ GAP.** Selom ingests
count matrices / h5ad / CSV but has **no spatial-coordinate + tissue-image ingest** and
no scale-factor/registration concept. This is the foundational spatial gap — every
module below depends on it.

### 1.2 QC & data transformation — `230829`, `231315`, `231322`, `231340`, `231351`, `231413`, `231421`, `231431`
Five tabs: **Original summary · Filter data · Normalize data · Pseudo-bulk analysis ·
Quilt plot.**
- *Original summary*: a searchable table — Total spots/cells, Total genes, Min/Avg/Max
  counts, Min/Avg/Max genes per sample; Download summary. It also carries **Summary |
  Violin plots | Boxplots** sub-tabs that render per-sample QC distributions of
  `total_counts`: an **interactive Plotly violin** (`231413`) and **boxplot** (`231431`,
  per-sample colored, outliers, legend-hide toggle) **and** a parallel **static R/ggplot
  violin** ("Variable: total_counts", `231421`, jittered points + sample legend). →
  **✅ HAVE** (`normalization_qc`, `scorecard`) — and the static ggplot variant is a
  **⭐ SELOM-EDGE** (we'd ship it as one editable Plotly figure, where they mix interactive
  Plotly with non-editable ggplot rasters).
- *Filter data*: three accordion stages — **Select samples · Filter spots/cells · Filter
  genes** (`231340`/`231351`). *Spots/cells*: keep-by counts range, keep-by expressed-genes
  range, keep-by %-of-counts with **mitochondrial (^MT-) / ribosomal (^RP[L|S])** presets +
  a regex (advanced) box. *Genes*: search/exclude gene lists, remove mito/ribo, remove-by-regex,
  keep genes with counts-between, keep genes expressed-in ≥N spots; APPLY FILTER. → **✅ HAVE**
  (cleaning/QC).
- *Normalize data* (`231322`): **Log-normal** (library-size scaling × **scaling factor 10000**,
  then ln+1) **or SCTransform** (Seurat regularized negative-binomial regression on counts).
  → **✅ HAVE** log-norm; **SCTransform is a minor GAP** (Selom has rnanorm TMM, scanpy
  normalize; no SCTransform/Pearson-residual mode).
- *Pseudo-bulk analysis* (`231315`): collapse spot counts → pseudo-RNAseq per sample for
  sample-level patterns, **plus a dimensionality-reduction sub-analysis** — **PCA and UMAP**
  over the pseudo-bulk counts (n most-variable genes = 3000; ≥4 samples required; the app
  states it carries **no spatial component**). → **✅ HAVE** (Selom's pseudobulk DE + PCA/UMAP).
  *Note:* this is spatialGE's **only PCA/UMAP** — sample-level pseudo-bulk only, **not** a
  per-spot/cell embedding.
- *Quilt plot (QC)*: spatial map of per-spot QC metadata (counts/genes per spot) to spot
  technical artifacts. → **⛔ GAP** (spatial-native QC viz).

**App-wide note — async compute (`231223`):** every method runs as a **server-side async
job** with a "Process sent to server / Send email when completed? (No/Yes) / Processing… /
CANCEL PROCESS" modal. Reinforces the heavyweight, re-run-everything posture (cf. §3 #4 —
the rigidity wedge): each parameter change is a queued backend job, not an instant
client-side restyle — the opposite of Selom's live cosmetic edits.

### 1.3 Visualization — "STplot" — `230844`
Two tabs: **Quilt plot · Expression surface.**
- *Quilt plot*: pick ≥1 gene → relative expression rendered at each spot/cell.
  Params: multi-gene search-select · **Point size** slider (default 2) · **Color
  palette** (e.g. *Sunset*) · **Data type** = Normalized expression / Raw counts ·
  GENERATE PLOTS. → **⛔ GAP** — the signature spatial figure: a colored spot-grid over
  tissue. (Render of the generated quilt was in the unhydrated batch.)
- *Expression surface* **(nav/label only)**: a smoothed/interpolated continuous
  expression surface across the tissue. → **⛔ GAP.**

### 1.4 Spatially variable genes — `230901`
Two tabs: **Spatial heterogeneity (SThet) · SPARK-X.**
- *SThet*: spatial-autocorrelation per gene per sample — **Moran's I** (−1…1) and
  **Geary's C** (0…2), method checkboxes; identifies expression "hot-spots". Workflow =
  RUN STHET → GENERATE PLOTS; comparative plot where **each point = a sample**, overlaid
  with sample-level variables (overall survival, tissue type). → **⛔ GAP** — Selom has no
  spatial statistics at all.
- *SPARK-X* **(nav/label only)**: a second, scalable spatially-variable-gene test. → **⛔ GAP.**

### 1.5 Spatial gene set enrichment — "STenrich" — `230915`, `230929`
Tests whether spots with high gene-set score are spatially aggregated (threshold =
mean + X·SD; permutation null).
- *Params* (`230915`): Select/upload gene-set DB · **GSEA score vs Average** · Permutations
  (100) · Seed (12345) · Min spots (5) · Min genes (5) · Standard deviations (1) · RUN
  STENRICH · Download parameter log / zipped results.
- *Results* (`230929`): a **Summary heatmap "STenrich FDR-adjusted p-values"** — rows =
  KEGG pathways, cols = samples, blue→red FDR scale, with **annotation tracks** for
  `patient` + `therapy` beneath the columns; "Sort samples by" + "Number of rows to show"
  slider (30). Tabs Summary | Results by sample; Download Excel. Detail cols: Gene set,
  Genes in sample, Genes in set, Proportion, p-value, Adjusted p-value.
  → **⛔ GAP** on the *spatial* enrichment method, but the **output figure (annotated
  pathway×sample heatmap) is ⭐ SELOM-EDGE** — Selom's `heatmap` + `enrichment`/`gsea`
  already render annotated heatmaps as **editable Plotly**, where theirs is a static raster.

### 1.6 Spatial domain detection — `230949`, `231004`, `231014`
Three method tabs: **STclust · SpaGCN · MILWRM.**
- *STclust params* (`230949`): hierarchical clustering of expression **weighted by
  spot-to-spot distance**. Spatial weight slider (0.02) · "Select a range of Ks" **or**
  "Use DynamicTreeCuts" (DeepSplit) · Number of domains range (2–5) · Number of most
  variable genes (3000) · RUN STCLUST · Color palette (Discrete Rainbow). → **⛔ GAP** —
  spatially-weighted domain detection; Selom clusters (leiden/umap) but with **no spatial term**.
- *STclust results viewer* (`231004`) — **their strongest UX, and Selom's biggest single
  miss**: K=2/3/4/5 tabs × per-sample tabs. **Side-by-side panes** — left = spot scatter
  colored by cluster; right = **the same spots overlaid on the H&E tissue image** with
  **Overlay Opacity / Base Opacity sliders**, pan/zoom/registration toolbar, and toggles
  (Enable Legend / Enable Background / Enable All Clusters / Point size). Below: rename
  clusters (Original → Modified annotation) + a per-cluster **DE markers table**. → **⛔ GAP**
  (the tissue-overlay viewer primitive). This pane *does* look interactive (Plotly-style),
  unlike their R-raster result plots.
- *DE markers table* (`231014`): Gene · Average log-Fold Change · Cluster · Wilcoxon's
  p-value · Adjusted p-value; searchable, paginated. → **✅ HAVE** (`markers`, `deg`).
- *SpaGCN / MILWRM* **(nav/label only)**: graph-convolution and multi-sample
  image-aware domain methods. → **⛔ GAP.**

### 1.7 Phenotyping — "STdeconvolve" — `231028`, `231037`
**Reference-free** cell-type deconvolution via **LDA topics** (topics ≈ cell-type
expression profiles; identities assigned after, via GSEA / markers). Tabs: Model
fitting · Biological identities.
- *Params* (`231028`): Fit LDA models with N topics (range 5–10) · Remove mitochondrial
  genes (`^MT-`) · Remove ribosomal genes (`^RP[LS]`) · Use N variable genes (1000) ·
  RUN LDA MODELS.
- *Model-fitting plot* (`231037`): a **dual-axis line chart** — rare (<5% freq) topics
  (blue) vs **model perplexity** (red) over number-of-topics, with model-alpha
  annotation and a "Suggested K=5". Export **ZOOM / PDF / PNG / SVG**. → This is a
  **static R/ggplot raster** (gray ggplot panel) — **⭐ SELOM-EDGE** on rendering (we'd
  ship it editable). The **method itself is ⛔ GAP**: Selom's `annotate` is
  reference-*based* (celltypist/decoupler); it has no reference-free spatial deconvolution.

### 1.8 Differential expression — `231052`, `231107`
Two tabs: **Non-spatial tests · Spatial tests.**
- *Non-spatial* (`231052`): selectable sample table · **Type of test** = Mixed models
  (also Wilcoxon / T-test per the results legend) · "All pairwise comparisons between
  tissue domains?" · Annotation to test · Cluster annotations to test · Number of most
  variable genes (100) · RUN. → **✅ HAVE** (`deg`).
- *Results* (`231107`): per-sample tabs, **Table | Volcano** sub-tabs; Excel-all-samples,
  Continuous scrolling; table = Gene · Avg log-FC · Cluster 1 · Mixed-model p-value ·
  Adjusted p-value. → **Table ✅ HAVE; Volcano ⭐ SELOM-EDGE** (our `volcano` is an
  editable Plotly figure; their volcano render — in the unhydrated batch — is a static tab).
- *Spatial tests* **(nav/label only)**: spatially-aware DE (mixed models incorporating
  spatial context). → **⛔ GAP.**

### 1.9 Spatial gradients — "STgradient" — `233514`, `233524`
Single tab: **Spatial gradients.** **STgradient** tests for genes whose expression forms a
**spatial gradient with respect to a reference tissue niche/domain** — it computes each
spot/cell's **distance to a reference domain** (a cluster defined via STclust, §1.6) and
**correlates that distance with expression** of the top-variable genes (higher-near /
lower-far = a gradient); Spearman is via R's `cor.test`.
- *Params* (`233514`/`233524`): selectable sample table (same QC columns as §1.2) ·
  **Number of most variable genes** (3000) · **Annotation to test** = a saved STclust result
  (e.g. *"STclust; Domains (k): 02; No spatial weight"*) · **Reference cluster** (niche to
  measure distances from; =1) · **Cluster(s) to exclude (optional)** · **Robust regression?**
  (on — blunts zero-inflation) · **Ignore outliers?** · **Restrict correlation to this limit**
  (3) · **Minimum number of neighbors** (3) · **Distance summary metric** = **Average** vs
  **Minimum** distance (min = short-range gradients, avg = whole-tissue) · RUN STGRADIENT ·
  Download parameter log / zipped results.
- *Results* (legend captured `233524`, render not): a per-gene table — **Gene** (→ GeneCards) ·
  **Linear-model slope** (expr~distance regression coefficient) · **Linear-model p-value** ·
  **Spearman's coefficient (rho)** · **Spearman's p-value** · **Spearman's adjusted p-value**
  (BH) · **Comment** (`zero_st_deviation` / `rob_regr_no_convergence` flags). A **Heatmap**
  results tab ("Sort samples by" patient/therapy) summarizes the per-sample gradient stats.
→ **⛔ GAP** on the *spatial* method (the distance-to-domain step needs spatial coords + an
STclust domain result Selom lacks), but the **output maps onto skills we already ship** —
the expression-vs-distance regression onto `regression`, the gene results table onto
`deg`/`markers`, and the per-sample summary onto our editable `heatmap`.

---

## 2. Coverage map vs Selom (figure-type rollup)

| spatialGE figure / module | Screenshot | Selom status | Note |
|---|---|---|---|
| Visium quadruple ingest (expr+coords+scalefactors+H&E) | `230818` | **⛔ GAP** | No spatial/image ingest at all — foundational |
| QC summary table | `230829` | **✅ HAVE** | `normalization_qc` · `scorecard` |
| QC violin / boxplot distributions | `231413/421/431` | **✅ HAVE** (ggplot variant **⭐ EDGE**) | Plotly violin+box; static ggplot variant we'd ship editable |
| Normalize (log-norm ×10000 / **SCTransform**) | `230829`/`231322` | **✅/⛔** | Have log-norm; SCTransform a minor gap |
| Pseudo-bulk + **PCA/UMAP** (sample-level, non-spatial) | `230829`/`231315` | **✅ HAVE** | pseudobulk DE + PCA/UMAP; their only dim-reduction |
| Quilt plot (gene expr on spot grid) | `230844` | **⛔ GAP** | Signature spatial viz |
| Expression surface (smoothed) | `230844`(label) | **⛔ GAP** | — |
| SThet — Moran's I / Geary's C | `230901` | **⛔ GAP** | No spatial statistics |
| SPARK-X (SVGs) | `230901`(label) | **⛔ GAP** | — |
| STenrich method (spatial enrichment) | `230915` | **⛔ GAP** | Permutation spatial test |
| STenrich figure (pathway×sample heatmap + tracks) | `230929` | **⭐ SELOM-EDGE** | `heatmap`+`enrichment`, editable & annotated |
| STclust / SpaGCN / MILWRM (spatial domains) | `230949` | **⛔ GAP** | Spatially-weighted clustering |
| **Cluster-on-H&E overlay viewer** (opacity/registration) | `231004` | **⛔ GAP** | Their best UX; biggest single miss |
| Per-cluster DE markers table | `231014` | **✅ HAVE** | `markers` · `deg` |
| STdeconvolve (reference-free LDA deconvolution) | `231028` | **⛔ GAP** | `annotate` is reference-*based* only |
| Model-fitting / perplexity plot | `231037` | **⭐ SELOM-EDGE** | Theirs is static ggplot raster |
| DE non-spatial (mixed/Wilcoxon/T) + table | `231052/107` | **✅ HAVE** | `deg` |
| DE Volcano | `231107`(label) | **⭐ SELOM-EDGE** | Editable Plotly volcano |
| DE spatial tests | `231052`(label) | **⛔ GAP** | Spatial mixed models |
| Spatial gradients — STgradient (distance-regression) | `233514/524` | **⛔ GAP** | Spatial method; output maps to `regression` + `deg` table + editable `heatmap` |

**Net:** every **⛔ GAP** is a *spatial* capability; every **✅/⭐** is the non-spatial core
where Selom already matches or beats them. spatialGE has **near-zero non-spatial breadth** —
its *only* dimensionality reduction is a **sample-level pseudo-bulk PCA/UMAP** (`231315`,
≥4 samples, explicitly non-spatial), **not** a per-spot/cell embedding — and **no bulk
RNA-seq, no proteomics/metabolomics, no ERG, no reproduction** and **no editable-figure /
auto-methods / data-routing** story. (The earlier "no PCA/UMAP at all" read was too strong:
they have the pseudo-bulk variant, which Selom already covers — it does not narrow our edge.)

---

## 3. Where Selom's edge dominates

1. **Editable, publication-ready figures.** Their *interactive* panes are limited to the
   quilt/overlay viewers; the analytical results (STdeconvolve perplexity `231037`,
   STenrich heatmap `230929`) are **static R/ggplot rasters** with only PDF/PNG/SVG
   download — **no post-export editing**. Selom's Plotly editor + JSON-Patch is a clean
   moat over every one of those.
2. **Faithful figure reproduction + auto-methods + provenance.** spatialGE shows none of
   this — no methods text, no reproducibility bundle, no citations.
3. **No-code multi-omics breadth.** spatialGE is **Visium-only spatial transcriptomics**;
   Selom spans scRNA, bulk, enrichment/GSEA, trajectory, integration (Melody), proteomics-
   adjacent, and the ERG module. Their depth is one lane; our breadth is the category.
4. **Data cleaning / QC / routing.** spatialGE demands a perfectly-formed Visium
   quadruple up front (`230818`) and re-runs everything on any change; Selom's ingest
   inspects/cleans/routes messy input. Their rigidity is our wedge.
5. **Annotation-track heatmaps as editable figures.** Their best static figure
   (pathway×sample FDR heatmap with patient/therapy tracks, `230929`) is exactly what
   Selom's `heatmap` already produces — but interactive and restyleable.

**Don't chase:** their *upstream-of-us* spatial infra is not where we win on day one —
but unlike OmicsBox's alignment/assembly (pure commodity), the **spatial last mile** (the
overlay viewer + the spatial-stat figures) *is* figure work and *is* in our lane. So,
selectively, we should close it.

---

## 4. The spatial backlog (P1→P4, mapped to the spine)

License note: `spatialGE` is an academic R package — **verify its LICENSE at decision
time** (likely GPL-family). Treat it like Harmony: **clean-room reimplement methods from
the papers, never bundle the R**. The license-clean spine for spatial is **`squidpy`
(scverse, BSD-3)** — it reads Visium natively (`sq.read.visium`), carries the image
container, and ships spatial neighbors + `sq.gr.spatial_autocorr` (Moran's I / Geary's C).
That keeps us scverse-aligned and AnnData-native (`.obsm['spatial']`). Validation oracle =
spatialGE's own R output (ADR 0002 pattern).

| Pri | spatialGE target | Selom skill / surface | Spine source / libs | Figure |
|---|---|---|---|---|
| **P1 (foundation)** | Visium ingest (`230818`) + **cluster/expr-on-H&E overlay viewer** (`231004`) + Quilt plot (`230844`) | new `spatial` ingest path → AnnData(`.obsm['spatial']`+image); **FE overlay primitive** (Plotly `scattergl` over a tissue-image raster, opacity sliders) | `squidpy` `sq.read.visium` · `scanpy`; FE = figure-editor image-layer + spot layer | Quilt plot · spot-over-tissue overlay |
| **P1/P2** | SThet — Moran's I / Geary's C (`230901`) | new `spatial_variable` | `squidpy` `sq.gr.spatial_autocorr` (BSD) | per-gene SVG ranking · sample-comparison scatter |
| **P2** | Spatial domain detection — STclust (`230949/231004`) | new `spatial_domains` | clean-room: distance-weighted hierarchical clustering (scipy + scanpy neighbors); `DynamicTreeCuts`→`dynamicTreeCut`/py port | domains-on-tissue overlay |
| **P2/P3** | STenrich (`230915/230929`) | extend `enrichment`/`gsea` → `spatial_enrichment` | permutation test over spot scores; **reuse existing annotated `heatmap`** | pathway×sample FDR heatmap + tracks (**already our edge**) |
| **P3** | STdeconvolve reference-free LDA (`231028/231037`) | extend `annotate` → `spatial_deconvolve` | `scikit-learn` / `gensim` LDA over spot counts | topic proportions on tissue · perplexity plot (editable) |
| **P3/P4** | Spatial DE (`231052` label) + STgradient (`233514/524`) | extend `deg` (spatial mixed models) · reuse `regression` | `statsmodels` mixed LM; distance-to-domain regression | spatial volcano · expr-vs-distance gradient |
| **P4 (polish)** | Expression surface (`230844` label) · SpaGCN / MILWRM (`230949` labels) | viz polish / later methods | interpolation (scipy) · graph-conv (defer) | smoothed expression surface |

**Single highest-value build:** **P1 — the spatial ingest + the spot-over-tissue overlay
viewer.** Rationale: (a) it's the foundational gap every other spatial module sits on; (b)
it's the *one* spatial figure that is squarely figure-editor work — a Plotly spot-scatter
layered over a tissue-image raster with opacity/registration controls — so it lands inside
**our** moat (editable figures) instead of theirs; and (c) it's spatialGE's signature
output and strongest UX, so matching it neutralizes their best demo while the rest of the
spatial backlog (P2–P4) reuses skills we already have (`enrichment`/`heatmap`/`deg`/
`regression`/`annotate`). Sequence: **P1 ingest+viewer → P2 SVG + domains → P3 enrichment/
deconvolve/DE (mostly broadening existing skills) → P4 polish.**

---

## 5. Sources

- App: spatialGE Web (Ospina Lab, Moffitt Cancer Center) — owner's logged-in session,
  2026-06-30 (login-gated; screenshots `230800`–`231107` + module-9 `233514`/`233524`).
- Method references (for clean-room reimplementation): the `spatialGE` R package +
  papers — STclust, SThet (Moran's I / Geary's C), STenrich, STdeconvolve, STgradient,
  SPARK-X.
- License-clean spine: `squidpy` (scverse, BSD-3) · `scanpy` · `scikit-learn`.
- House companions: `docs/records/competitors/omicsbox.md` (breadth) ·
  `docs/intake-questionnaire/spec.md` (intake angle, separate) ·
  Selom skill registry (`GET /skills`).

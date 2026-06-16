# RPGRIP1 organoid paper — figure reproduction (dogfood)

> Reproducing key panels of **Loi et al. 2025** (*Stem Cell Reports*, CMRI) — the RPGRIP1
> retinal-organoid paper — with Selom's verified skills + the new gap tooling (Cepo,
> the GSEA engine upgrade, the rnanorm TMM toggle). This is a dogfood record: what
> reproduces from local data today, with what skill, and what still needs a GEO pull.
>
> _Generated 2026-06-17 (Claude, acting FE+BE). Specs + PNGs render to a scratch dir; not
> committed. Local data: `D:/selom-data/rpgrip1/processed/rpgrip1_merged.h5ad` (83,659 cells
> × 33,538 genes; 9 samples, genotypes WT/C3/FS/PT; already carries `celltypes` =
> Rods1/2/3 · Cones/RGCs · Bipolar · Amarcrine/Horizontal · Glial-Astrocytes) and the EYG_28
> RPGRIP1_cpdHet bulk DE tables (limma/TMM)._

## Panel → skill map

| Paper panel | Selom skill | Status | Notes |
|---|---|---|---|
| **5A** GSEA (bulk) | `gsea` (Selom GSEA, gseapy.prerank over the GO/curated library) | ✅ reproduced | RPGRIP1_cpdHet vs control ranked DE. |
| **5B** PCA (bulk samples) | `pca` | ⚠️ needs GEO | local data is DE-results only — no per-sample bulk count/expression matrix. Needs GSE293982/GSE293984. |
| **5C** heatmap (bulk top DE × samples) | `heatmap` | ⚠️ needs GEO | same — needs the sample-level expression matrix. |
| **6A** UMAP/atlas + cell-type annotation | `umap_scrna` / `annotate` | ✅ reproduced | rendered from the paper's stored embedding coloured by `celltypes` (avoids a multi-minute recompute on 83k cells; `umap_scrna` recompute is available). |
| **6C / 6D** cell-type composition by genotype | `composition` | ✅ reproduced | celltype × genotype proportions derived from the h5ad, then the composition skill. |
| **6E** set overlap (markers / DE across types) | `upset` | ◻️ feasible, deferred | needs per-type marker/DE set derivation; tractable, not rendered in this pass. |
| **6F** per-cell-type GSEA | `gsea` | ◻️ feasible, deferred | needs per-celltype DE (markers/deg) → gsea; tractable, heavier compute on 83k cells. |
| **6G** marker violin by cell type | `violin` | ✅ reproduced | rod marker distribution across the 7 cell types. |

## What reproduced (this pass)

### 5A — GSEA on the RPGRIP1 bulk DE
`gsea` (engine=gseapy.prerank, BSD-3) over Selom's license-clean gene-set library:
- **curated library:** "Phototransduction & visual cycle" is **down** in RPGRIP1_cpdHet
  (ES −0.59, NES ≈ −1.87, FDR ≈ 0.002) — consistent with loss of photoreceptor/cilia function.
- **full GO library (~7.6k sets):** top depleted sets = ribosomal subunit / mitochondrial
  ribosome / proton-motive ATP synthesis (497 sets at FDR ≤ 0.25) — a translational/metabolic
  signature. (Full-GO gseapy is slow (~minutes); for interactive use prefer a smaller source.)

### 6A — cell-type atlas
Embedding scatter over the paper's stored tSNE coordinates, coloured by the 7 `celltypes`.

### 6C/6D — cell-type composition by genotype
Cell-type % within each genotype (from `celltypes` × `genotype` on the 83,659 cells):

| cell type | C3 | FS | PT | WT |
|---|---|---|---|---|
| Amarcrine/Horizontal | 2.59 | 2.17 | 4.12 | 6.47 |
| Bipolar | 3.88 | 5.16 | 4.12 | 6.62 |
| Cones/RGCs | 7.31 | 6.47 | 18.95 | 11.52 |
| Glial/Astrocytes | 20.90 | 11.83 | 13.59 | 14.45 |
| Rods1 | 21.17 | 28.28 | 15.84 | **6.37** |
| Rods2 | 7.75 | 9.03 | 18.84 | 15.95 |
| Rods3 | 36.40 | 37.05 | 24.54 | 38.63 |

Clear **rod-subpopulation shift**: the Rods1 subtype is strongly enriched in the variant
lines (FS 28%, C3 21%) vs. WT (6.4%) — the kind of rod-state redistribution the paper reports.

### 6G — marker violin
`violin` of the rod master-TF **NRL** across the 7 cell types (7 traces) — rod-restricted
expression, as expected. (RHO/GNAT1 available as alternates.)

## Gaps

- **5B / 5C** need the bulk **sample-level expression matrix** (raw counts or normalized),
  which is not in the local DE-results staging — pull **GSE293982 / GSE293984** to render them.
- **6E / 6F** are tractable from the local h5ad but need a per-cell-type DE/marker derivation
  step; deferred from this pass to bound compute.

## Tooling used

- `gsea` GSEA-engine upgrade (gseapy.prerank / blitzgsea / in-house) over the from-GO library.
- `cepo` (Selom Cepo) is available to regenerate cell-type stability markers (validated vs the
  Hani mmc2 oracle); not a direct Fig-5/6 panel but feeds marker selection for 6E/6G.
- `deg` rnanorm TMM toggle to match the paper's edgeR/limma-voom normalization on the bulk side.

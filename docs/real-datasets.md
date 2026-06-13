# Selom — real-world datasets (dogfooding / hardening catalog)

Real CMRI Eye Genetics data investigated for dogfooding. **Sources live on the
`\\cmri.com.au\…\Eye Genetics\` share; staged copies + processed outputs live under
`D:\selom-data\` (outside the repo).** Scouted 2026-06-13/14; key claims verified directly.
Selom ingest paths: scRNA `.h5ad`/AnnData (UMAP/cluster/violin/DEG); bulk **raw counts** →
`deg` (pyDESeq2); **DE-results tables** (gene+logFC+FDR) → `volcano`; **gene lists** →
`enrichment`/`go_graph`; CPM/normalized → heatmap.

| Dataset | What it is | Selom fit | Status |
|---|---|---|---|
| **RPGRIP1 (Hani)** scRNA | ShinyCell exports, 9 samples (WT/C3/PT/FS), human, log-normalized | converted → `rpgrip1_merged.h5ad`; DEG-by-genotype, violins, **stored t-SNE** all dogfooded | ✅ ingested + dogfooded |
| **EYG_28** bulk | RUVseq/limma **DE-results** (PDE6B + RPGRIP1_cpdHet vs Control, d120–d210); no raw counts | `volcano` ✅ + `enrichment`/`go_graph` (sig-gene derivation) ✅ dogfooded | ✅ staged + dogfooded |
| **EYG_05** bulk | 2022 RUV/limma; CPM matrix + DE-results + GO/KEGG enrichment results; **mutation** contrasts | volcano/enrichment; raw counts in its 478 MB `.RData`; GO/KEGG results = an enrichment **oracle** | 🔎 scouted (not yet used) |
| **ALPK1 single-cell** (Amin) | mouse retina; **no cell object shared** — only `.cloupe` QC + derived tables | 201 MB Seurat DEG CSV → `volcano`/`deg`/`enrichment`/`go_graph`; genes×celltype matrices → heatmap. **No UMAP/cluster** (needs the absent `.rds`/MTX or a Loupe re-export) | 🔎 scouted |
| **ALPK1 bulk RNA-seq** (Amin) | deep edgeR+RUV archive, multiple studies | **goldmine** — covers every ingest path (see below) | 🔎 scouted (standout) |
| **ALPK1 biochemical** (Mark Graham) | ALPK1 phospho-proteomics, MaxQuant, WT vs mu, **n=1**, single protein | **not a fit now** (no replicates → no stats; proteomics lane unbuilt). Good future proteomics **test fixture** | 🔎 scouted — parked |

## ALPK1 bulk — the standout (verified)
`…\ALPK1\Amin's Files\RNA-seq`. Clean edgeR+RUV outputs across studies; the **155 GB of BAMs are NOT ingestable** (skip).
- **Mouse P14/P30/P90 (2021)** — *verified directly*: `…_RUV_rawCounts.xlsx` = **32,285 genes × 77 samples, integer raw counts**; `…_RUV_all_genes.xlsx` = `Comparison/GeneID/…/logFC/AveExpr/t/P.Value/B/FDR`, **18 contrasts = NR+RPE × P14/P30/P90 × DA/MG/WT**. **The one dataset pairing a true time-course with raw counts → unblocks `deg` time-course (P1) AND raw-count pyDESeq2 `deg`.** ✅ **DONE 2026-06-14** — both validated.
  - **Design sheet (the missing piece, now found):** the rawCounts columns are opaque `S1…S80` with no embedded labels. The sample→condition map lives in the analysis `output/` folder as **`20220104_Amin_mm10RUV_K2_variates.tsv`** (comma-delimited despite `.tsv`): per-sample `SampleID,SampleName,Genotype,Age,Tissue,Strain,W_1,W_2` — `Age`=P14/P30/P90 is the time axis; `W_1/W_2` are the RUV covariates. Joins cleanly to all 72 design samples (count cols `S76–S80` are QC-dropped extras, excluded). Staged at `mouse_P14P30P90/sample_design_RUV_K2_variates.csv`. Path on the share: `…\2021_Genewiz_Mg,Da_P14,P30,P90\Results\From Nader\Batch2_…\20211121_RNASeq_mouse_Batch2\output\`.
  - Validated: pyDESeq2 contrast NR_P90 Homo-vs-WT (MG, n=4v3); time-course over P14/P30/P90 within NR adjusting for Genotype → 10,458 genes FDR<0.05.
- **EYG21 human iRPE (2024)** — clean CSV raw counts (ALPK1 = 30 samples) + DGE → end-to-end DEG→volcano→GO.
- **EYG29 (2025)** — cleanest small CSV pairs: `*_rawCounts.csv` (18 samples) + `*_DEGs_All_merged.csv` (logFC/FDR/GeneID).
- **Gene lists** (`Gene lists\*.xlsx`: MitoCarta, CiliaCarta, RD_GeneList, retinal markers) → drop-in `enrichment`/`go_graph` inputs.

## Recommended next dogfooding
1. ✅ **Mouse P14/P30/P90** → `deg` raw-count pyDESeq2 + time-course mode validated (2026-06-14, commit `8700937`).
2. **EYG29 / EYG21 CSV raw-count pairs** → quick end-to-end DEG → volcano → enrichment/go_graph (EYG29 AK1-vs-SCR done).
3. **ALPK1 gene lists** → enrichment/go_graph sanity checks.

## Tooling note
Real bulk data here is **`.xlsx`** (counts + DE). **Resolved 2026-06-14:** `openpyxl` is now a core dep and
`deg` reads `.xlsx` directly (`pd.read_excel` in `_read_counts`/`_load_design`), so the mouse xlsx ingests
without conversion. EYG29 CSV pairs also work as before.

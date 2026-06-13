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
- **Mouse P14/P30/P90 (2021)** — *verified directly*: `…_RUV_rawCounts.xlsx` = **32,285 genes × 77 samples, integer raw counts**; `…_RUV_all_genes.xlsx` = `Comparison/GeneID/…/logFC/AveExpr/t/P.Value/B/FDR`, **18 contrasts = NR+RPE × P14/P30/P90 × DA/MG/WT**. **The one dataset pairing a true time-course with raw counts → unblocks `deg` time-course (P1) AND raw-count pyDESeq2 `deg`.**
- **EYG21 human iRPE (2024)** — clean CSV raw counts (ALPK1 = 30 samples) + DGE → end-to-end DEG→volcano→GO.
- **EYG29 (2025)** — cleanest small CSV pairs: `*_rawCounts.csv` (18 samples) + `*_DEGs_All_merged.csv` (logFC/FDR/GeneID).
- **Gene lists** (`Gene lists\*.xlsx`: MitoCarta, CiliaCarta, RD_GeneList, retinal markers) → drop-in `enrichment`/`go_graph` inputs.

## Recommended next dogfooding
1. **Mouse P14/P30/P90** → build/validate `deg` raw-count pyDESeq2 + the time-course mode (now data-backed).
2. **EYG29 / EYG21 CSV raw-count pairs** → quick end-to-end DEG → volcano → enrichment/go_graph.
3. **ALPK1 gene lists** → enrichment/go_graph sanity checks.

## Tooling note
Real bulk data here is **`.xlsx`** (counts + DE). The skills currently read **CSV** only; `openpyxl` is
installed in the backend venv for inspection, but **xlsx ingestion in the skills is a follow-up** (add
`openpyxl` as a dep + `pd.read_excel` fallback, or convert xlsx→CSV in a prep step). EYG29 offers CSV pairs
that work today without that.

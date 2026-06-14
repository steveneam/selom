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
| **ALPK1 RO/iRPE (Fidelle)** bulk | human iPSC retinal-organoid + iRPE; EYG_05 RO time-course DE (d120–d230) + EYG_08 iRPE **raw counts** (d311/d207) + Reactome/IPA results | RO DE → `volcano`/`enrichment`/`pathway`/`go_graph`; **iRPE raw counts → `deg` pyDESeq2** ✅ dogfooded; Reactome summary = `pathway` oracle | ✅ staged + deg dogfooded |
| **RPGR (Fidelle)** RO+iRPE | RPGR retinal-disease model (NEW gene); iRPE **raw counts** + RO GSEA (hallmark/KEGG/Reactome) + GO-result CSVs + custom gene lists | iRPE raw counts → `deg`; GSEA/GO tables = enrichment/`pathway` **oracle**; ciliopathy/proteostasis gene lists → `enrichment`/`go_graph` (dogfood only) | ✅ staged |
| **ALPK1 mouse proteomics (Fidelle)** | mass-spec proteome, HOM vs WT × 4 reps, P14/P30/P90 × NR/RPE; `FDR/log2FC/intensities/external_gene_name` | **NEW modality** — `volcano` (proteomics) now; future proteomics `deg` | ✅ staged |

## ALPK1 bulk — the standout (verified)
`…\ALPK1\Amin's Files\RNA-seq`. Clean edgeR+RUV outputs across studies; the **155 GB of BAMs are NOT ingestable** (skip).
- **Mouse P14/P30/P90 (2021)** — *verified directly*: `…_RUV_rawCounts.xlsx` = **32,285 genes × 77 samples, integer raw counts**; `…_RUV_all_genes.xlsx` = `Comparison/GeneID/…/logFC/AveExpr/t/P.Value/B/FDR`, **18 contrasts = NR+RPE × P14/P30/P90 × DA/MG/WT**. **The one dataset pairing a true time-course with raw counts → unblocks `deg` time-course (P1) AND raw-count pyDESeq2 `deg`.** ✅ **DONE 2026-06-14** — both validated.
  - **Design sheet (the missing piece, now found):** the rawCounts columns are opaque `S1…S80` with no embedded labels. The sample→condition map lives in the analysis `output/` folder as **`20220104_Amin_mm10RUV_K2_variates.tsv`** (comma-delimited despite `.tsv`): per-sample `SampleID,SampleName,Genotype,Age,Tissue,Strain,W_1,W_2` — `Age`=P14/P30/P90 is the time axis; `W_1/W_2` are the RUV covariates. Joins cleanly to all 72 design samples (count cols `S76–S80` are QC-dropped extras, excluded). Staged at `mouse_P14P30P90/sample_design_RUV_K2_variates.csv`. Path on the share: `…\2021_Genewiz_Mg,Da_P14,P30,P90\Results\From Nader\Batch2_…\20211121_RNASeq_mouse_Batch2\output\`.
  - Validated: pyDESeq2 contrast NR_P90 Homo-vs-WT (MG, n=4v3); time-course over P14/P30/P90 within NR adjusting for Genotype → 10,458 genes FDR<0.05.
- **EYG21 human iRPE (2024)** — clean CSV raw counts (ALPK1 = 30 samples) + DGE → end-to-end DEG→volcano→GO.
- **EYG29 (2025)** — cleanest small CSV pairs: `*_rawCounts.csv` (18 samples) + `*_DEGs_All_merged.csv` (logFC/FDR/GeneID).
- **Gene lists** (`Gene lists\*.xlsx`: MitoCarta, CiliaCarta, RD_GeneList, retinal markers) → drop-in `enrichment`/`go_graph` inputs.

## Fidelle RO/iRPE + RPGR + proteomics (2026-06-14 scout — 4 share folders)
Scouted `…\ALPK1\Amin's Files\…\Genewiz_ALPK1-RO_iRPE_Fidelle's samples`, `…\Fidelle\ALPK1`,
`…\Fidelle\RNAseq and GSEA`, `…\Fidelle\RStudio files` (subagents + self-verification). Staged the
small/new/high-value subset (~75 MB; left ~13 GB of microscopy TIFFs + MSigDB `.gmt` on the share).
- **`alpk1\ro_irpe\`** — EYG_05 **RO DE time-course** (`DE\ro_eyg05_timecourse_d120-d230_DE.csv`, 4
  timepoints, ALPK1 vs isogenic) + d210 single contrast; curated **gene_lists** (Phototransduction,
  CiliaGenes, CiliumAssembly, Mitochondria); **ipa_oracle** (IPA pathway CSVs) +
  `reactome_human_pathways_summary.xlsx`. No raw counts here (RUV-CPM only) → downstream skills.
- **`alpk1\irpe_rawcounts\`** — **EYG_08 iRPE raw integer counts** (d311: CE4_4/CE4_5 ALPK1 vs COR
  control, 9 samples; d207: clone-vs-clone, 6) + **derived design sheets** (`*_design.csv`, sample→
  condition from the column headers) + matching limma **DE oracle** tables. ✅ **`deg` dogfooded** —
  pyDESeq2 Wald, ALPK1(n=6) vs Control(n=3) d311, 21,173 genes tested, sensible hits (PENK/CTNNA2 down,
  MEG3/CHCHD2/SIM1 up). **First HUMAN raw counts for `deg`** (previously mouse-only).
- **`rpgr\`** (NEW gene/disease) — `rpgr_irpe_rawcounts.csv` + design (CE2_1 RPGR vs LM1F control);
  `gsea_oracle\` (RPGR RO GSEA hallmark/KEGG/Reactome Patient+Control reports + the `.rnk`);
  `go_oracle\` (GO-result CSVs, open GO); `expression\` (RO CPM + `.cls`); `gene_lists\` (custom
  **Ciliopathy** + **Proteostasis** sets — **dogfood only; confirm licensing before shipping**, NOT
  MSigDB). The GSEA/GO tables are a numeric **oracle** for Selom `enrichment`/`pathway`/`go_graph`.
- **`alpk1\mouse_proteomics\`** — 6 mass-spec proteome CSVs (P14/P30/P90 × NR/RPE; HOM vs WT n=4) →
  **new proteomics modality** (volcano now). **`alpk1\mouse_enrichment_oracle\`** — mouse GO/KEGG
  enrichment-result CSVs (P14 NR) = oracle.
- **Tool fix it forced:** the biomaRt-style DE header (clean `external_gene_name` beside a composite
  `GeneID = ENSG…~SYMBOL`) made `pathway`/`enrichment`/`go_graph`/`volcano` pick the unmappable
  composite → empty figures. Fixed: gene-column selection now prefers clean symbol columns over id
  columns (commit `6ec924f`).

## Recommended next dogfooding
1. ✅ **Mouse P14/P30/P90** → `deg` raw-count pyDESeq2 + time-course mode validated (2026-06-14, commit `8700937`).
2. **EYG29 / EYG21 CSV raw-count pairs** → quick end-to-end DEG → volcano → enrichment/go_graph (EYG29 AK1-vs-SCR done).
3. **ALPK1 gene lists** → enrichment/go_graph sanity checks.

## Tooling note
Real bulk data here is **`.xlsx`** (counts + DE). **Resolved 2026-06-14:** `openpyxl` is now a core dep and
`deg` reads `.xlsx` directly (`pd.read_excel` in `_read_counts`/`_load_design`), so the mouse xlsx ingests
without conversion. EYG29 CSV pairs also work as before.

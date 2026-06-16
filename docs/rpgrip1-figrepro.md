# RPGRIP1 organoid paper — figure reproduction (dogfood record)

> Reproducing **Loi et al. 2025** (*Stem Cell Reports* 20:102717, CMRI) — the RPGRIP1
> retinal-organoid paper — from **just the PDF + Selom + public raw data (GEO)**, matching the
> paper's printed numbers and recording every delta. This is the first end-to-end dogfood of the
> figure-repro mission (`docs/reproduction-engine/spec.md`).
>
> **Status: Fig 5 (bulk) + Fig 6 (scRNA) both run on real GEO data 2026-06-17** (Claude, acting
> FE+BE, Opus 4.8). Fig 5 validated on GSE293982; Fig 6 reproduced on GSE293984 — see §Fig 6.
> Specs+PNGs render to scratch (`D:/tmp-thl/fig5-real/`, `D:/tmp-thl/fig6-real/`); not committed.
> **Supersedes the prior version of this file, which reported "✅ reproduced" against
> *proxy/adjacent* data (EYG_28 RPGRIP1_cpdHet bulk + the `rpgrip1_merged.h5ad` WT/C3/FS/PT
> atlas) — those are NOT the paper's samples.**

## Data (real, this run)

- **Bulk (Fig 5):** `GSE293982_dedup_countTable_geneName.tsv.gz` — featureCounts gene-symbol matrix,
  36,591 genes × **9 samples** (Control1 / MS-VUS / LCA1 ×3). Staged `C:/Temp/selom-geo/GSE293982/`.
- **Gene-set source:** MSigDB **C5** GO (10,454 sets), `D:/selom-data/msigdb/c5_go_2024.1.Hs.COMMERCIAL-RESTRICTED.json`
  (tagged `commercial_restriction`; build-now/gate-before-launch).
- **Validation oracle:** **R 4.6.0** + **edgeR 4.10.1** (`C:/Users/.../AppData/Local/Programs/R/R-4.6.0`).
  R is **validation-only** (ADR 0002) — used to recapitulate the authors' actual pipeline and measure
  Selom's Python delta, never on the shipped path.

## The exact methods being matched (STAR Methods, pp.35–37)

- **Bulk DE:** STAR → featureCounts → **edgeR TMM** → filter **CPM<2 in the smallest group** →
  3-group NB-GLM → **glmLRT** → **BH adj-p<0.05** (groups Control-1 / MS-VUS / LCA-1).
- **Signature:** MSigDB-C5 sets containing `RPGRIP1` with name in {EYE, RETINAL, CILIUM, PHOTORECEPTOR}
  & size>10 → union (the "RPGRIP1-associated universe") ∩ DE(Control-1 vs MS-VUS).
  Methods say the result is **181 genes** at adj-p<0.05; the results text + every figure legend say **78**.
- **GSEA (5A):** fgsea ranked by **logFC**, MSigDB sets, BH adj-p<0.05; show terms negatively enriched
  in **both** MS-VUS & LCA-1 vs Control-1 (stronger in LCA-1).

## Headline findings

1. **The deterministic part reproduces EXACTLY.** RPGRIP1-associated universe = **1,133 genes** from 16
   GO sets — byte-for-byte the paper's number.
2. **Per-gene magnitudes reproduce to within 1–4 points** (Selom pyDESeq2 + TMM, normalized-expression %):
   RHO −73%/−35% (golden −71%/−34%), PRPH2 −57%/−20% (golden −53%/−18%), RPGR +56.5% MS-VUS (golden +59%).
3. **Selom's DE engine is validated against the authors' actual edgeR** — near-identical across the whole
   threshold curve (signature@adj-p: Selom 19 = edgeR 19; down-in-both 13 = 13; LCA-1 sig 5,181 ≈ 5,510).
4. **The paper's printed signature counts (78 / 181 / 49) are NOT reproducible from the deposited data
   under the methods-stated threshold — not even by edgeR itself.** They only appear under **unadjusted**
   p-value cuts, and at *three different* cuts — i.e. the paper's own methods + numbers don't self-reconcile.

### Signature count vs threshold (edgeR oracle, MS-VUS vs Control-1, ∩ 1,133 universe; Selom in parens)

Only **882 of 1,133** universe genes survive the CPM<2 filter (251 too low-expressed to test → a hard cap).

| Threshold | universe∩ signature | down-in-both | matches paper's… |
|---|---|---|---|
| **adj-p<0.05 (methods-stated)** | **19** (Selom 19) | **13** (13) | nothing |
| raw-p<0.02 | 73 | 37 | ~**78** (figures) |
| raw-p<0.026 | ~78 (Selom signature cut) | — | **78** (figures) ✅ |
| raw-p<0.035–0.04 | 99–107 | **49** (exact) | **49 down** ✅ |
| raw-p<0.1 | **176** (Selom 171) | 86 | ~**181** (methods) ✅ |

**Reading:** "78" ↔ raw-p<~0.022; "49 down" ↔ raw-p<~0.04; "181" ↔ raw-p<~0.1. Each printed number maps
to a *different* unadjusted threshold, none to the stated adj-p<0.05. This is a documented edge case:
**methods text and reported numbers can't always be trusted; Selom + edgeR agree with each other, not with
the paper's labels.**

## Panel → skill map + verdicts

| Panel | Selom skill | Verdict | Notes |
|---|---|---|---|
| **5A** GSEA dotplot | `gsea` (gseapy.prerank, BSD) over MSigDB C5 | **close** (form+claim) | retinal/photoreceptor/cilium terms negatively enriched; dark/significant in LCA-1, pale in MS-VUS — the paper's "stronger in LCA-1." MS-VUS alone clears 0 terms at FDR<0.05 (mild contrast); LCA-1 = 17. |
| **5B** PCA (78 sig genes) | `pca` (sklearn) | **close** (claim ✓) | three distinct clusters; **MS-VUS separates** from Control-1 & LCA-1 (PC1 64.6%, PC2 18.5%) — matches 5B. |
| **5C** heatmap (78 sig genes, row z) | `heatmap` (+ row dendrogram) | **close** (claim ✓) | retinal genes (NR2E3/GRK1/PDE6A/GNGT1/RPGR/ABCA4/TULP1/OPN1MW) high in Control-1, low in variants — the "downregulated retinal block." |
| signature count 78/181/49 | `deg` (pyDESeq2+TMM) | **fail-as-printed / reproduced-with-caveat** | unreachable at the stated adj-p<0.05 even with edgeR; reproducible only at unadjusted thresholds (above). |
| universe = 1,133 | (deterministic) | **exact** | |
| RHO/PRPH2/RPGR % | `deg` | **close** (≤4 pts) | |
| **5D** PRPH2 IHC · **5E** RT-qPCR · **5F** PROTEOSTAT | — | **out of scope (structural)** | wet-lab imaging / independent qPCR; not derivable from RNA-seq. |

For the figure panels the signature is defined as the **78 most-significant universe genes** (MS-VUS
contrast) = the paper's printed count (≈ raw-p<0.026), since the stated adj-p<0.05 yields only 19 —
reverse-engineered to the count and documented as such.

## Fig 6 (scRNA) — reproduced on the real GSE293984 deposit (2026-06-17)

First end-to-end Fig-6 dogfood on the **real** scRNA deposit (supersedes the prior proxy
`rpgrip1_merged.h5ad` WT/C3/FS/PT panels, which were NOT the paper's samples).

### Data + structural limits (deposit vs figure)
- **GSE293984** = 6 samples of 10x CellRanger v3.1 counts: **Control1_3 ×1, LCA1_1/2 ×2, MSVUS_1/2/3 ×3.**
  The **figure shows 8** (Control-1 (1)/(2)/(3), LCA-1 (1)/(2), MS-VUS (1)/(2)/(3)). Those replicates are
  **experimental** (organoid/differentiation batches of a *single* iPSC line per genotype), **not
  biological** replicates — so genotype is confounded with cell line throughout (n=1 line each for
  Control-1, LCA-1, MS-VUS). The deposit holds **1 of Control-1's 3 experimental replicates** → less
  within-control replication to model batch (edge case #6 + the batch≈genotype confound below).
- The deposit's `features.tsv` is a **combined GRCh38 + mm10** CellRanger reference (33,538 human +
  31,053 mouse gene names; organoids on a mouse substrate). Kept human genes only; recorded per-cell
  mouse fraction as QC (median 0.4–8%/sample). Extracted the human GENCODE-v27 gene Ensembl⇄symbol map as
  a reusable Selom asset (`D:/selom-data/refs/gencode-v27-10x-genemap/`).
- **Ingest + QC (faithful):** genes ∈ [1000, 7000] & MT < 20% (STAR methods) → **37,720 cells**
  (Control-1 6,283 · LCA-1 12,030 · MS-VUS 19,407) × 24,624 genes, 17 Leiden clusters. emptyDrops
  (DropletUtils) + DoubletFinder 7.5% are R-only → recorded as DELTAS (substituted by the gene/MT filter).

### Method substitutions (recorded — Python-faithful where the paper's R tool isn't shippable)
| Paper (R) | Selom (Python) | Why / impact |
|---|---|---|
| Seurat label-transfer vs Swamy 2021 ref (FindTransferAnchors 30 PCs + TransferData) | **marker-score annotation** (scanpy `score_genes`, canonical `retinal` panel; new Swamy-ref-derived `retinal_swamy` panel as cross-check, 13/17 clusters agree) | reference **expression matrix unavailable** (only the Swamy paper + its marker table staged). Recovered 6/7 non-rod types. |
| Negative-binomial **GLM-PCA** (Townes 2019) for rod sub-PCs | **Harmony** batch integration (harmonypy 0.0.10, BSD) on standard PCA | glmpca unavailable; un-integrated PCA was batch-confounded — see 6D. |
| **fgsea** (R) ranked by Cepo DS | **gseapy.prerank** (Selom `gsea`) over MSigDB C5 + **fgsea oracle** on the *same* rankings | engine delta **measured**, not assumed (edge case #8) — see 6E. |
| Cepo (R) | Selom Cepo reimpl (validated vs mmc2) | same algorithm. |

### Panel → verdict
| Panel | Skill | Verdict | Notes |
|---|---|---|---|
| **6A** atlas | `annotate` + rod subcluster | **close** | 9-type UMAP reproduced (rod mass → Rod 1/2/3 + Cone/Bipolar/Amacrine/Horizontal/Müller islands; visually verified). **Delta:** Retinal-ganglion did NOT separate (rare; marker-scoring-vs-label-transfer consequence); a tiny **RPE** cluster (48 cells, 0.1%) appears instead → 9 types but the set differs by {RGC↔RPE}. |
| **6B** markers | (feature plots) | n/a | the 6 markers (Cone:PDE6H, Rod:RHO, Müller:VIM, Bipolar:VSX1, Amacrine:CDH7, Horizontal:ONECUT2) are present and drove the annotation. "the 6 cell types shown" in the legend = these **6 markers**, resolving the 6-vs-9 question (6A still has 9 clusters). |
| **6C** composition | `composition` | **close** | per-sample 9-type stacked bar reproduced; rod-dominant (rods 64.5%). Control rows can't fully match (1 control replicate deposited). |
| **6D** rod composition | `composition` | **close (direction) / fail (magnitude)** | **The headline finding.** Un-integrated rod subclustering is a **batch artifact** (Rod-2 = 99.2% MS-VUS cells; 58× MS-VUS / 0.3× LCA-1 = "Rod-2 ≈ the MS-VUS batch"). After **Harmony** integration the subtypes become *shared* and Rod-2 is **directionally** variant-enriched (Control 0.18 · **LCA-1 0.33 = 1.8×** · **MS-VUS 0.21 = 1.1×**) — the paper's *direction* (Rod-2 ↑ in variants) reproduces, but the printed **"≥2× in BOTH variants" magnitude does NOT**. Root cause = the **1-control deposit makes batch ≈ genotype** (single experimental-replicate line per genotype; the paper's 3 control replicates gave the replication to separate them) + GLM-PCA→Harmony substitution. Post-integration Rod-2 is actually higher in LCA-1 than MS-VUS — the *opposite* of the batch artifact, underscoring how method-sensitive this panel is. |
| **6E** Venn (GO terms) | `gsea` (Cepo→gseapy) + fgsea oracle | **fail (counts + structure) — causes disambiguated** | Venn is of **enriched GO terms** (not genes): golden 27/52/10 unique, **52 triple**, 13/10/2 pairs. (1) **Counts**: gseapy.prerank = Rod1 24 / Rod2 36 / Rod3 1 (FDR<0.05); the **fgsea oracle on the identical Cepo rankings** = **62 / 95 / 85** — *comparable to the paper's totals* (102/119/74). So the count gap is a **GSEA-engine delta**: Selom's gseapy is markedly more conservative than the paper's fgsea (actionable Selom insight — see RISKS). (2) **Structure**: the **52-shared-by-all-three core is irreproducible even with fgsea** (all-three = 0 for both engines) — so the missing core is **upstream**, not the engine: my Harmony+Cepo-hclust rod subtypes are too mutually distinct to share an identity core, unlike the paper's reference-anchored GLM-PCA subtypes. Blame correctly assigned. |
| **6F** Rod-2 GO dotplot | `gsea` | **close** | Rod-2's enriched terms (fgsea) hit **3 of the paper's 4 functional groups** — ROS/oxidative stress (8 terms, e.g. GOMF_OXIDOREDUCTASE_ACTIVITY), mitochondrial (4, e.g. GOBP_NADH_METABOLIC_PROCESS), fatty-acid/lipid (16, dominant). **Proteostasis (proteasome/ubiquitin/chaperone) = 0** — the one group that does not surface. |
| **6G** 49-down violin | (box) | **close** | 50 down-regulated bulk-signature genes (≈ paper's 49; recovered from Fig 5 down-in-both) scaled across rods. Form + the key direction reproduce (**Rod-1 highest**: medians Rod-1 +0.14 > Rod-2 −0.09 > Rod-3 −0.19). **Delta:** paper has **Rod-2 lowest**; I get Rod-3 lowest, and magnitude is compressed (cell-mean of z-scores). |
| **6B/feature, IHC** etc. | — | n/a | no wet-lab panels in Fig 6. |

### Headline (Fig 6)
1. The **9-type atlas + composition forms reproduce** via real Selom skills on the real deposit; markers + the rod-dominant structure match.
2. **6D is the differentiating result.** The naïve pipeline yields a *batch artifact* (Rod-2 = MS-VUS batch); even with proper batch integration the printed "≥2× in both variants" is **not reproducible from the deposited 6 samples** — a structural consequence of **1 control experimental-replicate line** (batch ≈ genotype), not a Selom error.
3. **6E blame is fully disambiguated by the fgsea oracle**: the term-*count* shortfall is a **GSEA-engine delta** (gseapy ≪ fgsea ≈ paper), while the **shared-term-core** mismatch is **upstream** (rod-subtype definition), since fgsea reproduces neither the core. This separation — engine vs upstream — is exactly what the mission exists to surface, and it pinpoints a concrete Selom improvement (GSEA sensitivity).
4. Method substitutions (annotation, GLM-PCA→Harmony, GSEA engine) are recorded and, where possible, **measured against an R oracle** rather than assumed.

### Reproducibility (Fig 6)
Scripts in `D:/tmp-thl/fig6-real/`: `ingest.py` (faithful 6-sample ingest), `annotate_subcluster.py`
(annotation + first rod subcluster), `rod_harmony.py` (Harmony-integrated rods → 6A/6C/6D),
`gsea_panels.py` (Cepo DS → gseapy → 6E/6F/6G), `fgsea_oracle.R` (the authors' fgsea on the same
rankings). Engine = EDR-workaround uv-3.12 + `SELOM_SKILLS_ENGINE=real`; Harmony from a scratch
`pylibs/` install (harmonypy 0.0.10, patched for modern-pandas bool dummies). Golden targets in
`D:/tmp-thl/rpgrip1_target_spec.md`. New shipped asset: `annotate` `retinal_swamy` panel (Swamy 2021
reference-derived markers, attributed).

## Reproducibility (this run)

Scripts in `D:/tmp-thl/fig5-real/`: `de.py` (Selom DE), `edger_oracle.R` (validation), `fig5_sweep*.py`
(threshold sensitivity), `fig5A_gsea.py`, `build_panels.py` (panels via the real skills). Engine =
EDR-workaround uv-3.12 + `SELOM_SKILLS_ENGINE=real`. See `docs/reproduction-engine/figure-repro-sop.md`
for the step-by-step procedure this run followed.

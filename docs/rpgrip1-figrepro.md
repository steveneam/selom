# RPGRIP1 organoid paper — figure reproduction (dogfood record)

> Reproducing **Loi et al. 2025** (*Stem Cell Reports* 20:102717, CMRI) — the RPGRIP1
> retinal-organoid paper — from **just the PDF + Selom + public raw data (GEO)**, matching the
> paper's printed numbers and recording every delta. This is the first end-to-end dogfood of the
> figure-repro mission (`docs/reproduction-engine/spec.md`).
>
> **Status: Fig 5 (bulk) validated on real GEO data 2026-06-17** (Claude, acting FE+BE, Opus 4.8).
> Fig 6 (scRNA) not yet run on the real deposit — see §Fig 6. Specs+PNGs render to scratch
> (`D:/tmp-thl/fig5-real/`); not committed. **Supersedes the prior version of this file, which
> reported "✅ reproduced" against *proxy/adjacent* data (EYG_28 RPGRIP1_cpdHet bulk + the
> `rpgrip1_merged.h5ad` WT/C3/FS/PT atlas) — those are NOT the paper's samples.**

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

## Fig 6 (scRNA) — NOT yet run on the real deposit

Real scRNA is `GSE293984` (6 samples; **structural limit: 1 control deposited vs the figure's 3**). The
prior "✅" Fig 6 panels in this file were on the adjacent `rpgrip1_merged.h5ad` (WT/C3/FS/PT) — *not* the
paper's Control-1/MS-VUS/LCA-1. The Swamy et al. 2021 human-retina reference (for Seurat label-transfer
annotation) is now staged at `…/Desktop/Claude code and website tips/Data/Swammy/` (paper + supplement).
Next: reference-based 9-type annotation + rod subclustering on GSE293984 → 6A–6G, with the same
golden-vs-computed verdict discipline. Golden targets in `D:/tmp-thl/rpgrip1_target_spec.md`.

## Reproducibility (this run)

Scripts in `D:/tmp-thl/fig5-real/`: `de.py` (Selom DE), `edger_oracle.R` (validation), `fig5_sweep*.py`
(threshold sensitivity), `fig5A_gsea.py`, `build_panels.py` (panels via the real skills). Engine =
EDR-workaround uv-3.12 + `SELOM_SKILLS_ENGINE=real`. See `docs/reproduction-engine/figure-repro-sop.md`
for the step-by-step procedure this run followed.

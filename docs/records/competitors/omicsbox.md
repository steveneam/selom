# Selom vs OmicsBox (BioBam) — Competitor Teardown & Skill Backlog

> **What this is.** A reverse-engineering teardown of BioBam's **OmicsBox** — the
> leading no-code bioinformatics suite — down to the tool/algorithm/file-format
> level, plus the **prioritized Skill-Foundry backlog** it implies for Selom.
> Owner-directed (2026-06-12): "look at every link and line… so we can reverse
> engineer what workflow / tools / things Selom needs." Companion to
> `docs/records/external-integrations.md` (porting sources), `docs/command-center/design.md §6.5`
> (toolchain) and `docs/build-charter.md` (sequencing). API-reuse cross-refs the
> sibling **eamos** project. Binding decisions still land in `agent_handoff/DECISIONS.md`.
>
> _Filed 2026-06-12 · Claude (acting FE+BE), owner-directed · source: full crawl of
> biobam.com + docs.omicsbox.biobam.com (see §9)._

---

## 1. What BioBam / OmicsBox is

OmicsBox is the incumbent **no-code, end-to-end NGS** suite — a **desktop Java GUI**
retrofitting cloud (OmicsBox Web, OmicsCloud, CloudSync). Heritage product **Blast2GO**
(2005) still anchors the functional-annotation module and is the **only** automation
surface (a property-file CLI — **no public API**). Sold as **General Tools + 5 modules**.

**The shape of the competitor in one line:** deep upstream genomics, desktop-first,
raster figures, quote-based + compute-metered pricing, NGS-only (zero mass-spec).

## 2. Full tool/algorithm catalog (by module)

Every entry is a real, named tool they ship — i.e. a candidate Selom skill. Wedge tag:
🟢 = Selom's last-mile (analysis→figure, our fight) · 🟡 = adjacent (count tables/QC) ·
🔴 = heavy upstream commodity (alignment/assembly/calling — **not** our fight).

**General Tools:** FASTA/FASTQ/BAM tools · FastQC 🟡 · Trimmomatic 🟡 · LongQC · Cutadapt ·
Barcode splitter · Genome Browser · **Venn Diagram** 🟢 · **Workflows** (pipeline chainer).

**Genome Analysis** (🔴 almost all upstream): ABySS / SPAdes / Flye assembly · BWA / Bowtie2 ·
Pilon polishing · BUSCO / QUAST · RepeatMasker · AUGUSTUS (euk) / Glimmer (prok) gene-finding ·
MLST typing.

**Genetic Variation** (🔴): BCFtools mpileup · FreeBayes · VCF merge/filter · dDocent ·
Beagle phasing · VEP annotation · ADMIXTURE · GWAS (GAPIT3) · MAGMA gene-set 🟢.

**Transcriptomics** (the richest module for us):
- Upstream 🔴: STAR / BWA / Minimap2 · Trinity de-novo · TransDecoder / CPAT / CD-HIT · HTSeq / RSEM quant 🟡.
- **Last-mile 🟢: DESeq2 · edgeR · NOISeq · maSigPro (time-course) · interactive volcano · WGCNA co-expression (new in 4.0).**
- **Single-cell 🟢: STARsolo · Seurat v5 clustering · UMAP/tSNE viewer · SingleR / CellKB cell-typing · Monocle3 trajectory · scRNA DEG.**
- Long-read: IsoSeq3 / FLAIR / IsoQuant / SQANTI3 / TAMA.

**Functional Analysis** (Blast2GO heritage — 🟢 mostly ours): BLAST / CloudBLAST · InterProScan ·
**GO mapping/annotation · GO-Slim · EggNOG · Enzyme codes · RFAM · PSORTb** · **Enrichment: Fisher's
exact + GSEA** · **KEGG + Reactome pathway viz · Combined GO graphs · Pathway browser · word clouds**.

**Metagenomics** (mostly 🔴/🟡): Kraken2 (SILVA/Greengenes/GTDB/UNITE/MiDAS) · MetaSPAdes / MEGAHIT ·
FragGeneScan / Prodigal · EggNOG-Mapper / PfamScan · SortMeRNA · edgeR diff-abundance 🟢 ·
**Krona / PCoA / Chao1 / rarefaction** 🟢.

**File formats they touch:** `.box` (proprietary project), `.b2g`, `.fasta`, `.fastq`,
`.gff/.gtf`, `.vcf`, `.bam`. **Notably absent: `h5ad`/AnnData and any mass-spec format.**

## 3. Figure & methods head-to-head (the core wedge)

| Capability | OmicsBox | Selom |
|---|---|---|
| Figure export | **PNG raster + CSV/table**; the manual barely documents image-format options — figures are screenshot-grade. No SVG/PDF editable path surfaced. | **Live Plotly editor, vector, JSON-Patch editable, publication-ready** |
| Post-export editing | Re-run the analysis to change the chart; node/edge customization is in-app only | Direct manipulation of the rendered figure |
| Methods text | **NEW in 4.0: "AI-powered analysis summaries"** (enrichment / taxonomy / annotation) ⚠️ | Auto-methods text + **reproducibility bundle** (B4): provenance, typed params, input SHA, citations |
| Reproducibility | `.box`/`.b2g` project files + PDF report | Per-figure provenance bundle w/ env snapshot |

**Two takeaways.** (1) Their figures are **raster-first** → our editable-vector figure is a
real, defensible moat. (2) ⚠️ **OmicsBox 4.0 shipped "AI-powered analysis summaries"** — the
closest thing to our auto-methods text and the one axis where they're moving toward us. Ours is
reproducibility-grade (citations + provenance bundle); theirs reads like an LLM blurb on results.
**Keep the moat = citations + reproducibility, not just prose.**

## 4. Pricing, packaging & GTM

- **Model:** quote-based, configurator-gated (no public sticker price). **5 à-la-carte
  modules**; **12-month minimum**; seat + computer-count licensing (their example: all
  modules / 2 seats / 4 computers). Academic vs commercial split. PO or card. **No auto-renew
  by default.** sales@biobam.com.
- **Cloud metered separately (concrete numbers):** "Cloud Units" = CPU-seconds + data volume.
  **€1 per 40,000 units**; storage first 5 GB free then **15 units/GB/day**; auto-recharge =
  25% off, **€1,000/mo** default cap. **Billable tools:** BLAST, Diamond, InterProScan, STAR,
  Trinity, SPAdes, MEGAHIT, MetaSPAdes, assembly — i.e. exactly the 🔴 upstream heavy tools.
  Light analysis is free.
- **Positioning:** "end-to-end, no-code, user-friendly," targeting "top public & private
  research institutions." No named logos/testimonials. AWS-backed (ISO27001).

**Selom implication:** their pricing is opaque + compute-metered → **transparent SaaS price +
free editable figures** is a clean wedge. Their billable-tool list is also a map of *what is
expensive to run* → exactly the tools Selom should push to **async cloud workers** (not inline).

## 5. Cloud / Web / automation surface

- **OmicsCloud:** AWS VPC, spot instances, pay-as-you-go; "hundreds of pipelines/month." Compute
  backend, not a scriptable product.
- **OmicsBox Web** (omicsbox.biobam.com): a *thin companion* — Dashboard / Files / Jobs / Results /
  Settings. **Desktop stays primary**; web only checks jobs, moves files, opens results. **They
  are not web-native — this is the seam Selom attacks.**
- **CloudSync (4.0):** 30+ heavy tools run detached in cloud, real-time log streaming, Cloud Usage viewer.
- **Blast2GO CLI:** their **only** automation surface — property-file driven, **no API**, Java 11 +
  MongoDB, perpetual license. → confirms there is **no BioBam API to wrap** (holding the
  printing-press CLI was correct).

## 6. Strategic synthesis — gaps = opportunities, threats

**Gaps (Selom's opportunities):**
1. **Mass-spec / proteomics / metabolomics = total whitespace.** OmicsBox is NGS-only, zero mzML.
   Selom's multi-omics ingest is a category they don't play in. *(highest-leverage differentiator)*
2. **Web-native SaaS** vs a desktop app with a thin web shell.
3. **Editable vector figures** vs PNG export.
4. **Transparent pricing** vs quote-gated, compute-metered.
5. **`h5ad`/AnnData-native** vs Seurat-object-based (their single-cell stack is R/Seurat).

**Threats:**
- **AI analysis summaries (4.0)** narrowing the auto-methods gap — defend with citations + reproducibility.
- **Breadth.** They cover the full NGS pipeline; Selom must not get drawn upstream. Win the last mile.

**Don't fight here (🔴):** alignment / assembly / variant-calling / metagenomics-taxonomy — heavy,
commodity, compute-metered even for *them*. Selom starts from the **count matrix / AnnData / feature
table** and owns the analysis→figure last mile.

## 7. The 🟢 last-mile Skill-Foundry backlog (prioritized, mapped)

Each OmicsBox last-mile tool → a Selom skill, mapped to its **porting source** (primary =
OmicVerse `ov.*` isolated worker per `external-integrations.md §1.1` / §3; license-clean primitives =
scanpy / scikit-learn; validation = the R-oracle, ADR 0002 / RISKS #7). "Status" = against the
live `GET /skills` registry.

| Pri | OmicsBox tool(s) | Selom skill | Status | Porting source / libs | Input | Figure |
|---|---|---|---|---|---|---|
| **P1** | edgeR / DESeq2 / **NOISeq** (no-rep) / **maSigPro** (time-course) | `deg` (+ no-rep + time-course modes) | `deg` exists | `ov.bulk.pyDEG` · PyDESeq2 · R-oracle | count matrix / h5ad / CSV | volcano · MA |
| **P1** | Fisher's exact (FET / over-representation) | `enrichment` (ORA mode) | GSEA exists | gseapy `enrichr` · `ov.bulk.pyGSEA` | gene list + GMT | bar · dot |
| **P1** | KEGG Combined Pathway · Reactome | **`pathway`** (new) | — | **KEGG REST + Reactome ContentService** (new API — printing-press candidate, NOT in eamos) · `reactome2py` | gene list + fold-change | colored pathway map |
| **P1** | Combined GO graph (BP/MF/CC DAG) | **`go-graph`** (new) | — | GO / QuickGO API · `obonet` + `networkx` + graphviz | annotated GO terms | GO DAG |
| **P2** | Seurat clustering / UMAP-tSNE viewer | `cluster` · `umap` | both exist | scanpy · `ov.pp.leiden/umap` · scikit-learn (silhouette guardrail done) | h5ad | UMAP / tSNE |
| **P2** | Seurat FindMarkers | **`markers`** (new) | — | scanpy `rank_genes_groups` · `ov.single` | h5ad (clustered) | dotplot · rank · heatmap |
| **P2** | **SingleR / CellKB** cell-typing | **`annotate`** (new) | — | `ov.single` · celltypist · decoupler | h5ad (clustered) | UMAP by cell type |
| **P2** | **Monocle3** trajectory / pseudotime | **`trajectory`** (new) | — | `ov` trajectory · scFates · scanpy PAGA | h5ad | UMAP + pseudotime · PAGA graph |
| **P3** | **WGCNA** co-expression (new in 4.0) | **`coexpression`** (new) | — | PyWGCNA · `ov` gene-network | count matrix | network + module-trait heatmap |
| **P3** | Venn · PCoA · Krona · Chao1 / rarefaction | **`venn`** · **`pcoa`** (new) | — | matplotlib-venn · scikit-bio · scikit-learn | sets / abundance table | Venn · PCoA · rarefaction |
| **P4 🆕whitespace** | *(none — OmicsBox gap)* proteomics DEG | **`proteomics-deg`** (new) | — | limma (R-oracle) / PyDESeq2 · MaxQuant/DIA + mzML parsers | mzML / MaxQuant / DIA matrix | volcano · heatmap |
| **P4 🆕whitespace** | *(none — OmicsBox gap)* metabolomics | **`metabo`** (new) | — | matchms · MetaboAnalystR (oracle) | mzML / feature table | PCA · enrichment |

**Existing skills to broaden, not rebuild:** `deg`, `enrichment`/GSEA, `cluster` (silhouette
guardrail landed), `umap`, `volcano`, `heatmap` (hierarchical row-ordering, B3). P1 is mostly
*breadth* on infra you already have; P2–P4 are new skills.

**Sequencing recommendation:** P1 (DEG/enrichment breadth + pathway/GO figures) → P2 (single-cell
depth, h5ad-native = their weakness) → P3 (leapfrog their 4.0 WGCNA) → **P4 (the whitespace —
proteomics/metabolomics they can't match).** P4 is the long-term moat; P1 closes the nearest gap.

## 8. API-reuse from eamos (don't rebuild)

The sibling **eamos** clinical/variant tool already ships annotation-API plumbing Selom would
otherwise build (per owner + `…/EAMOS Web Tool/Wiki/syntheses/build-ledger.md`):

- **Already live next door — reuse/port, don't rebuild:** **Ensembl VEP · UniProt · NCBI
  E-utilities · PubMed · LitVar2 · gnomAD (GraphQL)** as live tools in eamos `tools/*.py`.
  - **NCBI E-utilities + PubMed/LitVar2** → power Selom's **auto-methods citations** (B4) directly.
  - **UniProt** → protein/gene annotation for the P4 proteomics module + functional analysis.
  - **Ensembl VEP** → only if Selom ever adds a variant lane (not the wedge — likely skip).
- **Reusable patterns:** eamos's **AI-gateway** (Groq `llama-3.3-70b-versatile` narration +
  **citation-verify**) is the template for Selom's auto-methods prose **with parity against
  OmicsBox 4.0's AI summaries** — but citation-verified. eamos's **SVG report-viz** stack
  (Nightingale, PDBe-molstar, visx/Observable Plot) is a reference for the figure layer.

**Net effect on the printing-press question:** VEP / UniProt / NCBI are *solved* in eamos → **not**
printing-press targets. The remaining genuine API gaps (and thus the real printing-press CLI
candidates) are the **pathway/enrichment annotation APIs eamos lacks: KEGG · Reactome · EggNOG ·
GO/QuickGO · STRING** — these back the P1 `pathway` + `go-graph` skills.

## 9. Sources

- [BioBam home](https://www.biobam.com/) · [OmicsBox](https://www.biobam.com/omicsbox/)
- Modules: [Functional Analysis](https://www.biobam.com/functional-analysis/) ·
  [Transcriptomics](https://www.biobam.com/transcriptomics/) ·
  [Genetic Variation](https://www.biobam.com/genetic-variation-module/) ·
  [Metagenomics](https://www.biobam.com/metagenomics) ·
  [Genome Analysis](https://www.biobam.com/genome-analysis/)
- Pricing/cloud: [Subscription](https://www.biobam.com/omicsbox-subscription/) ·
  [Cloud Computation](https://www.biobam.com/cloud-computation/) ·
  [OmicsCloud](https://www.biobam.com/omicscloud-cloud-platform/)
- Automation: [Blast2GO CLI](https://www.biobam.com/blast2go-command-line-tools/) ·
  [Blast2GO](https://www.blast2go.com/)
- Docs/roadmap: [User manual TOC](https://docs.omicsbox.biobam.com/latest/) ·
  [Export](https://docs.omicsbox.biobam.com/latest/Export/) ·
  [OmicsBox 4.0 release](https://www.biobam.com/omicsbox-4-0-release/) ·
  [Introducing OmicsBox Web](https://www.biobam.com/introducing-omicsbox-web/)

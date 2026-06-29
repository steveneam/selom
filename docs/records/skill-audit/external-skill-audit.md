# External Skill Audit — bioSkills · ClawBio · OmicVerse (s42)

> **Question (owner):** of the ~300–650 external bioinformatics "skills" out there, which
> should Selom **get rid of / never touch (useless/off-thesis)**, which are **useful but
> kept for ourselves (proprietary moat)**, which have **overlapping functions** (dedup),
> and how do they **rank by usefulness**?
>
> **Strategic steer (owner, 2026-06-21):** Selom should **NOT compete on breadth** (number
> of packages/modules). We do our own thing — the editable-figure last mile + the
> reproduction/scoring engine + the proteomics/metabolomics whitespace — and we
> **collaborate**: offer bioSkills / ClawBio / OmicVerse an **IDE / editable-figure
> frontend / deployment layer** for *their* runnable packages. So the audit's verdict axis
> is **BUILD-NATIVE (our moat) vs HOST/INTEGRATE (their package behind our frontend) vs
> SKIP (breadth we don't chase).**

Method: 8 parallel sub-agents, one per Selom-affinity cluster, classified every skill in
the three catalogs against Selom's thesis + its current 30 skills. Raw inventory:
`graphify-out/scratch/skill-audit-inventory.md`.

---

## 0. The universe (the "~300" reconciled)

| Source | Repo | What it is | Count | Code license | Host-ability |
|---|---|---|---|---|---|
| **bioSkills** | `GPTomics/bioSkills` | Reference SKILL.md (method + parameter **guides**, NOT runnable) | **547** across 64 categories | **MIT** | n/a — they're docs; mine the *insight*, not a runner |
| **ClawBio** | `ClawBio/ClawBio` | **Runnable** Python pipelines (`--demo` → PNG + backing CSV) | **88** | **MIT** | ✅ easy — MIT, in-process or subprocess |
| **OmicVerse** | `Starlitnightly/omicverse` (= `omicverse/omicverse`) | Large multi-omics **framework**, 25 modules | hundreds of fns | **GPL-3.0** ⚠ | ⚠ **arms-length only** (see §1) |

≈ **650 items** total — the owner's "~300 or so" rounded. bioSkills are guides (no code to
host); ClawBio + OmicVerse are runnable.

---

## 1. License findings (decisive for the collaboration model)

- **bioSkills = MIT.** They are *reference guides*, not code. Value = the **load-bearing
  method insight** (e.g. proteomics differential-abundance: "model MNAR as left-censored,
  don't impute + Welch"). Mine these into Selom's native skills; nothing to "host."
- **ClawBio = MIT.** Runnable, permissive — the clean collaboration target. Selom can host
  a ClawBio skill behind its frontend with no license friction. **Watch embedded tools**:
  MiXCR (non-commercial), Boltz-2 weights (`struct-predictor`, restrictive), Enrichr data
  (non-commercial wrinkle).
- **OmicVerse = GPL-3.0 — hard blocker for in-process hosting.** `import omicverse` in
  Selom's FastAPI backend would make the whole stack a derivative work → GPL contamination
  ([[license-decision-framework]]). The **only** clean host pattern is **arms-length,
  out-of-process**: an isolated OmicVerse worker (subprocess/container, ideally via its own
  `omicverse.mcp` server seam) that takes an h5ad and returns a **table + numbers**, which
  Selom's editable-Plotly layer renders. That's mere aggregation and defensible — but it's
  heavier than the MIT "just import it" path and inherits a messy `external/`
  transitive-license surface (scVI/Tangram/cell2location etc.). **Per high-value method,
  decide host-arms-length vs clean-room-native (the [[selom-harmony-reimplementation]]
  Melody recipe).** Container work here needs owner sign-off ([[ask-before-docker-wsl]]).

---

## 2. The five answers the owner asked for

### A. KEEP FOR OURSELVES — build native, this is the moat (proprietary)
The few things that are **differentiated AND fit Selom's editable-figure/reproduction
thesis**. Owning these is the bet; hosting them would surrender the moat.

| # | Native build | Why it's moat, not breadth |
|---|---|---|
| 1 | **Harden `proteomics_de` (limma/DEqMS/proDA moderation)** | Our shipped skill uses naive *impute + Welch* — the exact method the bioSkills guide flags as a systematic false-positive generator at n=3–5. Folding in moderated testing + missingness-modeling makes it defensibly best-in-class. **Highest-leverage single upgrade.** |
| 2 | **`metabolomics_de` + metabolite enrichment (mummichog/MSEA)** | Net-new proprietary **metabolomics pillar** — Pareto/UV scaling → OPLS-DA + VIP + volcano; mummichog works pre-annotation. No competitor (incl. OmicsBox) covers it; extends the proprietary enrichment family beyond genes. |
| 3 | **The editable-Plotly figure layer itself** (never host OmicVerse `pl` / ClawBio static PNGs) | Every catalog's plotting layer is static matplotlib. Selom's reason to exist is the **editable last mile**. Consume partners for *numbers/tables*; render figures ourselves. |
| 4 | **The reproduction + two-axis scoring + auto-methods layer** (don't host `repro-enforcer`/OmicVerse `report`) | `repro-enforcer` is env-packaging, not paper-scoring; OmicVerse `report` is a static HTML dump. Selom's re-run-and-score-on-two-axes engine is unique — keep native. |
| 5 | **Clean-room a few moat-critical single methods** (only where GPL blocks the shipped path) | Melody recipe: SCENIC regulons, MOFA+ multi-omics factors, Slingshot flowy-trajectory ([[selom-trajectory-flowy-curve]]), WGCNA modules, one spatial deconvolution method — build-from-paper, keep the GPL original as oracle, stays in-process. |
| 6 | **New editable-figure *types* Selom can't yet render** (see §3) | oncoprint, Manhattan/QQ, lollipop, forest/funnel, KM survival, sequence-logo — pure table→Plotly verticals, our home turf. |

Plus the **last-mile sharpeners** to fold into the editor (proprietary because they make our
figures better than anyone's): **statistical-annotation** (significance brackets + correct
test on box/violin), **figure-export** technique (editable fonts, vector/raster hybrid,
journal CMYK), **color-palettes / multipanel** into the theme + journal-styles registry.

### B. ACTUALLY USEFUL — host them (collaboration: our frontend, their package)
The owner's collaboration thesis lands hardest here. These are genuinely useful, fill Selom
**whitespace**, but we should **not reimplement** — wrap the partner's runnable package
behind Selom's IDE + editable figures + reproduction scoring.

| Rank | Host capability | Source | Whitespace it fills | License |
|---|---|---|---|---|
| 1 | **Spatial transcriptomics suite** (deconvolution Tangram/cell2location, domains STAGATE/GraphST/SpaGCN, SVGs, spatial niches) | OmicVerse `space`, bioSkills spatial-* (squidpy) | Selom has **nothing** spatial — biggest greenfield | OmicVerse GPL → arms-length; squidpy permissive |
| 2 | **Cell-cell communication** (LIANA / CellPhoneDB / COMMOT) | OmicVerse `single`, bioSkills single-cell/cell-communication | Zero in Selom's 30 skills | mixed — LIANA permissive |
| 3 | **Multi-omics integration** (MOFA+ / mixOmics / SIMBA) | OmicVerse `single._mofa`, bioSkills multi-omics-integration | Melody only does *batch*; cross-modal factors missing | verify per-method |
| 4 | **Affinity proteomics (Olink / SomaScan)** | ClawBio `affinity-proteomics` | Huge platform Selom doesn't touch; already emits our volcano/heatmap/PCA contract | **MIT — shovel-ready** |
| 5 | **Metabolomics preprocessing pipeline** (xcms/MS-DIAL → annotate) | OmicVerse `metabol`, bioSkills metabolomics | Feeds the §A.2 native metabolomics moat | OmicVerse GPL → arms-length |
| 6 | **CRISPR-screen analysis** (MAGeCK / DrugZ / ClawBio crispr-screen-triage) | ClawBio (MIT, runnable), bioSkills crispr-screens | Canonical screen volcano/rank-plot — perfect editable-figure fit | ClawBio MIT; MAGeCK GPL CLI arms-length |
| 7 | **nf-core RNA-seq / scRNA-seq fronts** (FASTQ→matrix) | ClawBio `nfcore-*-wrapper` | Host the upstream we deliberately don't own; Selom owns the DE/UMAP/figure tail | MIT wrappers; Nextflow needs infra ([[ask-before-docker-wsl]]) |
| 8 | **Foundation-model annotation** (scGPT / Geneformer / scFoundation) | OmicVerse `llm` | AI cell-type annotation + consensus voting | GPL + GPU/weights infra |
| 9 | **inferCNV / cNMF gene-programs / GRN regulons (SCENIC)** | OmicVerse `single` | Tumor CNV + expression programs + TF regulons | GPL → arms-length or clean-room |
| 10 | **Bulk→single / spatial deconvolution** (VAE) + **WGCNA co-expression** | OmicVerse `bulk2single`, `bulk._wgcna` | Deconvolution + module networks adjacent to corr_heatmap | GPL → clean-room candidates |

### C. OVERLAP — we already have it (dedup; ours is superior)
Do **not** rebuild or host these — feed the partner's result table into the existing skill.

- **Core DE / enrichment / GSEA**: deseq2/edger/de-results/rnaseq-de/pathway-enricher/
  go-enrichment/gsea/reactome/wikipathways/OmicVerse `bulk`+`es` → **Selom `deg` /
  `enrichment[P]` / `gsea[P]` / `ssgsea` win** (editable Plotly + two-axis repro + GO/Reactome
  data, no KEGG/Enrichr/MSigDB license gate). edgeR stays the validation oracle only.
- **DE/marker viz**: de-visualization / diff-visualizer / OmicVerse `pl` → **our editable
  `volcano`/`heatmap`/`markers`/`pca` win** over their static matplotlib. (Only **MA-plot**
  + **dotplot** are small deltas worth bolting on.)
- **scRNA core**: clustering / preprocessing / markers-annotation / doublet-detection /
  trajectory / pseudobulk / scrna-orchestrator → **Selom's shipped 30-skill stack wins**.
- **Batch integration**: sc/batch-integration · scrna-embedding(scVI) · OmicVerse `pp` batch
  · data-harmonization → **Melody[P] wins** (clean-room, GPL off the shipped path).
- **Platform already reimplemented**: **data-extractor** ([[selom-chart-extractor]] shipped),
  **lit-synthesizer** ([[selom-lit-synthesizer]] shipped), **bio-orchestrator** ≈ our
  deterministic 4-layer skill router ([[selom-skill-keyword-index]]). The catalogs *validate*
  our build choices — nothing to take.

### D. PLATFORM — fold into the backend (not catalog skills, but the reproduction engine wants them)
- **`geo-data` + `article-data-fetcher`** — "paste a GSE / DOI → fetch the deposited raw data
  → reproduce." **Highest-value platform pickup for the repro moat** (default-to-raw,
  SuperSeries/GSE-GSM-GPL handling). Pair them.
- **proteomics `data-import`** — strips decoy/contaminant/site-only rows, LFQ-vs-iBAQ,
  DDA-MNAR vs DIA-MCAR — directly removes silent errors from the proteomics path.
- **gene-id-mapping**, **UniProt** domain coords (for lollipop), **Entrez/BioMart/Ensembl/SRA**
  as ingest/annotation sources, **BAM→counts** ([[selom-bam-ingest]]) / **VCF→matrix** ingest
  seeds, **multiple-testing** (already implicit in `deg`/`enrichment`).
- **OmicVerse `mcp` server** — *if* we host OmicVerse arms-length, its MCP seam is the
  cleanest out-of-process boundary.

### E. GET RID OF / NEVER TOUCH — off-thesis breadth (don't compete)
Whole sub-domains that don't fit table→editable-figure and aren't our moat:
- **Chemoinformatics (all 20), structural-biology (all 6), OmicVerse `mol`** — drug-discovery /
  3D structure; a different product surface.
- **Genomics infrastructure** — read-qc, aligners, assembly, annotation, variant-calling,
  copy-number, long-read, sequence/interval IO, phasing — *upstream of Selom's data matrix*.
- **Clinical / consumer / population genomics** — GWAS/PRS, clinical-databases, pharmGx,
  nutrigx, UK Biobank, ancestry/DTC, liquid-biopsy — wrong domain + regulatory liability.
- **Metagenomics / microbiome infra, phylogenetics, comparative / ecological / epidemiological
  genomics** — separate verticals (microbiome `differential-abundance` already ≈ our
  `diff_abundance`).
- **clip-seq, genome-engineering, rna-structure, restriction-analysis, primer-design** — entire
  bioSkills categories, no editable-figure fit.
- **OmicVerse static layers** — `pl` (matplotlib), `report` (static HTML), `agent`/`jarvis`
  (embedded LLM) — these *compete with* our moat; never host.
- **R-runtime / notebook content** — ggplot2/matplotlib/jupyter/quarto/rmarkdown guides,
  bioconductor/galaxy/illumina bridges (outsource compute or sequencer-ingest, against the
  native-runtime thesis; R stays validation-only per ADR 0002).

### F. LICENSE-BLOCK — cannot ship even if useful
OmicVerse in-process (GPL-3) · MiXCR (non-commercial) · `struct-predictor` Boltz-2 weights ·
clinical-databases (ClinVar/gnomAD data + ACMG diagnostic liability) · UK Biobank (DUA bars
SaaS redistribution) · consumer/DTC genomics · methylation arrays (Illumina IDAT manifests) ·
data gates: KEGG (commercial), Enrichr (non-commercial), MSigDB (commercial — we use
GO/Reactome/WikiPathways).

---

## 3. New editable-figure types worth BUILD-NATIVE (our home turf)
Pure table→Plotly verticals Selom can't render today — each is a clean catalog skill:

| Figure | Input | Audience | License | Priority |
|---|---|---|---|---|
| **oncoprint / mutation matrix** | MAF | cancer genomics | clean | ★ highest — per-cell alteration stacking ≠ heatmap |
| **Manhattan / QQ** | GWAS summary stats | GWAS/causal | clean (LocusZoom needs LD ref) | ★ opens the GWAS paper class |
| **lollipop protein map** | MAF + gene (Pfam/UniProt coords) | cancer/proteomics | clean | ★ distinctive |
| **KM survival + forest** | event table | clinical-omics | lifelines MIT | ★ high-demand, zero overlap |
| **forest / funnel (meta-analysis)** | effect estimates | clinical / MR | clean | mid |
| **sequence logo** | PWM/alignment | motif/ATAC/CLIP | logomaker MIT | mid |
| **MA-plot + dotplot** | DE / marker table | general | clean | small deltas on `volcano`/`markers` |

---

## 4. Usefulness ranking (top picks, condensed)

**Build-native, do soon (moat):** ① harden `proteomics_de` (limma/proDA) · ② `metabolomics_de`
+ mummichog · ③ oncoprint · ④ KM survival · ⑤ Manhattan/QQ · ⑥ statistical-annotation in the
editor.

**Host / collaborate (whitespace, biggest reach):** ① spatial suite (squidpy/OmicVerse
`space`) · ② cell-communication (LIANA) · ③ affinity-proteomics (ClawBio, MIT, shovel-ready)
· ④ multi-omics MOFA+ · ⑤ CRISPR-screen (ClawBio) · ⑥ nf-core fronts.

**Platform (repro engine):** ① geo-data + article-data-fetcher · ② proteomics data-import.

**Ignore:** everything in §2.E — ~60% of the 650.

---

## 5. The collaboration model (answering the steer)

The audit *confirms* the owner's instinct. Selom's 30 skills already cover the high-frequency
transcriptomics core; ~60% of the external universe is off-thesis breadth we should never
chase; and the genuinely-useful remainder is **mostly whitespace better reached by hosting a
partner's runnable package than by reimplementing it**. So:

- **We build native** only the moat: the editable-figure last mile, the reproduction/scoring
  engine, the proteomics/metabolomics analysis pillars, and a short list of new figure types.
- **We host / integrate** (the collaboration product = the Skill Foundry / IDE,
  [[selom-command-center-architecture]]): bioSkills as *method knowledge* (auto-methods +
  the skill-keyword index), **ClawBio as the MIT runnable-skill catalog** (easiest partner —
  affinity-proteomics + CRISPR-screen + nf-core fronts first), and **OmicVerse arms-length**
  (GPL → isolated worker, per-method host-vs-clean-room).
- **Pitch to each partner:** "you wrote the analysis; Selom is the no-code IDE + editable
  publication-figure frontend + reproduction-scoring + deployment layer your users lack." The
  GPL of OmicVerse makes the *frontend/deployment* framing (separate process) the natural,
  license-clean shape — we never fork their breadth, we surface it.

**Next concrete steps (owner to pick):** (1) ship the ClawBio MIT collaboration slice first
(affinity-proteomics is shovel-ready); (2) the §A.1 `proteomics_de` hardening (pure native,
no deps, immediate moat gain); (3) scope the arms-length OmicVerse worker seam *before* any
spatial build (it's the gate for the whole spatial/cell-comm/multi-omics whitespace) — ASK on
the Docker/worker infra first.

---

## 6. The primary goal: a non-bioinformatician brings their OWN data → cleaned → output

> **Owner (2026-06-21):** the everyday goal is a user who is *not* a bioinformatician putting
> in **their own data**, having Selom **clean and process it**, and getting **the output they
> want** — using our framework + omics skills as the guide.

Figure-reproduction is the *proving ground* (it forces correctness against published numbers);
**this own-data journey is the daily product.** It reweights the audit: the **cleaning / QC,
guided-routing, and ingest** layers — which read as mere "PLATFORM" above — are actually
**first-class to this goal**, because a non-expert can't pick the right method, can't spot a
dirty matrix, and won't hand-write QC. The journey decomposes into four stages, and the audit
maps cleanly onto each:

| Stage (the non-expert's path) | What it needs | From the audit | Build vs Host |
|---|---|---|---|
| **1. Bring any data** | Accept h5ad/CSV/mzML/MaxQuant/DIA-NN/FCS/10x/GEO/BAM/VCF | ingest breadth: `geo-data`, `article-data-fetcher`, proteomics `data-import`, `fcs-handling`, spatial readers, BAM→counts | **PLATFORM (native)** + host upstream nf-core fronts |
| **2. Clean / process it** (the hardest, most-skipped step for non-experts) | Adaptive QC, normalization with the *right* method, batch/drift correction, doublet/contaminant removal, honest "your data has a problem" flags | bioSkills `normalization` (composition-bias failure catalog), proteomics `data-import` + `proteomics-qc`, metabolomics `normalization-qc`, adaptive-MAD QC, Scrublet (shipped) | **Build native** — this *is* the moat for non-experts: correctness + guardrails, not breadth |
| **3. Pick the analysis without knowing the methods** | "I have this data + this question → which skill?" routing + guardrails that refuse nonsense | our deterministic **skill-keyword router** ([[selom-skill-keyword-index]]) extended from papers→raw data; `bio-orchestrator` validates the pattern; experimental-design advisory (power/batch) | **Build native** (we already own the router) |
| **4. Get the output they want** | Editable publication figure + the stats table + auto-methods text explaining what was done | the editable-Plotly last mile + `methods`/lit-synth (both shipped) | **Build native (moat)** |

**Implication for the strategy:** the *cleaning + guidance* layer (stages 2–3) is where Selom
earns the "for non-bioinformaticians" claim, and it is **native moat work, not hosting** — the
bioSkills *guides* are gold here (they encode the method-choice + failure-mode knowledge a
non-expert lacks), but the runner must be ours so the guardrails and the two-axis honesty hold.
Hosting (§2.B) extends the *menu of analyses* once the data is clean; it does not replace the
clean-and-guide core. Concretely this elevates: **proteomics/metabolomics QC + data-import**
correctness (already #1–2 in §A), an **adaptive-QC / "is my data clean?" guardrail pass**, and
**raw-data routing** (the router already exists for papers) — these become the highest-value
near-term native work *because* they serve the everyday non-expert, not just the repro demo.

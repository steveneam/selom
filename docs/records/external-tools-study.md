# External Tools & Resources Study — DIY-Transcriptomics · ARCHS4 · phylogenomics · OmicsBox annotation · PDF metadata

> Owner-supplied research-and-reflection pass (session 27), the same shape as the OSCA study:
> mine five external resources for the *what* and *why*, gap-check them against Selom, and turn
> the result into a scoped, license-clean build backlog. **Reference-only — we reimplement
> license-clean in Python; R is validation-only (ADR 0002), never shipped.**
>
> _Authored 2026-06-19, Claude (acting FE+BE). Method: five parallel research subagents, then
> five **independent adversarial verifiers** that re-checked every load-bearing license / API /
> capability claim from primary sources. The verified facts below supersede the first-pass
> reports wherever they differed (and they differed — see §0)._

## 0. Method & verification scorecard

Each thread was researched by one subagent and then fact-checked by a second, adversarial
subagent reading primary sources (GitHub `LICENSE` files, official docs, live API probes).

| Thread | Report reliability | Decisive verifier correction |
|---|---|---|
| DIY-Transcriptomics | MEDIUM | `decoupler`, `salmon`, `liana-py` are now **BSD-3** (reported GPL-3) — usable on the shipped path. `gseapy.ssgsea` BSD-3 + exists = confirmed. |
| ARCHS4 | HIGH | Data is **non-commercial** ("commercial → contact MSIP"), verbatim. The `rooky` signature endpoint **404s / is undocumented**; the documented surface is `archs4py` + the `matrixapi` Correlation API. |
| Phylogenomics | MEDIUM | **RAxML-NG and ASTER/ASTRAL are AGPL-3.0 blockers** (reported GPL-3 / Apache-2.0). **toytree is BSD-3** (reported GPLv3) — safe for tree figures. |
| OmicsBox tools | HIGH | **eggNOG-mapper AGPL-3.0** (SaaS blocker) and **MMseqs2 MIT** both confirmed → the permissive path is sound. |
| PDF metadata | HIGH | `pdf2doi` transitively pulls **PyMuPDF (AGPL)** — confirmed trap. OpenAlex CC0 + commercial confirmed; rate limit is now "100k *credits*/day", email pool → API keys. |

**Meta-finding:** ~7 of ~40 license claims were wrong, moving in *both* directions — copyleft
tools quietly relicensed permissive, and "clean" tools that are actually AGPL blockers. **License
facts are time-sensitive; verify the current `LICENSE` file at decision time, never from memory.**
The adversarial pass paid for itself.

---

## 1. Per-thread findings (verified)

### 1.1 DIY-Transcriptomics (Beiting, UPenn) — the spine matches; one clear gap

A semester bulk-RNA-seq course (lightweight/open ethos): **Kallisto** pseudoalignment (lecture/
upstream) → **tximport** transcript→gene (Step1) → filter+TMM (edgeR, Step2) → PCA + interactive
tables (`plotly`/`gt`/`DT`, Step3) → **edgeR + limma-voom + sva** DE (Step5) → module heatmaps
(`heatmaply`, Step6) → **GSVA + gProfiler2 + clusterProfiler + msigdbr + enrichplot** functional
enrichment (Step7) → Rmarkdown/`renv` reproducibility (Step8); plus two scRNA lessons
(**Seurat + DropletUtils + scater + SingleR + celldex**; labs add trajectory + cell-cell comm).
Volcano is `ggplot2`/`plotly`, **not** EnhancedVolcano (verified).

Selom covers the spine (`deg`, `volcano`, `heatmap`, `gsea`, `enrichment`, `pca`, `umap_scrna`,
`markers`, `annotate`, `trajectory`, `cluster`, `normalization_qc`). Verified gaps, ranked:

1. **ssGSEA / GSVA (per-sample pathway scores)** — *confirmed gap*: our `gsea` is `gseapy.prerank`-
   only (verified in code). Fix = `gseapy.ssgsea` (**BSD-3, exists** — verified). Output is a
   sample × pathway score matrix → heatmap. **Best ROI; pure-Python; effort S.** → BUILD #1.
2. **Reference-based cell-type annotation** — *same as OSCA Gap E*; DIY-T's SingleR/celldex use
   independently confirms its priority. `celltypist` = MIT (verified); clean-room
   correlation-to-reference = no-dep (recommended route, per OSCA §3 E1).
3. **tximport-equivalent** (Kallisto/Salmon `abundance.h5`/`quant.sf` → gene rollup) — widens the
   front door without touching FASTQ. `pytximport` = GPL-3 → reimplement clean-room (read h5/tsv +
   tx2gene group-sum + length offset; small). Effort S–M.
4. **Bulk batch correction (ComBat / sva)** — *confirmed gap* (no dedicated skill; `integration`
   is scRNA-Harmony). `sc.pp.combat` ships in scanpy (clean). Effort S.
5. Lower priority: a **limma-voom** DE engine (fidelity only — DESeq2 already covers bulk DE; matters
   for reproducing limma-based papers exactly); **cell-cell communication** (`liana-py` is now
   **BSD-3**, `CellPhoneDB` MIT — shippable, but L effort, scRNA-only).

NOT-A-FIT: FASTQ alignment/QC (Kallisto/FastQC/MultiQC) — heavy infra, ASK-before-Docker; if ever
pursued, `kb-python`/`kallisto` (BSD-2) and now `salmon` (BSD-3) are all clean.

**UX borrow:** an interactive, sortable/searchable **DEG result table next to the volcano** (the
course's `gt`/`DT` ethos) is a cheap FE delight that mirrors Selom's editable-figure thesis.

### 1.2 ARCHS4 (Ma'ayan Lab) — high value, but a launch-gated *data* dependency

1.5M+ uniformly-reprocessed GEO/SRA RNA-seq samples (human+mouse, kallisto pipeline, gene+transcript
HDF5 >30 GB each — all verified, incl. the 2018 paper's 84,863 human / 103,083 mouse) with derived
gene-centric analytics: tissue/cell-line expression distributions, **gene–gene co-expression**
(claimed to beat GTEx/CCLE for functional prediction — verified "in almost all categories"),
predicted GO/TF/kinase, and signature search.

- **Decisive constraint — the DATA is non-commercial.** Verbatim on the live site: *"All data is
  free to use for non-commercial purposes. For commercial use please contact MSIP."* A coexisting
  CC-BY-4.0 label on "provided gene expression files" creates tension; the conservative read for a
  commercial product is **non-commercial → launch-gate (the MSigDB build-now-gate-later pattern)**.
- **Code is clean:** `archs4py` = Apache-2.0.
- **Access reality:** the `loadExpressionTissue.php` tissue endpoint is live (CSV) but an
  *undocumented internal AJAX* endpoint; the `/custom/rooky` signature endpoint **404s**. The
  *documented* programmatic surface is `archs4py`/`archs4r` (local HDF5) + a **Correlation API at
  `maayanlab.cloud/matrixapi/`** — use that, not the scrape endpoints.

**Verdict:** a high-value *reference / co-expression* enrichment layer (a "context for this gene"
panel; a co-expression source for the gene-set-builder), but **dev/dogfood only under a
commercial-restriction marker** until MSIP-cleared or replaced. Only a *coarse bulk* reference for
the scoped SingleR-style annotation. Lower priority than the in-house build gaps.

### 1.3 Phylogenomics + future omics-type breadth — the actionable bit is the navigation facet

The product wedge (editable-figure last mile) holds for phylogenomics: the figure layer is pure-
Python and clean, while the inference tier stays out-of-process. `mossmatters/phyloscripts` proves
this — it's a Python/Jupyter *visualization* companion to HybPiper, while the heavy compute is not.

- **Figure-shaped, clean (good fits):** tree rendering (Newick/Nexus → editable Plotly tree),
  support display, D-statistic / f-branch introgression plot (heatmap-on-tree), MSA viewer,
  divergence-time tree — all buildable on **DendroPy (BSD)**, **Bio.Phylo (BSD)**, **toytree
  (BSD-3 — verified clean, *not* GPL)**. *Avoid `ete3` (GPL-3).*
- **Inference tier — NOT-A-FIT / ASK-before-Docker:** MAFFT (BSD), trimAl (GPL-3), IQ-TREE (GPL-2),
  **RAxML-NG (AGPL-3.0 — verified blocker)**, BEAST2 (LGPL-2.1), **ASTER/ASTRAL (AGPL-3.0 — verified
  blocker)**, **Dsuite (no declared license — all-rights-reserved risk)**.

**The near-term actionable idea: a lightweight `omics_type` facet on `skill.json`** — list-valued,
with a `general` sentinel for cross-omics skills (heatmap/volcano/pca/enrichment), surfaced via
`GET /skills` exactly like the existing `origin` flag. Cheap future-proofing while the library is
small; lets users navigate by interest (transcriptomics / proteomics / phylogenomics / metabolomics /
genomics) and doubles as ingest-routing metadata. → BUILD #3.

Defining data types per omics (the facet's backbone): transcriptomics = counts / `h5ad` / 10x mtx;
proteomics = intensity matrices / `mzML` / MaxQuant; phylogenomics = FASTA alignments / Newick-Nexus
trees / VCF; metabolomics = `mzML` / feature tables; genomics = VCF / BAM / GFF. Metabolomics, if
ever pursued, has a clean Python backbone: **OpenMS / pyOpenMS (BSD-3)** + **matchms (Apache-2.0)**.

### 1.4 OmicsBox functional-annotation tools — peripheral now, a non-model-organism future play

The Blast2GO/OmicsBox pipeline is **de-novo functional annotation for non-model organisms**
(DIAMOND/BLAST homology + InterProScan domains + eggNOG orthology → GO). Verified facts:

- **DIAMOND** — GPL-3 (usable arms-length as a subprocess; don't bundle).
- **eggNOG-mapper** — **AGPL-3.0 → do not ship** (network clause; a stale `__license__="GPL v2"`
  string in source is an inconsistency, but the repo `LICENSE` AGPL governs).
- **InterProScan** — code Apache-2.0, but member DBs **Phobius/SignalP/TMHMM are commercially
  restricted and off by default** (the *data* is the gate); ~6.6 GB data download, optional local
  lookup >1 TB → heavy, ASK-before-Docker.
- **eggNOG DB data** — commercial-use-OK-with-attribution, but the exact label (CC0 / CC-BY / EBI
  ToS) is *not firmly established from the portal* — cite-don't-gate, verify before any legal claim.

Selom's dogfoods are human/mouse — already symbol+GO annotated — so this pipeline is largely
redundant for the current mission. **Verdict: future market-expansion (the OmicsBox whitespace), not
core.** If pursued, the clean entry point is **`pyhmmer` (MIT) + Pfam → GO (Pfam2GO)** for domains,
with **MMseqs2 (MIT)** for the homology arm — both permissive, in-memory, modest footprint.

### 1.5 PDF metadata extractor (Papers / mekentosj) — the explicit ask, fully license-clean

Papers' value was its **identifier-first Article Matcher** (140M-citation DB, ~95% match, DOI-first
then title+first-author, first-page scan, preprint disambiguation — all its own published figures).
No solid evidence it embedded bibliographic XMP back into PDFs (so XMP write-back is a *"better than
Papers"* differentiator we can add). Selom's `papers.py` today reads only the raw `/Info` dict — no
enrichment.

**The replicable, fully license-clean architecture** (an ordered, fail-soft enrichment chain, mirror
of the lit-synth injected-Fetcher seam):

```
PDF → (0) extract candidate IDs (page-1 first): DOI regex on text + XMP (pikepdf) + /Info + filename
    → (1) DOI/arXiv?  → OpenAlex (CC0) primary, CrossRef (habanero) cross-check   [deterministic]
    → (2) else title+author → OpenAlex / PubMed (existing NCBI key) / CrossRef     [ranked, flag preprint]
    → (3) last resort → GROBID (Apache-2.0, out-of-process, ASK-before-Docker)
    → (4) store record beside the extracted figures (+ OPTIONAL XMP write-back via pikepdf)
```

License-clean backbone (all verified): **OpenAlex** (CC0, commercial-OK; 100k credits/day + 100
req/s with a free API key), **CrossRef** REST metadata (no ownership claim, cacheable, commercial-
OK; client `habanero` MIT), **PubMed E-utilities** (no commercial restriction; Selom already holds
an NCBI key), **arXiv** (CC0 metadata, branding caveat); **pikepdf** (MPL-2.0 / qpdf Apache-2.0) for
XMP I/O; **GROBID** (Apache-2.0) optional/out-of-process. **Avoid `pdf2doi` as a dependency** — its
own code is MIT but it transitively pulls **PyMuPDF (AGPL)**; borrow its algorithm only. → BUILD #2.

---

## 2. Verified license ledger (durable reference)

Clean = permissive (BSD/MIT/Apache/MPL/CC0) and shippable. ⚠ = copyleft concern. ⛔ = blocker
(AGPL / non-commercial / undeclared). Corrections from the verification pass are marked **(corr.)**.

| Tool / resource | Verified license | Shippable verdict |
|---|---|---|
| gseapy (incl. `ssgsea`) | BSD-3 | ✅ clean — GSEA + ssGSEA engine |
| **cnsplots** (v0.6.0) | **BSD-3-Clause** | ✅ clean — **styling values ported, not depended on** (Phase F). Copy + credit; no clean room needed. Its runtime set (`lifelines`, `comprisk`, `pycomplexheatmap`, `statannotations`, `biopython`) is **not** a Selom dependency and is triaged separately if ever adopted. |
| blitzgsea | Apache-2.0 | ✅ clean (opt-in; slow JIT in-env) |
| decoupler-py | **BSD-3 (corr.; was reported GPL-3)** | ✅ clean |
| salmon | **BSD-3 (corr.)** | ✅ clean (FASTQ tier only) |
| liana-py | **BSD-3 (corr.)** | ✅ clean (cell-cell comm) |
| CellPhoneDB | MIT | ✅ clean |
| celltypist | MIT | ✅ clean (reference annotation) |
| kallisto / kb-python | BSD-2 | ✅ clean (FASTQ tier; ASK-before-Docker) |
| pytximport | GPL-3 | ⚠ reimplement clean-room |
| scanpy `sc.pp.combat` | BSD (scanpy) | ✅ clean (bulk ComBat) |
| inmoose (ComBat) | GPL-3 | ⚠ prefer scanpy combat |
| archs4py (code) | Apache-2.0 | ✅ clean |
| **ARCHS4 data** | **non-commercial (contact MSIP)** | ⛔ launch-gate; dev/dogfood only |
| Biopython / Bio.Phylo | Biopython/BSD-3 | ✅ clean (tree IO) |
| DendroPy | BSD-3 | ✅ clean (tree IO) |
| toytree | **BSD-3 (corr.; was reported GPLv3)** | ✅ clean (tree figures) |
| ete3 | GPL-3 | ⚠ avoid (use Bio.Phylo/DendroPy) |
| MAFFT | BSD-3 | (inference tier — out-of-process) |
| IQ-TREE | GPL-2 | (inference tier — out-of-process) |
| RAxML-NG | **AGPL-3.0 (corr.; was reported GPL-3)** | ⛔ don't bundle |
| ASTER / ASTRAL (chaoszhang) | **AGPL-3.0 (corr.; was reported Apache)** | ⛔ don't bundle |
| BEAST2 / SNAPP | LGPL-2.1 / undeclared | (inference tier — out-of-process) |
| Dsuite | **none declared (corr.)** | ⛔ all-rights-reserved risk |
| trimAl | GPL-3 | (inference tier — out-of-process) |
| ClipKIT | MIT | ✅ clean |
| OpenMS / pyOpenMS | BSD-3 | ✅ clean (future metabolomics/proteomics MS) |
| matchms | **Apache-2.0 (corr.; was reported MIT)** | ✅ clean |
| DIAMOND | GPL-3 | ⚠ arms-length OK, don't bundle |
| eggNOG-mapper | **AGPL-3.0** | ⛔ don't ship |
| eggNOG DB data | commercial-OK-w/-attribution (label uncertain) | ✅ cite-don't-gate; verify label |
| InterProScan (code) | Apache-2.0 | ✅ code clean; ⚠ member-DB data gated + heavy |
| MMseqs2 | MIT | ✅ clean (DIAMOND substitute) |
| pyhmmer (HMMER/Easel) | MIT (BSD-3) | ✅ clean (InterProScan-lite domains) |
| pikepdf / qpdf | MPL-2.0 / Apache-2.0 | ✅ clean (XMP I/O) |
| pypdf | BSD-3 | ✅ clean (already in repo) |
| pdf2doi | MIT but pulls **PyMuPDF (AGPL)** | ⛔ borrow algorithm, don't depend |
| PyMuPDF / fitz | AGPL-3.0 | ⛔ (already avoided in `papers.py`) |
| habanero (CrossRef client) | MIT | ✅ clean |
| OpenAlex data | CC0 (commercial-OK) | ✅ clean — primary metadata backbone |
| CrossRef REST metadata | no-ownership / cacheable / commercial-OK | ✅ clean |
| PubMed E-utilities | no commercial restriction | ✅ clean (have NCBI key) |
| arXiv API metadata | CC0 (branding caveat) | ✅ clean |
| Semantic Scholar API | mixed (CC BY-NC vs ODC-BY) | ⚠ conditional — optional only |
| GROBID | Apache-2.0 | ✅ clean code; ⚠ heavy JVM/Docker, out-of-process |

---

## 3. The reusable license-decision framework

Distilled from this pass (and worth applying to every future dependency):

1. **Separate-process GPL CLI = "mere aggregation."** Shelling out to a GPL binary (data via
   files/stdin/stdout) does *not* relicense Selom's code. The obligation attaches to *linking* a GPL
   library into our process, or *bundling/redistributing* the binary in a shipped image. So a GPL
   CLI is usable arms-length in dev; the cleaner move for a hosted product is still a permissive
   substitute (e.g. MMseqs2/MIT over DIAMOND/GPL).
2. **AGPL flips the calculus for a SaaS.** AGPL §13 extends copyleft to users interacting *over a
   network* — exactly the hosted-service case. The arms-length defense is weak/risky. Treat AGPL
   tools (eggNOG-mapper, RAxML-NG, ASTER, PyMuPDF) as **do-not-ship**; dev-only behind a marker.
3. **The DATA license is frequently the bigger gate than the CODE.** InterProScan (Apache code,
   gated member DBs), ARCHS4 (Apache code, non-commercial data), eggNOG (AGPL code, permissive
   data) all decouple the two — always clear code *and* data separately.
4. **Verify the current `LICENSE` file at decision time.** Licenses change (decoupler/salmon/liana-py
   went permissive; some "permissive" tools are AGPL). Never decide from memory or a single source.

→ Captured in memory as `license-decision-framework`.

---

## 4. Prioritized build backlog

Owner approved all three in-house builds (session 27) and relaxed the timeline ("divide over a few
sessions, do it properly"). Each is its own scoped `feat(backend)` commit, defaults safe.

### Chosen builds

**BUILD #1 — `ssgsea` skill (per-sample pathway enrichment).** *Effort S.*
- New skill (output differs from prerank GSEA — a sample × pathway score matrix, drawn as a heatmap),
  via `gseapy.ssgsea` (BSD-3). Reuses the GO library (`gene_sets/library.py`) and the publication
  theme. New-skill stamp: skill.json + run stub + run_real + methods template + golden + add the id
  to both SKILLS lists (`tests/regen_golden.py`, `tests/test_skills_golden.py`).
- Closes the verified DIY-T Step-7 gap; complements existing `gsea`/`enrichment`.

**BUILD #2 — `papers.py` metadata enrichment layer.** *Effort M.* (Owner's explicit ask.)
- The ordered fail-soft chain in §1.5: candidate-ID extraction (DOI regex + `pikepdf` XMP + `/Info` +
  filename, page-1 first) → OpenAlex (CC0) / CrossRef (habanero) by DOI → PubMed (existing key) /
  arXiv / OpenAlex by title+author (ranked, preprint-flagged) → optional GROBID fallback
  (out-of-process, ASK-before-Docker) → store beside figures (+ optional XMP write-back).
- Injected-Fetcher seam (testable offline, like litsynth). New optional dep `pikepdf` in the `pdf`
  extra. Seeds the future Papers/EndNote-style spinoff.

**BUILD #3 — `omics_type` facet on `skill.json`.** *Effort S.*
- Additive, list-valued field (default `["transcriptomics"]`; `general` sentinel for cross-omics
  skills), surfaced through `GET /skills` exactly like the existing `origin` flag — zero runner/
  contract change. Backfill the ~29 skills. Lets the UI group by omics interest and future-proofs
  proteomics/phylogenomics/metabolomics navigation.

Suggested order: **#1 ssGSEA (smallest, high-value) → #3 omics_type (additive) → #2 PDF metadata
(largest)** — but owner may reorder.

### Gated / future (scoped, not chosen this round)

- **Reference-based annotation** (OSCA Gap E) — reinforced by DIY-T's SingleR/celldex; clean-room
  correlation recommended (no dep). The one remaining OSCA gap.
- **ARCHS4 reference/co-expression layer** — dev/dogfood only, launch-gated (non-commercial data);
  use `matrixapi`/`archs4py`, not the scrape endpoints.
- **Non-model functional annotation** — future "annotate my sequences" skill via `pyhmmer`+Pfam→GO
  (+ MMseqs2); the OmicsBox whitespace.
- **Phylogenomics omics-type** — `tree_render` / `tree_support` / `d_statistics` / `msa_view` on
  toytree/DendroPy/Bio.Phylo (all BSD); inference tier stays out-of-process.
- **Bulk ComBat batch correction**; **tximport-equivalent** ingest; **interactive DEG table** (FE);
  **cell-cell communication** (liana-py BSD); **limma-voom** fidelity engine.

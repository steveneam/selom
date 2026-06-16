# Selom — DECISIONS (Locked)

> Binding decisions for the Selom build. Agents treat these as authoritative.
> Supersede by append (with a new stamp), never silently overwrite. Deep ADRs
> live in the research vault; this file is the build-side quick reference.

_Last updated: 2026-06-16 — **corrected #9**: gseapy is BSD-3 (not AGPL) — the earlier rationale conflated gseapy=code with MSigDB=data; the decision (GO/Reactome over MSigDB) is unchanged because it is about the gene-set DATA license, but gseapy.prerank is now an allowed GSEA engine (see the corrected row + the new Notes bullet). Prior: 2026-06-14 — added #11 (gene-set builder: open-core, list-first UX, MSigDB/KEGG validation-only-then-drop, ship the Fidelle ciliopathy/proteostasis lists as owned panels), owner-ratified. Prior: 2026-06-13 added #10 (skill-scope bet) from the OmicsBox teardown._

| # | Decision | Rationale | Source |
|---|---|---|---|
| 1 | **Stack = Python (FastAPI) backend + Next.js frontend.** R is **validation-only** — never on the hot path; used to produce golden reference outputs the Python skills are tested against. | Single production language (Python) for skill runners; R kept as a correctness oracle only. | ADR 0002 |
| 2 | **The build repo lives at `D:/selom`** — separate from the research vault. | Code stays in `D:/selom`; the vault holds research + operational mirrors only. Clean separation of build vs. knowledge. | Project layout |
| 3 | **Commercial / licensing gates are intentionally DEFERRED** for build-for-self. | Owner directive: build the product first, apply commercial/licensing gates before launch. Gates never block in-lane build work. See `RISKS.md` #6 (AGPL) for the one item that must clear the pre-launch gate. | Owner directive |
| 4 | **Git staging is explicit** — never `git add -A` after the initial scaffold commit. | Disjoint two-agent lanes mean blanket staging risks committing the other agent's in-flight work. Stage named paths only. | Coordination protocol |
| 5 | **No-code figure editor = a custom panel, NOT `react-chart-editor`.** `react-plotly.js` (render) + shadcn/ui controls → RFC-6902 JSON-Patch; the same patch protocol the LLM copilot emits against the editable Plotly spec. | `react-chart-editor` 0.46.1 is abandoned (no React 18/19); the editable-spec + shared-patch loop is the product wedge ("AI navigator, not analyst"). **Already built** in `app/frontend` — this ratification locks existing truth. Lane: Claude (FE). | ADR 0002 · build-setup-and-toolchain §7 · `RISKS.md` #1 |
| 6 | **Async job queue = arq + Redis** (not Dramatiq). | arq is asyncio-native and matches the FastAPI async stack + every vault manifest/schematic; Dramatiq (heavier, broker-flexible) was considered and is not needed. **Backend-lane (Codex-owned)** — locked to the vault's recommended default under the owner's "ratify all 5" directive; Codex confirms, or supersede-by-appends if a Dramatiq-specific need surfaces. See `CURRENT.md → Cross-Agent Requests`. | build-ledger §3 · selom-build-kickoff §2 |
| 7 | **Distribution = web-first SaaS for v1.** No consumer desktop (Electron/Tauri); on-prem / BYO-cloud is reserved as a later enterprise tier (pharma data-residency). | The only model where the GPL SaaS-gap holds (server-side use ≠ distribution → no copyleft re-trigger), compute is metered, and there's nothing to pirate; bundling copyleft into a desktop app would re-trigger GPL. | distribution-web-vs-desktop · ADR 0002 |
| 8 | **IP strategy = trade-secret + copyright, NOT patents.** | The Extract-Skills method is best kept secret (patents force disclosure and are hard to enforce on a method); the durable moat is curation / UX / verified-reproducibility — protected by copyright (compilation) + trade-secret, with an open-core boundary for public parts. | commercialisation-ip-trademark §B |
| 9 | **GSEA / pathway-enrichment gene-set DATA source = Reactome / GO** (license-clean), NOT MSigDB. _(Corrected 2026-06-16: the decision is about the gene-set **data** source. gseapy is **BSD-3 code**, not AGPL — it is an allowed GSEA **engine**; the only restriction is MSigDB's gene-set **data** license.)_ | MSigDB's gene-set **data** carries CC-BY + per-set restrictions (incl. a no-Docker clause) that would have to clear the pre-launch gate; Reactome + GO are openly licensed (GO = CC-BY-4.0, the same upstream MSigDB curates its C5 from), so the `selom.enrichment`/`gsea` skills stay launch-safe with no cleanup. The earlier "gseapy = AGPL" framing was **wrong** — it conflated gseapy (BSD-3 code) with MSigDB (restricted data); **gseapy.prerank (BSD-3) + blitzgsea (Apache-2.0) over the from-GO library are allowed engines.** Owner-approved at B2 sign-off; correction owner-flagged 2026-06-16. Lane: Codex (BE). | Owner directive · `RISKS.md` #6 · build-charter B2/B4 |
| 10 | **Skill scope = win the analysis→editable-figure last mile + own the proteomics/metabolomics whitespace; do NOT chase upstream NGS** (alignment/assembly/variant-calling). Backlog sequence: **P1** (broaden `deg`/`enrichment` + new `pathway`/`go-graph` figure skills) → **P2** (single-cell depth: `markers`/`annotate`/`trajectory`) → **P3** (WGCNA/venn/pcoa) → **P4** (proteomics/metabolomics — the long-term moat). **P1 COMPLETE 2026-06-14** (all 6 P1 items shipped); **P2 single-cell depth (`markers`/`annotate`/`trajectory`) SHIPPED 2026-06-14** (+ supporting `pca`/`composition` skills); P3 next. | OmicsBox is NGS-only, desktop-first, raster-figure, and compute-metered on exactly the heavy upstream tools → the durable wedge is the editable-vector last mile (Selom starts from the count matrix / AnnData / feature table; `h5ad`-native = their Seurat weakness) plus the mass-spec whitespace they don't play in. Reuse eamos's live annotation APIs (NCBI/PubMed/UniProt/VEP); the only genuine new-API gaps are the pathway/enrichment ones (KEGG/Reactome/GO/QuickGO/STRING) backing P1. Owner-approved 2026-06-13. | `docs/competitors/omicsbox.md` · `docs/build-charter.md` (Competitor-driven skill priorities) |
| 11 | **Gene-set builder = open-core, list-first UX, collection-capable architecture.** Build a unified, provenance-stamped **`GeneSet`** object + open-core source adapters **once**; lead the UX with list-building (type a topic → compile → apply), and expose the same corpus as the `enrichment`/ORA library underneath (the two share ~90% of the machinery). **Open core = GO · Reactome · WikiPathways (CC0) · HGNC · HPO · Open Targets** (all open). **MSigDB + KEGG = validation/oracle use ONLY** until Selom's own open-core library reaches parity, then **dropped pre-launch** (easy gate). The Fidelle-derived **Ciliopathy / Proteostasis** lists are **ours to ship as owned curated panels** (no third-party claim). Open-core builder first; the grounded LLM/literature free-text→genes layer comes later. | Gene sets power `enrichment`/`pathway`/`go_graph` + list subset/highlight/plot; a provenance-stamped, license-clean, apply-in-one-click builder extends the publish-confidence thesis, is launch-safe where MSigDB-dependent tools aren't, and the `GeneSet` object is the durable abstraction Supabase persistence / sharing / the Skill Foundry build on. Extends #9 (off MSigDB/gseapy) + #10. Owner-ratified 2026-06-14. | `docs/gene-set-builder-design.md` |

## Notes

- Decision #1 (Python + Next.js, R validation-only) defines the lane split:
  Codex owns Python `app/backend`; Claude owns Next.js `app/frontend`.
- Decision #3 is the policy behind `RISKS.md` #6: deferred does not mean
  cancelled — the AGPL / commercial gate must be cleared before any external user.
- Decision #4 binds both agents: after the scaffold commit, every commit stages
  explicit paths so the disjoint lanes never cross-contaminate.
- **Ratification (2026-06-11):** the kickoff listed **5** pending vault `[DECISION]`s to
  formalise. Reconciled against this register: *repo = `D:/selom`* was already locked as
  **#2**, so only four were newly added — **#5** (custom figure editor), **#6** (arq vs
  Dramatiq), **#7** (web-first), **#8** (trade-secret IP). All five are now ratified.
- **#6 (arq) is backend-lane:** Codex owns the implementation. It is recorded here per the
  owner's "ratify all 5" directive using the vault's recommended default; Codex confirms or
  supersedes-by-append. Flagged in `CURRENT.md → Cross-Agent Requests`.
- **Vault mirror TODO (wiki agent):** the deep ADRs for #5–#8 (vault numbering `0004`–`0007`)
  should be filed into the research vault's `Selom/Wiki/decisions/` by the wiki agent — this
  build session is **read-only** in the vault, so it cannot write them. This file is the
  authoritative build-side reference until then.
- **Refinement to #10 (owner-directed, 2026-06-14):** **BAM is an accepted input file type.** This
  refines "do not chase upstream NGS" — *ingest flexibility* (a user hands us a BAM, we quantify it to
  a count matrix) is distinct from *being an aligner*, and lowering the barrier to the editable-figure
  wedge serves it. **In scope:** BAM → gene-level **count matrix** (against a bundled open GTF —
  GENCODE/Ensembl — via featureCounts / htseq / pysam; all open, GPL fine server-side per #7), which
  then feeds the existing `deg`/`volcano`/`enrichment` skills. Owner rationale: not license-gated, gives
  users a file-type choice. **Still out (for now):** FASTQ → BAM **read alignment** (STAR/HISAT2 — the
  heaviest commodity step); add later only if owner wants full flexibility. **Build considerations:**
  BAMs are GB-scale → bypass the in-memory Next proxy (RISKS #8) via direct/chunked upload + an async
  job (arq/Redis = Docker-gated on Windows → ASK owner). Test set: 20 GRCh38 iRPE-control BAMs on the
  CMRI share (`…/RNA-seq/2025_BAM files_Control samples`, ~38 GB). Present a plan before building.
- **Clarification to #11 #3 (owner, 2026-06-14):** "ship the Fidelle lists as our own" is refined —
  gene lists extracted from **papers / publications / public repos are generally not license-gated**
  (gene symbols are facts), so they are **shippable**. Where a list traces to a third party or a
  reference (e.g. **CiliaCarta** = van Dam 2013, **RetNet**, a specific paper), we **attribute /
  reference the source in the set's provenance** rather than claim it as Selom-original — not exclude
  it. "Selom (owned)" is reserved for genuinely Selom-compiled sets (e.g. the canonical
  phototransduction/cilium panels shipped in Phase A). Supersedes the conservative
  "NOT shipped / confirm provenance" reading filed in `docs/gene-set-builder-design.md` §8.1.
- **Correction to #9 (owner-flagged, verified 2026-06-16):** the earlier rationale wrongly
  listed **gseapy** as AGPL. **gseapy (zqfang/GSEApy) is BSD-3-Clause** (verified the LICENSE
  file) — permissive, commercial-OK, attribution-only. The error **conflated gseapy (the BSD
  *code*) with MSigDB (the restrictive gene-set *data*).** The decision is **unchanged** — it
  was always about the gene-set **data** source, and the GO/Reactome-over-MSigDB call still
  stands on MSigDB's *data* license (CC-BY + per-set restrictions + a no-Docker clause),
  independent of any GSEA-runner code. Net: **gseapy is clean code; MSigDB is restricted data.**
  Consequently **gseapy.prerank (BSD-3) and blitzgsea (Apache-2.0) are now allowed GSEA engines**
  over our own from-primary-GO library (closing the RPGRIP1 Fig5/6 GSEA gap). `RISKS.md` #6 and
  the #9 note + `app/backend/pyproject.toml [omics]` comment are corrected to match.

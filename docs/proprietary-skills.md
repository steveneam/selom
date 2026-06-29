# Selom — Proprietary vs. Commodity skills (the open-core boundary)

> Authoritative, **honest** classification of what is genuinely Selom-original IP
> versus a thin wrapper over a public library. Realizes the open-core boundary in
> `agent_handoff/DECISIONS.md` #8 (IP = trade-secret + copyright; the durable moat is
> curation / UX / verified-reproducibility), #10 (win the analysis→editable-figure last
> mile), and #11 (gene-set builder = open-core by design).
>
> _Last updated: 2026-06-20 (Claude, acting FE+BE) — added the Skill Keyword Index (4-layer paper→skill router) as a flagship proprietary module._

## The honest headline

**Most of the moat is not a "skill" at all.** The single biggest differentiator is the
**cross-cutting reproducibility / editable-figure layer** that wraps *every* skill —
not any one algorithm. Branding individual scanpy/pyDESeq2 wrappers as "proprietary"
would be dishonest and would dilute the real signal. So:

- A small set of skills are genuinely original IP → `origin: "proprietary"`.
- The bulk are honest commodity wrappers → `origin: "commodity"` (default). Their value
  is the editable Plotly output + provenance + the curated, verified, reproducible
  pipeline they sit in — **not** the underlying algorithm, which anyone can call.
- The deepest moat is the layer below, classified separately at the end.

## How it's wired

- **`origin`** field in each `skill.json` (`skills/contract.py::SkillSpec`, default
  `"commodity"`). `GET /skills` exposes `origin` + a derived `proprietary` boolean.
- **`skills/proprietary/<id>/`** — a physical namespace the loader scans alongside the
  flat `skills/<id>/` dirs (see `skills/proprietary/README.md`). New proprietary skills
  go here; already-shipped proprietary skills stay flat (to preserve entrypoints +
  goldens) and are marked by the flag.
- **`catalog.name`** carries the branded display name (e.g. "Selom Cepo"); falls back to
  the plain functional `title`.

## Proprietary — genuinely Selom-original (`origin: proprietary`)

### Skills (in the registry)

| Skill | Why it's IP |
|---|---|
| `enrichment` (**Selom Enrichment**) | In-house hypergeometric ORA + BH-FDR over a **from-primary-GO** license-clean library — a reimplementation, not a gseapy/MSigDB wrapper (DECISIONS #9). |
| `go_graph` (**Selom GO Graph**) | Turns enriched GO terms into an **editable Plotly node-link** drawn in the is_a/part_of DAG. The editable-graph-figure last mile (#10). |
| `pathway` (**Selom Pathway Map**) | Reactome enrichment drawn in the event hierarchy as an **editable, fold-change-coloured** node-link. |
| `string_network` (**Selom STRING Network**) | Live STRING PPI turned into an **editable** node-link figure. |
| `gsea` (**Selom GSEA**) | In-house running-enrichment GSEA with leading-edge viz over our own GO library. The engine may wrap `gseapy.prerank` (BSD-3) / `blitzgsea` (Apache-2.0), but the **editable figure + license-clean set library + provenance** are ours. |
| `cepo` (**Selom Cepo**) | **Clean-room Python reimplementation** of Cepo differential-stability markers — no Python port exists anywhere upstream (R-only, MIT). Real algorithmic IP. Validated against the Hani `mmc2` Cepo oracle on real RPGRIP1 data (top-DS genes recover the published markers far above chance — Amacrine p=4e-14, Glial p=1e-6, Bipolar p=2e-8). Cites Kim 2021. First resident of `skills/proprietary/`. |
| `integration` (**Selom Melody**) | **Clean-room pure-numpy reimplementation** of the Harmony batch-integration *method* (Korsunsky et al. 2019), built from the published Online Methods — `skills/integration/melody.py`. The whole upstream Harmony lineage (`harmonypy`, R `harmony`) is **GPL-3.0**; Melody copies none of it (only code expression is copyrightable, a published algorithm is not), so it removes a GPL dependency from the shipped path. Deterministic (seeded), `numpy`/`scikit-learn` only — no C++/CMake build. Validated by the batch-mixing METRIC vs. the harmonypy oracle on real GSE201356 (kept installed as oracle only). **s30: an opt-in `harmony2` mode (default off) folds in the two *Harmony2* (Patikas et al., bioRxiv 2026) anti-over-integration improvements — the stabilized scale-invariant diversity penalty + dynamic per-batch ridge — clean-room from the 2026 preprint (also GPL-3.0; read paper not source). This deepens the moat: there is no permissively-licensed Harmony2 anywhere (the canonical Harmony2 is the GPL R/C++ package), and ours is validated to MATCH it on metric (vs the R `harmony` 2.0.5 oracle).** Cites Korsunsky 2019 + Patikas 2026. (Ships flat at `skills/integration/`, marked by the `origin` flag; v0.3.0.) |

### Flagship modules (not figure-skills)

- **Selom PDF Extractor (SPE)** = `app/backend/papers.py` — paper → text / figure
  legends / GEO accessions / rasterized figures, permissive-only (no AGPL `fitz`). The
  "extract skills from papers" intake — the v2 Extract-Skills moat. Not a Plotly
  `run_skill`, so it is *not* in the skill registry; it is the flagship proprietary
  **module**, surfaced here and shipped behind the `pdf` extra + `scripts/extract_pdf.py`.

- **Skill Keyword Index** = `app/backend/extract/routing/` — a dropped paper → its
  **skill inventory + per-figure feasibility map**, with **no LLM on the critical path**.
  The IP is the **layered deterministic core** (`docs/records/skill-keyword-index/legend-hardening-scope.md`),
  designed so the core promise rests on the most robust layer:
  - **L1 structured** (clean numbered captions / headers / exact match) +
    **L2 recovery sweep** (de-spaced/garbled/glyph markers, ordinal number recovery,
    header-less citation-cluster reference detection, forward attribution) — together they
    **see through journal-format variance** that breaks naive keyword sweeps.
  - **L3 paper vocab sweep** — the **authoritative skill inventory** (exact + a token-canonical
    relaxed matcher that collapses surface variation: `heat map`→heatmap, `differentially
    expressed`→`differential expression`). Near-100% recall, robust to per-figure attribution
    error: the core promise.
  - **L4 AI** — paid, optional; verifies low-confidence/recovered figures and mines new
    synonyms back into the vocab. Never required; the deterministic core always returns a map.

  Two protected assets: the **curated synonym vocabulary** (`synonyms.json` — the hand-authored
  domain moat the registry can't express) and the **validation set** — four hand-built reproduction
  ledgers (RPGRIP1 / JEV / Hani / Dorgau) the router is backtested against, which nobody else has.
  Not a `run_skill`, so it is *not* in the registry; surfaced via `POST /papers/route`. Open-core:
  the deterministic L1–L3 core is free; the L4 AI verify/mine + OCR/vision over scanned PDFs are the
  paid tier (same split as the gene-set builder, DECISIONS #11).

## Commodity — honest wrappers (`origin: commodity`, default)

Standard, anyone can write these; the value is the editable output + provenance, not the
algorithm:

`umap_scrna` · `cluster` · `markers` · `deg` · `volcano` · `heatmap` · `pca` ·
`composition` · `violin` · `normalization_qc` · `corr_heatmap` · `proteomics_de` ·
`sankey` · `upset` · `scorecard` · `trajectory`

(`deg` wraps pyDESeq2; `trajectory` wraps simpleppt; `proteomics_de` is a limma-style
moderated-t over standard stats; etc. All genuinely useful — none secret.)

## The deepest moat (cross-cutting, *not* a skill)

These wrap **all** skills and are the real differentiator — classify as proprietary
*infrastructure*, tracked here so the open-core split treats them deliberately:

- **Reproducibility / lineage layer** — `provenance.py` + `methods.py` + `guardrails.py`
  (BE) + `lib/lineage/*` staleness / versioning / compare (FE). The publish-confidence
  thesis. Biggest single differentiator.
- **GeneSet builder** — `gene_sets/` (provenance-first, open-core *by design*,
  DECISIONS #11). The `GeneSet` abstraction + license-clean source adapters.
- **Publication theme + journal-style registry** — `theme.py` / `styles.py` (one look
  across every skill; installable style packs).

These stay where they are (cross-cutting), but the open-core release must decide for each
whether the *interface* is public and the *curation/implementation* is the protected part.

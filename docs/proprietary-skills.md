# Selom — Proprietary vs. Commodity skills (the open-core boundary)

> Authoritative, **honest** classification of what is genuinely Selom-original IP
> versus a thin wrapper over a public library. Realizes the open-core boundary in
> `agent_handoff/DECISIONS.md` #8 (IP = trade-secret + copyright; the durable moat is
> curation / UX / verified-reproducibility), #10 (win the analysis→editable-figure last
> mile), and #11 (gene-set builder = open-core by design).
>
> _Last updated: 2026-06-16 (Claude, acting FE+BE)._

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

### Flagship module (not a figure-skill)

- **Selom PDF Extractor (SPE)** = `app/backend/papers.py` — paper → text / figure
  legends / GEO accessions / rasterized figures, permissive-only (no AGPL `fitz`). The
  "extract skills from papers" intake — the v2 Extract-Skills moat. Not a Plotly
  `run_skill`, so it is *not* in the skill registry; it is the flagship proprietary
  **module**, surfaced here and shipped behind the `pdf` extra + `scripts/extract_pdf.py`.

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

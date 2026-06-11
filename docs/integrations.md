# Selom — External Integrations & Research

> **What this is.** Assessment of external tools/skills evaluated for Selom, the
> decisions taken, and the queued next-session work. Owner-requested review
> (2026-06-12) of OmicVerse, scikit-learn, R for Data Science, and the Hermes
> bioinformatics gateway. Companion to `docs/command-center/design.md §6.5`
> (toolchain) and the Skill Foundry. Source of truth for sequencing stays
> `docs/build-charter.md`; binding decisions stay `agent_handoff/DECISIONS.md`.
>
> _Filed 2026-06-12 · Claude (acting FE+BE), owner-directed._

---

## 1. Sources evaluated

### 1.1 OmicVerse — `github.com/Starlitnightly/omicverse` (GPL-3.0) — **highest value**
A unified, **scverse-native** (AnnData/MuData/pandas/numpy) multi-omics framework
bundling **50+ published tools** (Scanpy, MOFA, scVI, Harmony, CellphoneDB, Tangram…)
behind ~1000 consistent-API functions across modules: `ov.pp` (qc/scale/pca/neighbors/
umap/leiden/preprocess), `ov.bulk` (`pyDEG`, `pyGSEA`), `ov.single`, `ov.spatial`,
`ov.pl` (publication viz: PyComplexHeatmap, marsilea), `ov.utils`, `ov.external.datacollect`
(pull from GEO etc.). Ships **MCP-based tool serving** (`docs/mcp_quickstart.md` — `ov.pp.leiden`
etc. exposed as MCP tools over an `adata_id`) and a J.A.R.V.I.S. agent. Nat. Commun. 15:5983 (2024).

**Why it matters for Selom:** it's a curated superset of the wedge + everything the
roadmap grows into (batch correction, annotation, trajectory, deconvolution, cell–cell
interaction, multi-omics). It's the **single richest Skill-Foundry porting source** —
each `ov.*` call maps almost 1:1 onto a Selom skill (`ov.pp.leiden`→`cluster`,
`ov.bulk.pyDEG`→`deg`, `ov.bulk.pyGSEA`→`enrichment`, `ov.pl.*`→figure shaping).

**Blocker (RISKS #9):** OmicVerse pins `pandas<3.0, scipy<1.12, anndata<0.12`. Selom
deliberately runs `pandas>=3.0` + `anndata>=0.12`, so `omicverse` **cannot share the
backend venv** — adding it makes `uv` unsolvable (verified: it broke even core `uv run`).
**License:** GPL-3.0 + 50 transitive tools → fine server-side (DECISIONS #7 SaaS-gap) but
a real SCA-gate surface.
**Decision (this session):** NOT added to `[omics]`. Integrate **out-of-process in an
isolated env/container** (the §6.5C/E per-skill-env model), called over a thin RPC/MCP
boundary. See §3.

### 1.2 scikit-learn — `scikit-learn.org` (BSD) — **use now**
Foundational ML primitives, already pulled transitively by scanpy. License-clean (BSD,
no gate). Directly useful: **clustering-quality metrics** (`silhouette_score`,
Calinski–Harabasz) as publish-confidence guardrails; **hierarchical linkage** for heatmap
row-ordering/dendrograms; **PCA/NMF/t-SNE** as license-clean primitives.
**Decision (this session):** promoted to an explicit **core dependency**; added the
**silhouette guardrail to the `cluster` skill** (surfaced as a figure subtitle).

### 1.3 R for Data Science (Hadley, 2e) — `r4ds.hadley.nz` — **reference, not a dep**
Canonical tidyverse reference: **ggplot2 grammar of graphics** (data→aesthetics→geoms→
scales→facets→themes), dplyr/tidyr wrangling, and **Quarto** reproducible reporting.
**Why it matters:** (a) the grammar-of-graphics framing is the right blueprint for the
editable-spec editor + auto-methods-text; (b) it's the how-to for the **R validation
oracle** (limma/DESeq2/ggplot2 reference outputs — ADR 0002 / RISKS #7); (c) Quarto's
code→polished-doc pattern models **B4**'s methods-text + reproducibility bundle. R stays
**validation-only** (ADR 0002) — not a runtime dep.

### 1.4 Hermes `research-bioinformatics` — Nous gateway — **pattern + provenance reference**
Confirms the Skill-Store/Foundry thesis already in `design.md §1.3`: one front door over
many third-party skills, shallow-cloned on demand, `SKILL.md` as an expert guide, output
bundled as `report.md + commands.sh + environment.yml + figures`. **Updated counts:**
bioSkills **385** + ClawBio **33** (≈418), vs the seed's hard-coded 540/88 → 628.
**Don't depend on Hermes** (hosted gateway, not a library); copy the pattern + true-up the
catalog numbers via the live ingest job.

---

## 2. Done this session

- **scikit-learn → core dep** (`app/backend/pyproject.toml`) — BSD, license-clean.
- **`cluster` skill silhouette guardrail** — `silhouette_score` on the PCA embedding vs
  Leiden labels, surfaced as the figure subtitle ("N clusters · silhouette 0.42 — higher =
  cleaner separation"); stub mirrors a deterministic subtitle. Golden regen, `pytest` = 14
  passed, real engine smoke-verified.
- **RISKS #9** filed (OmicVerse pandas-3 conflict + GPL/SCA surface).
- **OmicVerse kept OUT of `[omics]`** with an in-file note explaining the conflict + the
  isolated-worker path.
- **context7 MCP** confirmed working (resolved `/omicverse/omicverse`, 2501 snippets); it's
  already pinned in `.mcp.json` — just needs `CONTEXT7_API_KEY` in `.env` if rate-limited.

---

## 3. Queued for next session (owner-approved 2026-06-12)

In addition to **B3** (arq+Redis async, R2 store, live `GET /skills`):

1. **OmicVerse as a second Verified engine + Foundry source — isolated.** Stand up an
   OmicVerse worker in its own env/container (pinned `pandas<3`/`anndata<0.12`) and call it
   out-of-process (subprocess JSON or its **MCP server** — `ov.*` tools over `adata_id`,
   per `omicverse/docs/mcp_quickstart.md`). First port targets: route `cluster`/`deg`/
   `enrichment`/`heatmap` optionally through `ov.pp.leiden`/`ov.bulk.pyDEG`/`ov.bulk.pyGSEA`/
   `ov.pl`, then fan out to trajectory/annotation/deconvolution. Each port: SkillSpec +
   golden test + provenance. **SCA-gate the 50 transitive deps; drop `gseapy` from `[omics]`.**
2. **heatmap hierarchical row-ordering** via sklearn/scipy linkage (+ optional dendrogram).
3. **R4DS/Quarto + ggplot2 reference set for B4** — methods-text + reproducibility-bundle
   shape (mirror Hermes' `commands.sh + environment.yml`), journal-quality figure defaults,
   and the **R validation oracle** harness (limma/DESeq2/ggplot2 golden references; RISKS #7).
4. **Catalog-count true-up** — `scripts/ingest-catalog` pulls the live bioSkills/ClawBio
   catalogs; replace the FE seed's hard-coded 540/88→628 with the real numbers (≈385/33→418).
5. **MCP servers:**
   - **context7** — already in `.mcp.json`; set `CONTEXT7_API_KEY` in `.env`. Use it for
     up-to-date library docs during the OmicVerse/scverse port.
   - **JARVIS / OmicVerse MCP** — launch OmicVerse's own MCP server **inside the isolated
     OmicVerse env** (see `omicverse/docs/mcp_quickstart.md` for the exact command) and add
     it to `.mcp.json` once the env exists. This doubles as the §3.1 RPC boundary. Do NOT add
     it before the env exists (a broken MCP entry fails the session connect).

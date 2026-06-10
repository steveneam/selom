# Selom Command Center — Design & Architecture

> **Status:** Design / framework doc. Authored 2026-06-11 by Claude (frontend lane)
> after owner research brief (Hermes bioinformatics gateway + bioSkills + ClawBio
> + UI references). This doc is the **single source of truth for the command-center
> expansion** — the move from a one-skill figure tool into a project-first,
> no-code multi-omics **IDE** with a browsable/installable skill "App Store".
>
> It does not restate the figure-editor architecture (see
> `docs/` + memory `selom-figure-editor-architecture`) or the agent-handoff rules
> (`agent_handoff/README.md`); it *builds on* them.

---

## 0. TL;DR

Selom today is a single-surface tool: drop a file → run the one `umap_scrna`
skill → edit the returned figure. This design turns it into a **project-first
command center**:

- **A left sidebar of project folders** (the MarketCap "Files +" pattern). Each
  project holds **datasets**, an **installed-skills workbench**, and **figures**.
- **A Skill Store** — browse and install bioinformatics skills as easily as apps
  on the Mac App Store. Inventory = the **~600 skills** in **bioSkills** (540
  reference) + **ClawBio** (88 runnable). Every skill is *browsable* from day one;
  execution lights up progressively (**hybrid-tiered**, see §6).
- **A guided intake** — when a file is dropped, ask a few pre-made questions
  (organism, cell type of interest, condition/disease, expected findings…), feed
  them to an LLM, and have it **propose** a cleaning + analysis pipeline with
  pre-filled parameters — *only when the user hasn't already pre-picked skills*.
  The LLM is a **navigator, not an analyst**: it proposes; the scientist approves.
- **Automatic ingest + QC** — Selom does the initial cleaning/normalization to get
  lab-specific data into an analysis-ready state, surfacing **statistical
  guardrails** (batch, normalization, low-cell, multiple-testing warnings) before
  any figure is served.
- The existing **figure editor** becomes **one panel inside a project**, unchanged
  in its internals (spec = source of truth, RFC-6902 JSON-Patch, dark-IDE brand).

**North star (owner directive, 2026-06-11):** *every one of the 500+ catalog
skills eventually runs in Selom* — by hand-porting ("building it ourselves") and/or
sandboxed execution. The hybrid-tiered plan below is the staged road there; the
**Skill Foundry** (§6.3) is the pipeline that promotes a browsable skill into a
runnable one.

---

## 1. Research synthesis — the supply side

The owner's brief points at three real, open artifacts. They define what the
"App Store" actually stocks and, crucially, *how those skills are meant to run*.

### 1.1 bioSkills (`github.com/GPTomics/bioSkills`)
- **540 reference skills across 63 categories** — "skills that guide AI coding
  agents through common bioinformatics tasks." Each is a **directory** with a
  `SKILL.md` (description must include a *"Use when…"* clause + a *Version
  Compatibility* block), example scripts with version headers, Quick-Start bullets,
  and example prompts.
- Categories incl. **Workflows (41)** (RNA-seq, variant calling, ChIP-seq, scRNA,
  spatial, Hi-C), **Single-cell (14)**, **Comparative genomics (13)**,
  **Copy-number (11)**, **CLIP-seq (12)**, **Data visualization (20)**, plus
  genome assembly/annotation, pathway analysis, metagenomics, immunoinformatics.
- **These are reference/decision-tree skills**, not turnkey services: they teach an
  agent *how* to do the analysis. Installed by populating an agent's skills dir
  (`install-claude.sh`, `--categories`, `--validate`, `--dry-run`).

### 1.2 ClawBio (`github.com/ClawBio/ClawBio`)
- **"The first bioinformatics-native AI agent skill library"**, **88 skills (29
  production-ready)**. *Runnable* pipelines: `skills/<name>/` = `SKILL.md` (declarative
  spec: inputs/params/outputs) + `<skill>.py` (validated code) + bundled **demo
  data** (`--demo`) + a **reproducibility bundle** (`commands.sh`,
  `environment.yml`, `checksums.sha256`, `runtime-lock.json`).
- Standardized **output bundle**: `report.md` + `figures/` (publication PNGs) +
  `tables/` (CSV) + `reproducibility/`.
- A machine-readable **`skills/catalog.json`** is the key artifact for us — per
  skill: `status` (production|beta|community), `trigger_keywords`, `demo_command`,
  `chaining_partners`, `input_formats`, `scale` (personal|population|clinical|research).
- A **Bio Orchestrator** auto-routes an input file to the right skill — the
  conceptual seed of our guided intake's "suggest a skill" behavior.
- Runs via CLI/lib (`clawbio run <skill> --demo`, `run_skill(...)`) over **conda**
  envs, or as a Claude Code plugin.

### 1.3 Hermes gateway (`hermes-agent.nousresearch.com/.../research-bioinformatics`)
- A single "research-bioinformatics" skill that is a **gateway to 400+ skills**
  from the two libraries above; installs reference repos on demand and follows their
  `SKILL.md` as guidance. Confirms the *aggregator* pattern: one front door over many
  third-party skills, each producing `report.md + commands.sh + environment.yml`.

### 1.4 The load-bearing reality
**None of these is a hosted API.** They are (a) reference material for a coding
agent or (b) local conda/CLI pipelines. So "install and run a skill in Selom"
cannot be a thin proxy — it spans a spectrum from *curated-native re-implementation*
to *sandboxed execution of the real repo*. §6 resolves this; everything else in the
product is downstream of it.

### 1.5 The demand side (why this shape)
From `PRODUCT.md`: ~35% of wet-lab scientists have no bioinformatician, 74% can't
code, 86% use only Excel. They have **lab/field-specific data** but want
**field-agnostic figures**. The product's job: absorb the per-lab specificity at
**intake** (a few guided questions + auto-clean), then route to **standardized,
reproducible skills** that emit **editable, publication-ready figures**. The store
makes the breadth discoverable; the intake makes it approachable.

---

## 2. Product surface — the project-first command center

### 2.1 Information architecture
A single authenticated workspace. Persistent **left rail**; a context-switching
**main stage**; a contextual **right inspector** (only where editing happens).

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TOP BAR   SELOM ▸ <Project>            search · run-status · account      │
├───────────────┬──────────────────────────────────────────────────────────┤
│  LEFT RAIL    │   MAIN STAGE (route-dependent)                             │
│               │                                                            │
│  ⌂ Home       │   • Home dashboard  — recent projects, runs, suggestions   │
│  ⊞ Skill Store│   • Skill Store     — browse/install catalog (the apps)    │
│               │   • Project view    — tabs: Overview · Data · Workbench ·   │
│  PROJECTS  +  │                       Figures                              │
│   • PBMC scRNA│   • Figure editor   — the existing editable-Plotly canvas, │
│   • Tumor DEG │                       docked as the Project ▸ Figures view │
│   • Phospho…  │                                                            │
│               │                                                            │
│  ⚙ Settings   │                                                  [Inspector]│
└───────────────┴──────────────────────────────────────────────────────────┘
```

### 2.2 Screen map
| Route | Screen | Purpose | Lane / state |
|---|---|---|---|
| `/` | **Home dashboard** | Recent projects, recent runs, "continue" cards, store highlights, empty-state CTA to create a project / drop a file. (Dense-but-calm; Scout-Lab/MarketCap visual language.) | FE, mock store |
| `/store` | **Skill Store** | Browse the full catalog by category/tier/omics; skill detail; **Install** to a project. | FE, mock catalog (→ `GET /skills`) |
| `/p/{id}` | **Project ▸ Overview** | Project summary: datasets, installed skills, figures, activity. | FE, mock store |
| `/p/{id}/data` | **Project ▸ Data** | Datasets in the project; upload; **intake questionnaire**; auto-clean/QC report + guardrail flags. | FE, mock (→ `POST /upload`, `POST /intake`) |
| `/p/{id}/workbench` | **Project ▸ Workbench** | The installed-skill workspace: pick a skill (or accept the LLM-proposed pipeline), set params, **Run** → produces a figure. | FE, mock (→ `POST /skills/{id}/run`) |
| `/p/{id}/fig/{figId}` | **Project ▸ Figure** | The existing editable-Plotly editor (canvas + tabbed inspector + JSON-Patch). | FE, **already built** |

### 2.3 The on-ramp (the "magic" path the owner described)
> *drop your file in → select pre-made tools/conditions/skills → apply it to your
> data; we do the initial cleaning.*

Concretely, two entry flows that converge on the Workbench:

1. **Guided (no skills pre-picked):** drop file → **intake questionnaire** →
   auto-clean + QC → **LLM proposes** a pipeline (cleaning steps + 1–3 skills +
   pre-filled params, each with a one-line rationale) → user reviews/edits →
   **Run** → figure opens in the editor.
2. **Power (skills pre-picked):** install skills from the Store first → drop file
   into a project that already has skills → intake is offered but **skippable** →
   **Run** the chosen skill directly.

Both are **traceable**: every run records the skill version, params, cleaning
recipe, and guardrail flags into the figure's provenance bundle (PRODUCT.md
"reproducibility bundle").

---

## 3. The Skill Store (the "App Store")

### 3.1 The skill as the unit of inventory
A **catalog entry** (one "app") is the union of what bioSkills/ClawBio expose plus
Selom's own runtime metadata:

```jsonc
// SkillCatalogEntry — the store/listing shape (FE-facing)
{
  "id": "clawbio.scrna-orchestrator",      // namespaced: <source>.<slug>
  "name": "scRNA Orchestrator",
  "summary": "QC → cluster → marker detection for single-cell RNA-seq.",
  "source": "clawbio",                      // clawbio | bioskills | selom
  "category": "single-cell",                // from the source taxonomy
  "omics": ["scRNA-seq"],                   // facet for filtering
  "tier": "verified",                       // verified | community  (see §6)
  "status": "production",                   // production | beta | community
  "engine": "python",                       // python | r | agent-sandbox
  "input_formats": [".h5ad", ".csv"],
  "trigger_keywords": ["single cell", "cluster", "umap"],
  "chaining_partners": ["selom.deg", "selom.volcano"],
  "outputs": ["figure", "report", "tables"],
  "license": "MIT",                         // provenance + launch-gate metadata
  "provenance": { "repo": "ClawBio/ClawBio", "path": "skills/scrna-orchestrator" },
  "version": "1.0.0",
  "popularity": 0,                           // for sort/curation
  "installed": false                         // per-workspace, joined client-side
}
```

> The store ingests the **full ~600-skill catalog** as `SkillCatalogEntry` rows so
> the shelves look full from day one. `tier`/`engine`/`status` drive what the
> Install button does (§6). ClawBio's `skills/catalog.json` maps almost 1:1; for
> bioSkills we derive entries from each `SKILL.md` frontmatter (name, "Use when…",
> primary_tool, category).

### 3.2 Store UX (modeled on the references)
- **Browse:** category nav + omics/tier facets; cards with name, source badge,
  tier badge, omics chips, one-line summary, install state. Dense but calm, dark-IDE
  surface, cyan accents (Scout Lab visual density; MarketCap card rhythm).
- **Skill detail:** what it does, inputs/outputs, params preview, chaining partners
  ("works well with…"), provenance/license, demo. **Install** adds it to a project's
  workbench. Verified skills install instantly; Community skills show
  **"Request / Queue"** with an honest *"runs in a future sandbox"* state (no silent
  truncation — §6.4).
- **Curation:** "Selom Picks" (the wedge: scRNA + proteomics), "New", "Popular",
  "Runs now vs Coming soon".

### 3.3 Install semantics
"Install" = **add a `SkillCatalogEntry` to a project's installed-skills set**
(a join row). It does *not* download a repo to the user's machine. For Verified
skills the runner already exists server-side; for Community skills it records intent
and (later) provisions a sandbox. Mock-first: the install set lives in the local
project store, schema-aligned to a future `skill_installs` table (§5).

---

## 4. Guided intake — questionnaire → LLM → proposed pipeline

### 4.1 Why intake exists
"A lot of the data is very lab/field-specific, but the graphs are not." Intake is
where Selom absorbs the lab-specific context once, converts it into **analysis
parameters + a skill proposal**, and then hands off to standardized skills.

### 4.2 The questionnaire (pre-made, adaptive)
Shown right after upload **when no skills are pre-selected** (skippable otherwise).
A short, friendly form — not a wall. Fields adapt to the detected file type:

- **Universal:** organism/reference, omics type (auto-detected, confirmable),
  experimental design (groups/conditions, replicates), what you want to learn
  (free text: "expected findings").
- **scRNA-specific:** tissue/sample, **cell type(s) of interest**, expected
  populations, integration needed? (multiple samples/batches).
- **Bulk RNA-seq:** condition vs control, the contrast(s) of interest, paired?
- **Proteomics:** labeling (LFQ/TMT), phospho? contaminant DB.
- **Condition/disease context:** disease/condition, treatment/timepoint.

### 4.3 The LLM step (navigator, not analyst)
Input = questionnaire answers + dataset shape (from auto-ingest: n cells/samples,
n features, detected modality, QC flags) + the installed/available skills. Output =
a **structured pipeline proposal**, never a silent auto-run:

```jsonc
// IntakeProposal — what the LLM returns (BE: POST /intake)
{
  "summary": "Single-cell PBMC dataset, 2 conditions; you want T-cell subsets.",
  "cleaning": ["filter low-gene cells", "normalize (log1p)", "HVG", "scale"],
  "guardrails": [{ "level": "warn", "msg": "Batch effect likely (2 samples) — consider integration." }],
  "steps": [
    { "skillId": "selom.umap_scrna", "rationale": "Embed + cluster to see T-cell structure.",
      "params": { "n_neighbors": 15, "resolution": 1.0, "color_by": "leiden" }, "confidence": 0.86 },
    { "skillId": "selom.deg", "rationale": "Rank markers to label T-cell subsets.",
      "params": { "group": "condition", "method": "wilcoxon" }, "confidence": 0.7 }
  ],
  "alternatives": ["clawbio.scrna-orchestrator"]
}
```

The Workbench renders this as an **editable plan** (toggle steps, tweak params,
swap a skill) with a prominent **Run** button. The user is always in control; the
proposal is explainable (each step carries a rationale + confidence).

### 4.4 Engine
Use the **shared AI gateway** (the EAMOS/Selom shared spine). The intake prompt is
a constrained, schema-validated tool call (returns `IntakeProposal`), so the model
fills parameters rather than improvises code. This is a *backend* endpoint
(`POST /intake`, Codex lane); FE mocks it with a deterministic stub keyed off the
detected modality until it's live.

---

## 5. Data model (mock-first, schema-aligned)

Owner choice: **mock-first in the browser, schema designed to match the planned
Supabase tables exactly** so the swap is mechanical. The FE persists to
`localStorage`/IndexedDB behind a `ProjectStore` interface; the same interface gets
a Supabase implementation later (Codex). Proposed tables (filed to Codex, §
cross-agent request):

| Table | Key columns | Notes |
|---|---|---|
| `projects` | `id`, `owner`, `name`, `created_at`, `color/icon` | RLS by `owner`. The sidebar's folders. |
| `datasets` | `id`, `project_id`, `filename`, `modality`, `n_obs`, `n_var`, `qc`, `storage_key` | One row per uploaded file; `qc` = ingest report + guardrails. |
| `skill_installs` | `id`, `project_id`, `skill_id`, `tier`, `installed_at` | Join: which skills are added to a project. |
| `intake_sessions` | `id`, `dataset_id`, `answers`, `proposal`, `created_at` | Questionnaire answers + the LLM `IntakeProposal`. |
| `figures` | `id`, `project_id`, `dataset_id`, `skill_id`, `spec`, `provenance`, `created_at` | The editable Plotly spec + reproducibility bundle. Already implied by P0/P1. |
| `figure_history` | `id`, `figure_id`, `patch`, `actor`, `ts` | RFC-6902 patch audit trail (panel + LLM copilot share it). |
| `skill_catalog` | `id`, `name`, `source`, `tier`, `engine`, … (§3.1) | The store inventory; can be a seeded table or served from a manifest. |

FE-side types live in `lib/projects/types.ts`; the mock store in
`lib/projects/store.ts` implements the interface that the Supabase client will later
satisfy. **No FE code calls Supabase directly** — it goes through `ProjectStore`.

---

## 6. Execution model — hybrid-tiered, with a road to 500+

This is the architectural spine. The catalog is **fully browsable** immediately;
**runnable coverage grows** along a defined path.

### 6.1 Tiers
- **Verified** — a first-class server-side runner exists. Two ways in:
  1. **Selom-native runners** (the current `SkillSpec` path: scverse — scanpy,
     pyDESeq2, decoupler, gseapy; proteomics — alphastats/pyteomics). The launch
     wedge (~6–8 skills: UMAP, cluster, DEG, volcano, heatmap, enrichment).
  2. **ClawBio runnable skills** (~29 production) wrapped behind the same contract,
     emitting a Plotly spec (adapt their `figures/`+`report.md` outputs to our
     editable-spec convention).
  Verified skills **run now** (sync for fast skills, async via arq for heavy ones).
- **Community** — browsable, *installable as intent*, **not yet executable**. These
  are the long tail (most of bioSkills' 540 + ClawBio beta/community). The Install
  button is honest: **"Queued — runs in a future sandbox."**

### 6.2 Sandbox (the eventual Community executor — v2 infra)
To run a Community skill *for real* without hand-porting, Selom provisions a
**per-skill sandbox**: build the skill's `environment.yml` (conda) in an isolated,
network-restricted container, run its script on the user's dataset, capture
`report.md`/`figures/`/`tables/`, and **adapt the figure into an editable Plotly
spec** where possible (else present the static figure + offer "make editable" via a
Foundry port). This is heavy (compute, security, supply-chain, AGPL exposure — see
RISKS #6) and is **explicitly v2**; the design reserves the seam (`engine:
"agent-sandbox"`) without building it now.

### 6.3 The Skill Foundry — how a skill gets *promoted* (the path to 500+)
The owner's directive ("eventually all 500+, even if we build it ourselves") is a
**porting pipeline**, not a one-off. The **Skill Foundry** converts an external
skill into a Verified Selom runner:

```
external skill (bioSkills SKILL.md │ ClawBio pipeline │ paper+repo)
        │
        ├─ read spec/methods + code            (today: human/Codex; later: LLM-assisted)
        ├─ define SkillSpec (typed param_spec, inputs, Plotly outputs)
        ├─ implement/adapt the runner (Python; R only as validation oracle)
        ├─ golden-image test + provenance/license metadata + guardrails
        └─ publish → catalog entry flips Community → Verified
```

- **Now:** the Foundry is **manual** — Codex hand-ports the wedge + selected ClawBio
  skills. Each port is small and contract-shaped, so throughput is steady.
- **Later:** the Foundry is **LLM-assisted** — this is exactly the **v2
  "Extract-Skills" moat** (PRODUCT.md), generalized: *drop a paper/repo → generate a
  reproducible Selom skill.* The same pipeline that lets a user port a paper lets
  Selom burn down the 500-skill backlog.
- **Coverage telemetry:** the catalog tracks `tier` per skill, so "how many of 600
  run today" is a first-class, visible number (and a roadmap metric), never a silent
  cap.

### 6.4 Honesty principle
The store **never pretends** a Community skill runs. Browsable ≠ runnable is shown
explicitly (tier badge, install copy, a coverage counter). This protects trust and
matches PRODUCT.md's "no black box."

### 6.5 Toolchain — what we download/install to test & run the skills
Running real bioSkills/ClawBio skills is **not** `npm install`; it is a
bioinformatics runtime. This is mostly **Codex/BE + infra lane**, captured here so
the plan is complete. Grouped by purpose:

**A. Catalog ingest (needed first — builds the store inventory).** Cheap, local,
do-now.
- `git clone --depth 1 https://github.com/ClawBio/ClawBio` → read
  `skills/catalog.json` (maps ~1:1 to `SkillCatalogEntry`) + each `skills/*/SKILL.md`.
- `git clone --depth 1 https://github.com/GPTomics/bioSkills` → derive entries from
  the README category table + each skill dir's `SKILL.md` frontmatter ("Use when…",
  primary_tool, category).
- An **ingest script** (`scripts/ingest-catalog.{py,ts}`) emits the seed manifest the
  FE catalog reads (mock now → served by `GET /skills`, B1). *This alone makes the
  store real; no heavy installs required.*

**B. Verified-tier native runners (the wedge — already specced).** The
`app/backend` `[omics]` extra: **scanpy, anndata, scvi-tools, pydeseq2, decoupler,
gseapy** (scRNA + bulk) + **alphastats, pyteomics** (proteomics) + **plotly +
kaleido** (figure spec + export). Installed via **uv** (`uv sync --extra omics`).
Already in `pyproject.toml`. This is what powers the launch ~6–8 skills.

**C. ClawBio runnable skills (~29 production).** To execute the real pipelines:
- **`pip install clawbio`** *or* `git clone … ClawBio && uv sync`; run via
  `clawbio run <skill> --demo` / `run_skill(...)`.
- **conda/mamba** (Miniforge/mambaforge) — ClawBio skills ship per-skill
  **`environment.yml`** conda snapshots; build the env per skill on first run.
- **bioconda + conda-forge** channels for the underlying tools.
- Some skills need **external data/DBs/APIs** (gnomAD, ClinVar, UK Biobank schema,
  Galaxy via the **Galaxy Bridge** = 8,000+ tools) — provision per skill as needed.

**D. bioSkills reference execution (the long tail).** These guide a *coding agent*,
so the runtime is **(an AI agent) + the bioinformatics CLI toolchain** they
reference — installed from **bioconda**: `samtools, bcftools, bwa, STAR, HISAT2,
bowtie2, salmon, kallisto, featureCounts, GATK4, bedtools, fastp, kraken2,
minimap2, NCBI-BLAST+`, plus workflow managers **Snakemake / Nextflow**, and R/
Bioconductor (`DESeq2, edgeR, limma, Seurat, clusterProfiler`) where a method is
R-native (validation-only per ADR 0002). This is the bulk of the 500+ and is where
the **Skill Foundry** (§6.3) ports each into a Verified runner over time.

**E. Sandbox executor (Community tier — v2 infra).** **Docker** (Desktop 4.75 / WSL2
on Win11) + **mamba**-based per-skill images, **bioconda/conda-forge**, a
**network-restricted** policy, and **compute** (CPU; GPU only for scvi-tools /
AlphaFold / Boltz / Chai). This is the heavy path and stays deferred; the
`engine: "agent-sandbox"` seam is reserved now.

**F. Skill Foundry tooling.** Porting harness: SkillSpec scaffolder + `param_spec`
(Pydantic v2) + Plotly-spec adapter + **golden-image** test rig (the R oracle:
limma/DESeq2 cross-checks) + provenance/license capture. Manual now (Codex);
LLM-assisted later (= Extract-Skills moat).

> **Do-now (cheap) vs. defer (heavy):** A + B are immediate and already in-repo or
> one `uv sync` away. C is a contained next step (install `clawbio` + Miniforge in a
> worker, light up its demos). D is incremental per-skill via the Foundry. E is the
> v2 infra lift. The FE never blocks on any of this — it builds against the mock and
> the additive contracts in §8.

---

## 7. Auto-clean / ingest + QC

"We do the initial cleaning and processing to get it there." Concretely, an
**ingest step** that runs on upload (backend; FE mocks the report):
- **Detect** modality + shape (`.h5ad`/`.csv`/`mzML` → scRNA/bulk/proteomics; n_obs,
  n_var).
- **Clean** to an analysis-ready baseline per modality (scRNA: filter cells/genes,
  normalize, log1p, HVG; bulk: filter low-count genes, design-aware normalization;
  proteomics: contaminant removal, log-transform, imputation choice surfaced).
- **Guardrails** as a *feature*: batch-effect, normalization, low-cell, low-replicate,
  multiple-testing warnings — surfaced **before** figures, with one-line "why this
  matters" + the recommended fix. This is the research analogue of EAMOS's "no black
  box" and a differentiator (PRODUCT.md).
- The cleaning recipe is **recorded** into provenance (reproducible, inspectable,
  overridable). Defaults are sensible; nothing is silently irreversible.

---

## 8. Architecture & lanes

### 8.1 What changes where (respecting the handoff lanes)
- **Frontend (Claude):** the entire command-center shell — project-first IA,
  sidebar, Home dashboard, Skill Store, intake questionnaire UI, Workbench, and the
  `ProjectStore` mock. Reuses the existing figure editor unchanged. Mock-first; no
  Codex dependency to build.
- **Backend (Codex):** new endpoints + data. Filed as cross-agent requests (FE does
  not edit the contract):
  - `GET /skills` (catalog list, filterable) + `GET /skills/{id}` (detail/SkillSpec)
    — registry-driven, served from the ingested bioSkills/ClawBio manifest.
  - `POST /upload` returning a dataset handle + **ingest/QC report**.
  - `POST /intake` → `IntakeProposal` (LLM via shared AI gateway, schema-constrained).
  - `POST /skills/{id}/run` (already exists for `umap_scrna`) generalized to any
    Verified skill; async (arq) for heavy ones.
  - Supabase schema (§5) + RLS.
- **Contract seam:** unchanged wire format for figures (Plotly `{data, layout}`
  JSON). New shapes (`SkillCatalogEntry`, ingest report, `IntakeProposal`) are
  additive and specced here for Codex to own/finalize.

### 8.2 FE module plan (mock-first)
```
app/frontend/
  app/
    (workspace)/layout.tsx        // left rail + top bar shell
    page.tsx                      // Home dashboard
    store/page.tsx                // Skill Store
    p/[id]/…                      // project routes (overview/data/workbench/figure)
  components/
    shell/                        // sidebar, project-list, rail-nav, top-bar
    store/                        // catalog grid, skill-card, skill-detail, filters
    intake/                       // questionnaire, proposal-plan
    project/                      // overview, data panel + QC report, workbench
    figure/                       // (existing editor — reused as the Figure view)
  lib/
    projects/{types,store}.ts     // ProjectStore interface + localStorage impl
    catalog/{types,seed}.ts       // SkillCatalogEntry + seeded ~600-row mock
  mocks/                          // MSW handlers extended: /skills, /upload, /intake
```

### 8.3 Reuse, not rewrite
The figure-spec engine (`lib/figure-spec.ts`, `lib/patch.ts`,
`hooks/use-figure-store.ts`) and the editor components are **unchanged**. The
command center wraps them; `app/page.tsx`'s single-surface flow is refactored into
the project-first shell, with the upload→editor flow preserved as the Project ▸
Data → Workbench → Figure path.

---

## 9. Phased plan

> Numbered to extend the existing P0–v2 roadmap. FE phases are mock-first and
> unblocked; BE phases are filed to Codex. (The existing P0 hello-UMAP and P1
> figure editor are done/in place.)

| Phase | Lane | Goal | Exit |
|---|---|---|---|
| **C1 — Command-center shell** | FE | Project-first IA: left rail, projects sidebar, Home dashboard, routing. `ProjectStore` mock (localStorage). Figure editor docked as Project ▸ Figure. | Create a project, see it in the sidebar, open it, reach the editor — all mock, tsc clean, browser-verified. |
| **C2 — Skill Store** | FE | Ingest the full catalog as `SkillCatalogEntry` (seed mock from ClawBio `catalog.json` shape + bioSkills categories). Browse/filter, skill detail, Install → project. Tier/coverage honesty. | Browse ~600 skills, filter by omics/tier, install a Verified skill into a project. |
| **C3 — Guided intake** | FE | Questionnaire UI (adaptive by modality), proposal-plan renderer, Workbench run flow. Mock `POST /intake` (deterministic stub) + mock ingest/QC report. | Drop file → answer questions → see an editable proposed pipeline → Run (mock) → figure opens. |
| **B1 — Registry API** | BE (Codex) | `GET /skills` + `GET /skills/{id}` served from the real ingested manifest. | FE catalog reads live registry; skill picker fully registry-driven. |
| **B2 — Ingest + intake** | BE (Codex) | `POST /upload` returns real QC report; `POST /intake` returns a real `IntakeProposal` via the AI gateway. | Guided path works end-to-end against the live backend. |
| **B3 — Verified runner expansion** | BE (Codex) | Generalize `/skills/{id}/run`; **Skill Foundry (manual)** ports the wedge + selected ClawBio skills; async via arq for heavy ones. | ≥6–8 Verified skills run live + return editable specs. |
| **B4 — Supabase persistence** | BE (Codex) | Swap `ProjectStore` mock for Supabase (schema §5 + RLS + auth). | Projects/datasets/figures persist per-user; mock impl retired. |
| **v2 — Sandbox + LLM Foundry** | BE | Community-skill sandbox executor (`engine: agent-sandbox`) + LLM-assisted Foundry (= Extract-Skills moat) to burn down the 500-skill backlog. | A Community skill runs in a sandbox; a paper/repo auto-generates a Verified skill. |

**This session delivers C1 scaffold + the docs that lock C1–C3 and B1–B4** (owner
chose "docs + plan + scaffold FE shell").

---

## 10. Open questions / deferred

- **Sandbox security & cost model** (v2): per-skill conda images, network policy,
  compute metering, AGPL quarantine on the paid path (RISKS #6, LAUNCH-GATES §1/§4).
  Deferred with the rest of the commercial gates, but the sandbox seam is reserved now.
- **bioSkills entry derivation:** how richly to parse each `SKILL.md` (frontmatter
  vs. full body) for catalog metadata — start shallow (name/category/"Use when…"),
  enrich during Foundry porting.
- **Catalog freshness:** the upstream repos change; decide a periodic re-ingest of
  `catalog.json` + bioSkills categories (a scheduled job, post-B1).
- **Intake depth:** how many questions before it feels like a wall — start minimal
  (4–6), make adaptive, measure.
- **Multi-omics chaining UX** (chaining_partners → derived figures): designed into
  the Workbench seam but full chaining UX is post-C3.

---

## 11. Pointers (do not duplicate)
- Figure-editor internals: memory `selom-figure-editor-architecture` + the existing
  `lib/`/`components/figure/` code. Unchanged here.
- Brand/visual language: memory `selom-knowledge-vault` (dark IDE, cyan accent,
  molecular hex mark) + `app/frontend/app/globals.css` tokens.
- Handoff/lane rules & locks: `agent_handoff/README.md`. Cross-agent requests &
  live state: `agent_handoff/CURRENT.md`.
- Commercial/licensing gates (deferred): `LAUNCH-GATES.md`, RISKS #6.
- Roadmap (extended by §9): `ROADMAP.md`.

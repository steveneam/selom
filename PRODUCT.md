# Selom — Product Vision

## Mission

Let any wet-lab biologist turn raw omics data into **publication-quality figures — without a bioinformatician** — by dropping a file and applying composable, reproducible analysis **skills**.

Promise (provisional): *"Your data. Your figures. No code."*

## North Star

A bench scientist uploads scRNA-seq / bulk RNA-seq / proteomics data, picks skills (UMAP, clustering, pseudotime, DEG volcano, heatmap, GSEA), chains them, and gets publication-ready, reproducible figures plus methods text in minutes — every figure traceable to a versioned, citable recipe, not a black-box button.

## Why now

The opportunity is grounded: ~35% of wet-lab scientists have no bioinformatician, 74% can't code, 86% use only Excel. No competitor combines no-code + multi-omics breadth + a curated composable skill library + paper-to-skill extraction.

## The two signature features

1. **Skill library (v1).** Curated, parameterised, combinable analysis+plot recipes. Apply a skill to your data, tune parameters, chain skills into derived figures. Each skill is a versioned, reproducible unit behind a language-agnostic contract (Python / R / selom-native interchangeable).
2. **Extract-Skills (v2 beta) — the moat.** Drop a paper PDF or point at its GitHub repo; the tool reads the methods + figures, finds the code, and auto-generates a reproducible custom skill so you can recreate that figure on your own data. Sandboxed; do not build until v1 is live.

## The product surface — a project-first command center

The two features above are delivered through a **no-code multi-omics IDE**, not a
single upload box. Full design: `docs/command-center/design.md`. The shape:

- **Project folders in a left sidebar.** Each project holds datasets, an
  installed-skills workbench, and figures. The command center is where the magic
  happens — intuitive and guiding, not a blank canvas.
- **A Skill Store** — browse and install bioinformatics skills as easily as apps on
  the Mac App Store. Inventory = the ~600 skills in **bioSkills** (540 reference) +
  **ClawBio** (88 runnable). Every skill is browsable from day one; execution lights
  up progressively (**hybrid-tiered**: *Verified* runs now, *Community* is queued).
- **Guided intake.** Drop a file and Selom asks a few pre-made questions (organism,
  cell type of interest, condition/disease, expected findings). An LLM turns the
  answers + the dataset shape into a **proposed** cleaning + analysis pipeline with
  pre-filled parameters — only when the user hasn't already pre-picked skills. The
  LLM proposes; the scientist approves (navigator, not analyst).
- **Automatic ingest + cleaning.** Selom absorbs the lab-specific data at intake
  (detect modality → clean/normalize → surface statistical guardrails) so the
  user reaches standardized, field-agnostic figures fast.

**North star (owner directive):** *every one of the 500+ catalog skills eventually
runs in Selom* — by hand-porting ("building it ourselves") and/or sandboxed
execution. The **Skill Foundry** (manual now, LLM-assisted later) is the pipeline
that promotes a browsable skill into a runnable one — and it is where the v2
Extract-Skills moat generalizes (drop a paper/repo → a reproducible Selom skill).

## Scope (v1)

Broad multi-omics from day one: **scRNA-seq + bulk RNA-seq + mass-spec proteomics/phosphoproteomics**. Launch bundle is ~6-8 skills (UMAP, cluster, DEG, volcano, heatmap, enrichment) — the first **Verified** tier of a catalog designed to grow to the full ~600.

## Differentiators

- **Proteomics wedge** — first-class from v1; every scRNA-centric competitor lacks it.
- **Editable Plotly spec.** A figure is an editable JSON spec, never a baked PNG. Style edits (colour, title, font, axis) are client-side JSON-Patch operations — instant, no recompute; data edits re-run the skill. One patch protocol (RFC-6902) serves both the property panel and the LLM copilot.
- **Reproducibility bundle** on every figure: `provenance.json` + parameter hash + pinned versions + golden-image reference + auto methods-text and figure legend.
- **Statistical guardrails as a feature** — batch-effect / normalization / multiple-testing / low-cell warnings before figures are served. The research analogue of EAMOS's "no black box."
- **AI navigator, not analyst.** The AI guides the scientist to the right skill and explains tradeoffs; it does not silently make the scientific call. The user stays in control and every step is traceable.

## Model (provisional)

B2B / academic SaaS — freemium for students and researchers, per-seat for labs, compute-metered credits for GB-scale jobs, site licences for institutes/cores, a commercial tier for biotech/pharma.

## Relationship to EAMOS

Sister project and research-to-clinical funnel feeder: a candidate gene surfaced in a Selom figure can hand off to EAMOS variant interpretation. Shared spine (Supabase / Stripe / R2 / AI gateway), separate runtimes and user tables.

Full identity and entity profile live in the research vault:
`C:/Users/seamegdool/Desktop/Claude code and website tips/EAMOS Web Tool/Business/selom.md`

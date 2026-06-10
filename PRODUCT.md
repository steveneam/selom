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

## Scope (v1)

Broad multi-omics from day one: **scRNA-seq + bulk RNA-seq + mass-spec proteomics/phosphoproteomics**. Launch bundle is ~6-8 skills (UMAP, cluster, DEG, volcano, heatmap, enrichment).

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

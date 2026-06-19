# Skill Keyword Index — spec

> **Status: DRAFT for owner review (spec-before-code, session 32, 2026-06-20).** No code written
> yet. This doc scopes a deterministic keyword→skill routing layer that turns a dropped paper's
> method-nouns / chart-forms / modality signals into a per-figure **feasibility map** (the
> Dorgau-style table — produced today BY HAND), and flags out-of-scope modalities with a reason.
> The discipline matches the prior pillars (memory `selom-prism-pillar-phases`): research →
> saved spec → **owner review** → plan → build. Owner-sequenced 2026-06-20 ("do the keyword thing
> next session"; memory `selom-skill-keyword-index`). Cross-lane (backend front-half + a future FE
> surface); Codex away, Claude covering both.

## What

A layer that reads an ingested paper and **routes its content to Selom skills / tools** — or marks a
figure's modality out-of-scope — **without an LLM on the critical path**. Given the PDF text it
produces, per figure, a ranked list of `RoutingCandidate`s (`skill_id` or `out-of-scope:reason` +
score + the evidence terms) and rolls them up into a paper-level **feasibility map** identical in
shape to the one written by hand in `docs/dorgau-figrepro/scope.md`.

Three target kinds:

1. **A Selom skill** — `integration` (Melody), `trajectory`, `markers`, `deg`, `volcano`, `gsea`,
   `enrichment`, `umap_scrna`, … (the live registry).
2. **An out-of-scope modality + reason** — scATAC → `modality_unsupported:atac`; Visium / spatial →
   `modality_unsupported:spatial`; IPA / SCENIC GRN → `modality_unsupported:grn`; IHC / qPCR →
   `wet_lab`. (Maps onto the engine's existing scope constants, below.)
3. **A skill gap** — a strong method-noun that routes to *nothing* in the registry. This is itself a
   signal: it feeds the Skill Foundry backlog (D13).

**AI verifies; it is not the backbone.** The deterministic index always returns an answer offline.
An optional LLM pass only (a) adjudicates *ambiguous* routings and negations and (b) **mines missed
synonyms that are then ADDED to the vocabulary** — so the AI *improves* the deterministic layer
rather than replacing it. LLM/RAG over the full paper and OCR/vision over scanned PDFs are the
**paid tier** (open-core, like `docs/gene-set-builder-design.md`).

## Why it matters

- **Credibility.** A reproducibility tool's routing must be inspectable, offline, free, and
  repeatable — no hidden black-box input. A deterministic keyword index matches the engine's
  validate-by-metric / library-only (D12) / provenance-first ethos.
- **Proven by hand, four times.** Mapping a paper's figures to skills is *already* pure keyword
  routing: Dorgau's `Harmony→Melody`, `Monocle3/pseudotime→trajectory`, `FindMarkers→markers`,
  `Visium/scATAC/IPA→out-of-scope` was done by reading the method nouns. We have **four hand-built
  ground-truth feasibility maps** (RPGRIP1, JEV, Hani, Dorgau) to backtest against — the validation
  set already exists.
- **Compounding.** Each next ledger's feasibility map becomes near-instant instead of a manual read
  (memory `compound-capability-each-task`); the vocab strengthens every time the AI mines a synonym;
  terms that route to nothing surface skill gaps automatically.

## Context — seeds to reuse (do not duplicate)

The pieces already exist; the missing layer is the one that **inverts** them into `keyword → target`.

| Seed | What it gives | Today it maps to |
|---|---|---|
| `extract/golden.py` `_TOOLS` / `_NORMALIZATIONS` | method-noun lexicon (edgeR, DESeq2, Seurat, Harmony, Monocle, fgsea, …) | the *methods digest* — NOT a skill |
| `extract/classify.py` `_CHART_KEYWORDS` | chart-form keywords (volcano→volcano, umap→umap, heatmap→heatmap, …) | a *chart form* string |
| `extract/classify.py` `_WET_LAB_MARKERS` / `_TRANSCRIPTOMIC_MARKERS` | scope classification (guard 7) | `wet_lab` vs `transcriptomic` |
| `skills/<id>/skill.json` via `skills/registry.py` | `id`, `title`, `catalog.summary`, `chains_with`, `omics`, `omics_type` | the Skill-Store catalog |
| `papers.extract_text` (`papers.py`) | the durable PDF text layer (pypdfium2/pypdf, no AGPL) | raw page text |
| `reproduction.py` scope constants | `TRANSCRIPTOMIC` / `WET_LAB` / `DATA_NOT_DEPOSITED` / **`MODALITY_UNSUPPORTED`** | the route's out-of-scope target |

The chart-form lexicon already half-routes (`volcano`→the `volcano` skill is a near-identity). The
new work is: (1) a **method-noun → skill** synonym layer (the domain moat), (2) **registry-derived**
vocab so the index extends free per new skill, (3) a **section-weighted matcher**, and (4)
**section segmentation** of the PDF (the highest-leverage extractor upgrade, not yet built).

## Design

### Vocabulary — two layers

**Layer 1 — registry-derived (auto, free per new skill).** Walk `skills/registry.list_skill_ids()`;
for each `SkillSpec` invert its own self-description into keywords pointing back at it:
- `id` and `title` tokens (`integration`, `trajectory`, `differential expression`…),
- `catalog.summary` salient tokens (filtered through a stopword list + the method lexicon so
  "batch-correct", "pseudotime", "marker" become routing terms),
- `chains_with` (a skill that chains with `volcano` shares its DE neighbourhood),
- `omics` / `omics_type` (modality facets).

This layer means **adding a skill auto-extends the index** — the same "drop a skill dir, the Store
shows it" property the registry already has.

**Layer 2 — curated synonyms (the domain-knowledge moat).** The nouns papers *actually* use, which
the registry can't express, hand-authored in a diffable data file (`extract/routing/synonyms.json`).
Each entry: `{ terms[], target, weight, note }`. Initial seed (illustrative, not exhaustive):

```
Harmony | batch correction | batch-correct | integrate | integration | RPCA | CCA | scVI | LIGER   -> skill:integration
Monocle | Monocle3 | Slingshot | DPT | diffusion pseudotime | PAGA | pseudotime | lineage | trajectory -> skill:trajectory
FindMarkers | FindAllMarkers | cluster markers | marker genes | Wilcoxon rank-sum | Cepo            -> skill:markers   (Cepo -> skill:cepo)
DESeq2 | edgeR | limma | voom | differential expression | DEG | DGE | glmLRT                        -> skill:deg
fgsea | GSEA | gene set enrichment | prerank | ssGSEA                                               -> skill:gsea / skill:ssgsea
enrichR | over-representation | ORA | GO enrichment | pathway enrichment                            -> skill:enrichment / skill:go_graph
volcano plot                                                                                        -> skill:volcano
UMAP | t-SNE | tSNE | Leiden | Louvain | graph-based clustering                                     -> skill:umap_scrna / skill:cluster
DoubletFinder | scrublet | emptyDrops | percent.mt QC                                               -> skill:normalization_qc
--- out-of-scope ---
Signac | chromVAR | scATAC | ATAC-seq | peak calling | motif footprint | TOBIAS | CellRanger-ATAC   -> oos:atac
Visium | spatial transcriptomics | MERFISH | Slide-seq | Xenium | H&E | histology section           -> oos:spatial
IPA | Ingenuity Pathway | SCENIC | SCENIC+ | gene regulatory network | eGRN | regulon               -> oos:grn
IHC | immunostain | immunofluoresc | qPCR | RT-qPCR | western blot | TUNEL | confocal                -> oos:wet_lab
```

`oos:*` targets map to the engine scopes: `atac|spatial|grn → MODALITY_UNSUPPORTED` (data is
deposited, Selom has no skill); `wet_lab → WET_LAB`. The reason string (`atac`/`spatial`/`grn`) is
carried for the feasibility map's human-readable verdict.

### Section segmentation — the extractor upgrade (highest leverage)

Segment `papers.extract_text` output into `methods | results | legends[] | refs | body` by detecting
section headers (case-insensitive, line-anchored): *Methods / Materials and Methods / STAR Methods /
Online Methods*; *Results*; *Figure legends* / per-figure `Fig. N` caption blocks; *References /
Bibliography*. Deterministic, offline, no model. Two payoffs:

1. **Section weighting** (below) needs it.
2. **Refs must be excluded.** The References section is a minefield of tool names — "Korsunsky et
   al. *Harmony*…" in the bibliography is **not** evidence the paper used Harmony. Dropping/heavily
   down-weighting refs is the single biggest false-positive guard. (This is why segmentation, not
   just a flat keyword sweep, is required.)
3. **Per-figure association.** `Fig. N` legend blocks let routing hits attach to a *specific figure*,
   so the feasibility map is per-figure (Dorgau-shaped), not just per-paper.

Segmentation also directly improves the existing extractor: DE counts read cleaner from
results/legends, the methods digest from methods only.

### Matcher — fast, deterministic, section-weighted

- **Inverted index / automaton.** Compile the merged vocab into a multi-pattern matcher (an
  Aho-Corasick automaton, or a compiled alternation regex with word boundaries — same `\b`-anchored
  discipline as `golden._has_token`, so "RLE" doesn't fire inside "Morley"). No model.
- **Section weighting.** A hit's weight = `term.weight × section_weight`, with
  `methods (1.0) > legends (0.8) > results (0.6) > body (0.3) > refs (0.0, excluded)`. Sum per
  `(figure, target)`.
- **Negation guard.** A short left-window check ("did not use", "without", "no ~") zeroes a hit, or
  (if ambiguous) flags it for the AI-verify seam rather than silently routing.
- **Output.** Per figure: ranked `RoutingCandidate[]`; `top` + a `confidence` (margin between #1 and
  #2). Paper-level `FeasibilityMap` = one row per figure with `in_scope`, `top_skill | oos_reason`,
  and the evidence terms — the auto-generated Dorgau table.

### AI's role — verify + mine, never replace

Gated exactly like the existing `extract/classify.VisionClassifier` / Claude-as-gateway dev profile
(`selom-claude-acts-as-ai-gateway`): absent a gateway the layer degrades to the deterministic result,
never crashes.

- **Verify ambiguous routings** — when #1/#2 tie, a hit is negated/contextual, or a modality is
  unclear. The deterministic layer still returns; AI only adjusts the borderline.
- **Mine missed synonyms** — method-section terms that matched *nothing* but co-occur with a routed
  skill become candidate synonyms surfaced for review → **added to `synonyms.json`** → the
  deterministic layer gets stronger. This feedback loop is the compounding mechanism.

### Data model (Pydantic; mirrors `extract/models.py`)

```
RouteTarget   "skill:<id>" | "oos:<reason>"            # reason ∈ {atac, spatial, grn, wet_lab, ...}
VocabEntry  { terms[], normalized[], target, kind: registry|curated, weight, note }
SectionedText { methods, results, legends[]: {figure, text}, refs, body }
RoutingHit  { term, target, section, weight, figure? }
RoutingCandidate { target, score, evidence[]: RoutingHit }
FigureRoute { figure, candidates[], top: RouteTarget?, in_scope, confidence }
FeasibilityMap { paper_id, figures[]: FigureRoute, unmatched_terms[] (skill-gap signal), generated_at }
```

### Module layout

```
app/backend/extract/routing/
  vocab.py        build the vocabulary (registry-derive + load curated synonyms)
  synonyms.json   the curated synonym layer (diffable data file)
  segment.py      section segmentation (methods/results/legends/refs/body) — the extractor upgrade
  index.py        the compiled matcher + section weighting + negation guard
  route.py        SectionedText -> FigureRoute[] -> FeasibilityMap; the gated AI-verify seam
```

Reuses `skills/registry.py` (vocab), `extract/golden._TOOLS` + `extract/classify._CHART_KEYWORDS`
(seed terms — promote, don't re-list), `papers.extract_text` (text). Wires into
`extract/golden.build_extracted_spec` so each `PanelDraft` / engine `Panel` gains a **suggested
`skill_id`** (today `to_engine_panels` emits chart-form only — the index fills the gap that
`build_ledger()` hand-encodes).

### Endpoint

`POST /papers/route` (or `GET /papers/{slug}/feasibility`) → `FeasibilityMap`, mirroring `main.py`
style. Internal/dogfood-first per the engine's D12 posture; FE surface deferred (pairs with the
paper-metadata intake wiring).

### Free / paid line (open-core)

- **Free / open (deterministic core):** registry-derived vocab + curated synonyms + the matcher +
  section segmentation + the feasibility map. Fully offline, inspectable, repeatable.
- **Paid / premium:** LLM verification of ambiguous routings, LLM synonym mining, and OCR/vision over
  scanned/image-only PDFs and equations-as-images (the gap hit in the Harmony2 scope). Same
  open-core split as `selom-gene-set-builder`.

## Validation (validate-by-metric)

The killer test already exists: **backtest the index against the four hand-built ledgers.**

1. **Routing accuracy** — for each of RPGRIP1 / JEV / Hani / Dorgau, the index's per-figure
   `top` target must reproduce the hand-written feasibility map (skill id or out-of-scope reason).
   Metric = precision/recall vs the hand map; Dorgau's table (in `docs/dorgau-figrepro/scope.md`) is
   the literal golden. Target: ≥ the hand mapping on the in-scope figures, with every spatial/scATAC/
   IPA/wet-lab figure correctly flagged out-of-scope.
2. **Refs-exclusion guard** — a tool named *only* in References does NOT route (synthetic + real:
   Harmony appears in every retina paper's bibliography).
3. **Negation guard** — "we did not use Monocle" does not route to `trajectory`.
4. **Segmentation** — methods/results/legends/refs correctly delimited on the four real PDFs
   (spot-checked offsets).
5. **Registry extensibility** — adding a fixture skill dir makes its id auto-routable with no synonym
   edit.

No network, no heavy deps for the unit/backtest suite (the PDFs/text are local fixtures).

## Decisions (proposed — for owner confirmation)

- **K1 — Deterministic core, AI as verifier/miner only.** No model on the critical path; LLM verify +
  synonym mining are additive and gated (degrade-clean like the vision classifier). *(Owner steer,
  memory `selom-skill-keyword-index`.)*
- **K2 — Two-layer vocab: registry-derived (auto) + curated synonyms (the moat).** Adding a skill
  extends the index free; the synonym file is the only hand-maintained surface.
- **K3 — Section segmentation is in-scope and required** (not deferred) — it is what makes section
  weighting and refs-exclusion possible, and it improves the existing golden/methods extraction.
- **K4 — References excluded; methods > legends > results > body weighting.** The load-bearing
  false-positive guard.
- **K5 — Out-of-scope routing maps onto the engine's existing scope constants** (`MODALITY_UNSUPPORTED`
  for atac/spatial/grn, `WET_LAB` for staining/qPCR) — no new scope vocabulary.
- **K6 — Validate by backtest against the four ledgers** before any FE surface. Library-only (D12).
- **K7 — Open-core free/paid line** = deterministic core free; LLM verify + OCR/vision premium.

## Resolved (owner, 2026-06-20)

1. **Routing granularity = per-figure** ✓ — one route per figure (legend segmentation associates hits
   to `Fig. N`); matches the Dorgau table shape.
2. **v1 surface = feasibility-map read-only first** ✓ — build the router + map, backtest against the
   four ledgers, do NOT touch `reproduction.py` yet. Auto-populating `Panel.skill_id` is a fast-follow
   *after* the backtest passes.
3. **Unmatched terms = surface only** ✓ — list `unmatched_terms[]` on the map; auto-filing to the
   Skill Foundry backlog (D13) is deferred until the negation/refs guards are tuned.
4. **Name = "Skill Keyword Index"** ✓ — keep the functional name (module `extract/routing/`).
5. **Curated synonym storage = `extract/routing/synonyms.json`** (defaulted to the recommended diffable
   data file; not separately asked — flip to a Python module on request).

## Out of scope (this spec)

- The LLM/RAG full-paper reading path and OCR/vision (the paid tier — separate spec when prioritised).
- A new FE Reproduction/feasibility view (pairs with the paper-metadata intake wiring; deferred).
- Auto-*generating* a skill from an unmatched term (Skill Foundry's job; this layer only *reports* the gap).

---

## Built + validated (session 32, 2026-06-20)

v1 shipped exactly to the resolved decisions — `app/backend/extract/routing/` (`vocab.py` +
`synonyms.json`, `segment.py`, `index.py`, `route.py`, `models.py`) + `POST /papers/route`.
Deterministic, library-only, no new deps. `feat(backend)` commit `9834f09`.

**Validated by backtest against all four hand-built ledgers** (`tests/test_routing.py`): the router
reproduces each ledger's per-figure in-scope skills + out-of-scope modality verdicts —
- **Dorgau**: Fig 1 → {umap_scrna, trajectory, markers} in-scope; Fig 2 spatial / 4 atac / 6 grn /
  7 wet_lab out-of-scope; Harmony → `skill:integration` (the Melody dogfood signal).
- **Hani**: Fig 1 composition · 2 {corr_heatmap, boxplot} · 3 {violin, cepo} · 4 regression · 6 umap.
- **JEV**: Fig 3 volcano · Fig 4 pca · paper-level {deg, gsea, pca}.
- **RPGRIP1**: paper-level {deg, gsea, pca} + annotate + wet_lab.

Plus guard tests: word-boundary (PCA ∉ PVCA), longest-match (ssGSEA ≠ GSEA), negation ("did not
use Monocle" → no route), **references-exclusion** (Harmony in the bibliography only → no route),
registry-extensibility, curated-target validation, and the endpoint.

**Live dogfood on the real JEV PDF text** (`D:/selom-data/_jev_text.txt`, 105k chars): recovers the
JEV ledger skill set (deg/pca/trajectory/markers/composition/enrichment/umap/gsea/volcano) + flags
`oos:wet_lab` (immunohistochemistry), **zero false skill-gaps**. `MATERIALS AND METHODS` / `Results`
headers segmented correctly.

**Honest limitation surfaced (the next iteration):** paper-level routing is reliable on real PDFs;
**per-figure routing degrades to results-attribution when the PDF has no detectable "Figure legends"
section** (the JEV dump had none → a mixed figure can mis-top to wet_lab). Section/legend
segmentation hardening on legend-less real PDFs is the highest-leverage follow-up (already flagged as
K3's deeper form). Fast-follows, in order: (1) legend-segmentation hardening; (2) wire the suggested
`skill_id` into `to_engine_panels`/`build_ledger` (the engine front-half); (3) the gated AI-verify +
synonym-mining seam; (4) the FE feasibility surface.

pytest **BE 509** (495 + 14); ruff clean.

**Fast-follow #1 (engine wiring) SHIPPED — session 34.** Both legend-segmentation hardening (s33,
the 4-layer core) and the engine wiring are now done. The router's L3 inventory + per-figure routes
feed the reproduction engine via `extract/routing/engine.route_to_panels` / `build_auto_ledger` +
`extract/golden.to_engine_panels(feasibility=)` — a dropped paper auto-produces the figure→skill
ledger skeleton the four ledgers hand-encode. See `docs/skill-keyword-index/engine-wiring-scope.md`.
Remaining: (3) the L4 AI-verify + synonym-mining seam; (4) the FE feasibility surface.

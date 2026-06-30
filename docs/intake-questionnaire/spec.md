# Intake Questionnaire — dynamic, layered, AI-prefilled — design spec

_2026-06-30 22:05 +10:00 (Australia/Sydney). **Design-first** (owner-decided 2026-06-30, Q4). The coupled
deliverable of the ingest stage (Layer A Phase 2, `docs/ai-cross-stage-entry-points/spec.md`): the data-
intake surface becomes a **dynamic, layered questionnaire** the engine pre-fills and the AI optionally
sharpens. Activates the on-hold rethink ([[selom-intake-questionnaire-rethink]]). Built from the SpatialGE
end-to-end review (2026-06-30) — used as a **negative template**. Build NOT started; §9 lists open calls._

## 1. Problem

The current "Tell Selom about your data" intake pane is **static + modality-mismatched** (FE reality-map):
the same fixed questions regardless of what was dropped or what analysis is intended. It neither captures
the design (control/treatment, n conditions, replicates) the analysis needs, nor adapts its questions to
the data. The owner wants it **dynamic and layered**, AI-assist-to-fill, and explicitly **not overwhelming
like SpatialGE**.

## 2. The SpatialGE lesson (negative template)

SpatialGE's *irreducible inputs are sound*, but its UX overwhelms for four fixable reasons (review,
2026-06-30):

1. **No-op defaults** — every `filter_data()` threshold defaults to `0`/`NULL`; the user must supply every
   cutoff → a blank wall, not a confirmable start.
2. **Min/max twins** — almost every metric ships a min *and* a max knob → the panel is mechanically doubled
   for max-cutoffs nobody sets.
3. **Front-loaded jargon** — `spot_minpct`, `^MT-`, SCTransform, kriging, Moran's I, all at once, no plain
   language, no "why we ask."
4. **Asks what it could detect** — platform pick (Visium/CosMx) and an exact-name sample↔metadata join the
   tool could infer.

**Selom inverts all four.** What SpatialGE does *right* and we keep: typed-input-first (the type constrains
everything downstream, GraphPad-style), a live summary, a commit point before running, and a reproducibility
param log.

## 3. The five irreducible inputs (what any analysis actually needs)

1. **The data file(s)** — already dropped.
2. **What the data IS** — modality/assay + orientation (raw counts vs normalized vs already-a-DE-table). *Auto-detectable (engine 1d).*
3. **The design** — which column is the group/condition; how many conditions; control/reference; replicate structure (n/condition); batch (optional).
4. **The analysis intent** — which figure/skill (often already chosen via a skill tile / route-AI).
5. **Analysis-specific params** — normalization + thresholds. *Almost all have sensible defaults → hidden behind "Advanced".*

## 4. The two-layer model

### Layer 1 — structure (which sections to even show) — ≤3 questions

Chosen by `(modality × analysis)`. The payoff is **one confirm-the-detection card** (Datawrapper step-2),
not a blank form. Everything deterministically inferable is shown as a **filled answer to confirm**, never
a blank to fill.

- **Always — 2 confirm-chips, engine-prefilled:**
  - *"This looks like ___"* → detected modality + orientation ("bulk RNA-seq DE results" / "raw scRNA
    counts, 6 samples"). One click to correct.
  - *"You want to make ___"* → analysis/skill (pre-selected when entered via a skill tile or route-AI).
- **Only if the analysis needs a design** (DE/volcano, ERG, grouped spatial, group-faceted correlation):
  - *"Which column is the group/condition?"* → dropdown **pre-selected** with the engine's best guess.
  - *"How many conditions?"* → detected count (the **trigger into Layer 2**).
  - *"Which is the control/reference?"* → dropdown, pre-selected by keyword heuristic.
- **If unsupervised** (clustering/UMAP): **no design questions** — at most one optional *"color points
  by?"*.

### Layer 2 — per-condition expansion (details)

When Layer 1 detects *N* conditions, render *N* labelled boxes, each **engine-prefilled**, with
**add / remove / rename**. Fields are analysis-typed (the matrix, §6).

## 5. The deterministic / AI split (mirrors [[layered-deterministic-extraction]] + the S5 ✨ layer)

- **L1–L3 deterministic (PRIMARY, AI-off-safe).** On file inspect (the engine already has this — `engine/
  route.py::route_data`, `engine/qc.py`, modality detection 1d, `data_check`): infer modality + orientation;
  detect candidate group columns (low-cardinality categoricals); guess control via keyword
  (`control|ctrl|wt|vehicle|dmso|untreated|baseline|0h`); count distinct levels; count replicates/level.
  **This fully populates Layer 1 + Layer 2 with no AI.** Every field has a deterministic default or guess.
- **L4 AI (OPTIONAL, gated — the ingest `<AskAi>` Phase 2 work).** Only *refines* what the deterministic
  layer left ambiguous: map messy free-text sample names → conditions; propose a control when the keyword
  heuristic misses; suggest the analysis. Surfaced as **✨-marked suggestions** the user accepts/overrides
  (the shipped S5 attribution convention). AI off → the user just sees deterministic prefills and edits.
- **Anchor the promise to L3:** the questionnaire is *complete and correct with AI off*; AI is the click-
  reducer, never a dependency. (The exact engine pattern — L3 robust recall is the promise, L4 is the
  upsell.)

## 6. The dispatch matrix — "what each analysis needs to know" (the form's backbone)

Legend: **E** = essential (block/warn if missing) · **O** = optional (good default) · **–** = not asked.
**Build rule:** an **E** cell in the chosen analysis's row → a **Layer-1 question**; its per-item detail →
the **Layer-2 boxes**; every **O** / Advanced param is *applied silently with its default*, revealed only
under an "Advanced" fold.

| Analysis | Groups / condition col | Replicates | Control / reference | Normalization | Key params (default, hidden in Advanced) |
|---|---|---|---|---|---|
| **DE / volcano** | **E** group col + ≥2 levels | **E** warn if n=1/group | **E** which level is reference | **O** TMM/log default | log2FC=1, padj=0.05, test (Wilcoxon/t) |
| **Clustering / UMAP** | – (unsupervised); **O** color-by | – | – | **E** raw→normalize+log | n_neighbors=15, min_dist, resolution, HVGs=3000 |
| **Enrichment / GSEA** | inherited from DE (ranked list) or a gene set | – | inherited | – (uses the stat) | gene-set DB (GO/KEGG/Hallmark/Reactome), min/max set size, perms |
| **Correlation** | **O** group/facet | – | – | **O** | method (Pearson/Spearman), variable pair/matrix |
| **Spatial QC/transform** | **O** sample metadata vars | per-sample | – | **E** log vs SCTransform | spot-min(500), gene-min(100 / 20 spots), mito%(20) — all defaulted |
| **ERG** | **E** genotype/condition | per-eye/animal | **E** control genotype | – (physiological) | a/b-wave landmark times (auto-measured), flash intensities |

## 7. The seven anti-overwhelming rules (SpatialGE failure → Selom rule)

1. **Typed input picks the questions** (GraphPad) — `modality × analysis` decides which sections exist; a
   bulk-RNA volcano user must **never** see spot-mito sliders. The single biggest lever.
2. **Ship real defaults, pre-applied** — the opposite of SpatialGE's 0/NULL floor. log2FC=1, padj=0.05,
   HVGs=3000, n_neighbors=15, norm=log: applied, shown as "using defaults", editable.
3. **Collapse min/max pairs** — one threshold with a default; the max-cutoff + the second half of every pair
   live in Advanced.
4. **Progressive disclosure within a stage** — Layer 1 ≤3 questions; Layer 2 expands on trigger; expert
   knobs behind one "Advanced" fold.
5. **Plain language + "why we ask"** — "Drop low-quality cells (high mitochondrial %)", not `spot_minpct /
   ^MT-`; the number hides in Advanced.
6. **One confirmation card before running** (Datawrapper step-2) — *"Detected: bulk RNA-seq · 6 samples · 2
   conditions (PDE6B vs Control) · 3 reps each — correct?"* That card **is** the questionnaire's payoff.
7. **Auto-join, don't hand-match** — infer the sample↔metadata join; never SpatialGE's exact-name
   requirement.

## 8. Where this plugs in

- **Reads:** the engine's existing inspect output — `engine/route.py::route_data`, `engine/qc.py`,
  modality detection (1d), surfaced FE-side via `data_check` / `POST /data/inspect` (the workbench already
  consumes `data_check`). The deterministic L1–L3 prefill = this output reshaped into the questionnaire.
- **Writes:** confirmed answers → the run params (group column → `_column_override` / design; control →
  reference level; thresholds → skill params) — **staged** into the shared pending queue, one re-run via
  the provenance chokepoint (the ingest Phase-2 contract).
- **The AI layer** = the ingest `<AskAi stage="ingest">` (Layer A Phase 2) — the L4 refiner.
- **Relationship to the design-sheet upload:** for bulk/time-course DE the design sheet already exists; the
  questionnaire should *read it as the prefill source* when present (auto-join), and only ask when absent.

## 9. Open decisions (owner)

1. **Where does the questionnaire live in the flow?** Stay on the Data stage (intake), or move to a
   confirm-card that gates the first run? *Recommend: on the Data stage, with the §7.6 confirm-card as the
   "ready to run" payoff.*
2. **Modality × analysis coverage for v1** — start with the rows we dogfood most (DE/volcano, clustering/
   UMAP, ERG), defer correlation/spatial/enrichment Layer-2 detail? *Recommend: yes, the 3 dogfood rows first.*
3. **"Advanced" fold granularity** — one fold per section, or one global Advanced? *Recommend: per-section.*
4. **How much does the engine already detect** vs needs new detection (replicate counting, control keyword
   guess)? An audit of `route_data`/`qc.py` outputs precedes the build.
5. **Sequencing** — this is Layer A's *last* phase (most entangled). Build the questionnaire's deterministic
   skeleton first (AI off), then layer the ingest `<AskAi>` L4 prefill on top.

## 10. Invariants

- Deterministic path primary — the questionnaire is complete + correct with the gateway off (L3 promise).
- Typed-input-first — questions are a function of `(modality × analysis)`, never a fixed wall.
- Every defaultable knob is pre-applied + hidden; nothing blocks on an expert param.
- AI prefills are ✨-attributed and user-overridable; confirmed answers stage through the one provenance
  chokepoint like any ingest write.

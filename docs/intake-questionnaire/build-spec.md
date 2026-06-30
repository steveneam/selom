# Intake Questionnaire — BUILD spec (deterministic skeleton)

_2026-07-01 01:50 +10:00 (Australia/Sydney). The buildable companion to the design spec
(`docs/intake-questionnaire/spec.md`, which carries the rationale, the SpatialGE negative template, the
dispatch matrix, and the two-layer model). This doc resolves that spec's §9 open decisions, pins the
contract, and slices the work. It is **Layer A Phase 2 (ingest)** of the FE Experience Spine
(`docs/fe-experience-spine/README.md`) — but the **AI refiner (L4) is explicitly deferred**; this build is
the **deterministic skeleton only** (the §5 "anchor the promise to L3" half)._

> **Review status:** forcing-questions answered 2026-07-01 (owner). **PAUSE for owner review before any
> code.** `review-gauntlet` + `fe-review` are deferred to next session by owner directive — so this slice
> ships UN-reviewed by those two gates, and that debt is recorded in `CURRENT.md` ▸ LIVE.

## 1. Decisions locked (forcing-Qs 2026-07-01 + the engine audit)

| # | Decision | Choice |
|---|---|---|
| Scope | How far this session | **Full deterministic skeleton (FE+BE)** — confirm-card + Layer-2 design boxes + the new BE `suggest_design_hints` + a new `/data/inspect` field. **AI ingest `<AskAi>` L4 = next session.** |
| Flow | Where it lives | **In place on the Data stage** — the §7.6 "ready to run" confirm card is the payoff at the bottom of the intake pane; no extra gating screen. |
| Free-text | Fate of tissue/cell-type/organism/goal | **Demote to an optional "Add context for the AI (optional)" fold** beneath the structured confirm-card; it still feeds `/ai/propose`. |
| Fit verdict | data-aware-routing followups #1/#2 | **Include now** — reuse `components/reproduction/DataFitVerdict` on the intake surface + a confidence band on the dataset cards. |
| Coverage (§9.2) | modality × analysis for v1 | **Design layer for `deg` bulk + `deg` pseudobulk** (the EYG28 + RPGRIP1 dogfood rows). Unsupervised (clustering/UMAP) and volcano-on-an-existing-DE-table → **no design layer** (just the two confirm chips). **ERG + time-course = fast-follow** (own detection paths; not v1). |
| Advanced fold (§9.3) | granularity | **Per-section** — analysis thresholds (log2FC, padj, top_n, normalization) live under a per-section "Advanced" fold, pre-applied with defaults. |

### The audit finding that shapes the split

- **STRUCTURE layer = already returned by `/data/inspect`** (no new detection): modality+orientation
  confidence (`profile.code/confidence/reason/candidates`), intended analysis (`routing.steps`), `columns`,
  `n_numeric_cols`, per-skill `data_fit`. The FE already persists `routing` + `dataFit` on the `Dataset`
  ([[DATA-AWARE-ROUTING]] `689d3bf`).
- **DESIGN layer = NOT detected today** (the new BE work): candidate group/condition columns, distinct
  level counts, the control/reference keyword guess, replicate-per-level counts.
- **The write path = already exists** (the decisive finding — NO new apply-machinery). The `deg` runner
  (`skills/deg/run_real.py`) already consumes the design as plain params:
  `reference` + `treatment` (logFC = treatment vs reference), `group_col` (design-sheet column),
  `group_regex` (replicate-suffix strip; default `_\d+$`), `condition_col` + `sample_col` (pseudobulk),
  optional `label_col`/`label`. Auto-defaults reference/treatment when exactly 2 groups exist. So the
  questionnaire's confirmed answers map **directly** onto run params the engine already reads + records in
  provenance → "AI compiles away" is automatic (deterministic re-run reproduces).

## 2. The contract — new `engine/questionnaire.py::suggest_design_hints` + a new inspect field

### 2a. Models (`engine/questionnaire.py`, pydantic — mirrors the engine's existing model style)

```python
class LevelHint(BaseModel):
    name: str               # the condition level, e.g. "Control" / "PDE6B"
    n_replicates: int       # samples (bulk cols / pseudobulk samples) at this level

class GroupCandidate(BaseModel):
    key: str                # the design source: an obs/design-sheet column name, OR
                            # the sentinel "__column_names__" for bulk inferred-from-headers
    label: str              # human label ("genotype", "sample columns", …)
    levels: list[LevelHint]
    n_levels: int
    reference_guess: str | None   # control keyword guess among `levels` (None if no match)

class DesignHints(BaseModel):
    needs_design: bool      # the routed/likely analysis consumes a design (deg-from-counts / pseudobulk)
    source: str             # "column_names" | "obs" | "design_sheet" | "none"
    modality: str           # echoes bundle.kind for the FE
    group_candidates: list[GroupCandidate]
    best_group: str | None  # key of the best candidate (pre-selects the group dropdown)
    note: str               # plain-language one-liner ("inferred 2 conditions from sample columns")
```

### 2b. Detection — modality-aware, REUSING `deg`'s own label logic (so detection == what the run does)

- **`bulk_counts`** (genes × samples; first column = gene id): condition labels from the **sample column
  names** with the trailing replicate suffix stripped — reuse `deg.run_real.DEFAULT_REP_REGEX` +
  `_labels_from_design_or_names`'s rule (`ctrl_1`/`treat_2` → `ctrl`/`treat`). Skip the gene-id column
  (the first, or the `data_fit.columns[0]`). One `GroupCandidate(key="__column_names__")`; `levels` =
  distinct prefixes; `n_replicates` = count of columns per prefix; `reference_guess` = first level matching
  `_CONTROL_RE`. `needs_design=True` when ≥2 levels detected.
- **`sc_counts`** (AnnData): scan `obs` for candidate condition columns — the `deg._CONDITION_FALLBACKS`
  aliases first, then any low-cardinality (`2 ≤ nunique ≤ 12`) non-numeric column; and sample columns
  (`deg._SAMPLE_FALLBACKS`). One `GroupCandidate` per condition candidate (`key`=obs col, `levels`=value
  counts → `n_replicates` = **distinct sample ids** per level when a sample column exists, else cell count
  with a note). `reference_guess` via `_CONTROL_RE`. `best_group` = the first fallback-alias hit, else the
  lowest-cardinality candidate. `needs_design=True`.
- **`de_results`** (already-computed DE table) / **`proteomics`** / **`metabolomics`** / **`generic_table`**
  / **`unknown`**: `needs_design=False`, `group_candidates=[]`, `source="none"` — the confirm-card shows
  only the two structure chips (no design questions). *(volcano/enrichment read a ready DE/ranked table —
  there is no design to capture.)*
- **Design sheet present** (`_design_path`, when one is already attached to the run/dataset): read it via
  the shared `skills._design.load_design` and prefer its columns as `source="design_sheet"` candidates
  (auto-join, never hand-match — §7.7).

`_CONTROL_RE` (new, shared): `re.compile(r"(?i)\b(control|ctrl|wt|wild.?type|vehicle|dmso|untreated|baseline|mock|sham|0h|day0|d0)\b")`.

**Fail-soft (E4, like `_inspect_for_run`):** any error in `suggest_design_hints` returns
`DesignHints(needs_design=False, source="none", …)` — it never breaks `/data/inspect`.

### 2c. Wire into `/data/inspect` (`routers/data.py`)

Add a top-level `design: DesignHints | None` field to the inspect response (sibling to `data_fit`/`routing`),
populated by `suggest_design_hints(bundle, routing=…, design_path=None)`. **Additive — no existing field
changes.** This is a contract change → backend-led; I hold both lanes (Codex away), so I make it and keep
the BE drop-in-ready (verify vs CURRENT.md).

## 3. FE — the layered confirm-card, in place on the Data stage

Restructure `components/intake/intake-questionnaire.tsx` (today a static `Record<string,string>` form) into
the layered confirm-card. `data-panel.tsx` keeps the vertical stack
(`DataTypeStrip → CleaningReport → IntakeQuestionnaire`); the questionnaire becomes dynamic.

- **Layer 1 — always (two confirm chips, engine-prefilled):**
  1. *"This looks like ___"* — modality + orientation. **Reuse `DataTypeStrip`'s existing detection**
     (`profile` + confidence chip + override); do not duplicate it. The questionnaire references the
     confirmed type, it doesn't re-ask it.
  2. *"You want to make ___"* — analysis/skill. Pre-selected from the route (`routing` best step / the
     skill the user entered via a tile or the route-AI chip).
- **Layer 1 — only when `design.needs_design`:**
  - *"Which column is the group/condition?"* — dropdown over `group_candidates`, pre-selected `best_group`.
  - *"Which is the control/reference?"* — dropdown over the chosen candidate's `levels`, pre-selected
    `reference_guess`.
  - *"How many conditions?"* — the detected `n_levels` (the trigger into Layer 2).
- **Layer 2 — per-condition boxes** (when `needs_design` and a group is chosen): N labelled boxes, each
  prefilled `{name, n_replicates}`, with **rename / remove** (and an **add** to introduce a level the
  detector missed). A `n_replicates < 2` box shows an inline "DE needs ≥2 replicates" warning (matches the
  runner's own guard, `deg.run_real` `min(n_ref,n_treat) < 2`).
- **The "ready to run" confirm card (§7.6) — the payoff:** *"Detected: bulk RNA-seq · 2 conditions (PDE6B
  vs Control) · 3 reps each — correct?"* with the **Run** button. For `needs_design=False` it degrades to
  *"Detected: bulk RNA-seq DE results · ready to plot"* + Run.
- **Free-text → optional fold:** the existing tissue/cell-type/organism/research-goal questions move into a
  collapsed `<details>` "Add context for the AI (optional)". Still collected as `IntakeAnswers` and still
  passed to `/ai/propose` (unchanged wire).
- **Per-section Advanced fold:** thresholds (log2FC=1, padj=0.05, top_n=10, normalization) under a
  per-section "Advanced", pre-applied with defaults, editable.

### 3a. Persistence (mirror `routing`/`dataFit` — [[selom-reconcile-preserves-client-only-fields]])

`Dataset` gains `design?: DesignHints | null` (client-only, no backend column) + a `designChoice?` (the
user's confirmed `{group_key, reference, levels[], ...}`). Thread `design` through `inspect.ts`
(`InspectResponse`/`InspectResult`); persist on inspect; **preserve across a server-wins reconcile via the
existing `mergeDatasets`** (extend it to carry `design`/`designChoice` like `routing`/`dataFit`). Survives
reload, no re-inspect — same invariant Slice 2 established.

### 3b. The write path — confirmed answers → run params (NO new machinery)

On **Run** from the confirm-card, the confirmed design is added to the run params for a design-consuming
skill:
- **bulk `deg`** (`source="column_names"`): set `reference` + `treatment` (the two chosen levels);
  `group_regex` only if the user corrected the replicate pattern. (No `group_col` — labels come from
  headers, as the runner already does.)
- **scRNA pseudobulk `deg`** (`source="obs"`): set `mode="pseudobulk"`, `condition_col`=group key,
  `sample_col`=the detected sample column, `reference` + `treatment`; optional `label_col`/`label`.
- **design sheet** (`source="design_sheet"`): set `group_col` + `reference`/`treatment`; the sheet already
  threads via `_design_path`.

These are params the runner already reads and `provenance.build` already records (`routers/_run.py`) → a
gateway-off re-run reproduces (invariant 2). **Apply-discipline:** for the deterministic skeleton the
confirm-card's Run **is** the explicit commit (one deliberate run carrying the confirmed params); the
shared staged pending-queue is the **AI** ingest-phase contract (next session), not needed here.

### 3c. Fit-verdict surfacing (followups #1/#2 — reuse, don't build new)

- **Intake:** render `DataFitVerdict` (or the lean `DataFitPanel` for own-data) from the persisted
  `dataFit` on the intake surface (it exists, wired only into paper-reproduction today).
- **Dataset cards:** add a `ConfidenceChip` band from `dataFit.confidence`/`quality` to the cards in
  `data-panel.tsx` (the shared `BAND_TONE`/`CONFIDENCE_META` vocabulary).

## 4. Slices (build order THIS session)

1. **BE — `suggest_design_hints` + models + inspect wiring + tests.** `engine/questionnaire.py`; wire into
   `routers/data.py`; unit tests on the dogfood shapes (a 2-condition bulk counts header set → 2 levels +
   replicate counts + control guess; an AnnData obs with a `condition` column → candidate + levels; a
   de_results table → `needs_design=False`). Fast gate + ruff.
2. **FE — the layered confirm-card** (thread `design` → persist → `mergeDatasets`; the Layer-1/Layer-2 UI
   in place; demote free-text; map confirmed answers → run params). tsc + vitest + eslint.
3. **FE — fit-verdict surfacing** (followups #1/#2; reuse `DataFitVerdict` + dataset-card band).

**Deferred (next session):** the ingest `<AskAi stage="ingest">` L4 refiner (messy free-text sample names →
conditions; propose a control the keyword heuristic missed; ✨-attributed) · **`review-gauntlet` +
`fe-review` over this whole slice** · ERG + time-course design detection · followups #3 ("not a fit" trace)
+ #4 (route-composer transparency).

## 5. Verification (real data + live backend, NOT dev:mock — [[verify-on-real-data-not-mock]])

Live uvicorn on a non-:8000 port (e.g. :8010), gateway OFF, real dogfood data:
- **EYG28 bulk counts** (`D:\selom-data\eyg28`, PDE6B+RPGRIP1 vs Control) → inspect returns `design` with
  the inferred conditions + replicate counts + a `Control` reference guess → the confirm-card prefills →
  Run `deg` (bulk) with `reference=Control`, `treatment=PDE6B` → the contrast bar renders; `provenance`
  records the params; a reload re-attaches `design` via `mergeDatasets` (no re-inspect).
- **An RPGRIP1 / scRNA h5ad** with an obs condition column → `source="obs"` candidate; pseudobulk run
  carries `condition_col`/`sample_col`/`reference`/`treatment`.
- **A de_results CSV** (a ready DE table) → `needs_design=False`; the confirm-card shows only the two
  structure chips + Run → volcano renders (no design questions). The honest "no design to capture" case.
- Console clean; the free-text fold still posts to `/ai/propose`.

## 6. Invariants (the seven spine invariants — all hold)

- **Render = f(spec)** — the run is unchanged; the questionnaire only sets params.
- **AI compiles away** — N/A this slice (no AI); the deterministic confirmed params re-run reproduce.
- **One provenance chokepoint** — the deterministic run records params via the normal run path
  (`provenance.build`); the AI chokepoint (`stamp_ai_actions`) is for the deferred L4 phase only — no
  parallel path introduced.
- **Apply-discipline by consequence** — ingest = STAGED→one explicit run; here the confirm-card Run is that
  single deliberate commit.
- **Deterministic path primary** — the questionnaire is complete + correct with the gateway off (the L3
  promise); AI is the deferred click-reducer.
- **One pending queue** — untouched (the AI staged-queue integration is the next phase).
- **Inference-first** — the design detection is from `(modality × analysis)`, never a fixed wall.

## 7. Open calls for the reviewer (owner)

1. **`DesignHints` placement** — top-level inspect field `design` (proposed) vs nesting under `data_fit`.
   *Recommend top-level: design is a dataset-structure fact, not a per-skill fit.*
2. **scRNA replicate counting** — count **distinct sample ids per condition** (correct biological-replicate
   semantics; needs a sample column) vs raw cell counts. *Recommend distinct-sample-ids, with a note when
   no sample column is found.*
3. **Bulk "group column" sentinel** — modeling header-inferred groups as a pseudo-candidate
   `key="__column_names__"` (proposed) vs a separate `inferred_from: "headers"` flag. *Recommend the
   sentinel — keeps one `GroupCandidate` shape for the FE dropdown.*
4. **ERG in v1?** — owner deferred ERG to fast-follow (different ingest path, `ingest_many`). Confirm ERG
   genotype/condition design is **out** of this slice. *Recommend out.*

## Reading order

This build-spec → the design spec (`docs/intake-questionnaire/spec.md`, rationale + dispatch matrix) → the
Layer-A spec (`docs/ai-cross-stage-entry-points/spec.md`, the apply-discipline contract) → the spine README
(`docs/fe-experience-spine/README.md`). Memory anchors: [[selom-ai-helpers]] ·
[[selom-data-fit-scorer]] · [[selom-reconcile-preserves-client-only-fields]] ·
[[verify-on-real-data-not-mock]] · [[layered-deterministic-extraction]].

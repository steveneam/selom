# P1 Ingest Engine Hooks — column-override + cleaning-step-toggle

_Spec · 2026-06-29 · **refreshed 2026-06-30** (forcing-Qs answered + the engine re-modeled
against the real code) · status: **in build** (NEXT#1, "build-the-gaps")._

> **Refresh note (2026-06-30).** The original spec was written from the S3 *AI-side*
> investigation and located both hooks in `databundle.py` / `compat.py`. Reading the run path
> showed that is **not** where the effect lives:
> - **Column-picking is per-skill** — each runner has its own `_pick(cols, candidates)` over its own
>   synonym lists (`volcano/run_real.py`, `gsea/run_real.py`, …). The classifier only returns a
>   *Kind*; it never resolves a named column for the figure. So to flip the **figure**, the override
>   must reach the runner **and** survive the D1 (`compat`) + D2 (`frame_schema`) gates — else a
>   mis-named DE table is blocked with `missing_columns` *before* the runner ever sees it.
> - **Cleaning is applied internally by each skill** — `plan_cleaning` only *describes* steps; the
>   skill cleans itself. `_run.py` passes `plan.steps` to `lineage.materialize_bundle` as a *record*,
>   not an execution pipeline. There is **no plan→execution path** to toggle. But the `normalize`
>   step already maps 1:1 to a declared **`normalize` skill param** (`deg`/`umap_scrna` read
>   `params.get("normalize", True)`); `filter_genes(min_cells=3)` is hard-coded with no param.
>
> **Two forcing-Qs answered (owner, 2026-06-30):**
> 1. **Cleaning toggle → param-backed.** `apply_cleaning_step` flips the *controlling skill param*
>    where one exists (`normalize` step → `normalize=false`), reusing the proven `set_param` recompute
>    path so the figure genuinely changes + is recorded; a step with no backing param returns an
>    honest gap. No per-skill cleaning rewrite.
> 2. **Column-override → volcano proving ground.** A shared `engine.columns` resolver (override wins
>    over synonyms) consulted at D1 + D2 + the **volcano** runner so the figure flips end-to-end;
>    `enrichment`/`gsea`/`deg` adopt the same resolver later (≈one line each).
>
> **Side-decisions (stated, not vetoed):** roles = **logFC / pval / gene** (disjoint from
> `set_design`, which already stages condition/batch); reproducibility = record `_column_override` as
> a recorded param (`resolved_params` allowlist) so a re-run re-applies it with **zero AI** — the
> cleaning toggle needs no special recording because it compiles to a real param (`normalize`).

## What

Two small P1 (ingest) **engine** capabilities that AI-Helpers S3 surfaced as honest
`CapabilityGap`s: a **user column-override** ("treat column X as role Y") and a **cleaning-step
toggle** (enable/skip a proposed `CleaningStep`). Building them flips the existing `map_columns` /
`apply_cleaning_step` AI actions from "return a gap" to "return a wired effect" — completing the
dynamic-intake revival. This is **engine work (P1 spine)**, distinct from the AI-helper epics; the AI
side is already skeletoned (S3), so the build is a fill-in-the-blanks change there.

## Context

S3's engine-surface investigation found the engine has **no user override** for either:
- `engine/databundle.py` — `_LOGFC`/`_PVAL` are read-only synonym **auto-detection** sets; no API to
  say "use column X as logFC".
- `engine/cleaning.py::plan_cleaning` — proposes a list of `CleaningStep` verbatim; no enable/skip
  parameter, and `CleaningStep` has no `enabled` field.

So `map_columns` → `gap(missing_column_op)` and `apply_cleaning_step` → `gap` (recorded in the
CapabilityGap backlog — the gap-loop surfaced them). These complete the parked dynamic-intake
([[selom-intake-questionnaire-rethink]]): let the user (via an AI suggestion or by hand) correct a
mis-detected column or skip an inappropriate cleaning step before analysis. Per the integrity
boundary, gaps are *surfaced for review, built by deliberate decision* — this spec is that decision's
scope; the owner sequences when (proposed: after S5).

## Requirements

1. **Column-override** — an ingest-time `{role: column_name}` map (roles = the engine's detected
   groups: logFC, pval, gene, condition, batch). Resolution uses the override over synonym
   auto-detection. **Honest: override-only** — it may only point at an *existing* column; it never
   fabricates or synthesizes one.
2. **Cleaning-step toggle** — `CleaningStep` gains `enabled: bool = True` (preferred) or
   `plan_cleaning` accepts a skip/include set; the run applies only enabled steps; the applied/skipped
   set is recorded.
3. **Reproducibility** — both overrides are recorded in the run's `provenance.params` (reserved keys,
   like `_design_path`), so a re-run from the record reproduces the figure with **zero AI in the loop**
   — the "AI compiles away" invariant extended to ingest overrides.
4. **The AI-action flip** — once the hooks exist, `ai/registry.py::_validate_map_columns` /
   `_validate_apply_cleaning_step` stop returning gaps and return the wired effect (validate the
   override against `ctx.data_columns` / the plan, stage `{_column_override: …}` / `{_cleaning_skip: …}`).
   No new action types — both are already in the closed registry (S3). The backlog item then resolves
   (the gap stops recurring), which the gap-loop reflects.
5. **Fail-soft + honest** — an override at a missing column → a clear 4xx (not a crash); a no-op
   override → an honest no-op.

## Design

### Column-override (`map_columns` flip)
- **`engine/columns.py` (new)** — the single role→column resolution source. `ROLE_SYNONYMS =
  {logFC: _LOGFC, pval: _PVAL, gene: GENE}` (reusing `databundle._LOGFC`/`_PVAL`),
  `OVERRIDABLE_ROLES = {logFC, pval, gene}`, and `override_column(override, role, df_columns)` —
  returns the user-mapped column **only when it exists** in the frame (override-only, never
  fabricate), else `None`. `role_of_synonyms(syns)` reverse-maps a synonym group → role (identity on
  the shared tuples) so the gates can ask "is this group satisfied by an override?".
- **The gates consult the resolver** (so a mis-named DE table survives to the runner):
  - `compat._check_schema(skill_id, fa, override)` — a required group is *present* if the override
    maps its role to an existing column **or** a synonym matches. `compat.fit(…, column_override=…)`
    threads it; all other callers default `None` (unchanged).
  - `frame_schema.check_skill_input(skill_id, payload, override)` — the resolved column for a role is
    the override column when set (else the synonym match), then the same usability checks run on it.
  - `databundle.classify(payload, *, override=None)` gains the param (DE-detection honours an
    override) for engine completeness + unit tests; **not** threaded through `ingest` in this slice —
    volcano isn't gated on exact Kind once its columns resolve, so the displayed profile stays
    auto-detected (honest: "we saw a generic table, but you mapped these columns").
- **The volcano runner reads it** — `volcano/run_real.py` resolves `fc/p/gene` as
  `engine.columns.override_column(ov, role, df.columns) or _pick(cols, …)`; `ov =
  params["_column_override"]`. The figure is drawn from the overridden column.
- **`routers/_run.py::_execute_skill_run`** — `column_override = params.get("_column_override")`
  (tolerates a JSON string); a **runtime guard** rejects any override pointing at a missing column
  with a clear 400 (skipped under `override=true`, like the other gates); threads it into
  `compat.fit(column_override=…)` + `frame_schema.check_skill_input(override=…)`. It stays in
  `params`, so the runner reads it and provenance records it.
- **Reproducibility** — `resolved_params` allowlists `_column_override` (kept while `_design_path`
  is still stripped) → it lands in `provenance.params` → a re-run posts it back → the figure
  reproduces with **zero AI** ("AI compiles away" extended to ingest overrides).

### Cleaning-step toggle (`apply_cleaning_step` flip — param-backed)
- **`engine/cleaning.py`** — `CleaningStep` gains `enabled: bool = True` + `param: str = ""` (the
  skill param that toggles this step, `""` = no backing param / hard-coded). `STEP_PARAM =
  {"normalize": "normalize"}` is the single source; the **single-cell** normalize step (`_sc_plan`)
  carries `param="normalize"` so the plan self-describes which steps are togglable. The bulk DESeq2
  size-factor step is **not** param-backed (pyDESeq2 fits size factors internally; the `normalize`
  param controls only the scRNA log-norm path), so it stays an honest gap. A guard test
  (`test_step_param_coupling_guard`) ties every `STEP_PARAM` entry to a real plan step + a declared
  skill param, so the convention can't drift silently.
- **AI flip** (`ai/registry.py`): `_validate_apply_cleaning_step` reads `{step_id, enabled}`; if the
  step is param-backed (`STEP_PARAM`) **and** the active skill declares that param, it validates
  `{param: enabled}` via the existing `validate_param_ranges` (no parallel path) and stages it; a
  non-param-backed step, no active skill, or a skill without that param → an honest
  `gap(validation_blocked)`. `_apply_apply_cleaning_step` returns `{"params": {param: enabled}}` — a
  real skill param, so it's validated + recorded + reproduced by the existing machinery (no
  `_cleaning_skip` reserved key needed).

### Column-override (`map_columns`) AI flip
- `_validate_map_columns` reads the `{role: column}` map (the payload itself); rejects unknown roles
  (malformed, no gap); when `ctx.data_columns` is provided, a column not in the data →
  `gap(validation_blocked)` (mirrors `set_design`); else ok. `_apply_map_columns` stages
  `{"params": {"_column_override": map}}`.

## Decisions

- **Override roles** — **logFC / pval / gene** only (the DE-figure column roles). **Disjoint from
  `set_design`**, which already stages condition/batch/control/treatment — two actions must not own
  the same effect. Not arbitrary column math / derived columns. Reversible.
- **Cleaning toggle = param-backed** (forcing-Q answered) — `apply_cleaning_step` compiles to the
  controlling skill param (`normalize` step → `normalize=false`) via the proven `set_param` path; a
  step with no backing param returns an honest gap. `CleaningStep.enabled`/`param` are added so the
  plan self-describes, but the *effect* is a real param, not a plan-execution skip.
- **Column-override breadth = volcano proving ground** (forcing-Q answered) — wired end-to-end
  through volcano via a shared `engine.columns` resolver the other DE-table skills adopt later.
- **Reproducibility** — the cleaning toggle needs no special recording (it is a real param);
  `_column_override` is allowlisted in `resolved_params` so it lands in `provenance.params`. Both
  ship behind the same run gates (QC/D1/D2) and reproduce with zero AI.

## Invariants

- Override-only, never fabricate (honest classification).
- Recorded in provenance → reproducible ("AI compiles away" extends to ingest overrides).
- Fail-soft (missing column → clear error, never a crash).
- The AI flip reuses the existing action skeleton — **no new action types**.

## Testing Strategy

- **Resolver** (`engine/columns.py`): override wins over a synonym; a missing override column →
  `None` (never fabricated); no override → synonym match.
- **Gates honour the override**: a DE table with a non-standard FC column (`FoldChange_custom`) is
  `missing_columns`-gated by `compat.fit` *without* the override, and **fits** *with*
  `column_override={logFC: "FoldChange_custom", …}`; `frame_schema` resolves + usability-checks the
  overridden column.
- **Volcano reads it**: the runner draws the figure from the overridden columns; a re-run from the
  recorded `provenance.params["_column_override"]` reproduces the figure with no AI.
- **`_execute_skill_run`**: the override threads end-to-end; an override at a missing column → a clean
  400 (`column_override_missing`), overridable via `override=true`.
- **Provenance**: `_column_override` appears in `provenance.params`; `_design_path` is still stripped.
- **AI flip** (rewrite the S3 gap tests): `_validate_map_columns` stages `{_column_override: map}`
  (status `staged`); a column ∉ `data_columns` → `validation_blocked` (status `rejected`); an unknown
  role → rejected (no gap). `_validate_apply_cleaning_step` for the `normalize` step on `deg`/
  `umap_scrna` stages `{normalize: false}` (status `staged`); a non-param-backed step (e.g.
  `filter_genes`) → `validation_blocked` (honest gap). The closed-registry structure guard stays
  green; the backlog gaps stop recurring.

## Out of Scope

- Not built now — deferred to **after AI-Helpers S5** (owner-sequenced).
- The FE control to set an override / toggle a step is S5/FE.
- Arbitrary column transforms / derived columns (only role-overrides on existing columns).

## Open questions — RESOLVED (2026-06-30)

1. ~~Which roles?~~ → **logFC / pval / gene** (disjoint from `set_design`).
2. ~~`enabled` field vs `plan_cleaning(skip=…)`?~~ → neither drives the effect: the toggle is
   **param-backed** (compiles to `normalize`). `CleaningStep.enabled`/`param` added for the plan to
   self-describe.
3. ~~Reproducibility record shape?~~ → `_column_override` recorded via the `resolved_params`
   allowlist (lands in `provenance.params`); the cleaning toggle is a real param already recorded.

# P1 Ingest Engine Hooks — column-override + cleaning-step-toggle

_Spec · 2026-06-29 · status: **scoped, deferred** (build after AI-Helpers S5) · owner-sequenced._

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

- **Column-override** lives in the ingest/classify path: `engine/databundle.py` (the classifier
  accepts an override map that wins over synonym detection) + `engine/compat.py` (column-resolution
  reads the override). Threaded from the run via a `_column_override` reserved param through
  `routers/_run.py::_execute_skill_run` → ingest (mirrors `_design_path`).
- **Cleaning-step toggle** — `engine/models.py` / `engine/cleaning.py`: `CleaningStep.enabled` +
  `plan_cleaning`/the apply path honour it; threaded via a `_cleaning_skip` reserved param.
- **AI flip** (`ai/registry.py`): `_validate_map_columns` → validate each `{role: column}` (role is a
  known group; column ∈ `ctx.data_columns`) → stage `{_column_override: map}`; `_validate_apply_cleaning_step`
  → validate the step id exists in the plan → stage `{_cleaning_skip: […]}`. Delete the gap returns.

## Decisions

- **Override granularity** — only the engine's existing detected roles (logFC/pval/gene/condition/
  batch); not arbitrary column math or derived columns. Reversible.
- **`CleaningStep.enabled` vs a skip-list param** — prefer the declared `enabled` field (keeps the
  plan self-describing for the FE/AI to toggle) over a separate skip param. `Assumption:` revisit at build.
- Overrides ship behind the same run gates (QC/D1/D2) and are recorded → reproducible.

## Invariants

- Override-only, never fabricate (honest classification).
- Recorded in provenance → reproducible ("AI compiles away" extends to ingest overrides).
- Fail-soft (missing column → clear error, never a crash).
- The AI flip reuses the existing action skeleton — **no new action types**.

## Testing Strategy

- Column-override flips a mis-detected column (force a non-standard "FC" column → logFC); the skill
  reads it; a re-run from the recorded override reproduces the figure.
- Cleaning-toggle skips a step → the result reflects the skip; the skip is recorded.
- The AI flip: `_validate_map_columns` / `_validate_apply_cleaning_step` no longer gap — they stage
  the override; the gauntlet + structure guards stay green; the corresponding backlog gap stops recurring.
- Honest errors: override → missing column → 4xx; no-op → no-op.

## Out of Scope

- Not built now — deferred to **after AI-Helpers S5** (owner-sequenced).
- The FE control to set an override / toggle a step is S5/FE.
- Arbitrary column transforms / derived columns (only role-overrides on existing columns).

## Open questions

1. Exactly which roles are user-overridable (start: logFC/pval/gene/condition/batch)?
2. `CleaningStep.enabled` field vs a `plan_cleaning(skip=…)` param — confirm at build.
3. Reproducibility record shape — `provenance.params` reserved keys (`_column_override` /
   `_cleaning_skip`) vs a dedicated provenance block.

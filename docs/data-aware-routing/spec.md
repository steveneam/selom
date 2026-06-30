# Data-aware routing (Slice 2) — spec

> Status: **draft, awaiting owner approval** · 2026-07-01 · Claude (covers FE + BE while Codex is away).
> Cross-lane: touches `app/backend` (the `/ai/propose` contract + `/data/inspect` summary) **and**
> `app/frontend`. Backend-led contract change — kept drop-in-ready for Codex.

## What

Make Selom's routing **data-aware** and its data-driven recommendations **persistent**.

Two coupled changes:

1. **Backend** — `POST /ai/propose` stops flying blind. Today it hardcodes `data_fit=None`
   (`routers/ai.py:108-115`), so the route-stage `select_skill` action can never reach its compat
   gate and the AI can recommend a skill the data cannot feed. `ProposeRequest` gains
   `data_columns` + `data_kind` (+ `data_n_numeric_cols`); `propose()` populates `ActionContext`
   from them so the **already-built** `_validate_select_skill` compat check
   (`ai/registry.py:526-591`) goes live. The fit *verdict* is still computed server-side
   (`engine.compat.fit`) — the client supplies only a column list + kind, never a verdict.

2. **Frontend** — "Recommended for your data" stops being ephemeral. Today the chips read an
   in-session mock proposal (`proposeForModality` → `recommendedSkills`), which vanishes on reload.
   They will read the **real `/data/inspect` route result** (`routing` + `data_fit`), persisted on
   the dataset in the client-authoritative project store, so they show on every load of an
   inspected dataset. Demo/sample datasets (no inspected file) keep modality-based **mock** chips
   (owner note). The route composer (`<AskAi stage="route">`) sends the same persisted data context
   so its AI suggestion is also data-aware.

## Context

### The engine already computes the data-aware route — the FE just doesn't keep it

`POST /data/inspect` (`routers/data.py:11-60`) already returns, for a real dropped file:

- `routing` — the suggested skill pipeline + honest note (`route_profile(bundle, prof.code)`); and
- `data_fit` — `{quality, confidence, fits[]}`, where each `fits[]` entry is a `DataFit`
  (`engine/compat.py:283`) scoring one routed skill against the **actual** data (modality class →
  named columns → coarse modality), best-first.

So the deterministic, data-aware recommendation is **already produced**. The gaps are only that
(a) the FE inspect wrapper throws `data_fit` away (`lib/intake/inspect.ts:96` returns
`{kind, profile, plan, qc, routing}` — no `dataFit`), (b) the chips are sourced from the FE mock
`proposeForModality` instead of that result, and (c) the result isn't persisted on the dataset.

### `/ai/propose` is the one routing path still data-blind

`propose()` builds `ActionContext(..., data_fit=None)` unconditionally. `_validate_select_skill`
already knows how to use `ctx.data_fit` + `ctx.data_columns` — it reconstructs a `FileAssessment`
and calls `compat.fit(target_skill, fa)`, emitting an honest `no_fitting_skill` gap on a certain
mismatch (`ai/registry.py:562-589`). That whole branch is dead today because `data_fit` is always
`None` (fail-soft skip). Populating it is the entire backend behavior change.

### Relevant code

| Concern | Location |
|---|---|
| `ProposeRequest` + `propose()` (hardcodes `data_fit=None`) | `app/backend/routers/ai.py:82-117` |
| `ActionContext` (already has `data_fit`, `data_columns`) | `app/backend/ai/models.py:75-92` |
| `_validate_select_skill` compat gate (already built) | `app/backend/ai/registry.py:526-591` |
| Data-fit scorer (the reused engine) | `app/backend/engine/compat.py` (`fit`, `FileAssessment`, `assess_bundle`) |
| `/data/inspect` (returns `routing` + `data_fit`) | `app/backend/routers/data.py:11-60` |
| FE inspect wrapper (drops `data_fit`) | `app/frontend/lib/intake/inspect.ts:61-100` |
| Chips (`recommendedSkills(proposal)`) | `app/frontend/lib/catalog/quick-apply.ts` |
| Chips consumer | `app/frontend/components/project/workbench-panel.tsx:97-118` |
| Ephemeral proposal state | `app/frontend/components/project/project-workspace.tsx:124,452-457,1075` |
| Slug-normalize precedent (`selom.<slug>`) | `app/frontend/components/project/project-workspace.tsx:468-476` |
| Route composer (`mode="select"`, sends no data) | `app/frontend/components/ai/ask-ai.tsx:122-158` |
| Propose wrapper / `ProposeRequest` (FE) | `app/frontend/lib/ai/api.ts:21-48` |
| Inspect + AI mocks | `app/frontend/mocks/handlers.ts:104,165` |

### Prior lessons this must honor

- **Slug keying** — backend routing steps are **bare** slugs (`volcano`); the FE catalog is keyed
  `selom.<slug>`. `ad453fe` shipped a guaranteed silent no-op from exactly this mismatch that 406
  green tests missed. Any FE resolution of backend slugs must normalize the same way
  `pickSuggestedSkill` does. [[selom-skill-keyword-index]]
- **Mock mirrors the contract** — change a wire shape → update its MSW handler in the same move;
  the mock proves the wire only. [[mock-must-mirror-backend-contract]] [[selom-mock-is-wire-only-verify-real]]
- **Verify on real data** — the chips' data-fit content and the compat gate are *content*, not
  wire; verify on `npx next dev --webpack` + a live uvicorn (non-`:8000`) + a real file, not
  dev:mock alone. [[verify-on-real-data-not-mock]]

## Requirements

### Backend

- R1. `ProposeRequest` accepts optional `data_columns: list[str] | None`, `data_kind: str | None`,
  and `data_n_numeric_cols: int | None`, all defaulting to `None`. Existing callers that omit them
  are byte-unaffected (the analyze composer sends none → `data_fit` stays `None`).
- R2. `propose()` populates `ActionContext.data_fit` and `.data_columns` from the request **only
  when** data context is present (any of the three new fields set). `data_fit` is a dict carrying at
  least `{"kind": data_kind or "unknown", "n_numeric_cols": data_n_numeric_cols or 0}` plus a
  permissive `score`/`qc_ok` default; the actual compat *verdict* is computed inside
  `_validate_select_skill`, never accepted from the client.
- R3. The route-stage `select_skill` compat gate becomes live: when the gateway proposes switching
  to a skill the data certainly cannot feed (`DataFit.gated`), the turn records a `no_fitting_skill`
  gap and the action is not staged — exactly the existing behavior, now reachable.
- R4. The `gsea` numeric sub-check is **not** falsely tripped. `_validate_select_skill` must build
  its `FileAssessment` with the real numeric-column count (`data_n_numeric_cols`) instead of the
  current hardcoded `n_numeric_cols=0`. When the count is unknown (`None`), the numeric
  sub-requirement is treated as satisfied (don't manufacture a "missing numeric score" gate from
  missing information).
- R5. `POST /data/inspect`'s `data_fit` summary additionally exposes `columns: list[str]` and
  `n_numeric_cols: int` (both already on the `FileAssessment` it builds at `routers/data.py:39`).
  These are the source of `data_columns` / `data_n_numeric_cols` for the FE.

### Frontend

- R6. The FE inspect wrapper (`InspectResult`) carries the full `data_fit` summary
  (`{quality, confidence, columns, n_numeric_cols, fits[]}`) — no longer dropped.
- R7. The dataset record (FE store) gains `routing` + `dataFit`, captured when `/data/inspect`
  runs and persisted with the project (client-authoritative, same store as QC). They survive reload.
- R8. "Recommended for your data" reads from the persisted dataset, **not** the ephemeral proposal:
  - inspected dataset with a real `routing`/`dataFit` → chips are the data-fit-ranked **verified**
    skills, backend slugs normalized to `selom.<slug>`, skills whose fit is a *certain mismatch*
    (`compatible === false`) dropped, de-duplicated, capped at 4;
  - dataset without a real route result (demo/sample) → fall back to modality-based **mock** chips
    (`proposeForModality(dataset.modality, {})`) so demo data still shows recommendations;
  - neither available → the row is hidden (unchanged: no popularity fallback).
- R9. The route composer (`<AskAi stage="route" mode="select">`) sends `data_columns` + `data_kind`
  + `data_n_numeric_cols` from the active dataset's persisted inspect result, so the AI suggestion
  is scored against the real data. When the dataset has no inspect result, it sends none (degrades
  to today's data-blind-but-functional behavior).
- R10. The inspect and `/ai/propose` MSW handlers mirror the new fields (R5, R1) so dev:mock and
  vitest exercise the real wire shape.

## Design

### Backend

**`routers/ai.py` — `ProposeRequest` + `propose()`**

```python
class ProposeRequest(BaseModel):
    stage: str = "analyze"
    skill_id: str | None = None
    params: dict = {}
    goal: str = ""
    figure_spec: dict | None = None
    capability_surface: dict | None = None
    # Slice 2 — data-aware routing. The server derives the fit VERDICT (engine.compat.fit);
    # the client supplies only the column list + kind (data description, not a verdict).
    data_columns: list[str] | None = None
    data_kind: str | None = None
    data_n_numeric_cols: int | None = None


@router.post("/ai/propose")
def propose(req: ProposeRequest):
    data_fit = None
    if req.data_columns is not None or req.data_kind is not None or req.data_n_numeric_cols is not None:
        data_fit = {
            "kind": req.data_kind or "unknown",
            "n_numeric_cols": req.data_n_numeric_cols,   # None ⇒ unknown (R4)
            "score": 80,        # permissive default; the verdict comes from compat.fit, not this
            "qc_ok": True,
        }
    ctx = ActionContext(
        stage=req.stage, skill_id=req.skill_id, params=req.params,
        figure_spec=req.figure_spec, capability_surface=req.capability_surface,
        data_fit=data_fit, data_columns=req.data_columns,
    )
    turn = run_helper_turn(ctx, req.goal, get_action_gateway())
    return turn.model_dump()
```

Replace the stale `ProposeRequest` docstring (it currently claims `data_fit` is "intentionally
absent" and that Slice 2 is future work — Slice 2 is now).

**`ai/registry.py` — `_validate_select_skill` numeric count (R4)**

The `FileAssessment` reconstruction currently hardcodes `n_numeric_cols=0`
(`ai/registry.py:576`). Source it from `ctx.data_fit`:

```python
n_numeric = ctx.data_fit.get("n_numeric_cols")
fa = FileAssessment(
    ...,
    columns=ctx.data_columns or [],
    # Real count when known; len(columns) when unknown so the gsea numeric sub-check (≥1 numeric
    # col) is satisfied rather than falsely tripped from missing info (don't gate on what we
    # didn't measure). _check_schema is shared with the D1 run gate — do NOT weaken it; fix the
    # caller's assessment instead.
    n_numeric_cols=n_numeric if n_numeric is not None else len(ctx.data_columns or []),
)
```

> `len(columns)` as the unknown-fallback is an over-count, but it can only ever *satisfy* the
> `≥1 numeric` floor, never invent a false miss — the honest direction. The named-column groups
> (fold-change / significance / gene) are matched by name and are unaffected.

**`routers/data.py` — inspect `data_fit` summary (R5)**

```python
data_fit = {
    "quality": fa.quality,
    "confidence": fits[0].confidence if fits else ("uncertain" if fa.loadable else "unreadable"),
    "columns": fa.columns,             # NEW — source of data_columns for the FE
    "n_numeric_cols": fa.n_numeric_cols,  # NEW — source of data_n_numeric_cols
    "fits": [f.model_dump() for f in fits],
}
```

### Frontend

**Types (`lib/intake/inspect.ts` + a shared `DataFit` type)**

Add a `DataFitSummary` (`{quality, confidence, columns, n_numeric_cols, fits: DataFit[]}`) and a
`DataFit` type mirroring `engine/compat.py:DataFit` (`skill_id, score, compatible, verdict,
confidence, reason`). Reuse the existing `DataRouting` from `@/lib/skills/api`. Thread `dataFit`
through `InspectResponse` → `InspectResult` (stop dropping it at line 96). Keep modules in their
feature dirs — no flat `lib/*-api.ts`, no barrels (structure guard).

**Dataset record (`lib/projects/types.ts`)**

Add `routing?: DataRouting | null` and `dataFit?: DataFitSummary | null` to the `Dataset` type.
Captured in the inspect handler (`data-panel.tsx`, beside the existing `qcFromInspect` write) and
persisted by the existing project store — so reload re-hydrates them.

**Chips (`lib/catalog/quick-apply.ts`)**

```ts
// route result present → data-fit-ranked verified skills (backend slugs normalized);
// else → modality mock fallback; pure, unit-tested.
export function recommendedSkills(
  route: { routing: DataRouting | null; dataFit: DataFitSummary | null } | null,
  modality: Modality | null,          // for the demo/sample mock fallback
): CatalogSkill[] {
  const fromData = route ? recommendedFromRoute(route) : [];
  if (fromData.length) return fromData;
  return modality ? recommendedFromProposal(proposeForModality(modality, {})) : [];
}
```

`recommendedFromRoute` walks `routing.steps` (the recommended pipeline order), normalizes each
bare slug to `selom.<slug>`, resolves via `getSkill`, keeps `tier === "verified"`, drops any whose
`dataFit.fits` entry has `compatible === false` (a certain mismatch), de-dupes by id, caps at 4.
The slug normalize must match `pickSuggestedSkill` exactly (the `ad453fe` lesson).

**Chips consumer (`workbench-panel.tsx`) + wiring (`project-workspace.tsx`)**

`workbench-panel` takes the active dataset's `routing`/`dataFit`/`modality` (read from the
persisted dataset, available on every load) instead of relying on the in-session `proposal`. The
`ProposalPlan` full-plan panel may keep using the intake proposal `p`; only the **chips** move to
the persisted source.

**Route composer (`ask-ai.tsx` + `lib/ai/api.ts`)**

`AiContext` gains `dataColumns?`, `dataKind?`, `dataNumericCols?`; the `mode === "select"` branch
forwards them into `proposeActions`. `ProposeRequest` (FE) + the body in `proposeActions` gain
`data_columns` / `data_kind` / `data_n_numeric_cols`. The workbench passes the active dataset's
`dataFit.columns` / `kind` / `dataFit.n_numeric_cols`.

### Data flow (after)

```
drop file → POST /data/inspect ──► { kind, routing, data_fit{columns,n_numeric_cols,fits} }
                                      │
              persist on Dataset ◄────┘  (FE store, survives reload)
                    │
   ┌────────────────┼─────────────────────────────┐
   ▼                                               ▼
recommendedSkills(route, modality)        <AskAi stage="route">  ── POST /ai/propose
   → data-fit chips (real) | mock (demo)        { data_columns, data_kind, data_n_numeric_cols }
                                                     │
                                          _validate_select_skill → compat.fit(verdict server-side)
```

## Decisions

- **D1 — Client sends columns + kind; server derives the verdict.** (Owner-chosen.) Alternatives:
  `dataset_id` re-derive (strongest honesty, **blocked** on deferred 7c upload wiring) and passing
  the precomputed `data_fit` blob (weaker honesty, limited to pre-scored skills). Columns+kind
  works today, mirrors the existing `_validate_select_skill` path, and keeps the verdict
  server-computed. Reversible: a later slice can switch to `dataset_id` without changing the FE
  chip logic. The honesty boundary is preserved — the client describes the data, the server judges
  fit.
- **D2 — Persist on the dataset in the FE store (read on load).** (Owner-chosen.) Alternatives: a
  backend `route_data` column + Alembic migration (durable/cross-device, heavier, needs the dataset
  server-stored) and recompute-on-load (always fresh, needs the file server-side each load). The FE
  store is already client-authoritative and persists QC the same way; this is the smallest change
  that makes the chips survive reload. Reversible: the dataset field can later be hydrated from a
  backend column.
- **D3 — Real route result for inspected data; mock fallback for demo/sample.** (Owner note: "demo
  should also have mock chips.") The chips prefer the real `/data/inspect` result and fall back to
  `proposeForModality(modality, {})` only when there is no real result. This keeps demo datasets
  populated without reintroducing a popularity list, and retires the *ephemeral* mock-proposal
  state as the chip source (it becomes a modality-derived fallback computed from the persisted
  dataset). Reversible.
- **D4 — Thread the real `n_numeric_cols` (fix the latent gsea false-gate).** The hardcoded
  `n_numeric_cols=0` in `_validate_select_skill` is dormant only because `data_fit` is always
  `None` today; populating `data_fit` (R2) makes it live and would falsely gate `gsea`. Sourcing
  the real count (with a satisfy-on-unknown fallback) is required for R3/R4 to be honest, not a
  drive-by. Reversible.
- **Assumption:** the active dataset whose context the route composer/chips use is the one the
  workbench already tracks (`datasetId` in `project-workspace`). No new selection state.
- **Assumption:** exposing the user's own column names back to their own FE (R5) is not a privacy
  concern (own-data product surface).

## Invariants

- **Honesty rule (load-bearing).** `data_fit` is never trusted from the client as a verdict; the
  server computes it via `engine.compat.fit`. The request carries only data *description* (columns,
  kind, numeric count). Check: a request asserting `compatible:true` for a wrong-modality file is
  still gated. (`engine/compat.py` docstring; mirrors `provenance.stamp_ai_actions` server-control.)
- **Zero-regression default.** Gateway off → `/ai/propose` still returns an empty plan; a request
  with no data context behaves exactly as today (`data_fit=None`). The analyze composer is
  untouched. Check: existing `routers/test_ai*.py` stay green unchanged.
- **AI compiles away.** This slice adds no AI to the recommendation floor — the chips are the
  deterministic `engine.compat`/`route_profile` result and work gateway-off. The gateway only
  sharpens the *route composer's* NL suggestion.
- **Slug keying.** Every FE resolution of a backend slug normalizes to `selom.<slug>` before
  `getSkill`. Check: a unit test resolving a bare `volcano` step yields the catalog skill, not
  undefined (the `ad453fe` regression guard, extended to the chips).
- **Structure guards stay green** — `lib/structure.guard.test.ts`, the SSR-plotly import test, the
  backend `test_structure_guard` (no flat modules, routes in `routers/`).

## Error behavior

- Inspect fails / file uninspectable → `inspectData` already returns `null` (fail-soft); the
  dataset gets no `routing`/`dataFit`; chips fall back to the modality mock (D3). No throw.
- `/ai/propose` with malformed/absent data context → `data_fit=None`, compat check skipped
  (fail-soft, unchanged). The compat block in `_validate_select_skill` already swallows its own
  exceptions (`ai/registry.py:588-589`).
- A backend slug in `routing.steps` that doesn't resolve in the catalog → dropped from the chips
  (not rendered as a broken chip), same as today's `recommendedSkills`.
- Gateway off and no proposal and no modality → row hidden (unchanged).

## Testing strategy

- **BE unit (`pytest -m "not slow"`, the uv-3.12 PY + `PYTHONPATH` per CURRENT ▸ ENV):**
  - `propose()` with `data_columns`/`data_kind` populates `ctx.data_fit` (assert via a stub gateway
    that echoes the context, or assert the `select_skill` gate fires).
  - a `select_skill` proposal for a wrong-modality file → `no_fitting_skill` gap recorded, action
    not staged (R3); a fitting file → staged.
  - `gsea` with a numeric column present is **not** gated (R4); the unknown-count fallback satisfies
    the numeric floor.
  - `propose()` with no data context → `data_fit=None`, behavior identical to today (regression).
  - `/data/inspect` `data_fit` now carries `columns` + `n_numeric_cols` (R5).
- **FE unit (vitest):**
  - `recommendedSkills` — real route result → data-fit-ranked verified skills with slugs
    normalized; a `compatible:false` fit dropped; demo (no route, modality only) → mock chips;
    nothing → `[]`. Extend `quick-apply.test.ts` against the real seed.
  - `inspect.ts` maps `data_fit` through (not dropped).
  - MSW parity: inspect + `/ai/propose` handlers carry the new fields (R10).
- **Integration / browser ([[verify-on-real-data-not-mock]]):** `npx next dev --webpack` + live
  uvicorn on a non-`:8000` port (gateway off is fine for the chips):
  - drop a real bulk-counts CSV → intake → chips show data-fit-ranked DEG/Volcano/Enrichment;
    **reload the page → chips persist** (the headline win).
  - a demo/sample dataset → modality mock chips show.
  - with `SELOM_AI_GATEWAY=operator` (free) or `=gateway` (live Llama): the route composer proposes
    a skill, and a goal that names a non-fitting skill surfaces the honest "no fitting skill" note.
- **Review:** `review-gauntlet` (correctness/invariants) + `fe-review` (V·R·D·A·R·N) on the FE diff,
  both by `scriptPath`.

## Out of scope

- The `dataset_id` re-derive path and any 7c upload wiring (deferred; D1 is reversible toward it).
- A backend `route_data` column / migration (D2 chose the FE store).
- Auto-generating an intake proposal for demo datasets that never went through the questionnaire —
  the mock fallback (D3) is computed on the fly from `dataset.modality`; seeding richer demo
  proposals is a separate enhancement.
- The analyze / ingest / grade / methods AI composers (Layer A remaining phases — NEXT#2).
- Any change to how `_execute_skill_run` / `/ai/apply` runs or stamps provenance.
```

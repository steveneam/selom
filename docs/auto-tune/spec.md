# Auto-tune button (Layer A — AI Assist) — spec

> Status: **draft, awaiting owner approval** · 2026-07-01 · Claude lane (covers FE + BE while Codex is away).
> Cross-lane: adds one small `app/backend` engine module + endpoint (analyze) and `app/frontend` wiring;
> route/ingest/methods reuse already-shipped backend surfaces. Kept drop-in-ready for Codex.
>
> Forcing-questions resolved this session (owner): **(1) source = the deterministic engine** (works with the
> gateway off, ✨-free, human-attributed); **(2) presentation = per-stage default** (each stage's `<AskAi>`
> gets a one-click button beside its typed-goal chat); **(3) analyze depth = static defaults + a small,
> curated set of rule-based data-scalings** (not a full per-knob recommender).

## What

A one-click **"Auto-tune"** affordance at each engine-spine stage that fills in the **best-practice
defaults** for that stage — the "one-click default" half of the spine's "one surface (the one-click default
*flows into* chat)" model. It is **deterministic**: it reuses the engine's already-shipped recommendation
substrate (the routed skill, the design prefill, the skill param defaults, the methods ledger draft) plus one
new deterministic param recommender for the analyze stage. It works with the AI gateway **off** (the shipped
default), carries **no ✨ marker**, and is **human-attributed** — the user clicks it, reviews the resulting
diff, and confirms. The AI path (a typed goal: "tune for my data" / "fix what's off") stays the separate
`<AskAi>` chat, unchanged. The Auto-tune button never returns a black box: it returns a reviewable
OLD→NEW-plus-why diff a human could have typed, staged through the one pending queue and committed through the
one provenance chokepoint.

## Context

### Where this sits

This is **Layer A** (AI Assist) of the FE Experience Spine (`docs/fe-experience-spine/README.md`), governed by
the apply-discipline contract in `docs/ai-cross-stage-entry-points/spec.md`. That spec already declares a
per-stage **"default affordance"** column (route = suggested-skill chips · ingest = one-click auto-detect ·
analyze = goal box + chat · grade = conversational · methods = one-click ledger draft). The Auto-tune button
**unifies and completes** that column: it makes the one-click default a first-class, uniform affordance at
every stage — most importantly **analyze**, which today has *only* the typed-goal chat and no one-click path.

The owner's product framing (the three-option model): **option 1 = best-practice defaults → this button**;
**options 2/3 = data-tuned / fix-what's-off → the typed-goal AI chat** (`<AskAi>`, gateway-gated, ✨). This
spec builds option 1 only; it does not change the chat path.

### What already exists (the deterministic substrate — most of the button is reuse)

`POST /data/inspect` (`app/backend/routers/data.py:11-71`) already returns, for a real dropped file, three
deterministic, AI-free recommendation layers that the FE persists on the dataset (`routing`, `dataFit`,
`design`; data-aware-routing Slice 2 + INTAKE-DESIGN):

| Stage | What the button produces | Deterministic source | Shipped? |
|---|---|---|---|
| **route** | pre-select the top data-fit skill | `dataFit.fits[0]` (best-first `engine.compat.fit`) / `routing.steps` (`engine.route.route_profile`) | ✅ persisted on the dataset |
| **ingest** | prefill the design questionnaire (group/reference/sample/levels) | `design` (`engine.questionnaire.suggest_design_hints`) on `/data/inspect` | ✅ shipped (INTAKE-DESIGN `99bd6e4`) |
| **analyze** | recommended params (skill defaults + curated data-scalings) | **NEW** `engine.recommend.recommend_params` | ⬜ this spec |
| **grade** | advisory card: recommended test/correction given the design | `design` + the skill's method (advisory, never applied) | ⬜ this spec (thin) |
| **methods** | a draft methods/legend paragraph | `companions.methods.build_body` via `POST /methods/compose` (`routers/litsynth.py:19`) | ✅ shipped (lit-synthesizer) |

So **four of five stages are wiring over shipped engine output**; the single new backend deliverable is the
analyze param recommender. Skill defaults themselves are already exposed deterministically via
`skills.contract.defaults(spec)` / `resolved_params(spec, params)` (`app/backend/skills/contract.py:139-208`).

### The FE machinery this rides (do not fork it)

- `<AskAi>` (`app/frontend/components/ai/ask-ai.tsx`) — the stage-parameterized composer; today wires
  `mode="staged"` (analyze) + `mode="select"` (route). The Auto-tune button is added **here** so every stage
  reuses it (spine invariant: one composer per stage).
- The analyze composer wrapper `app/frontend/components/ai/ai-propose-composer.tsx`; both AskAi mounts live in
  `app/frontend/components/project/project-workspace.tsx`.
- The **one pending queue** + derivations (`app/frontend/lib/ai/proposals.ts` — `proposalsFromTurn`,
  `pendingCounter`, `authorOf`, `applyAcceptedProposals`): staged params, one explicit re-run (invariant 6).
  Auto-tune's analyze recommendations enter **this same queue** as human-authored staged changes.
- The provenance chokepoint `app/backend/companions/provenance.py::stamp_ai_actions` (invariant 3): the run
  the user commits records its params through the normal run path — no parallel attribution.

### Prior lessons this must honor

- **Deterministic path primary** (spine invariant 5): the button works gateway-off; it must not call
  `/ai/propose`. [[selom-ai-helpers]]
- **AI compiles away → here, no AI at all**: the recommendation is a pure function of the skill spec + the
  data description; a gateway-off re-run from the recorded params reproduces the figure (invariant 2). It is
  therefore **not** ✨-marked (✨ means an AI actor; this actor is a human clicking a deterministic button).
- **Slug keying** — backend skill ids are bare (`deg`); the FE catalog is keyed `selom.<slug>`. Any FE→BE
  skill-id must normalize exactly as `pickSuggestedSkill` does (the `ad453fe` silent no-op). [[selom-skill-keyword-index]]
- **Mock mirrors the contract** — the new endpoint gets an MSW handler in the same move; the mock proves the
  wire only. [[mock-must-mirror-backend-contract]] [[selom-mock-is-wire-only-verify-real]]
- **Verify on real data** — the recommended values are *content*, not wire; verify on `npx next dev --webpack`
  + a live uvicorn (non-`:8000`), real files, gateway off. [[verify-on-real-data-not-mock]]

## Requirements

### Backend (analyze recommender — the only new BE surface)

- **R1.** A new deterministic module `app/backend/engine/recommend.py` exposes
  `recommend_params(skill_id: str, ctx: RecommendContext) -> ParamRecs`. It never calls the AI gateway and has
  no AI dependency (peer of `engine/route.py` and `engine/questionnaire.py`).
- **R2.** `ParamRecs` carries, per parameter, `{key, value, default, why, scaled}` where `value` is the
  recommended value, `default` is the skill's static `param_spec` default, `why` is a one-line plain-language
  reason, and `scaled` is `true` only when a curated rule moved `value` off `default` using the data. The
  static baseline is exactly `skills.contract.defaults(spec)` — so with no data context, every rec is
  `value == default`, `scaled=false`, `why="skill default"`.
- **R3.** The recommended values are **valid**: `recommend_params` returns only keys in the skill's
  `param_spec`, and every returned `value` passes `skills.contract.validate_param_ranges(spec, {...})`
  (type / range / options). A curated rule that would produce an out-of-range value is clamped to the spec
  bound (never emitted invalid).
- **R4. Curated scalings (bounded — the "static + curated" owner decision).** v1 ships a *small, documented*
  rule set; every other knob stays the static default:
  - **`deg` / `proteomics_de`** — map the persisted **design** (`ctx.design`: `best_group`,
    `reference_guess`, `sample_col`) onto the run's design params (`condition_col` / `reference` / `treatment`
    / `sample_col`). This is the same detection INTAKE-DESIGN already surfaces; the analyze button carries it
    into the run params. `why = "from the detected design (<group>: <ref> vs <treatment>)"`.
  - **`umap_scrna` / clustering** — `n_neighbors` lightly scaled to cell count (scanpy guidance: the ~15
    default for typical n; a documented small-n / large-n adjustment, clamped to the `param_spec` range).
    `why = "scaled to ~<N> cells"`.
  - Everything else (thresholds like volcano FDR / |log2FC|, top-N, etc.) = **static** `param_spec` default,
    `why="skill default"`, `scaled=false`.
  - The rule table lives in one place in `recommend.py` with a comment per rule citing its basis; adding a
    rule is a localized change, never a branch on skill id scattered across the codebase
    ([[generalize-via-flagged-plugins-over-shared-spine]]).
- **R5.** `RecommendContext` mirrors the data description the FE already persists + forwards (data-aware
  routing): `data_columns: list[str] | None`, `data_kind: str | None`, `data_n_numeric_cols: int | None`,
  and `design: dict | None` (the persisted `DesignHints`). All optional; any missing field degrades that
  rule to the static default (never an error). Fail-soft: any internal error yields the all-static baseline.
- **R6.** Endpoint `POST /skills/{skill_id}/recommend-params` (in `app/backend/routers/skills.py`) accepts the
  `RecommendContext` body and returns `ParamRecs.model_dump()`. `skill_id` is the **bare** slug (like the run
  path); an unknown skill → 404. No gateway, no key required.

### Frontend (the button, per stage)

- **R7.** `<AskAi>` gains an optional one-click Auto-tune button rendered above the goal input: props
  `autoTuneLabel?: string` and `onAutoTune?: () => Promise<AutoTuneOutcome>` (`{ ok: boolean; note: string }`).
  When `onAutoTune` is absent the button does not render (byte-identical to today for any caller that doesn't
  opt in). The button shows a busy state and renders its returned `note` in the existing note area. The
  typed-goal chat below is **unchanged**.
- **R8.** The Auto-tune button is **never ✨-marked** and its surface uses a **neutral** (not `--stage-ai`)
  accent — it is deterministic, not AI. (The `<AskAi>` container's ✨ header belongs to the chat path; the
  Auto-tune button sits visually distinct above it.)
- **R9. analyze** — `onAutoTune` normalizes the active skill id to the bare slug, POSTs the active dataset's
  persisted data context (`dataFit.columns` / `kind` / `dataFit.n_numeric_cols` / `design`) to
  `/skills/{id}/recommend-params`, and **stages** each `scaled || value≠current` rec into the **same pending
  queue** the analyze chat uses (the figure-data params), so one explicit re-run commits them (invariants
  4/6). The returned `note` summarizes the diff (`"Set N best-practice inputs — review below"`) and the
  per-param `why` is shown on each changed control (reuse the changed-control affordance; `s5-followups.md`
  #6). No skill selected / no dataset context → the button is disabled with a hint.
- **R10. route** — `onAutoTune` reads the persisted `dataFit.fits[0]` (best-first, drop `compatible===false`)
  → its bare slug → the existing `onSelect` path (pre-selects in the picker; the user confirms + runs). Note:
  `"Selected <name> — the best fit for your data."` No new backend call; no gateway. When no fit exists, the
  button is disabled.
- **R11. ingest** — `onAutoTune` applies the persisted `design` prefill (`best_group` / `reference_guess` /
  `sample_col`) into the intake questionnaire answers (INTAKE-DESIGN's confirm-card), which **stage** into the
  next run's design params via the shared queue. This is a re-trigger of the deterministic prefill the
  questionnaire already renders; no new backend call.
- **R12. methods** — `onAutoTune` POSTs the current run's ledger to `POST /methods/compose` and inserts the
  returned draft into the methods/legend card as **DRAFT** (inline, editable, AI-marked-as-draft-not-✨). Chat
  polish stays the typed-goal path. (Migrates unchanged when pillar-2 splits the Methods stage.)
- **R13. grade** — `onAutoTune` renders a deterministic **advisory card**: the recommended test/correction
  given the detected design (e.g. "2 groups × 3 replicates → Wald test, BH FDR"). **ADVISORY only** — it is
  never applied and stages nothing (spine invariant 4: statistics is advisory-only). If this duplicates what
  the scorecard already states, grade Auto-tune collapses to surfacing that existing advice (see Phasing).
- **R14.** The new endpoint gets an MSW handler mirroring `ParamRecs` (R6) so vitest + dev:mock exercise the
  real wire shape.

## Design

### The per-stage contract (one table, the whole feature)

| Stage | Button label | Deterministic source | Effect | Apply-discipline | ✨ | New BE? |
|---|---|---|---|---|---|---|
| route | "Auto-pick skill" | persisted `dataFit.fits[0]` | pre-selects in picker | SELECT | no | no |
| ingest | "Auto-detect design" | persisted `design` (suggest_design_hints) | prefills questionnaire → queue | STAGED | no | no |
| analyze | "Auto-tune" | `POST /skills/{id}/recommend-params` | stages param diff → queue | STAGED | no | **yes** |
| grade | "Recommended stats" | `design` + skill method | advisory card (never applied) | ADVISORY | no | no |
| methods | "Draft methods" | `POST /methods/compose` | inserts editable draft | DRAFT | no | no |

The net (spine): each button returns a reviewable, human-editable result rendered **into the same controls**
the manual path uses — a pre-selection, a staged param diff, prefilled answers, an advisory card, or draft
prose — never a separate artifact, never auto-committed, always undoable/editable.

### Backend — `engine/recommend.py` (analyze) + the endpoint

```python
# app/backend/engine/recommend.py  (peer of route.py / questionnaire.py — no AI import)
class ParamRec(BaseModel):
    key: str
    value: Any
    default: Any
    why: str = "skill default"
    scaled: bool = False          # True only when a curated rule used the data to move value off default

class ParamRecs(BaseModel):
    skill_id: str
    recs: list[ParamRec] = []
    note: str = ""

class RecommendContext(BaseModel):
    data_columns: list[str] | None = None
    data_kind: str | None = None
    data_n_numeric_cols: int | None = None
    design: dict | None = None    # the persisted DesignHints (best_group / reference_guess / sample_col)

def recommend_params(skill_id: str, ctx: RecommendContext) -> ParamRecs:
    spec = load_skill(skill_id)
    base = defaults(spec)                                   # static best-practice baseline
    recs = {k: ParamRec(key=k, value=v, default=v) for k, v in base.items()}
    try:
        _apply_curated(skill_id, spec, ctx, recs)          # R4 — small, documented rule set; clamps to spec
    except Exception:                                       # noqa: BLE001 — fail-soft to the static baseline
        pass
    # R3 — never emit an invalid value: keep only in-spec keys; a bad curated value is clamped upstream.
    return ParamRecs(skill_id=skill_id, recs=list(recs.values()),
                     note=_summary_note(recs))
```

```python
# app/backend/routers/skills.py
@router.post("/skills/{skill_id}/recommend-params")
def recommend_params_route(skill_id: str, ctx: RecommendContext):
    from engine.recommend import recommend_params
    try:
        return recommend_params(skill_id, ctx).model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown skill {skill_id!r}")
```

`_apply_curated` is the *only* place skill-id-specific rules live; each rule is a few lines with a basis
comment (R4). It reads `ctx.design` for `deg`/`proteomics_de` and `ctx.data_*` for size scaling; anything it
can't derive stays the static default.

### Frontend — the button in `<AskAi>` + per-stage handlers

`<AskAi>` renders the optional Auto-tune button and delegates the work to `onAutoTune` (the stage logic stays
in the parent, which already holds the dataset/run state — `<AskAi>` stays generic). `project-workspace.tsx`
supplies the handler per mount:

- **analyze** (`ai-propose-composer.tsx` mount): `onAutoTune` → normalize skill slug → `recommendParams(slug,
  ctx)` (new wrapper in `lib/ai/api.ts` or `lib/skills/api.ts`, its feature dir) → for each rec with
  `scaled || value !== current`, stage into the figure-data params (the same setter the accepted-proposal path
  uses) → return `{ ok, note }`. Recommendations land as **human-authored** pending changes: `authorOf()`
  returns `"user"` (no backing `AiProposal`), so they count under "you", carry **no ✨**, and are individually
  reviewable/revertible via the existing controls. The per-param `why` shows on the changed control.
- **route** → persisted `dataFit.fits[0]` → `onSelect(slug)` (existing path).
- **ingest** → persisted `design` → questionnaire prefill (existing confirm-card).
- **methods** → `POST /methods/compose` → insert draft.
- **grade** → advisory card from `design`.

### Data flow (analyze — the new path)

```
drop file → /data/inspect → { routing, data_fit{columns,n_numeric_cols}, design }  ─┐
                                                             persist on Dataset ─────┘ (survives reload)
pick skill →  [ Auto-tune ]  ── POST /skills/{slug}/recommend-params { columns, kind, n_numeric_cols, design }
                                      │
                          engine.recommend.recommend_params  (defaults + curated scalings, validated)
                                      │  ParamRecs { recs:[{key,value,default,why,scaled}] }
                                      ▼
                       stage diff into the ONE pending queue (human-authored, no ✨)
                                      │
                          one explicit re-run → run records params via the chokepoint (invariant 2/3)
```

## Decisions

- **D1 — Source is the deterministic engine, not the gateway.** (Owner-chosen this session.) The button works
  with the gateway off (the shipped default) so every user can use it; it is ✨-free and human-attributed. The
  AI (data-tuned / fix-what's-off) stays the separate typed-goal chat. Alternatives rejected: AI-generated
  (dead for the default-off config; would need a key) and hybrid (two code paths, behavior shifts invisibly
  with gateway state). Honors spine invariants 2 + 5. Reversible: the chat path can later share the same diff
  UI.
- **D2 — Per-stage button (the one-click default of `<AskAi>`), not a global cascade.** (Owner-chosen.)
  Matches the spine's "one surface per stage"; the user tunes each stage as they reach it, reviewing each
  diff. A global "set everything up" would couple route→ingest→analyze (analyze needs the skill chosen first)
  and hide per-stage review. Reversible: a later "Auto-tune all" could simply fire the per-stage handlers in
  order.
- **D3 — analyze depth = static defaults + a small curated scaling set.** (Owner-chosen.) The baseline is the
  skill's `param_spec` defaults (already best-practice); the curated rules (R4) add data-derived value where
  it clearly matters (design→deg params; n_neighbors→cell count) and are documented in one place. Rejected:
  static-only (the button would barely differ from the form's initial state) and full per-knob rule engine
  (big test surface, drifts into the option-2 AI-analysis territory the button is meant to stay out of).
  Reversible: rules are additive in `_apply_curated`.
- **D4 — Recommended params stage as human-authored pending changes (no new provenance actor in v1).** The
  recommendations enter the existing queue as `authorOf()=="user"` changes — reviewable, revertible,
  ✨-free — and the run records the final params through the normal chokepoint. This is the smallest change
  honoring "human-attributed + reviewable diff." A distinct **`engine`/"recommended"** provenance actor (a
  third banner category with a durable why) is a cleaner-honesty upgrade but adds a category to
  `pendingCounter`/`authorOf` + the banner UI — **deferred** (Out of scope). Reversible toward it.
- **D5 — New endpoint on the skills router, skill-scoped.** `POST /skills/{skill_id}/recommend-params` reads
  the skill's `param_spec`, so the skills router is its natural home (peer of `GET /skills`); the rule engine
  lives in `engine/recommend.py` (symmetric with `route.py`/`questionnaire.py`). Alternative: a
  `/data/recommend-params` on the data router (rejected — the recommendation is per-skill, not per-file).
  Reversible.
- **D6 — grade is advisory-only and phased last.** A one-click "best-practice stats" cannot auto-apply
  (invariant 4: statistics advisory-only). Grade Auto-tune therefore produces an advisory card, and if that
  duplicates the scorecard it collapses to surfacing existing advice. Lowest value-per-effort → last phase.
- **Assumption:** the active dataset/skill the button reads is the one the workbench already tracks
  (`datasetId` / selected skill in `project-workspace`); no new selection state.
- **Assumption:** the persisted `design` (INTAKE-DESIGN) is the source for deg/proteomics design params;
  analyze Auto-tune and ingest Auto-tune may both touch design keys, but they feed the **same** queue (keyed
  by param), so there is no double-stage — the later click just re-affirms the same value.

## Invariants (the seven spine invariants — all hold)

- **Render = f(spec)** — Auto-tune only changes params/selection; the figure re-renders from the run.
- **AI compiles away → no AI at all** — the recommendation is a pure function of the skill spec + data
  description; gateway-off re-run reproduces it. Check: `recommend_params` has no `ai.*` import; the endpoint
  needs no key. Therefore **not ✨-marked** (R8).
- **One provenance chokepoint** — the committed run records params via the normal run path; the button adds no
  parallel attribution (D4). Check: no new provenance write outside `stamp_ai_actions`.
- **Apply-discipline by stage** — route=SELECT · ingest=STAGED · analyze=STAGED · grade=ADVISORY (never
  applied) · methods=DRAFT. Check: grade Auto-tune stages nothing.
- **Deterministic path primary** — the button never calls `/ai/propose`; works gateway-off; renders into the
  existing manual controls. Check: analyze diff appears in the same figure-data controls + pending banner.
- **One pending queue** — analyze + ingest recommendations share the one stage-partitioned banner; one re-run
  commits.
- **Inference-first editor contract** — unaffected (no figure-model change).
- Plus: recommended values are **registry/spec-validated** (R3) — never an out-of-spec knob; unknown skill →
  404, never a fabricated recommendation.

## Error Behavior

- Unknown skill id → 404 (R6); the FE shows the honest note, stages nothing.
- Missing data context (no inspected dataset, no design) → `recommend_params` returns the all-static baseline
  (R5); the analyze button still works (sets defaults) and says so; route/ingest buttons disable with a hint.
- A curated rule that can't derive its input (e.g. `deg` with no `design`) → that param stays the static
  default; no error.
- Endpoint/internal error → fail-soft to the static baseline (R5); the FE surfaces a plain "couldn't tune"
  note and changes nothing.
- Gateway state is irrelevant — the button behaves identically off or on.

## Testing Strategy

- **BE unit (`pytest -m "not slow"`, the uv-3.12 PY + `PYTHONPATH` per CURRENT ▸ ENV):**
  - `recommend_params("volcano", empty ctx)` → every rec `value == default`, `scaled=false` (static baseline).
  - `recommend_params("deg", ctx with design)` → `condition_col`/`reference`/`treatment`/`sample_col` set from
    the design, `scaled=true`, `why` names the contrast; a `deg` ctx **without** design → those stay default.
  - `recommend_params("umap_scrna", ctx with N cells)` → `n_neighbors` scaled + clamped to the `param_spec`
    range; a curated value that would exceed the range is clamped, never emitted invalid (R3).
  - every returned rec passes `validate_param_ranges` (R3); only in-spec keys returned.
  - unknown skill → 404; internal error → static baseline (fail-soft).
- **FE unit (vitest):**
  - the analyze handler stages only `scaled || value≠current` recs into the params; a rec equal to current is
    a no-op (no spurious pending entry).
  - staged recommendations are `authorOf()=="user"` (no ✨) and revertible; the counter reflects them under
    "you".
  - route handler: `dataFit.fits[0]` slug normalized to `selom.<slug>` resolves to the catalog skill
    (the `ad453fe` guard); a `compatible:false` top fit is skipped.
  - `<AskAi>` without `onAutoTune` renders **no** button (byte-identical regression for existing mounts).
  - MSW parity: `/skills/{id}/recommend-params` handler returns `ParamRecs` shape (R14).
- **Integration / browser ([[verify-on-real-data-not-mock]]):** `npx next dev --webpack` + live uvicorn on a
  non-`:8000` port, gateway **off**, real files:
  - real bulk-counts CSV + design → pick `deg` → **Auto-tune** → the design params stage into the pending
    banner with per-param why; one re-run produces the figure; **reload → staged values persist** coherently.
  - route Auto-tune pre-selects the top-fit skill; ingest Auto-tune prefills the questionnaire; methods
    Auto-tune inserts an editable draft.
  - confirm **no ✨ marker** on Auto-tuned controls (they are human-authored).
- **Review:** `review-gauntlet` (correctness/invariants) + `fe-review` (V·R·D·A·R·N) on the FE diff, both by
  `scriptPath` (absolute path), per phase.

## Phasing (build order — each phase = build note + review-gauntlet + fe-review + verify + commit)

1. **analyze** (flagship — the only new BE): `engine/recommend.py` + `POST /skills/{id}/recommend-params` +
   MSW + the `<AskAi>` Auto-tune button wired to the analyze mount. The stage with no one-click today +
   highest value.
2. **route + ingest** (thin FE reuse — no new BE): wire the button to the persisted `dataFit`/`design`.
3. **methods** (DRAFT): the "Draft methods" button → `/methods/compose`.
4. **grade** (ADVISORY, smallest/most delicate): the advisory card, or collapse to surfacing scorecard advice.

## Out of Scope

- The AI (typed-goal) path — "data-tuned" / "fix-what's-off" (options 2/3) — is the existing `<AskAi>` chat,
  unchanged here.
- A distinct `engine`/"recommended" provenance actor + banner category (D4 deferred; v1 stages as
  human-authored).
- A **global** "Auto-tune everything" cascade (D2 per-stage; a later composition could fire the handlers in
  order).
- A full per-knob rule engine or any ML/AI-derived parameter search (D3 curated set only).
- New grade-stage *apply* actions (statistics advisory-only; a true "apply a different test" needs its own
  backend spec — already deferred in `docs/ai-cross-stage-entry-points/spec.md` Phase 3).
- Server-stored datasets / `dataset_id` re-derive (deferred 7c upload); the FE sends the persisted data
  description, as data-aware-routing does.
- Pillar-2 figure-styling AI and the editable table (separate specs).

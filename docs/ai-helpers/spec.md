# AI Helpers — Probabilistic Shell & Action Gateway

_Spec · 2026-06-29 · status: draft, awaiting owner review_

## What

Give every stage of Selom's deterministic engine spine a **user-approved AI helper** — an LLM
that can not only *read and explain* (today's posture) but *propose typed, schema-validated
actions* (set a parameter, add a filter, switch a skill, restyle a figure, resolve an unknown
data profile). The AI never mutates state directly: it emits an `ActionPlan` drawn from an
allowlisted, declared **action registry**; the existing deterministic gateway validates each
action; the user approves anything that recomputes data; the deterministic core executes and
records who proposed what. This is the **write side** of the Deterministic-Core / Probabilistic-
Shell (DCPS) pattern Selom already implements on the read side ([`VisionGateway`](../../app/backend/extract/vision.py),
[`RouteVerifier`](../../app/backend/extract/routing/verify.py)). The product promise: _the user is
always in control, but never lost when they need help — AI helpers end to end._

## Context

**Why now.** The backend is pre-server-wiring (step-8 split deploy is next). Adding the AI
write-path as a first-class seam now — before the live AI gateway and the AWS compute split are
wired — means the contract is designed once and both lanes build to it, rather than retrofitted.
Owner-sequenced 2026-06-29 as the active **tangent project**, ahead of 7c FE-3 upload wiring.

**What exists today (the read side is done and strong).**
- **Deterministic gateway** at the HTTP seam: `routers/_run.py` runs D1 data-contract (422),
  D2 frame-schema (400), QC-block (422), `validate_param_ranges` (400, `skills/contract.py:146`),
  skill `ValueError`→400. No unvalidated input reaches the core.
- **Read-only AI Protocols, swappable, fallback-clean.** `VisionGateway` (`extract/vision.py:64`)
  and `RouteVerifier` (`extract/routing/verify.py:34`) are typed Protocols with an always-available
  no-op default (`NullVerifier`) and a replayable `OperatorRouteVerifier` (Claude-as-gateway
  dev/dogfood, built/tested without a live LLM). The AI is never on the critical path.
- **Provenance** (`companions/provenance.py`) records skill+version, resolved params, input
  sha256, environment — the machine-checkable "is THIS the reproducible figure?" half.
- **Two-tier figure-edit UX already exists** (memory `selom-figure-edit-ux-pattern`): cosmetic =
  live client-side; data-recompute = staged → one top "pending changes" banner → one explicit
  re-run. **This is already a human-approval gate** — the AI becomes another producer feeding it.
- **Content-hash idempotency** (`jobs/queue.py`) keys `(skill_id, version, params, input_sha256)`.

**What is missing.** There is no write/action path for AI anywhere. Every AI seam is read-only.
This spec adds exactly that, reusing the gateway, the approval rail, and the provenance bundle
rather than building parallels.

**Related docs.** `pillars/plan.md` (the P1–P5 spine this maps onto), `figure-data-capabilities/`
(capability surface that gates actions), `figure-editor-contract/spec.md` (the staged-edit queue),
`ai-chat-context/spec.md` (Ask-Selom navigator — a sibling consumer of the same gateway model),
`reproduction-engine/` (the reproducibility invariant this must not violate).

## Requirements

1. **AI proposes, never mutates.** Every state change originates as an `Action` in an `ActionPlan`
   from the gateway; the core applies it, the AI does not.
2. **Allowlisted action vocabulary.** Actions are a closed, declared registry. An `ActionPlan`
   referencing an unregistered action type is rejected at parse time. AI cannot invent a mutation.
3. **Same validation as humans.** An AI-proposed action is validated by the *exact* existing
   functions (`validate_param_ranges`, `frame_schema.check_skill_input`, `compat.fit`, capability
   surface). No second validation path. An out-of-range AI param is rejected before it runs.
4. **Two-tier approval.** Each action declares a `tier`: `cosmetic` (auto-applies live, undoable)
   or `recompute` (staged → pending-changes banner → explicit user Apply). Default for an
   unclassified action is `recompute` (fail-safe to the stricter gate).
5. **Reversible + idempotent.** Cosmetic actions are undoable via JSON-Patch; recompute actions
   reuse the content-hash idempotency key so AI retries never double-run.
6. **Actor-tagged provenance.** Every applied AI action records `actor=ai`, the prompt, the model
   id, and `approved_by` + `approved_at` in the provenance bundle.
7. **AI compiles away (reproducibility invariant).** After an action is applied, re-running from
   the recorded resolved params reproduces the figure with **zero AI in the loop**. AI may help
   *choose* a param; it is never *itself* a param. The reproducibility score never depends on AI.
8. **Degrade clean.** With no live gateway (the default, and any outage), every helper falls back
   to today's deterministic behaviour with **zero regression**. The manual UI for every action
   always exists.
9. **Bounded loop.** The propose→validate→approve→execute→observe loop is driven by deterministic
   code; the AI is a subroutine. The loop terminates on a deterministic condition (schema valid /
   user approves / max turns), never on the AI's self-declared "done" alone.
10. **Operational guardrails.** Per-request token/cost budget, AI timeout, and a max self-correction
    retry count, all configurable; AI holds no session state (context passed per request).
11. **Visible attribution.** AI-touched values carry a distinct visual marker + hover provenance +
    one-click revert (see Design § Visual attribution).
12. **Capability-gap capture (self-improving loop).** Every action that is unfulfillable but
    *coherent* emits a structured `CapabilityGap` instead of being silently dropped; gaps aggregate
    into a frequency-ranked, **review-only** backlog. The log never mutates the registry or
    validation rules — it only tells humans where the spine is incomplete.
13. **AI Activity feed (aggregate view).** A dedicated Changes/Activity tab summarises, in plain
    language, what AI proposed/changed and why, with per-entry approve/revert — so the user reads
    one place instead of hunting element-by-element for the violet markers. It is a *derived view*
    of the actor-tagged provenance log (no separate state) and shares the pending-changes queue.

## Design

### Components (backend)

```
app/backend/ai/                      # NEW package — the Probabilistic Shell
  models.py        Action (discriminated union), ActionPlan, ActionContext, ActionResult,
                   ValidationOutcome, HelperTurn  (all Pydantic)
  registry.py      ACTION_REGISTRY: type -> ActionDef{tier, capability, handler, doc}
  gateway.py       ActionGateway Protocol + NullActionGateway + OperatorActionGateway
  execute.py       execute_action() / validate_action() — reuse existing gateway functions
  loop.py          run_helper_turn(): the bounded propose→validate→(stage|apply)→observe driver
  helpers/         one declared helper per spine stage (plug-ins over the shared spine)
    ingest.py route.py analyze.py grade.py output.py
  live/            (Slice 2) PydanticAIGateway — live model behind the Protocol
routers/ai.py                        # NEW router — POST /ai/propose, /ai/apply  (one-line include)
```

`main.py` gains one `include_router(ai.router)` line — per repo convention, no handlers in `main`.

### The Action contract

```python
# ai/models.py  (illustrative — exact fields pinned during Slice 1)
class Action(BaseModel):
    id: str                                   # stable id for provenance + revert
    type: Literal["set_param", "add_filter", "remove_filter", "select_skill",
                  "restyle_figure", "relabel", "recompute", "annotate",
                  "derive_calc", "set_profile", "map_columns", "apply_cleaning_step",
                  "set_design"]                # == registry keys; closed set
    target: str                               # what it acts on (param name, axis, skill_id, ...)
    payload: dict                             # action-specific, validated by the registry handler
    tier: Literal["cosmetic", "recompute"]    # drives the approval rail
    rationale: str                            # one line shown in the pending-changes banner

class ActionPlan(BaseModel):
    goal: str                                 # the user's NL request, verbatim
    actions: list[Action]
    notes: str = ""                           # AI's explanation, surfaced to the user

class ActionContext(BaseModel):               # the explicit, stateless context (no AI-held state)
    stage: Literal["ingest","join","route","analyze","grade","output"]
    data_profile: dict | None
    figure_spec: dict | None                  # current Plotly spec (read-only to AI)
    skill: dict | None                        # SkillSpec subset + param_spec
    capability_surface: dict | None           # from figure meta.selom (figure-data-capabilities)
    data_fit: dict | None
```

The **registry** is the moat-as-data (mirrors the skill registry and the
`generalize-via-flagged-plugins-over-shared-spine` pattern): generic loop code reads
`ActionDef.tier` / `.capability` / `.handler`; it never branches on an action's `type` string.

### The gateway seam (mirrors `RouteVerifier` discipline)

```python
@runtime_checkable
class ActionGateway(Protocol):
    def propose(self, context: ActionContext, goal: str) -> ActionPlan: ...

class NullActionGateway:                       # always-available default → empty plan
    def propose(self, context, goal): return ActionPlan(goal=goal, actions=[])

class OperatorActionGateway:                   # dev/dogfood: replays recorded ActionPlans (CI-safe)
    ...
```

Slice 2 adds `live/PydanticAIGateway` behind the same Protocol — the offline/inspectable/
repeatable core is never on the AI's critical path.

### The loop (`run_helper_turn`)

```
1. DET   build ActionContext from live engine state (profile, figure, skill, capability, fit)
2. AI    gateway.propose(context, goal) -> ActionPlan      (typed tool calls)
3. DET   for each action: validate_action() via the EXISTING gateway fns
            invalid -> collect Pydantic errors; if retries left, send back to gateway to self-
            correct (<=2x); else drop that action and fall back to manual UI for it
4. SPLIT cosmetic actions  -> apply now (JSON-Patch, undoable)
         recompute actions -> stage into the pending-changes queue (HelperTurn.staged)
5. HUMAN approves the staged set (the existing one explicit "Apply & re-run")
6. DET   execute approved actions -> re-run skill / patch spec -> new {figure, table, provenance}
            provenance records actor=ai, prompt, model, approved_by, approved_at per action
7. AI    observe result -> propose next or done -> loop to 2 (bounded by max_turns)
```

### Self-improving loop: capability-gap capture

Because AI and humans drive the **same** registry through the **same** validation, an AI action
that can't be fulfilled is a high-signal probe of where the spine is incomplete — not an error to
swallow. The loop's "drop the action / fall back to manual" branch (loop step 3) **emits a
structured `CapabilityGap`** instead of silently dropping:

```python
# ai/models.py
class CapabilityGap(BaseModel):
    stage: Literal["ingest","join","route","analyze","grade","output"]
    intent: str                  # the coherent thing the user/AI was trying to do
    unmet: Literal["no_such_action", "param_not_in_spec", "unsupported_filter",
                   "no_fitting_skill", "validation_blocked", "missing_column_op"]
    attempted: dict              # the action/payload that didn't land
    context_hash: str            # dedup key: canonical(stage + intent-class + unmet + skill_id)
    skill_id: str | None
```

Gaps aggregate (dedup by `context_hash`, frequency-ranked **across independent sessions**) into the
**usage-driven backlog for spine improvement** — the capabilities real users reach for (via AI or
by hand) and can't find. The tightening the owner intends is therefore **dual**:

- **Static:** declaring every human+AI capability in one registry forces the core to *enumerate and
  unify its action surface*, which today is implicit (scattered across `param_spec`, filter logic,
  skill specs). Writing the registry tightens the spine before any AI runs.
- **Dynamic:** the gap log turns real unmet intent into a prioritised backlog. Serving the AI better
  and tightening the spine become the same work — a self-serving improvement loop.

**Integrity boundary (non-negotiable).** The gap log is **surfaced for review, never acted on
automatically**: it never auto-adds a registry action, auto-relaxes a validation rule, or widens a
`param_spec`. Auto-expansion would breach invariant #2 (closed action set) and the determinism
guarantee. This is the exact discipline `extract/routing/verify.py::mine_synonym_candidates`
already uses for routing ("surfaced for review, never auto-written — the moat stays
human-curated"); this **generalises that proven precedent from routing synonyms to the whole action
surface**.

**Triage (gap vs noise).** A rejected action is a *gap candidate* only if its intent is coherent
(maps to a recognisable registry neighbour or a known param/column) **and recurs** across
independent contexts. Malformed or incoherent AI output is logged as `noise` and excluded from the
backlog, so AI hallucination never pollutes the roadmap. Recurrence is the signal; a one-off weird
ask is not.

### Per-stage helper map (each a declared plug-in)

| Stage | Deterministic core it rides on | Helper actions |
|---|---|---|
| **P1 Ingest** | `profile_data`, `plan_cleaning`, QC (`engine/cleaning.py`, `engine/qc.py`) | `set_profile` (resolve an `unsure` DataProfile), `map_columns`, `apply_cleaning_step`, `set_design` (condition/treatment) — revives parked `intake-questionnaire-rethink` |
| **P2 Join/Match** | combine + batch checks | `flag_confound`, join-key suggestion (read-mostly) |
| **P3 Route/Guide** | L1–L3 router + L4 `RouteVerifier` | `select_skill`, `suggest_skills` (gated by `compat.fit`) |
| **P4 Analyze** | `_execute`, param_spec, figure spec | `set_param`, `add_filter`, `remove_filter`, `restyle_figure`, `relabel`, `recompute`, `annotate`, `derive_calc`, `explain_result` |
| **P5 Grade** | scorer + SOP sweep (`reproduction/`) | explain score, propose threshold sweep (SOP step 9), explain blame |
| **Output** | methods/legend templates (`litsynth/synth.py`, `companions/methods.py`) | polish prose, translate to a journal style, draft legends (AI-optional over deterministic L3) |

### Visual attribution language (FE, Slice 5)

A dedicated **violet ✨ sparkle-star** = "AI involved", a **third dimension orthogonal** to the
existing amber (figure-data) / cyan (figure-styling) axis — a chip may carry both at once.
- **Hollow star** = proposed, pending approval. **Filled + muted star** = applied & approved.
- **Hover tooltip** surfaces the actor-tagged provenance + one-click revert:
  `✨ AI suggested: min_genes 50→200 · you approved 19:32 · click to revert`.
- **Never colour-only** — glyph + tooltip carry meaning (accessibility; passes an impeccable audit).
- AI proposals queue in the **same existing "pending changes" banner** — no separate AI inbox.

### AI Activity feed (aggregate view, FE Slice 5)

The per-element violet star is *pinpoint* attribution; the user also needs an *aggregate* view so
they never hunt tag-by-tag for what AI touched. A dedicated **Changes/Activity tab in the Ask-Selom
dock** (`ai-chat-context/spec.md`) renders a human-readable, reverse-chronological feed **derived
from the actor-tagged provenance log** (single source of truth — the feed holds no state of its own):

- **Grouped by turn/goal:** "You asked: _'show only significant genes, recolor by pathway'_ → AI
  proposed 3 changes", each change a line (what · why · status).
- **Per entry:** plain-language summary (`min_genes 50 → 200`), the AI's one-line rationale, a status
  chip (`proposed` · `applied` · `reverted`), timestamp, inline **approve / revert**.
- **Same queue as the banner:** pending proposals here ARE the pending-changes queue — approve/reject
  in either surface updates the one queue (no divergent state).
- **Narrates the loop:** each deterministic→AI→deterministic step lands as a feed entry, so the user
  sees the reasoning, not just the result.
- **Doubles as the audit trail:** being a view over the provenance log, it exports straight into the
  methods/provenance bundle — strengthening, not duplicating, the reproducibility story. Chat
  (converse) and Activity (consequences) sit side-by-side in one dock.

### Provenance extension

`companions/provenance.build()` gains an optional `actions` list; each entry:
`{action_id, actor: "ai"|"user", type, target, prompt, model, approved_by, approved_at}`. The
`params`/`input`/`environment` blocks are unchanged — they remain the sole basis for reproduction,
preserving the "AI compiles away" invariant.

## Decisions

- **Framework: Pydantic AI 2.0** (vs LangGraph, hand-rolled Anthropic SDK). Its deferred-tool /
  `requires_approval` stop-the-world flow is a 1:1 match for the propose→validate→approve→resume
  loop; tool args are validated by the Pydantic the gateway already speaks (no second schema
  layer); provider-agnostic seam keeps Claude-as-gateway swappable; durability (DBOS/Temporal) is
  a deferred opt-in, not baked in. **Reversible** — the `ActionGateway` Protocol means swapping
  frameworks (or to a raw Anthropic loop) is a one-file change. _Trigger to revisit toward
  LangGraph:_ runs must survive process crashes and resume mid-flight with built-in checkpointing,
  OR state-replay becomes a first-class audit need, OR the flow becomes a branching multi-node graph.
- **Action set is closed and declared**, not open-ended tool-calling. Chosen for auditability and
  the capability gate. Reversible (add registry entries over time).
- **Default tier = `recompute`** for any unclassified action — fail-safe to the stricter approval
  gate rather than silently auto-applying. Reversible per action.
- **Reuse the figure pending-changes banner** as the approval surface for figure-stage actions
  rather than a new AI inbox. _Assumption:_ ingest-stage (pre-figure) actions need their own
  lightweight approval surface — flagged as an open question, not assumed away.
- **Dogfood-first (`OperatorActionGateway`)** before any live model, mirroring vision/route seams —
  lets Slices 1, 3, 4 build and test the whole loop in CI with zero LLM dependency.

## Versions

- **Pydantic AI** `2.0.0` (released 2026-06-23, MIT) — `pydantic-ai-slim` core + `pydantic-ai[anthropic]`
  extra only. Source: PyPI / github.com/pydantic/pydantic-ai. **Confirm at build time (context7):**
  the exact `requires_approval` / `DeferredToolRequests` / `DeferredToolResults` /
  `ToolApproved` / `ToolDenied` API surface, since it is the load-bearing primitive.
- Add the backend dep with `uv pip install` (NOT `uv sync --extra` — memory `selom-uv-sync-footgun`).

## Invariants

| Invariant | Check |
|---|---|
| AI never reaches the core unvalidated | Every action flows through `execute.validate_action`; no router calls a handler directly. Unit test: a malformed action 4xx's, never runs. |
| AI compiles away | Re-run from recorded provenance `params` (no gateway) reproduces the figure byte-for-byte (figure-spec hash). Test in Slice 1. |
| Validation reuse (no parallel path) | `validate_action` calls the existing `validate_param_ranges` / `frame_schema` / `compat.fit`. Structure-guard test asserts no duplicate validation logic in `ai/`. |
| Closed action set | An `ActionPlan` with an unknown `type` fails Pydantic parse. Test with a fabricated type. |
| Zero-regression fallback | With `NullActionGateway`, every endpoint and run behaves identically to pre-spec `main`. Snapshot test. |
| Gap log is review-only | No code path lets a `CapabilityGap` add a registry action, relax validation, or widen a `param_spec`. Test: writing gaps leaves `ACTION_REGISTRY` and validators byte-identical. |

## Error Behavior

- **Invalid AI action** → return Pydantic validation errors to the gateway for ≤2 self-correction
  retries; on exhaustion, drop the action, keep valid ones, and surface "couldn't do X — here's the
  manual control" (deterministic fallback). Never partial-apply a recompute set.
- **Gateway unavailable / timeout / over budget** → `NullActionGateway` semantics: empty plan,
  deterministic UI unaffected, a quiet "AI helper unavailable" notice.
- **Capability not allowed** for an action on the current figure → action rejected with the
  capability reason (reuses `figure-data-capabilities` gating), surfaced as a disabled suggestion.
- **402 quota / cost-budget exceeded** → halt the loop, keep already-applied+approved actions,
  report remaining budget.

## Testing Strategy

- **Slice 1 (pure, no LLM):** unit-test the registry, `validate_action` (range/frame/compat/
  capability rejections), the cosmetic-vs-recompute split, JSON-Patch revert, and the "AI compiles
  away" reproduction test. `OperatorActionGateway` replays a recorded P4 plan end-to-end.
- **Structure guard:** extend `test_structure_guard.py` — `ai/` must not re-implement validation;
  `routers/ai.py` is the only route home; no action handler is called outside `execute.py`.
- **Slice 2 (live):** contract-test `PydanticAIGateway` against recorded fixtures; guardrail tests
  (budget cap halts, timeout → fallback, ≤2 self-correct retries then drop).
- **FE (Slice 5):** vitest for the violet-star state machine + tooltip provenance + revert; the
  AI-proposal-in-pending-banner flow; verify on real data + live backend (memory
  `verify-on-real-data-not-mock`), snapshot localStorage first (`selom-fe-probe-autopersist-gotcha`).
- **Backend test runner:** uv-3.12 PY + `PYTHONPATH=.venv\Lib\site-packages`, fast gate
  `pytest -m "not slow"` (memory `selom-backend-python-exec`).

## Build sequencing

- **Slice 1 — Action Gateway spine (BE, no live AI).** models + registry + `execute`/`validate`
  reuse + `OperatorActionGateway` + provenance `actions` field + the P4 Analyze vocabulary
  (params/filters/styling) first, because the staged-recompute approval rail already exists →
  lowest new-infra cost, proves the whole loop. Structure guard + reproduction invariant tests.
  Capability-gap **capture** lands here too (it is cheap — emit a `CapabilityGap` on the loop's
  drop branch into an in-proc/SQL store); aggregation + the FE backlog view come in Slice 4/5.
- **Slice 2 — Live Pydantic AI** behind the Protocol + operational guardrails (token/cost budget,
  timeout, self-correct retries). `POST /ai/propose`, `/ai/apply`.
- **Slice 3 — P1 Ingest helper** (highest "user-lost-without-help" value; resolves parked intake).
- **Slice 4 — P3 route switch-skill + P5 explain/sweep + Output polish.**
- **Slice 5 — FE:** violet-star attribution language, AI proposals in the pending-changes banner,
  the **AI Activity/Changes feed in the Ask-Selom dock** (aggregate, derived from the provenance
  log), per-stage helper entry points.

## Out of Scope

- The live `PydanticAIGateway` implementation detail and prompt engineering (Slice 2 — this spec
  fixes the seam, not the prompts).
- Durable/crash-resumable execution (DBOS/Temporal) — deferred opt-in; only if the LangGraph
  trigger conditions arise.
- Ask-Selom conversational navigator UI (`ai-chat-context/spec.md`) — a sibling consumer of this
  gateway, specced separately.
- Auto-fetch/accession download automation, BAM ingest infra — unrelated parked work.
- Billing/metering of AI usage beyond the per-request cost-budget guardrail (launch-gate item).

## Open questions (for review)

1. ~~Confirm the Pydantic AI API.~~ **CONFIRMED (context7, v2.0.0):** `requires_approval` /
   `ApprovalRequired` / `DeferredToolRequests` / `DeferredToolResults` exist;
   `AnthropicModelSettings(anthropic_task_budget={'type':'tokens','total':N})` is the per-loop
   token-budget guardrail; `claude-opus-4-8` is supported. **S2 design refinement:** use Pydantic AI
   as the structured-output *translator* (NL goal + context → a Pydantic-validated proposed plan →
   our `ActionPlan`); keep the S1 spine as the SINGLE authority for validation / approval / execution
   / provenance. Do **not** use Pydantic AI's own tool-approval/deferred-execution — our actions
   execute in `commit_recompute` after the user approves on the pending-changes rail, decoupled from
   the agent run, so using Pydantic's approval too would split approval across two systems (a parallel
   path the spine-consistency lens would flag). Strengthens the invariants and simplifies S2.
2. How does `ActionPlan` map onto the FE staged-edit queue contract (`figure-editor-contract`)?
   Same queue, or an adapter? (Recommend: same queue, AI actions are tagged producers.)
3. Do **ingest-stage** actions (pre-figure, no pending-changes banner yet) need a distinct approval
   surface? (Recommend: a lightweight inline "apply suggestion" confirm at the intake pane.)
4. Cost-budget defaults (per-request token ceiling, per-session cap)?
5. Confirm zero-regression fallback is observable in dev:mock (extend the mock to ack `/ai/*`,
   memory `mock-must-mirror-backend-contract`).

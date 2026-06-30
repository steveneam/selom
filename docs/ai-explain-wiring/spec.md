# AI explain wiring — `explain_score` + `propose_sweep` reach a UI surface

_2026-06-30 · NEXT#1 (build-the-gaps). Both `/ai/explain` helpers ship with **zero callers** —
endpoints + `lib/ai/api.ts explain()` + tests + MSW mock, no UI entry point ([[selom-shipped-not-reachable]]).
This wires each to its natural deterministic surface and, per the forcing-Q, **upgrades the
`propose_sweep` backend from echo-all-params to a real grounded ranking** so it is useful with the
gateway OFF (its default), not only when a live key lands._

## Decisions (forcing-Qs, 2026-06-30)

1. **`explain_score`** → an `Explain this score` button (neutral `Info` icon) on the **interpretation
   card** of the two-axis Score header → expands grounded text **inline** below the header.
2. **`propose_sweep`** → a `Suggest` button (neutral `Lightbulb` icon) in the **`SweepForm`**; **build a
   real deterministic recommender** server-side (rank the declared sweep knobs, return top 2–3 with
   reasons) and have the button **preselect the top-ranked param**.
3. **Scope** → the explain button shows on **both** the live Score stage **and** the public showcase
   detail (`/reproduction/jev`), via a `showExplain` prop both callers pass. _(Revised 2026-06-30: the
   forcing-Q first chose live-only to keep the showcase clean; on reflection the showcase is the
   most-viewed scorecard, its ledgers are real driven data, and the helper is read-only +
   collapsed-by-default — so surfacing it there best serves the reachability goal [[selom-shipped-not-reachable]]
   and makes it demonstrable. The prop stays so a future embed can still opt out.)_

## Honesty constraint — reserve ✨ for AI (owner steer, 2026-06-30)

The ✨ star is the app's **AI-attribution glyph** (S5 banner/marker). These helpers are **deterministic by
default** (`NullActionGateway` → `source: "deterministic"`) and only become real AI prose when
`SELOM_AI_GATEWAY=live` + `ANTHROPIC_API_KEY` (`source: "ai"`). So:

- **Buttons carry NO ✨** — neutral icons (`Info` / `Lightbulb`). The affordance is "explain"/"suggest",
  not "ask the AI".
- **✨ appears only on the result, only when `source === "ai"`** — a small "AI" badge. A
  `source: "deterministic"` result is labelled plainly ("Grounded summary" / "Selom"), no star. The
  helper visibly *lights up* into an AI affordance when a key is live, and ✨ never lies.

**Gateway-on posture (owner directive 2026-06-30, [[selom-claude-acts-as-ai-gateway]]).** The intended
default is the gateway **ON** (Claude as the dev model now; swap the model at launch) — deterministic is
the *degraded fallback*, not the resting state. This feature is already built for that: the lit/unlit
state is driven entirely off the response `source`, so flipping the gateway on lights up the explain
prose to ✨AI with **zero** edits here (the sweep picks stay deterministic *by design* — a grounded,
reproducible ranking, never an AI judgment; the AI value-add on the sweep surface is narrative prose, the
deferred follow-up #10). Turning the gateway on app-wide is a separate, cross-cutting change (it also
governs `propose`/`apply`), tracked outside this spec.

Neither helper is a mutation — `/ai/explain` never goes through `apply_plan`, never stages a param, never
records a gap (preserved; covered by existing tests).

## The deterministic sweep recommender (backend)

Today `_deterministic_explain`'s `propose_sweep` branch echoes every key
(`"Consider sweeping: <all params>…"`). Replace with a single ranking source of truth:

```
rank_sweep_space(sweep_space) -> list[{param, label, reason, breadth}]
```

**Grounded, never fabricated** — it ranks only by what the spec *declares* about each knob's value
space (it cannot claim figure impact without running):

- **range/number** with `min`,`max`,`step`: `breadth = round((max-min)/step)` distinct steps (a missing
  step falls back to `(max-min)/10`). Reason: `"widest declared range (min–max, ~N steps)"`. Numeric knobs
  sort first (most informative to sweep).
- **select**: `breadth = len(options)`. Reason: `"N options"`.
- **switch**: `breadth = 2`. Reason: `"on / off"`.
- knob with no usable range info: `breadth = 0` (kept, ranked last).
- **Sort**: by kind priority (numeric > select > switch > unknown), then `breadth` desc, then `label`
  for stable determinism. Return the top **3**.

`_deterministic_explain` builds its prose **from** this ranking, so the Null-gateway `text` and the
structured `suggestions` always agree. Empty / missing `sweep_space` → the existing
"No sweep space provided…" line + `[]`.

`explain_score` deterministic text is enriched to use the now-richer scorecard payload (confidence +
findings) — still grounded in the passed fields only:
`"Reproducibility X/100 (tier Y), Selom confidence Z/100. N panel(s) scored. <k> reproduced, <m>
paper-irreproducible. Improve by supplying data that matches the paper's figures more closely."`

## Contract change — `/ai/explain` response (additive, backward-compatible)

`routers/ai.py::explain` always computes the deterministic ranking for `propose_sweep` (independent of
the gateway — it is pure data, so it stays reproducible even when the prose is AI) and returns it
alongside the gateway `text`:

```jsonc
{ "request": "...", "text": "...", "source": "deterministic|ai",
  "suggestions": [ { "param": "resolution", "label": "Cluster resolution",
                     "reason": "widest declared range (0.1–2.0, ~19 steps)" } ] }  // [] for explain_score
```

`ExplainRequest` is unchanged (`scorecard` / `sweep_space` already exist). FE `ExplainResponse` gains
`suggestions?: SweepSuggestion[]`; `lib/ai/api.ts explain()` needs no change (the field rides along).

## FE data-shape mappers (pure, unit-tested) — `lib/ai/explain-inputs.ts`

- `buildScorecardPayload(ledger.scorecard)` → the flat shape the backend reads:
  `{ score: score.reproducibility, tier: score.tier, selom_confidence, panel_count: panel_scores.length,
  findings, coverage }`. (The FE `Scorecard` nests the number under `score.reproducibility`; the backend
  deterministic path reads a flat `score`/`tier`/`panel_count` — map at the boundary, don't reshape the
  backend.)
- `buildSweepSpace(fields: ParamField[], params: SkillParams)` → `{ key: { label, type, min, max, step,
  options, current } }` for the sweepable fields the `SweepForm` already loads.

## Surfaces (FE)

**A — Score stage explain** (`components/reproduction/score-report.tsx`)
- `ScoreReport` gains `showExplain?: boolean` (default **false**; both the live Score stage AND the
  showcase detail pass it `true` — a non-explain embed can still omit it).
- When true, the interpretation card renders an `Explain this score` button (`Info` icon, **no ✨**);
  click → `explain({ request:"explain_score", stage:"grade", scorecard: buildScorecardPayload(sc) })`.
- Inline-expands a panel below the header with the returned `text` + a source label: a plain "Grounded
  summary" when `source==="deterministic"`, or an **✨ "AI"** badge when `source==="ai"`. Spinner while
  loading; honest inline error on failure (the deterministic score above is unaffected). Collapsible;
  re-click re-runs.
- `ScoreStage` passes `showExplain`. The button only appears with a real `score` (the `ScoreHeader` path).

**B — Sweep suggest** (`components/project/sweep-form.tsx`)
- A `Suggest` button by the form title (`Lightbulb` icon, **no ✨**); click →
  `explain({ request:"propose_sweep", stage:"analyze", skill_id, sweep_space: buildSweepSpace(sweepable, baseParams) })`.
- On success: show the `text` as a one-line grounded hint (with the same ✨-only-when-`source==="ai"`
  badge rule) and **preselect `suggestions[0].param`** (only if it is a current sweepable key — never
  select a knob that isn't there), which re-suggests its values via the existing `suggestValues` effect.
  Spinner while loading; inline error on failure.
- No auto-run; the user still reviews values and clicks **Run sweep** (staged-recompute discipline).

## Mock fidelity ([[mock-must-mirror-backend-contract]])

`mocks/ai-fixture.ts::mockExplain` + `mocks/handlers.ts` updated to mirror the new shape: richer
`explain_score` text and a `propose_sweep` that returns the **same ranking** + `suggestions[]`, so a
`dev:mock` run exercises the real wire (preselect included). Verification is still on the **real engine**
([[verify-on-real-data-not-mock]]).

## Test plan

- **BE** (`tests/test_ai_s4.py`, extend Part C): `rank_sweep_space` orders numeric-by-breadth > select >
  switch and caps at 3; `propose_sweep` prose names the top params; the endpoint returns `suggestions`
  for `propose_sweep` and `[]` for `explain_score`; explain_score richer text includes confidence;
  the not-a-mutation / no-gap invariants still hold.
- **FE** (`lib/ai/explain-inputs.test.ts`): both mappers (nested→flat scorecard; fields→sweep_space,
  including the `current` value and option/range carry-through; non-sweepable types degrade clean).
- **FE** existing `lib/ai/api.test.ts`: `explain()` surfaces `suggestions` when present.

## Out of scope (deferred — `docs/ai-helpers/s5-followups.md`)

Cross-stage AI entry points (#0); committed-figure control attribution (#3); Activity/Gaps drill-through
(#4). This task is strictly: make the two built helpers reachable + make `propose_sweep` useful offline.

## Gates

BE fast gate (`pytest -m "not slow"`, the uv-3.12 PY + `PYTHONPATH=.venv/Lib/site-packages`
[[selom-backend-python-exec]]) + ruff; FE tsc + eslint + vitest. Review: **review-gauntlet** (correctness)
+ **fe-review** (V·R·D·A·R·N — this is an FE diff). Verify on real data + a live uvicorn on a non-:8000
port ([[full-app-smoke-test-before-handoff]]).

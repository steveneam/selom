# AI-explain follow-ons — Copy · refresh-on-rescore · sweep AI prose · prompt tightening

_2026-06-30 · NEXT#3 (`s5-followups.md` #8–10 + the AI-GATEWAY deferred prompt-tightening). Small,
deliberately-deferred enhancements on top of the shipped explain/sweep surfaces (AI-EXPLAIN `a7d477c`,
AI-GATEWAY `7580621`). Honesty rule unchanged: ✨ only when `source === "ai"`._

## #8 — Explain: Copy the grounded explanation

`ExplainScore` (`components/reproduction/score-report.tsx`) renders the explanation prose with no way to
capture it.

- Add a **Copy** button in the result header row (next to `ExplainSourceBadge`): copies `result.text` via
  `navigator.clipboard.writeText`, with a transient "Copied" affordance (✓ for ~1.5s) and a graceful
  fallback (no throw if clipboard is unavailable).
- **"Add to methods" stays deferred** — the explanation is about the *score* (a meta-assessment), not the
  figure's methods; feeding it into the per-figure/paper methods-synth would mislabel commentary as
  methods. Copy is the clean win; revisit add-to-methods only if a score-narrative surface appears.

## #9 — Explain: refresh on re-score

`ExplainScore` caches `result` in local state and only fetches on open. If the `scorecard` prop changes
(a re-scored run) while the panel is open, the shown text goes stale.

- Derive a stable scorecard key from `buildScorecardPayload(scorecard)` (e.g. JSON of the flat payload).
- In an effect keyed on that key:
  - if the panel is **open** and the key changed → re-run `run()` (fetch fresh).
  - if the panel is **closed** → clear the cached `result` so the next open is fresh.
- Keeps the existing collapse/re-click behaviour; no new control needed (the re-fetch is automatic). The
  spinner already covers the in-flight state.

## #10 — Sweep: surface the live AI prose

`SweepForm` (`components/project/sweep-form.tsx`) renders the deterministic ranked picks as chips but
**drops** `suggestion.text`. When the gateway is live, that text is the AI's narrative reasoning.

- Below the chips, when `suggestion.source === "ai"`, render `suggestion.text` as a prose line with an
  **✨ "AI"** badge (`ExplainSourceBadge`). The picks stay deterministic + unbadged (grounded,
  reproducible) — only the prose is AI-attributed.
- When `source === "deterministic"` (the default), render **nothing extra** — the chips' own grounded
  reasons already cover it; a redundant deterministic restatement adds noise. (This is the one place the
  ✨/plain split means "AI → show prose, deterministic → chips only".)

## Prompt tightening — stop the field-name paraphrase

The live `explain` prompt dumps the raw `data` dict with no field semantics
(`vercel_gateway.py::_explain_user_prompt`), and the system prompt is generic (`_EXPLAIN_SYSTEM`). Llama
then paraphrases `panel_count` as "reviewers" — re-interpreting schema-less numbers.

- Strengthen `_EXPLAIN_SYSTEM`: forbid re-interpreting or renaming any field; use each field with the
  exact meaning given; never invent entities (reviewers, comments, authors) not present in the data.
- Replace the raw-dump user prompt with a **field-labelled** prompt for `explain_score`: enumerate each
  known scorecard field with its meaning (e.g. `panel_count` = "number of figure panels graded — NOT
  reviewers/comments"; `score` = reproducibility 0–100; `tier`; `selom_confidence`; `findings`).
  `propose_sweep` similarly labels `sweep_space` knobs.
- Extract a shared `build_explain_prompt(request_type, data, goal)` so **both** live gateways
  (`vercel_gateway`, `pydantic_gateway`) use the identical tightened prompt (no drift). The deterministic
  fallback (`_deterministic_explain`) is untouched — already grounded.

## Test plan

- **FE** (`components/reproduction/score-report` test or `lib/ai` mappers): Copy writes `result.text`
  (mock `navigator.clipboard`); the re-score effect re-fetches when the scorecard key changes while open
  and clears the cache when closed.
- **FE** (`sweep-form` test): the AI prose line renders only when `source === "ai"`; deterministic shows
  chips only.
- **BE** (`tests/test_ai_*`): `build_explain_prompt` includes the field labels for both request types;
  both live gateways call it (a unit test asserting the prompt text contains the `panel_count` label and
  the "do not rename fields" instruction). Deterministic output unchanged (existing tests stay green).

## Honesty + scope guardrails

- ✨ appears only on `source === "ai"` results — never on a deterministic fallback or on the sweep picks.
- No mutation paths touched — `/ai/explain` stays informational (no `apply_plan`, no gap, no provenance).
- No backend response-shape change (the `text`/`source`/`suggestions` contract already carries everything).

## Gates

BE fast gate + ruff; FE tsc + eslint + vitest. Review: **fe-review** (the FE surfaces) +
**review-gauntlet** (the prompt/contract). Verify the live AI prose + the tightened prompt against a live
gateway (`SELOM_AI_GATEWAY=gateway` + the key, env-only) on a non-:8000 port
([[verify-on-real-data-not-mock]]); verify Copy/refresh in a real browser ([[stack-browser-verification]]).

# Skill Keyword Index — L4 AI-verify + synonym-mining seam (fast-follow #2)

> **Status: scoped 2026-06-20 (session 34), owner-approved ("continue with 2 and 3").** Adds the
> optional, gated L4 layer of the 4-layer router (`docs/records/skill-keyword-index/spec.md` §"AI's role —
> verify + mine, never replace"). **AI verifies and mines; it never replaces the deterministic
> core.** Mirrors the existing AI-gateway discipline (`extract/classify.VisionClassifier` +
> `extract/vision.OperatorVisionGateway`, memory `selom-claude-acts-as-ai-gateway`): a typed
> Protocol with a degrade-clean Null default and a replayable operator stand-in (Claude-as-gateway),
> built and tested WITHOUT a live LLM. The live service slots in behind the same Protocol later.

## What

A new `extract/routing/verify.py` + two typed artifacts in `extract/routing/models.py`:

- **`RouteVerdict`** — the AI's adjudication of one figure: `figure`, `verdict`
  (`confirm`/`override`/`uncertain`), `target` (the confirmed/overridden `skill:`/`oos:` target),
  `confidence`, `note`.
- **`SynonymCandidate`** — a mined synonym proposal: `term` (an unmatched method-noun), `section`,
  `co_targets` (routed targets co-present in that section), `note`. **Surfaced for review, never
  auto-written** to `synonyms.json` (the moat stays human-curated — spec resolved-decision #3).
- **`RouteVerifier`** Protocol — `verify_figure(figure_route) -> RouteVerdict`.
- **`NullVerifier`** — the default: returns no verdicts; `verify_map` with it is a **no-op** (the
  deterministic map is returned byte-identical). This is the always-available offline behaviour.
- **`OperatorRouteVerifier`** — Claude-as-gateway dev/dogfood stand-in: replays operator-recorded
  `RouteVerdict`s deterministically (CI-safe, like `OperatorVisionGateway`); raises/skips for any
  figure without a recorded verdict so the caller keeps the deterministic route.
- **`figures_needing_review(fmap, *, confidence_below=0.5)`** — the deterministic selector: a figure
  is flagged when its `tier == "recovered"` OR `confidence < confidence_below`. This is exactly the
  set the paid L4 tier would adjudicate (and the FE upsell counts).
- **`verify_map(fmap, verifier, *, confidence_below=0.5)`** — apply the verifier to the flagged
  figures only; attach each `RouteVerdict` to `FigureRoute.ai`; on `override` update the figure's
  `top`/`in_scope`/`reason`/`confidence`. Returns a NEW `FeasibilityMap` (pure given the verifier).
  **Never called by `route_text`** — the deterministic core is independent (off the critical path).
- **`mine_synonym_candidates(text, fmap, *, index=None)`** — deterministic candidate generator:
  for each `fmap.unmatched_terms` method-noun, the routed targets co-present in the same segmented
  section become its `co_targets`. Offline/free; the L4 AI tier (or the owner) confirms `term→target`
  and adds it to `synonyms.json`. Attaches to `FeasibilityMap.synonym_candidates`.

Two backward-compatible model fields: `FigureRoute.ai: RouteVerdict | None = None` and
`FeasibilityMap.synonym_candidates: list[SynonymCandidate] = []` (both default-empty → existing
output unchanged; both typed in `models.py` to avoid a circular import with `verify.py`).

## Why this shape

- **Off the critical path, by construction.** `route_text` is untouched; `verify_map` is a separate
  opt-in post-pass. With no gateway (`NullVerifier`) the map is identical to today — the credibility
  guarantee (free, offline, inspectable, repeatable) is never weakened by the AI tier.
- **The upsell signal is already deterministic.** `figures_needing_review` / `tier_summary` are
  computed with zero AI, so the FE (#3) can show "N clean / M need recovery → Pro AI" for free; the
  AI tier is what the upsell BUYS.
- **The moat stays curated.** Synonym mining proposes; a human/owner disposes. No silent vocab drift.

## Validation (validate-by-metric, offline)

`tests/test_routing.py` (+cases), no network, a `FakeVerifier` stand-in:
1. **Null is a no-op** — `verify_map(fmap, NullVerifier())` equals the input map (every figure
   `top`/`confidence` unchanged; `ai is None`).
2. **Override applies + is attributed** — a `FakeVerifier` that overrides a flagged figure changes
   that figure's `top`/`in_scope` and attaches `fr.ai` with `verdict="override"`; **unflagged
   (structured, high-confidence) figures are never touched**.
3. **Selector is correct** — `figures_needing_review` returns exactly the recovered-tier /
   low-confidence figures (drive it off the real JEV map: all 8 recovered → all flagged).
4. **OperatorRouteVerifier replays** — a recorded verdict is returned; an unrecorded figure is
   skipped (deterministic route kept).
5. **Synonym mining surfaces a gap** — a paper using an off-vocab method-noun (e.g. a deliberately
   gapped index) yields a `SynonymCandidate` whose `co_targets` include the section's routed skills;
   `synonyms.json` is **not** modified.

Library-only; no new deps; no live LLM. pytest + ruff green before any push.

## Out of scope (this slice)

- A live LLM/vision gateway (the paid tier; a `LiveRouteVerifier` implements the same Protocol later).
- Auto-writing mined synonyms into `synonyms.json` (human-curated by decision; the miner only proposes).
- A verify endpoint / FE wiring of verdicts (the FE surface, fast-follow #3, renders the deterministic
  tiers + the upsell; verdict display can follow once a gateway exists).

---

## Built + validated (session 34, 2026-06-20)

Shipped exactly to scope. `feat(backend)` commit `b72359c`. `extract/routing/verify.py`
(`RouteVerifier`/`NullVerifier`/`OperatorRouteVerifier` + `figures_needing_review` + `verify_map`
+ `mine_synonym_candidates`) + `RouteVerdict`/`SynonymCandidate` artifacts and the two
backward-compatible model fields. **Validated by metric** (`tests/test_routing.py`, +6, a fake
verifier, no network): Null is a no-op; override applies only to flagged figures + is attributed
(unflagged untouched); the selector skips a clean structured figure; the operator verifier replays
recorded verdicts and skips unrecorded; synonym mining surfaces a gapped term's co-skills without
writing the moat; real-JEV all-8-recovered → all flagged. Full backend suite **533 passed**; ruff
clean; library-only, no new deps. A live `LiveRouteVerifier` implements the same Protocol later.

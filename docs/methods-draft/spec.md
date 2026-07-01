# Phase 4 — Methods · DRAFT (Layer A cross-stage AI) — SPEC

_2026-07-01 +10:00 (Australia/Sydney) · a focused build-spec for Phase 4 of the Layer A remainder
(`docs/ai-cross-stage-entry-points/build-spec.md` §Phase 4), written after Phases 2c + 3 shipped so it
reflects the **real** surfaces (the AskAi composer as extended in Phase 3, the PublishConfidence card).
**Status: written — PAUSED for owner review before any code.** No author sign-off (owner's work)._

> This is the "what files change, in what order, with what tests" peer of the build-spec's Phase 4
> paragraph. It supersedes that paragraph where they differ (it is grounded in the shipped code).

## Goal

A one-click **"Draft methods"** + chat-polish on the **PublishConfidence** card's Methods section
(`components/project/publish-confidence.tsx`). The **deterministic draft is the run's own methods text**
(already computed by `companions.methods.build_body` and returned as `SkillMethods.text`, shown today in
the `Methods` sub-component). The AI **polishes** that text (AI-marked, fully editable); the deterministic
text is always the base and the fallback. Nothing is auto-applied; the methods text never feeds a run.

## What already exists (read before building — the seed is partly stale)

- **The deterministic methods text is already on the card.** `PublishConfidence` → `Methods({ methods })`
  renders `methods.text` + `methods.citations` with a Copy button. `SkillMethods = { text, citations }`
  rides every `/run` response. So the "deterministic draft" is **already present** — Phase 4 adds an
  AI polish *over* it, editable in place.
- **The informational AskAi path shipped in Phase 3.** `AskAi` now has an `onExplain(goal) =>
  Promise<ExplainResponse | null>` prop and renders a result block (text + `ExplainSourceBadge`, ✨ only
  when `source==="ai"`) for `mode="advisory"` **and `mode="draft"`** (the send() branch already handles
  both). Phase 4 reuses that path and adds the **editable + seed** behaviour draft needs.
- **The Auto-tune button slot is the deterministic seed.** `AskAi` renders a neutral primary CTA above
  the chat when `onAutoTune` is provided (`autoTuneLabel`). Phase 4 relabels it **"Draft methods"**: the
  one-click deterministic seed (`methods.text` verbatim, no gateway, no ✨) → the editable draft.
- **`/ai/explain` source honesty is by-comparison.** The endpoint stamps `source="ai"` only when the
  gateway's text `!= _deterministic_explain(...)`. For `draft_methods` the deterministic fallback IS
  `base_text`, so an unchanged (no-op) polish stays `deterministic` (no false ✨). This is the honesty
  lever — keep the fallback exactly `base_text`.

## Invariants (the seven spine invariants; Phase-4-specific reading)

1. **Render = f(spec).** Methods text is **prose about** a figure, never an input to it — drafting never
   touches the figure spec or a run. (Migration note: pillar-2 may later split a Methods & Legend stage;
   this composer moves there unchanged.)
2. **AI compiles away** — n/a to a mutation here (methods is not a param); the discipline instead is that
   the deterministic `base_text` is always the fallback and the base, so gateway-off yields the honest
   deterministic draft.
3. **One provenance chokepoint** — n/a: `draft_methods` is **informational** (`/ai/explain`, never
   `/ai/apply`), like `explain_score`/`grade_advice`. It produces no figure, records no gap, stamps no
   `provenance.actions[]`.
4. **Apply-discipline = DRAFT** — AI-marked, fully editable prose; nothing auto-applied; no re-run.
5. **Deterministic path primary** — the deterministic methods text is always shown and is the fallback;
   the AI renders *into* the same editable draft, never as a separate artifact.
6. **One pending queue** — n/a (no staged params; methods is not a run input).
7. **Honesty** — ✨ only when `source==="ai"` (text actually changed from `base_text`); an exported draft
   carries an `[AI-generated]` marker when the shown text is AI (Copy symmetry with the explain Copy).

## The one design decision to lock (forcing question)

**How editable is the draft, and where does the edited text live?** Three options — the spec recommends A.

- **A (recommended) — editable-in-place, ephemeral (session-only).** The drafted text renders in a
  `<textarea>` inside the Methods section; the user edits it freely and Copies it. It is **not persisted**
  to the figure (methods text is regenerated deterministically every run; a persisted hand-edit would
  drift from provenance and reopen the "which methods is canonical?" question). Lowest risk, matches
  "draft you paste into your paper". The deterministic `methods.text` stays the canonical base.
- **B — persisted per-figure draft.** Store the edited draft on `Figure` (client-only, like
  `aiProposals`), surviving reload. More work (a store field + `mergeFigures` preservation + a "revert to
  generated" control) and raises the canonical-text question. Defer unless the owner wants persistence.
- **C — read-only AI polish (no textarea).** Just show the AI-polished text with a Copy (no inline edit).
  Simplest, but the build-spec explicitly says "editable in place", so this under-delivers.

**Recommendation: A.** Ship an in-place, session-only editable draft; the deterministic text is the base
and canonical. Persistence (B) is a clean follow-up if the owner wants drafts to survive reload.

## BE — `routers/ai.py` + `ai/gateway.py` (+ recordings)

- **`ExplainRequest`**: extend `request` to `Literal["explain_score", "propose_sweep", "grade_advice",
  "draft_methods"]`; add `base_text: str | None = None` (the deterministic methods text to polish).
- **`explain()` handler**: thread `base_text` into the grounding `data` (`if req.base_text: data["base_text"]
  = req.base_text`). `suggestions` stays `[]`. Source labelling is unchanged (the by-comparison check).
- **`_deterministic_explain` `draft_methods` branch**: **return `data.get("base_text") or ""` verbatim.**
  This makes gateway-off return the deterministic draft honestly (`source="deterministic"`, no ✨) and is
  the fallback the live gateway is compared against (a no-op polish → still deterministic).
- **`build_explain_prompt` `draft_methods` branch**: instruct the live model to *polish* `base_text` to the
  user's goal (tighten, match a journal's tone) while **preserving every number, threshold, and citation**
  and inventing nothing. Grounds on `base_text` + `goal`.
- **`_operator_input_key` `draft_methods`**: key on `data["base_text"]`'s skill (pass `skill_id` in `data`
  as the other requests do) — key `draft_methods:<skill_id>`. Add one **operator recording** (a polished
  version of a dogfood run's methods text) so `SELOM_AI_GATEWAY=operator` lights up ✨ at zero credit.
- **No new endpoint** — extend `/ai/explain` (reuse, mirrors `grade_advice`). No `/ai/methods` sibling.

## FE — `lib/ai/types.ts` + `lib/ai/api.ts`

- **`ExplainRequest`** (types): `request` union += `"draft_methods"`; add `base_text?: string | null`.
- **`api.ts`**: `explain()` is already generic (passes the request through) — no change beyond the widened
  type. (No separate `draftMethods()` wrapper; one call site, keep it lean.)

## FE — `components/project/publish-confidence.tsx` (the surface)

Extend the `Methods` sub-component (not the whole card):
- Add a **"Draft methods"** affordance = `<AskAi stage="methods" mode="draft" …>` beneath the methods
  paragraph, with:
  - `onAutoTune` → the deterministic **seed**: sets the editable draft to `methods.text` verbatim and
    returns an `AutoTuneOutcome` note (no gateway, no ✨). `autoTuneLabel="Draft methods"`.
  - `onExplain(goal)` → `explain({ request:"draft_methods", skill_id, goal, base_text: <current draft or
    methods.text> })`; the returned text replaces the editable draft; ✨ via `ExplainSourceBadge` when
    `source==="ai"`.
- Render the draft in an **editable `<textarea>`** (option A) bound to local state, seeded from
  `methods.text`; a **Copy** that prefixes `[AI-generated]` when the last shown draft was AI (Phase 5 #11
  symmetry), else copies verbatim; a **"Reset to generated"** control that restores `methods.text`.
- **AskAi extension needed** (small): `mode="draft"` must render the result **into an editable textarea**
  and expose the edited text. Add an optional `onDraftChange?(text: string)` + seed the textarea from the
  explain result; keep `mode="advisory"` read-only (unchanged). Decide at build time whether the textarea
  lives inside AskAi (keeps the composer self-contained) or in the `Methods` section with AskAi only
  supplying the chat+seed (keeps AskAi read-only and the edit state with the owner of the text). **Lean:
  the textarea + edit state live in `Methods`; AskAi stays the input+seed+result surface** (advisory and
  draft then differ only in whether the caller lifts the result into an editable field).

## Tests

- **BE** (`test_methods_draft.py`): `_deterministic_explain("draft_methods", {base_text})` returns
  `base_text` verbatim; the endpoint returns `source="deterministic"` gateway-off (no ✨) and `"ai"` when a
  stub gateway changes the text; `draft_methods` records no gap; the operator recording replays + the
  well-formed recordings test still passes.
- **FE** (`api.test.ts`): `explain(draft_methods)` threads `base_text` + returns the polished text; MSW
  `draft_methods` branch (returns `base_text` as the deterministic mock). A `publish-confidence` render
  test: the "Draft methods" seed fills the textarea from `methods.text`; the AI-mark shows only on
  `source==="ai"`; Copy carries `[AI-generated]` only for an AI draft. (Rendering batches into the
  milestone fe-review too.)

## Sequencing & review

One slice (BE + FE together — it's small). Per-slice gate = tsc/eslint/vitest + BE fast gate + ruff + a
targeted check (the deterministic `base_text` fallback round-trips). **No `review-gauntlet` / `fe-review`
yet** — per the owner directive (2026-07-01) all Layer A reviews are **batched to one pass after Phases
2c + 3 + 4 + 5 are all done**. After Phase 4, build Phase 5 (the FE polish backlog), then run the single
batched milestone verify + gauntlet + fe-review.

## Open items to confirm at build time

1. **The design decision above (A/B/C).** Default A (in-place, session-only) unless the owner wants
   persistence.
2. **AskAi draft-mode shape** — textarea-in-`Methods` vs textarea-in-AskAi (lean: in `Methods`).
3. **`base_text` size** — methods text is short (a paragraph); no truncation needed. Confirm the live
   prompt preserves citations (they render separately from `methods.text`; the draft polishes the prose,
   the citation list stays deterministic).

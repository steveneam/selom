# AI Helpers — S5 Frontend (attribution + Activity feed)

_Spec · 2026-06-29 · the FE capstone of the AI-Helpers initiative. Build via the design skills
(impeccable / ui-ux-pro-max / frontend-design); verify on real data + a live backend, not dev:mock._

## What

The user-facing layer over the S1–S4 backend: AI proposals surfaced in the existing pending-changes
banner with a per-author **counter**, a distinct **✨ AI attribution marker** on touched controls, an
**AI panel** (Activity feed + gap backlog), all consuming the four endpoints already shipped.

## Decisions (locked with owner, 2026-06-29)

1. **AI accent = a NEW distinct hue** — `--stage-ai` ≈ **fuchsia `#d946ef`**, orthogonal to the
   existing axes (amber `--stage-figuredata` / cyan `--stage-figure` / violet `--stage-skill`). The
   spec's earlier "violet ✨" is superseded — violet is already the skill stage; reusing it would
   conflate "AI-touched" with "skill stage."
2. **Focused AI panel now** — a right-side panel reusing the `FigureDataPanel` dock pattern + Radix
   `Tabs` (**Activity** | **Gaps**). The full conversational Ask-Selom chat dock stays its own future
   Pillar-3 feature; S5 does not build it.
3. **Separate proposal queue, same banner, with a derived author counter** — AI proposals land in a
   separate `aiProposals[]` queue rendered IN the existing pending-changes banner; each is ✨-tagged;
   the user accepts/reverts each before the one explicit re-run.

## The counter (owner refinement)

The banner header shows a **derived, author-partitioned count**: `N pending · X you · Y ✨AI`.
- **Derived, not stored**: `N = count(params where staged ≠ base)`; each pending param carries an
  `author` (`user` | `ai`) = whoever set the *current* staged value. Single source of truth = the
  staged-vs-base diff + the author map; no manual counter to drift.
- **Reactive**: revert a value to **base** (`fdBaseParams`, the figure's current run values) → it
  leaves the diff → the count auto-decrements (the ✨ tally drops if it was an AI row); revert all →
  `N=0` → `fdDirty` false → the banner clears itself (existing behaviour). Editing an AI-proposed
  value yourself moves it from the ✨ bucket to the "you" bucket.
- "Base" = the figure's current params, NOT the skill default ("reset to skill default" is a separate
  gesture, out of scope here).
- The ✨ count is mirrored as a small badge on the AI panel's **Activity** tab.

## Backend contract (already shipped — a stable target)

- `POST /ai/propose` → `HelperTurn` (`{goal, plan, results, staged_params, figure_spec, gaps, provenance_actions}`).
- `POST /ai/apply` (multipart: `matrix, skill_id, goal, override, params, ai_actions`) → the run result
  (figure/table/**provenance.actions[]**/data_fit/…). **Rejects** empty/malformed `ai_actions` (400);
  `ai_actions` entries must be `{actor:"ai", type, target, …}`.
- `GET /ai/gaps` → ranked, categorized backlog `[{context_hash, stage, unmet, category, skill_id, count, sample_attempt}]`.
- `POST /ai/explain` (`{request: explain_score|propose_sweep, scorecard?, sweep_space?, goal}`) →
  `{request, text, source}` (`source="deterministic"` when the gateway is off — degrade-clean).
- Provenance action shape: `{action_id, actor, type, target, prompt, model, approved_by, approved_at}`.
- Default OFF: live AI needs `SELOM_AI_GATEWAY=live` + `ANTHROPIC_API_KEY`; without it the gateway is
  `Null` (empty proposals) / explain falls back to deterministic text. **S5 works without a key** — the
  panel + markers render from recorded/operator data; live proposal text awaits the key (its own step).

## Build pieces (map to spec S5 a–d)

| Piece | Where | Notes |
|---|---|---|
| **`lib/ai/api.ts` + `lib/ai/types.ts`** | new feature dir | propose/apply/gaps/explain typed wrappers (mirror `lib/extract/api.ts`); `AiProposal`, `CapabilityGap`, `AiAction` types. No flat file at `lib/` root; no barrel. |
| **`--stage-ai` token** | `app/globals.css` + Tailwind map | fuchsia; light/dark check. |
| **`components/ai/ai-marker.tsx`** (a) | on capability-gated controls (`figure-model.ts` surface) | ✨ glyph (lucide `Sparkles`); **hollow = proposed**, **filled+muted = applied**; hover tooltip = actor · model · approved-at + **click-to-revert**; never colour-only (glyph + tooltip). |
| **Banner extension** (b) | `project-workspace.tsx` (~786–800) | render `aiProposals[]` rows in the existing amber banner; the author counter header; per-row accept/revert; accept → stage into `fdParams`; one explicit `rerunFigureWithParams` → `/ai/apply`. |
| **`components/ai/ai-activity-feed.tsx`** (c) | the AI panel, **Activity** tab | reverse-chron, plain-language, derived from `provenance.actions[]`; per-entry status chip + revert; grouped by turn/goal; the audit/export surface. |
| **`components/ai/capability-gap-view.tsx`** (d) | the AI panel, **Gaps** tab | reads `GET /ai/gaps`; ranked + by `category` (incl. `engine_capability_missing` → the P1 engine backlog). Read-only. |
| **`components/ai/ai-panel.tsx`** | right dock (FigureDataPanel pattern + `Tabs`) | container: Activity | Gaps; ✨ badge on Activity. |
| **`Figure.aiProposals?: AiProposal[]`** | `lib/projects/types.ts` | additive; persisted with the project. |

## The loop (FE)

propose (`/ai/propose` with figure context) → proposals enter `aiProposals[]` (✨ hollow, in the
banner, counted) → user accepts/reverts each → accepted ones stage into `fdParams` → **one explicit
re-run** (`rerunFigureWithParams` → `/ai/apply` with the approved `ai_actions`) → result carries
`provenance.actions[]` (markers go ✨ filled) → the Activity feed shows it. Cosmetic actions
(restyle/relabel) apply live client-side (the figure store `set`/`commit`); recompute actions stage.

## Invariants (FE)

- **No duplicate state**: the counter is derived from the staged-vs-base diff; the marker + feed are
  views over `aiProposals[]` / `provenance.actions[]`. One source each.
- **Marker is never colour-only** (glyph + tooltip) — accessibility.
- **AI text degrades clean**: with the gateway off, the panel shows recorded/deterministic content,
  never errors or empty-crashes.
- **Reproducibility surfaced, not invented**: the feed renders what the backend recorded; revert =
  undo the staged value (back to base); the re-run is the single deterministic apply.

## Out of scope

- The full conversational Ask-Selom chat dock (future Pillar-3).
- Live AI-text verification (needs `ANTHROPIC_API_KEY`) — its own step once a key is set.
- Server-trusted / non-forgeable actor-tag (the `/ai/apply` backlog comment) — a backend/contract
  follow-on; S5 posts the actor-tagged actions the HelperTurn produced.
- The P1 ingest engine hooks (`docs/p1-ingest-engine-hooks/spec.md`) — deferred engine slice.

## Testing / verification

- vitest for the marker state machine + tooltip/revert, the derived author counter (revert
  decrements, all-revert clears the banner), the `lib/ai/api.ts` wrappers (mock the 4 endpoints).
- **Browser-verify on real data + a live backend** (`npx next dev --webpack` + a live uvicorn on a
  non-:8000 port, real figure), NOT dev:mock — mocks prove the wire, not the content
  ([[verify-on-real-data-not-mock]]). Snapshot localStorage before any live-store probe
  ([[selom-fe-probe-autopersist-gotcha]]). Extend the MSW mock + persistence handlers for `/ai/*`.
- Keep the structure guards green (lib feature-dir, no barrel, `dynamic(ssr:false)` for heavy libs).

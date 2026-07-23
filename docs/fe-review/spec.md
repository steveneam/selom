# Selom FE-Review Framework

_Spec · 2026-06-30 · a lightweight, Selom-specific review layer so the assistant catches
interaction / layout / affordance gaps **by default** on every frontend change — instead of the
owner having to point them out._

## What

**The third tool in the Selom operating layer.** Alongside **review-gauntlet** (the *correctness*
review — parallel invariant lenses over a diff, adversarially verified) and **retro** (the
*reflect* tool), `fe-review` is the **FE-interaction review** — the front-end counterpart of the
gauntlet. Same shape (parallel lenses → adversarially-verified findings), different axis:
interaction / layout / affordance instead of correctness / invariants. It is delivered as a
**workflow peer** (`.claude/workflows/fe-review.js`, invoked by `scriptPath` like its siblings)
governed by one mutation-lifecycle lens (V·R·D·A·R·N) plus two FE-specific gates, wired into the
Selom Playbook so it runs by default on FE diffs. It **orchestrates** the design skills
(ui-ux-pro-max + impeccable — **`frontend-design` dropped 2026-07-23**; it doesn't compose with
`impeccable`, which is the more capable and covers generation itself) — it does not rewrite them.

## Context

**Why this exists (a real miss, AI-Helpers S5, 2026-06-30).** Building the S5 AI-attribution UI, the
assistant ran `impeccable audit` — a *static, per-component, technical* pass (a11y / perf / theming /
anti-patterns) — and reported 18/20. But the owner then had to manually flag six issues the audit
structurally could not catch:

1. **Missing** changed-control highlight (no "which input did I touch?" signal).
2. **Missing** Reset-to-previous-values affordance.
3. The data-check header didn't **read** as a toggle (no hover/affordance) → "doesn't do anything".
4. Adding a Reset button **cramped** neighbouring helper text at the 360px figure-data dock width.
5. The AI panel (fixed dock) **overlaid** the Re-run button (covered the primary action).
6. The Activity History row **omitted** the applied value (`n_neighbors` with no `→ 30`).

Root cause is process/altitude, not the skills:
- (1)(2)(6) are **missing affordances** — no audit of *existing code* can find a feature that isn't
  there; they come from a **user-task walkthrough** done *before* building.
- (3) is an **affordance-discoverability** heuristic — impeccable has a `critique` mode (Nielsen
  heuristics) that targets exactly this, but the assistant ran `audit` (technical) instead.
- (4)(5) are **layout regressions only visible rendered**, at the *real* container width with the
  *real* neighbours — a static per-component audit cannot see "these don't fit in 360px".

The owner's six pieces of feedback are themselves a coherent lens (see Design). The fix is to
codify that lens + the two missing passes so the assistant runs them without being asked.

**What exists today.**
- Design skills (CLAUDE.md "## Coding Guidelines" + the Playbook dispatch table):
  **ui-ux-pro-max** (a searchable design knowledge DB) + **impeccable** (`audit` technical /
  `critique` heuristic / `polish` / generation; installed locally at `.claude/skills/impeccable/`,
  gitignored). **`frontend-design` was dropped** (owner 2026-07-23): it and `impeccable` don't
  compose, and `impeccable` is the more capable skill and covers generation itself.
- The **Selom Playbook** (`docs/operating/playbook.md` + the CLAUDE.md dispatch table) already
  routes "FE work or any FE audit/review → the design skills". This spec makes that row point at
  the new review skill, which then fans out to the two.
- Selom's design system: stage tokens in `app/frontend/app/globals.css`
  (`--stage-ai` fuchsia · `--stage-figuredata` amber · `--stage-figure` cyan · `--stage-skill`
  violet · `--stage-data` blue · `--stage-publish` green); the `TintChip` tinted-pill vocabulary;
  fixed **360px** docks (the figure-data dock, the AI panel); **desktop-only** widths
  ([[selom-desktop-only]] — verify at desktop, not mobile); the provenance / "AI compiles away"
  model (`provenance.params` + `provenance.actions[]`).

## Requirements

R1. A workflow at `.claude/workflows/fe-review.js`, a **peer to `review-gauntlet.js` and
`retro.js`** (invoked via `Workflow({scriptPath})`), that produces a review of an FE change against
the lens below — **scoped to a diff or a named surface**, not the whole app — fanning the lenses out
as parallel agents and adversarially verifying each finding before it survives (the gauntlet's
shape, applied to the interaction axis).

R2. The skill MUST apply the **mutation-lifecycle lens (V·R·D·A·R·N)** to every user- or
AI-initiated state change in scope:

| Letter | Lens | The question | S5 example that exposed it |
|---|---|---|---|
| **V** | Visible | Can the user see what changed? | changed-control amber highlight |
| **R** | Reversible | Can they undo / reset it? | Reset-to-previous values |
| **D** | Discoverable | Does the control look interactive? | data-check toggle affordance |
| **A** | Attributable | Who changed it (user vs AI)? | the ✨ `--stage-ai` marker |
| **R** | Recorded | Is it in backend provenance? | `provenance.params` / `actions[]` |
| **N** | Non-breaking | Did it regress a neighbour / layout? | cramped text, panel overlap |

R3. The skill MUST require two passes the static audit lacked, as **definition-of-done gates**:
- **G1 · User-task walkthrough (before/while building).** Enumerate the user's jobs-to-be-done for
  the surface; for each, confirm the affordance exists. This is the gate that surfaces *missing*
  features. Output: a short JTBD list with ✓ / gap per task.
- **G2 · Rendered-in-context review (before "done").** Open the *real* rendered surface at the
  *real* container width(s) (e.g. the 360px dock) with the *real* adjacent components, and walk the
  task in the browser (the existing `browser-verify` / chrome-devtools path). Catch layout
  regressions and overlap. Output: at least one screenshot per changed surface + a pass/fail note.

R4. The skill MUST dispatch the **correct** impeccable mode, not default to one:
- interaction / affordance / heuristics / "feels off" → `impeccable critique`;
- a11y / perf / theming / responsive / anti-patterns → `impeccable audit`;
- new visual generation → `impeccable` (generation / `polish`); design-knowledge lookups → `ui-ux-pro-max`.
It records which modes it ran and why.

R5. The lens checks MUST be **grounded in Selom's system**, not generic: V/A reference the stage
tokens + `TintChip` (amber = figure-data/pending, fuchsia `--stage-ai` = AI); R(ecorded) references
the provenance model; N references the 360px docks + desktop-only widths.

R6. The workflow MUST be **lean** — a single `fe-review.js` (the size/idiom of `review-gauntlet.js`),
no scoring ritual. The output is a short report: the JTBD list (G1), the V·R·D·A·R·N findings
(confirmed only), the rendered-pass screenshots (G2), and a prioritized fix list. The failure mode
to avoid is a heavy checklist nobody runs.

R7. The Selom Playbook dispatch row for FE work MUST point at `/fe-review` as the entry point
(which fans out to the design skills), and a lean memory pointer MUST be added so the habit
survives across sessions.

## Design

### Deliverable shape (Decision D1)

Three artifacts, mirroring how `review-gauntlet` + `retro` already ship:

1. **`.claude/workflows/fe-review.js`** — the workflow (peer to `review-gauntlet.js` /
   `retro.js`; read both first to match their `meta` + `agent()`/`parallel()`/`pipeline()` idiom).
   Stages:
   - **G1 · user-task walkthrough** (one agent): enumerate the surface's jobs-to-be-done from the
     diff + the rendered surface, mark each ✓ / gap. This is the stage that surfaces *missing*
     affordances (which no audit of existing code can find).
   - **V·R·D·A·R·N fan-out** (parallel agents, one lens each): each lens-agent inspects the diff
     against its Selom-grounded check (R2/R5) and proposes findings; **each finding is then
     adversarially verified** by a second agent before it survives (the gauntlet pattern). Lenses
     dispatch the right impeccable mode in-prompt (critique for D/V/N, audit for a11y/perf — R4).
   - **G2 · rendered-in-context** (one agent, when a dev server is reachable): drive chrome-devtools
     at the real container width(s) + real neighbours, screenshot each changed surface, walk the
     task. When no dev server is up, the workflow emits G2 as a **required inline gate** for the main
     loop to perform (it holds the live browser) — never silently skipped. Verify on real data + a
     live backend, not dev:mock ([[verify-on-real-data-not-mock]]).
   - **synthesize** (one agent): the lean report (R6).
2. **Playbook + CLAUDE.md dispatch update** — the "Reviewing a diff / before commit" pipeline gains
   `fe-review` as the FE counterpart to `review-gauntlet` (gauntlet = correctness, fe-review =
   interaction); the "FE work / any FE audit" row routes through it. Invoke by `scriptPath` (the
   `.claude/` registry only loads at session start, same caveat as the other workflows).
3. **Memory** — `selom-fe-review-framework` (How-I-work bucket) + a one-line MEMORY.md pointer: the
   V·R·D·A·R·N lens + the two gates + "the FE peer of review-gauntlet; run by default on FE diffs".

### How it runs (flow)

```
Workflow({scriptPath:".claude/workflows/fe-review.js", args:{scope}})
  → G1 user-task walkthrough   → JTBD list, mark gaps (MISSING affordances)
  → V·R·D·A·R·N parallel lenses → findings, each adversarially verified (gauntlet shape)
  → G2 rendered-in-context      → browser at real widths + neighbours, screenshots, walk the task
                                  (or emit as a required inline gate if no dev server)
  → synthesize                  → report: JTBD ✓/gap · confirmed lens findings (P0–P3) · shots · fixes
```

It is a **review** workflow (confirmed findings + a fix list); it does not auto-fix. Fixes route to
the implement/refactor path or `impeccable polish`, then `fe-review` re-runs to confirm.

### Relationship to the operating layer + design skills

`fe-review` sits beside `review-gauntlet` and `retro` as the third operating tool, and **conducts**
the three design skills (the *instruments*): it decides which impeccable mode to call per lens,
enforces the two gates, and applies the Selom-grounded lens — never duplicating their content. Split
of duties on a diff: **review-gauntlet** = correctness / Selom invariants (the backend-and-logic
axis); **fe-review** = interaction / layout / affordance (the FE axis). Run both on an FE diff that
also changes logic; fe-review alone on a pure-presentational diff.

## Decisions

- **D1 · Deliverable = a workflow peer to review-gauntlet/retro** (`.claude/workflows/fe-review.js`),
  not a local skill and not a doc-only checklist. Why: the owner framed VRDARN as "another tool like
  the gauntlet and the retro" — those are workflows, and the parallel-lens + adversarial-verify shape
  is exactly the gauntlet's. A workflow gives the lens fan-out + verification for free and sits in the
  same operating family/dispatch. A doc-only checklist is the "nobody runs it" failure mode (R6).
  Reversible: yes (delete the script, revert the Playbook line). _Alternative considered:_ a local
  `.claude/skills/fe-review` skill (lighter, inline, natural for the browser pass) — rejected for the
  family symmetry, but its strength (the interactive G2 browser pass) is preserved via the inline-gate
  fallback when no dev server is up.
- **D2 · Orchestrate, don't rewrite** the three design skills. Why: they're mature, single-purpose
  engines; the gap was *routing + two missing passes*, not their content. Reversible: yes.
- **D3 · The lens is V·R·D·A·R·N**, named and fixed, because it maps 1:1 to the six real misses and
  is memorable. Reversible: yes (the letters can grow/shrink as we learn).
- **D4 · G2 (rendered-in-context) is mandatory, not optional.** Why: 4 of 6 misses were only visible
  rendered. Cost: a browser pass per FE change. Mitigation: batch per [[stack-browser-verification]]
  (one end-of-work pass), scope to changed surfaces, and run it inline (main loop holds the browser)
  when the workflow can't. Reversible: yes, but skipping it defeats the purpose.
- **D5 · `fe-review.js` is first-party + committed**, like `review-gauntlet.js` / `retro.js`
  (`.claude/workflows/` is tracked; only the vendored `impeccable` skill is gitignored). Reversible.

## Testing Strategy

This is a process skill, so "tests" are validation that it *works as a procedure*:
- **Backtest on S5.** Run `/fe-review` against this session's S5 diff and confirm it independently
  surfaces all six owner-reported issues (the changed-highlight gap, the Reset gap, the data-check
  affordance, the cramped text, the panel overlap, the missing History value). If it misses one,
  the lens or a gate is incomplete — fix before declaring done. This is the acceptance test.
- **Dogfood on the next FE change** and confirm the owner does not have to flag a V·R·D·A·R·N item
  the skill should have caught.
- **Lint/structure:** the SKILL.md parses + appears in the skill list; the Playbook + CLAUDE.md
  edits are consistent (no dangling reference); MEMORY.md pointer is one line.

## Out of Scope

- Rewriting or forking ui-ux-pro-max / impeccable (D2).
- Mobile/responsive breakpoints — Selom is desktop-only ([[selom-desktop-only]]); G2 verifies at
  desktop widths + the fixed dock widths only.
- A numeric scoring system (impeccable `audit` already scores; this layer is about coverage, not a
  grade).
- Backend review (this is the FE layer; backend has its own review-gauntlet lenses).
- Fixing the S5 polish items themselves (already in progress this session) — the spec only uses them
  as the backtest corpus.

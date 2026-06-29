# The Selom Playbook

_The named operating system for how this repo gets built — the reliable dispatch layer so the
right part fires by situation, not by re-prompting. Date-stamped 2026-06-29._

## What this is

The **Selom Playbook** is the same architecture we give the product, pointed inward: a **declared
set of parts** (agents · skills · workflows) + a **deterministic dispatch** (route by situation) +
a **gap-loop** (reflect → improve). It is the Action-Gateway pattern applied to my own work
(`generalize-via-flagged-plugins-over-shared-spine`). gstack chains personas via prompts; we express
the same discipline as composable parts + a deterministic Workflow, tuned to Selom's invariants.

## Reliability model — where dispatch lives

Three layers, different reliability. Put each rule in the layer that actually fires it:

| Layer | Reliability | Holds |
|---|---|---|
| **Memory** (`~/.claude/.../memory`, "How I work") | recall-based — surfaces when relevant | the **why** / lessons |
| **CLAUDE.md** (`## Operating Playbook`) | always in context, overrides defaults | the **dispatch table** — situation → part |
| **Hooks** (`settings.json`) | harness-enforced, not me remembering | the **automatic** bits (capture-on-Stop, guards) |

"Don't make me prompt you each time" = a lean dispatch table in CLAUDE.md + (later) a couple of hooks.

## Parts catalog

- **Plan / decide** — `AskUserQuestion` (forcing questions), `spec` (write + pause for review),
  `plan` (agile slices), `decision-critic` / `deepthink`.
- **Review** — **`review-gauntlet`** workflow (Selom lenses), `code-review` (incl. `ultra` cloud),
  `quality-reviewer` · `architect` agents, `security-review`, `simplify`.
- **Build** — `developer` agent, `implement`, `tdd`, `refactor`; `codex:rescue` for a second pass.
- **Verify** — `verify`, `browser-verify` (real data + live backend, not dev:mock), the EDR-safe
  test runner (uv-3.12 PY + `PYTHONPATH=.venv\Lib\site-packages`, fast gate `pytest -m "not slow"`).
- **Research** — `deep-research`, `context7` (live library docs), PubMed MCP (domain).
- **Design (FE)** — `impeccable`, `ui-ux-pro-max`, `frontend-design`, `ui-ux-consultant`.
- **Orchestrate** — `Workflow` (deterministic fan-out), background / git-worktree / remote agents.
- **Remember** — the Ratchet: one durable home per lesson + a lean memory pointer.

## Named pipelines (run end-to-end, the same way each time)

- **Design loop** — forcing-Qs (`AskUserQuestion`) → `spec` (pause) → `review-gauntlet` → owner
  approve → `developer` build → `verify` → `commit` → Ratchet. _(This is exactly what AI-Helpers
  S1 ran; codifying it means I run it without per-step steering.)_
- **Change review** — diff → `review-gauntlet` → fix the confirmed findings → `verify`.
- **Reflect** — consume the **CapabilityGap backlog** (AI-Helpers S4) + recent commits + `CURRENT.md`
  → propose the next spine improvements. The product's self-improving loop and this retro share one
  artifact (`compound-capability-each-task`).

## The review-gauntlet

Run via `Workflow({ scriptPath: ".claude/workflows/review-gauntlet.js", args: { scope } })` — a
deterministic gauntlet: fan out Selom-specific **invariant lenses** over a diff in parallel, then
**adversarially verify** each finding (refute-by-default) so only real issues survive. The lenses are
defined **inline in the workflow** (self-contained — no dependency on session-scoped custom-agent
registration).

> **Dogfood lesson (2026-06-29).** `.claude/agents` + `.claude/workflows` load only at **session
> start**, so a freshly-added workflow isn't `name`-resolvable and a fresh `agentType` won't resolve
> in the same session — **invoke by `scriptPath`**, and keep lens logic **inline** rather than as a
> custom `agentType`. On its first real run the gauntlet caught **2 real S1 issues** (a cosmetic-
> action data/contract backdoor + a fail-soft hole) that manual review and 858 tests had missed —
> the gap-loop paying for itself.

The lenses:

- **repro-integrity-lens** — "AI compiles away", actor-tagged provenance, the two-axis score, no AI
  on the score's critical path, honest classification (no silent caps).
- **spine-consistency-lens** — one shared spine, declared plug-ins (no id-branching), **no parallel
  validation path**, frozen contracts, package conventions, fail-soft honesty, a guard for every rule.
- **license-lens** — AGPL/GPL on the shipped path, data-license gates, clean-room boundaries,
  commercial-gated markers; verify the CURRENT license.
- **design-lens** — FE only (no-ops on backend diffs): AI-slop, the figure-edit UX model + colour
  axes (amber data / cyan styling / violet ✨ AI), desktop-only, accessibility, Phosphor icons.

Optional `args`: `{ scope: "the changes in HEAD~2..HEAD" }` etc. Default = the working-tree diff.

## Roadmap

- **Built now** — this playbook, the CLAUDE.md dispatch table, the `review-gauntlet` workflow (4
  inline, self-contained lenses; dogfood-hardened on its first real run).
- **Next (with AI-Helpers S4)** — the **Reflect** pipeline as a scheduled agent that consumes the
  CapabilityGap backlog.
- **At step-8 deploy** — a **canary + Web-Vitals-before/after** scheduled agent (Vercel MCP + Lighthouse).
- **Optional** — `settings.json` hooks (capture-lesson on Stop, destructive-command guard) via
  `update-config` — owner confirms before any settings change.

## Cross-refs

The "How I work" memory bucket is the *why* behind these parts: `the-ratchet-durable-artifacts`,
`compound-capability-each-task`, `reflect-checkpoint-during-phase-build`,
`generalize-via-flagged-plugins-over-shared-spine`, `evaluate-external-guides-critically`,
`step-back-build-helpers-when-stuck`, `verify-on-real-data-not-mock`, `selom-backend-python-exec`.

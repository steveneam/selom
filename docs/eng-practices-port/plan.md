# Engineering-Practices Port: Executable Ratchets Replace graphify + Thalon/Swordfish Hardening

> Status: PLAN (authored 2026-07-09). Plan-authoring only -- the owner authorizes every build and push.
> Plan id: `01cbe4f0-a9fb-4395-84e5-056aa21b9a70`.
> This document renders the validated plan for review; no milestone here is implemented yet.

## Overview

### Problem

graphify currently plays Selom's code-wiring-integrity role via two local git hooks that rebuild a
knowledge graph; that signal is documentary and rots between rebuilds. Meanwhile Selom lacks the CI
supply-chain hardening, wired pre-commit hygiene, single-env-reader / LLM-inventory ratchets,
worktree/parallel-lane tooling, and the lean handoff that the read-only reference repos `E:/thalon`
and `E:/swordfish` already have. The port must replace graphify's wiring role with executable
structural ratchet tests and bring those patterns into `D:/selom` without ever writing to `E:/`.

**Out of scope:** the parallel campaign itself (WS3 dedup + the on-hold backlog) which runs AFTER this
port; graphify's semantic-navigation use (kept if actively used); and the M6 deploy/ops ratchets
(deferred until the AWS backend deploy is live).

### Approach

Land the hardening + ratchet substrate as its OWN milestone bundle before the parallel campaign,
because the executable guards are the seam that makes lanes safe. Every enforcement gate ships the
**3-move discipline**: MEASURE (report-only, count) then CONFORM (repo to zero) then ENFORCE
(blocking CI + a wired pre-commit gated on exit code). Extend Selom's existing FE/BE guards rather
than rebuild; add a new file only for genuinely new concerns (repo-wide hygiene, the LLM call-site
inventory). Consolidate the two path-filtered CI workflows into one `ci.yml` with an always-run
aggregate `ci` job so a single stable required check works across a monorepo.

Sequence: M0a hygiene + M0b boundary/env + M1 LLM inventory + M2 CI + M3 worktree tooling + M4 lean
handoff; M5 graphify-retire is GATED on the ratchet suite going green; M6 ops ratchets are recorded,
not built.

### The doctrine (why this replaces graphify)

The **ratchet strength ladder** -- `executable > structural > config > documentary > memory` -- is the
graphify-replacement doctrine: keep the STRONGEST expression of each invariant and prune the weaker
restatement. graphify re-derives "what connects to what" from a rebuilt graph (documentary, rots
between rebuilds); an executable ratchet test asserts the same boundary at CI/commit time and fails
the build when it drifts. Once the ratchets are green in CI, graphify's hooks can retire.

## Sequencing & waves

The port is its own milestone bundle sequenced BEFORE the parallel campaign (owner-locked). Full
M0-M4 bundle; M5 graphify-retire GATED on the ratchet suite green in CI; M6 deferred until the AWS
deploy is live.

| Wave | Milestones | Rationale |
|---|---|---|
| W-001 | M-001 | The scanner + wired pre-commit is the substrate every later gate reuses; lands first, alone. |
| W-002 | M-002, M-003, M-004, M-005, M-006 | Boundary/env ratchets, LLM inventory, CI consolidation, worktree tooling, and lean handoff can proceed in parallel once the substrate exists. |
| W-003 | M-007, M-008 | Graphify retirement is GATED on M-001..M-004 green in CI; M6 ops ratchets are recorded, not built. |

| # | ID | Milestone | Port | Type |
|---|---|---|---|---|
| 1 | M-001 | Ratchet doctrine + repo-hygiene gates | M0a | build |
| 2 | M-002 | Boundary ratchets: single-env-reader + import-boundary | M0b | build / refactor |
| 3 | M-003 | LLM/AI call-site inventory + accessor allowlist | M1 | build (guard) |
| 4 | M-004 | CI supply-chain hardening + stable aggregate required-check | M2 | build (CI) |
| 5 | M-005 | Parallel-lane worktree tooling | M3 | build (tooling) |
| 6 | M-006 | Lean handoff, overwrite model | M4 | docs |
| 7 | M-007 | Graphify wiring-role retirement (GATED on M-001..M-004 green in CI) | M5 | cutover |
| 8 | M-008 | Deferred deploy/ops ratchets, recorded not built | M6 | docs-only |

---

## Milestones

### M-001 -- Ratchet doctrine + repo-hygiene gates (port M0a)

Flags: `needs-rationale`, `security`

**Files:** `CLAUDE.md`, `docs/hardening-port/gate-ledger.md`, `.githooks/pre-commit`,
`scripts/guards/hygiene-scan.mjs`, `.gitattributes`, `.githooks/post-commit`,
`.githooks/post-checkout`, `.gitignore`

**Requirements**

- Document the ratchet strength ladder (`executable > structural > config > documentary > memory`) as
  CLAUDE.md doctrine plus the guard-gating rule (enforce on exit code; never a `;`-chain).
- Ship one node scanner (`scripts/guards/hygiene-scan.mjs`) that flags merge-conflict markers; a
  missing single trailing newline; and forbidden tokens (secrets/keys; `dev:mock` ship-blockers;
  AGPL-tainted refs); patterns are fragment-assembled so the scanner passes its own scan; `--all`
  scans `git ls-files`; `--staged` scans staged files.
- Wire a tracked `.githooks/pre-commit` selected by `core.hooksPath=.githooks` that runs the scanner
  on staged files and aborts the commit on non-zero exit.
- MEASURE first: run the scanner report-only over the tracked set; record the baseline count in
  `gate-ledger.md`; and CONFORM any hits to zero before ENFORCE.
- Pin LF normalization via `.gitattributes` so a CRLF line cannot smuggle a conflict marker past a
  carriage-return-naive matcher.
- Because `core.hooksPath=.githooks` makes Git ignore `.git/hooks/` entirely, MIGRATE graphify's two
  local hooks (`.git/hooks/post-commit` + `post-checkout`) into `.githooks/` in the SAME cutover so
  they keep firing; keep them local/untracked by gitignoring `.githooks/post-commit` +
  `.githooks/post-checkout` (only `.githooks/pre-commit` is tracked); the gated retirement stays in
  M-007, not here.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-001-001 | `CLAUDE.md` | Add the ratchet strength ladder doctrine as the graphify-replacement principle, plus the guard-gating rule (enforcement is on a guard's exit code, never a `;`-chained side effect); new invariants keep their strongest expression and prune weaker restatements. | DL-001, DL-005 |
| CI-M-001-002 | `scripts/guards/hygiene-scan.mjs` | Node scanner whose forbidden-token / merge-conflict-marker / single-trailing-newline patterns are fragment-assembled so it passes its own scan; `--all` scans the `git ls-files` tracked set (CI semantics), `--staged` scans staged files (hook semantics); exit non-zero on any hit with a per-hit `file:line` message. | DL-006 |
| CI-M-001-003 | `.githooks/pre-commit` | POSIX-sh hook, selected repo-wide by `core.hooksPath=.githooks`, runs `node scripts/guards/hygiene-scan.mjs --staged` and returns its exit code so a non-zero result aborts the commit; no skip-env backdoor. | DL-005 |
| CI-M-001-004 | `docs/hardening-port/gate-ledger.md` | The 3-move tracker: one row per gate recording the MEASURE baseline count, the CONFORM status, and the ENFORCE wiring, with MEASURE recorded before ENFORCE lands. | DL-002 |
| CI-M-001-005 | `.gitattributes` | LF-normalize tracked text files so a CRLF line cannot smuggle a conflict marker past a carriage-return-naive matcher. | DL-006 |
| CI-M-001-006 | `.githooks/post-commit` (+`post-checkout`, `.gitignore`) | In the `core.hooksPath` cutover, MOVE graphify's two local hooks into `.githooks/` so Git keeps firing them until M-007's gated retirement; keep them untracked via `.gitignore`; only `.githooks/pre-commit` is tracked; no graphify hook is retired here. | DL-005, DL-010 |

**Acceptance criteria**

- `hygiene-scan.mjs --all` exits 0 on the conforming tree and non-zero when a conflict marker,
  forbidden token, or missing trailing newline is introduced into a tracked file.
- A staged commit containing a forbidden token is blocked by `.githooks/pre-commit` (non-zero exit).
- `gate-ledger.md` records each gate at MEASURE/CONFORM/ENFORCE with its measured baseline count.
- The scanner does not flag itself (fragment-assembled patterns).
- After the `core.hooksPath` cutover graphify's post-commit/post-checkout still run from `.githooks/`
  (migrated); they stay untracked (`git ls-files` shows only `.githooks/pre-commit`); no graphify
  hook is retired in this milestone.

**Tests:** `scripts/guards/hygiene-scan.mjs`

---

### M-002 -- Boundary ratchets: single-env-reader + import-boundary (port M0b)

Flags: `needs-rationale`, `refactor`

**Files:** `app/backend/config.py`, `app/backend/skills/_engine.py`,
`app/backend/skills/umap_scrna/run.py`, `app/backend/paper_metadata.py`,
`app/backend/litsynth/pubmed.py`, `app/backend/litsynth/lookup.py`, `app/backend/routers/ai.py`,
`app/backend/tests/test_structure_guard.py`, `app/frontend/lib/config/env.ts`,
`app/frontend/app/msw-provider.tsx`, `app/frontend/components/project/data-panel.tsx`,
`app/frontend/components/project/project-workspace.tsx`, `app/frontend/lib/structure.guard.test.ts`

**Requirements**

- MEASURE: enumerate every `os.environ`/`os.getenv` read AND write in `app/backend` (17 across 13
  files) and every app-config `process.env` read in `app/frontend`; record counts and the
  environmental-allowlist set in `gate-ledger.md`; include the runtime-override WRITERS
  `reproduction/papers/hani.py` + `dorgau.py` (`SELOM_UMAP_ENGINE`).
- CONFORM backend: route app-config env READS through `config.Settings` (add typed fields for
  `SELOM_OPENALEX_EMAIL` / `SELOM_NCBI_*`, `SELOM_CITATION_CACHE`, `SELOM_PAPER_METADATA_CACHE`,
  `SELOM_SKILLS_ENGINE`, and the `ANTHROPIC_API_KEY` presence check); expose `SELOM_UMAP_ENGINE` via a
  LIVE `Settings` accessor that re-reads env at call time so the reproduction runtime-override still
  works; leave genuinely environmental probes (`AWS_LAMBDA_FUNCTION_NAME`, `LOCALAPPDATA`) and the
  repro/test override WRITERS (`hani.py`, `dorgau.py`, tests) allowlisted, not moved.
- CONFORM frontend: add `lib/config/env.ts` as the single accessor for app-config vars
  (`NEXT_PUBLIC_API_MOCKING`, `API_PROXY_TARGET`) and route
  `msw-provider`/`data-panel`/`project-workspace` through it; allowlist `NODE_ENV` and build/framework
  reads (`next.config.ts`, `scripts/`, `figure-canvas.tsx`, `params.ts`).
- ENFORCE env: extend `test_structure_guard.py` (BE) and `structure.guard.test.ts` (FE) to fail when
  any non-allowlisted module reads OR writes app-config env directly; the BE allowlist is `config.py`
  + `db/engine.py` + `oracle.py` + tests + `reproduction/papers/hani.py` + `dorgau.py` so CONFORM lands
  a zero count.
- ENFORCE boundary: extend both guards so `routers/` (BE) do not import engine internals and the FE
  `lib/` import boundaries hold.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-002-001 | `app/backend/config.py` | Add typed `Settings` fields for the app-config vars read ad hoc (`SELOM_UMAP_ENGINE`, `SELOM_OPENALEX_EMAIL` / `SELOM_NCBI_TOOL` / `SELOM_NCBI_EMAIL` / `SELOM_NCBI_API_KEY`, `SELOM_CITATION_CACHE`, `SELOM_PAPER_METADATA_CACHE`) and an accessor for the `ANTHROPIC_API_KEY` presence check; existing fields/validators unchanged. | DL-007 |
| CI-M-002-002 | `app/backend/skills/_engine.py` | Read `SELOM_SKILLS_ENGINE` via `config.Settings` instead of `os.environ`; apply the same conform to the other MEASURE-identified readers (`paper_metadata.py`, `litsynth/pubmed.py`, `litsynth/lookup.py`, `routers/ai.py` `ANTHROPIC_API_KEY`); for `SELOM_UMAP_ENGINE` read via a LIVE `Settings` accessor that re-reads `os.environ` at call time so the reproduction runtime override is honored; behavior preserved. | DL-007 |
| CI-M-002-003 | `app/backend/tests/test_structure_guard.py` | Add a single-env-reader case (`os.environ`/`os.getenv` only in `config.py` plus explicit allowlist: env probes `db/engine.py`, `oracle.py`; setup/override writers in tests + `hani.py` + `dorgau.py`) and a routers-do-not-import-engine-internals import-boundary case. | DL-007, DL-003 |
| CI-M-002-004 | `app/frontend/lib/config/env.ts` | Single FE accessor for app-config vars (`NEXT_PUBLIC_API_MOCKING`, `API_PROXY_TARGET`) via typed getters; route `msw-provider.tsx`, `data-panel.tsx`, `project-workspace.tsx` through it. | DL-007 |
| CI-M-002-005 | `app/frontend/lib/structure.guard.test.ts` | Add a single-env-reader FE case (app-config `process.env` only in `lib/config/env.ts`, with `NODE_ENV` + build/framework reads allowlisted) and an FE import-boundary case consistent with existing `lib/` rules. | DL-007, DL-003 |

**Acceptance criteria**

- Backend fast gate green (ruff + `pytest -m 'not slow'`) after conform; a new `os.environ` read
  outside `config.py` (non-allowlisted) fails `test_structure_guard.py`.
- Frontend tsc + eslint + vitest green; a new app-config `process.env` read outside `lib/config/env.ts`
  (non-allowlisted) fails `structure.guard.test.ts`.
- A router importing an engine-internal module fails the import-boundary case.
- Behavior unchanged: the same env vars select the same backends; verified live on the BE at `:8010`
  and the FE via `next dev --webpack`.
- The `SELOM_UMAP_ENGINE` reproduction override still selects scanpy at run time via the live
  `Settings` accessor; the env guard allowlists `hani.py` + `dorgau.py` so the conform count is zero
  (no false red).

**Tests:** `app/backend/tests/test_structure_guard.py`, `app/frontend/lib/structure.guard.test.ts`

---

### M-003 -- LLM/AI call-site inventory + accessor allowlist (port M1)

Flags: `security`, `needs-rationale`

**Files:** `app/backend/tests/test_ai_call_site_inventory.py`

**Requirements**

- Pin the exact set of guarded AI operation labels across the gateway/explain surface (`draft_methods`,
  `draft_legend`, `grade_advice`, `explain_score`, `propose_sweep`, and the rest) so a new label or
  handler is red until EXPECTED is updated.
- Count the call sites of the `provenance.stamp_ai_actions` chokepoint and pin the caller set
  (`routers/ai.py`, `ai/execute.py`); a new stamping site is red.
- Restrict raw model-client / gateway construction (`AnthropicModel(...)`, `VercelAIGateway(...)`, the
  operator gateway factory) to an explicit file allowlist (`ai/gateway.py`,
  `ai/live/pydantic_gateway.py`) and assert each allowlisted path still exists.
- VERIFY only (build nothing): compare Selom's degrade-clean gateways to the `withGatewayGuard` shape
  (budget-assert -> trace span -> record usage) and record in `gate-ledger.md` whether metering is
  warranted as a deferred note.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-003-001 | `app/backend/tests/test_ai_call_site_inventory.py` | Pin the exact guarded operation-label set; count the `provenance.stamp_ai_actions` call sites and pin the caller set (`routers/ai.py`, `ai/execute.py`); restrict raw model-client / gateway construction to an allowlist (`ai/gateway.py`, `ai/live/pydantic_gateway.py`) and assert each path exists. A new site, new label, or out-of-allowlist construction fails with a message naming EXPECTED and the SPINE sentence to update. | DL-015 |

**Acceptance criteria**

- Adding a new stamp/gateway call site, or a new operation label, fails
  `test_ai_call_site_inventory.py` with a message naming the EXPECTED set and the SPINE sentence to
  update.
- Constructing a raw model client outside the allowlist fails the accessor-allowlist case; a stale
  allowlist entry (moved file) also fails.
- Backend fast gate green with the new guard included.

**Tests:** `app/backend/tests/test_ai_call_site_inventory.py`

---

### M-004 -- CI supply-chain hardening + stable aggregate required-check (port M2)

Flags: `security`, `needs-rationale`, `ci`

**Files:** `.github/workflows/ci.yml`, `.github/workflows/backend-ci.yml` (removed),
`.github/workflows/frontend-ci.yml` (removed), `renovate.json`, `docs/hardening-port/gate-ledger.md`

**Requirements**

- MEASURE first: run zizmor report-only over the existing workflows and COUNT the unpinned `uses:`
  refs + the workflows/jobs missing a `permissions` block; record the baseline in `gate-ledger.md`
  before any blocking zizmor job or SHA-pin/permissions CONFORM lands.
- Consolidate `backend-ci.yml` + `frontend-ci.yml` into one `ci.yml`: a changes-detection job + a
  backend job + a frontend job (each gated on its path changes; steps moved verbatim) + a hygiene job
  (runs `scripts/guards/hygiene-scan.mjs --all`; not path-filtered) + a zizmor workflow-lint job + a
  final aggregate `ci` job (needs all; `if: always()`) that passes iff no required job FAILED (skipped
  is ok).
- Declare least-privilege permissions (default `contents: read`) at the workflow and job level; widen
  only where a job needs it.
- SHA-pin every `uses:` to a full 40-char commit SHA with the version tag in a trailing comment.
- Add `renovate.json` (`extends config:recommended` + `helpers:pinGitHubActionDigests` + a timezone) to
  bump the pinned digests.
- Remove `backend-ci.yml` and `frontend-ci.yml` once `ci.yml` reproduces their jobs.
- VERIFY before ENFORCE (owner-run): confirm repo plan/visibility supports branch protection (GitHub
  Pro; `enforce_admins: false`) then require the single check name `ci`.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-004-001 | `.github/workflows/ci.yml` | The consolidated gate: changes-detection job; backend job (`SELOM_SKILLS_ENGINE=stub` for structure/contract only -- real deg/gsea validation deferred per DL-017) and frontend job (each path-gated; steps moved verbatim); hygiene job (`--all`, not path-filtered); zizmor workflow-lint job enabled only after the ledger MEASURE baseline shows zero findings; final aggregate `ci` job (needs all; `if: always()`) passing iff no required job FAILED. Least-privilege `permissions` default `contents: read`; every `uses:` is a 40-char SHA with the tag in a trailing comment. | DL-004, DL-008, DL-014, DL-017 |
| CI-M-004-002 | `renovate.json` | `extends config:recommended` + `helpers:pinGitHubActionDigests` + a timezone so pinned action digests are auto-bumped by PR. | DL-008 |
| CI-M-004-003 | `.github/workflows/backend-ci.yml` | Removed once `ci.yml` reproduces its steps verbatim as the backend job; its path-filtered required-check role is superseded by the stable aggregate `ci` job. | DL-004 |
| CI-M-004-004 | `.github/workflows/frontend-ci.yml` | Removed once `ci.yml` reproduces its steps verbatim as the frontend job (lint, tsc, vitest, next build). | DL-004 |
| CI-M-004-005 | `docs/hardening-port/gate-ledger.md` | Add the CI supply-chain gate row: MEASURE (zizmor report-only finding count + unpinned `uses:` count + count of workflows/jobs missing a `permissions` block) recorded FIRST; then CONFORM (SHA-pin all `uses:`, add least-privilege permissions) to zero; then ENFORCE (blocking zizmor job in `ci.yml`). The blocking job does not land before CONFORM proves zero. | DL-002, DL-008 |

**Acceptance criteria**

- On a docs-only PR the `ci` check reports success (backend + frontend skipped) with no stuck required
  check.
- On a backend-only PR the backend job runs; frontend is skipped; and `ci` passes iff backend passes.
- zizmor and hygiene jobs run on every PR regardless of path; a workflow-lint finding fails `ci`.
- Every `uses:` is a 40-char SHA and `renovate.json` validates.
- Branch protection requires exactly `ci` and the name is stable across future sharding.
- `gate-ledger.md` records the CI supply-chain gate at MEASURE (baseline unpinned + permissions count)
  then CONFORM (zero) then ENFORCE; the blocking zizmor job is not enabled until CONFORM shows zero
  findings.

**Tests:** `.github/workflows/ci.yml`

---

### M-005 -- Parallel-lane worktree tooling (port M3)

Flags: `needs-rationale`, `windows`

**Files:** `scripts/worktree-setup.ps1`, `app/frontend/scripts/guard-worktree-install.mjs`,
`app/frontend/package.json`, `.claude/settings.json`, `COORDINATION.md`,
`docs/operating/contract-window.md`

**Requirements**

- `guard-worktree-install.mjs` (`app/frontend/scripts/`): a preinstall that refuses `npm install`
  inside a git worktree (detects `.git`-as-a-file) so a lane cannot clobber the shared junctioned
  `node_modules`; wire it as the FE package's preinstall.
- `worktree-setup.ps1` (repo-root `scripts/`): junction the single `app/frontend/node_modules` and the
  BE `.venv` into a lane worktree; copy `.worktreeinclude` files; verify the FE+BE toolchain
  end-to-end; idempotent; pure-ASCII; document teardown as `cmd /c 'rmdir /s /q'` NEVER PowerShell
  `Remove-Item -Recurse` (junction-follow wipes MAIN `node_modules`) with a main `node_modules` count
  snapshot before/after.
- Add `worktree.symlinkDirectories: ['app/frontend/node_modules']` and an attribution block
  `{commit:'', pr:''}` to `.claude/settings.json` (makes the no-AI-signoff rule executable; the
  junction script is the real guarantee since `symlinkDirectories` needs admin).
- Extend `COORDINATION.md`: Mode A (<=2 lanes; in-session worktree subagents) vs Mode B (>2; the
  vscode method) threshold; one-web-writer-per-wave; pre-provision runtimes at lane prep; and the
  kill-by-port-listener rule.
- Add `docs/operating/contract-window.md`: freeze the FE contract types + BE schema before lanes fork;
  additive-only within a window; each invariant naming the exact executable test to extend in the same
  change; one window per sprint with one owner.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-005-001 | `app/frontend/scripts/guard-worktree-install.mjs` | Preinstall guard that refuses `npm install` inside a git worktree (detects `.git`-as-a-file) so a lane cannot clobber the shared junctioned `node_modules`; a no-op on the main tree. | DL-012 |
| CI-M-005-002 | `scripts/worktree-setup.ps1` | Idempotent, pure-ASCII operator script that junctions the single `app/frontend/node_modules` and the BE `.venv` into a lane worktree, copies `.worktreeinclude` files, and verifies the FE+BE toolchain; documents teardown as `cmd /c 'rmdir /s /q'` (never PowerShell `Remove-Item -Recurse`, which follows the junction and wipes MAIN `node_modules`) with a main `node_modules` count snapshot before/after, and kill-a-server-by-port-listener. | DL-012, DL-013 |
| CI-M-005-003 | `app/frontend/package.json` | Add a preinstall script that runs `node scripts/guard-worktree-install.mjs`; other scripts unchanged. | DL-012 |
| CI-M-005-004 | `.claude/settings.json` | Add `worktree.symlinkDirectories` = `app/frontend/node_modules` (recorded as admin-inert on the no-admin box -- the junction is the real guarantee) and set `includeCoAuthoredBy: false` (the real Claude Code key that suppresses the Co-Authored-By commit trailer and the Generated-with-Claude-Code PR footer) as the executable backing for the no-AI-signoff rule; an inert `attribution:{commit:'', pr:''}` marker may sit alongside as future-proofing but the commit-skill convention + CLAUDE.md rule remain the real guarantee. Existing model/permissions/plugins/effort/theme keys unchanged. | DL-012 |
| CI-M-005-005 | `COORDINATION.md` | Add the Mode A (<=2 lanes, in-session worktree subagents) vs Mode B (>2, the vscode method) threshold, one-web-writer-per-wave, pre-provision-runtimes-at-lane-prep, and the kill-by-port-listener rule. | DL-013 |
| CI-M-005-006 | `docs/operating/contract-window.md` | Freeze the FE contract types and BE schema before lanes fork; additive-only within a window (never rename/remove/tighten outside a window); each invariant names the exact executable test to extend in the same change; one window per sprint with one owner; referenced from the operating playbook. | DL-016, DL-018 |

**Acceptance criteria**

- Running `npm install` inside a worktree aborts with a clear message; a normal main-tree install is
  unaffected.
- `worktree-setup.ps1` provisions a lane (junctions present; `.worktreeinclude` copied; toolchain
  verified) and re-running is a no-op; the file is pure ASCII.
- `.claude/settings.json` parses as valid JSON with the new worktree + attribution keys.
- `COORDINATION.md` states the Mode A/B threshold, one-web-writer, and kill-by-port rule;
  `contract-window.md` exists and is referenced from the operating playbook.

**Tests:** `app/frontend/scripts/guard-worktree-install.mjs`

---

### M-006 -- Lean handoff, overwrite model (port M4)

Flags: `docs`

**Files:** `agent_handoff/README.md`, `agent_handoff/CURRENT.md`,
`agent_handoff/archive/2026-07-09-current-history.md`

**Requirements**

- Revise README hard-rule 1 from "supersede by append; history preserved" to an OVERWRITE model:
  per-session narrative lives in git commit messages + `archive/`; `CURRENT.md` carries only the live
  slots (a SESSIONS index row + LIVE/NEXT/DEFERRED/ENV/READ).
- Archive the existing `CURRENT.md` SESSIONS narrative to
  `agent_handoff/archive/2026-07-09-current-history.md` (write-once; verbatim).
- Compress `CURRENT.md` to the ~60-line slot skeleton: SESSIONS as one-line rows (CODENAME; date;
  sha-range; one-line); LIVE ~3 bullets; then NEXT/DEFERRED/ENV/READ short lists and the Codex section.
- Reconcile the README's neighboring rules that reference the append model so no rule contradicts
  overwrite.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-006-001 | `agent_handoff/README.md` | Revise hard-rule 1 from supersede-by-append to the overwrite model (per-session narrative in commit messages + `archive/`, `CURRENT.md` = live slots) and reconcile neighboring rules so none still says append; keep the CURRENT.md-shape section that already prescribes the lean slots. | DL-011 |
| CI-M-006-002 | `agent_handoff/CURRENT.md` | Compress to the ~60-line slot skeleton: SESSIONS as one-line rows (CODENAME, date, sha-range, one-line), a LIVE block of ~3 bullets, then NEXT/DEFERRED/ENV/READ short lists and the Codex section; the multi-paragraph SESSIONS narrative is moved out. | DL-011 |
| CI-M-006-003 | `agent_handoff/archive/2026-07-09-current-history.md` | A write-once verbatim archive of the prior CURRENT.md SESSIONS narrative so no history is destroyed by the compression. | DL-011 |

**Acceptance criteria**

- `CURRENT.md` is about 60-80 lines and every SESSIONS row is a single line; the prior narrative is
  preserved verbatim in `archive/2026-07-09-current-history.md`.
- README rule 1 describes overwrite with git+archive history and no remaining rule says "append".
- The board-hygiene guard (single trailing newline; no conflict markers) passes on both files.

**Tests:** `agent_handoff/CURRENT.md`

---

### M-007 -- Graphify wiring-role retirement (port M5) -- GATED on M-001..M-004 green in CI

Flags: `needs-rationale`, `gated`

**Files:** `.githooks/post-commit`, `.githooks/post-checkout`, `.gitignore`

**Requirements**

- GATE: proceed only once the structural ratchet suite (M0a hygiene M-001 + M0b boundary/env M-002 +
  M1 LLM inventory M-003) is green IN CI; that CI-green state requires M2 (M-004) `ci.yml` to actually
  run those guard jobs; so the effective gate is M-001 through M-004 all green in CI.
- Remove the two MIGRATED local graphify hooks (`.githooks/post-commit` + `.githooks/post-checkout`
  that M-001 relocated); they are gitignored/untracked so this is not an untrack step; drop their two
  `.gitignore` lines and optionally delete the local `graphify-out/` directory.
- CONFIRM at execution whether any graphify semantic-navigation use is active; keep it only if used;
  retire only the wiring-integrity role.
- Update the graphify memory pointer (user memory; outside the repo) to reflect the retired wiring role.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-007-001 | `.git/hooks/post-commit` | Remove the graphify post-commit auto-rebuild hook once the ratchet suite (M0a+M0b+M1) is green in CI; `graphify-out/` is already gitignored so no untrack step is needed. | DL-010 |
| CI-M-007-002 | `.git/hooks/post-checkout` | Remove the graphify post-checkout auto-rebuild hook once the ratchet suite is green; confirm whether any semantic-navigation use is active and keep it only if used; the wired `.githooks/pre-commit` is unaffected. | DL-010 |

**Acceptance criteria**

- The two graphify hooks no longer run on commit/checkout; commits still succeed and the wired
  `.githooks/pre-commit` still fires.
- The ratchet suite (M-001 through M-004) is green in CI at the moment of removal (gate satisfied).
- No tracked file references `graphify-out` as a wiring source of truth.

**Tests:** `.githooks/post-commit`

---

### M-008 -- Deferred deploy/ops ratchets, recorded not built (port M6)

Flags: `docs`, `deferred`, `documentation-only`

**Files:** `docs/hardening-port/deferred-ops-ratchets.md`

**Requirements**

- Record the deferred deploy/ops ratchets adapted to Selom's Vercel + Fargate/Aurora stack (not a
  VPS): OIDC deploy with no static AWS keys; a content-verified restore drill (Aurora/S3) before
  launch; an external dead-man ping (healthchecks.io) on any cron; an idempotency proof on
  migration/seed; a post-deploy posture re-assertion; and a self-arming rot latch (a registered
  skill/route cannot silently vanish).
- For each item note the PRINCIPLE ported versus the Swordfish machinery skipped; plus the trigger to
  build it (AWS backend deploy live).
- Documentation-only: build no ops machinery now.

**Code intents**

| ID | File | Behavior | Decisions |
|---|---|---|---|
| CI-M-008-001 | `docs/hardening-port/deferred-ops-ratchets.md` | Record each deferred deploy/ops ratchet in Selom-adapted form (Vercel + Fargate/Aurora, not a VPS): OIDC deploy with no static keys, content-verified restore drill, external dead-man ping on any cron, migration/seed idempotency proof, post-deploy posture re-assertion, self-arming rot latch; for each note the principle ported vs the Swordfish machinery skipped and the build trigger (AWS backend deploy live); documentation-only. | DL-009 |

**Acceptance criteria**

- `deferred-ops-ratchets.md` lists each deferred ratchet with its Selom-adapted form and build trigger.
- The doc explicitly states these are out of scope for the current port and are built after deploy is
  live.

**Tests:** (none -- documentation-only)

---

## Design decisions

| ID | v | Decision | Reasoning (compressed) |
|---|---|---|---|
| DL-001 | 1 | Adopt the ratchet strength ladder (`executable > structural > config > documentary > memory`) as the graphify-replacement doctrine. | graphify's wiring role re-derives "what connects to what" from a rebuilt graph -- documentary, rots between rebuilds. An executable ratchet asserts the same boundary at CI/commit time and fails on drift, so keep the strongest expression and prune weaker restatements; that ladder is what lets graphify's hooks retire once the ratchets are green. |
| DL-002 | 1 | Every enforcement gate ships 3-move: MEASURE -> CONFORM -> ENFORCE, MEASURE authored first. | Flipping a blocking check onto a violating repo turns every commit red and pressures a bypass, so each gate counts violations, drives to zero with real fixes, then blocks; ENFORCE never lands before CONFORM proves zero. |
| DL-003 | 1 | Extend Selom's existing guards; only genuinely new concerns get a new guard file. | Selom already has mature FE/BE guards (structure.guard.test.ts, test_structure_guard.py with the AI single-caller pin + ACTION_REGISTRY closed-set sync); a parallel framework duplicates the harness and splits the source of truth. Only repo-wide hygiene and the LLM inventory get new files. |
| DL-004 | 1 | Stable aggregate required-check via a consolidated `ci.yml`. | Two path-filtered workflows can never be required checks (a skipped required check blocks a PR forever); GitHub `needs:` only aggregates within ONE workflow, so consolidate into one `ci.yml` with a changes-detection job gating backend+frontend, plus one always-run aggregate `ci` job (needs all, `if: always()`) that passes iff no required job FAILED. Branch protection requires the single stable name `ci`; sharding later never changes it. |
| DL-005 | 2 | Wire enforcement as a tracked `.githooks/pre-commit` via `core.hooksPath`, gated on exit code. | A guard whose result is ignored is not a ratchet, and a `;`-chained `guard; git commit` commits even on non-zero (a real secret leak in Thalon). But `core.hooksPath` makes Git ignore `.git/hooks/` entirely, so the M-001 cutover migrates graphify's two local hooks into `.githooks/` (kept untracked) so they keep firing until M-007's gated retirement. |
| DL-006 | 1 | The forbidden-token / conflict-marker scanner assembles patterns from fragments and scans the tracked/staged set. | A scanner that contains its own trigger literals would flag itself; assembling patterns at runtime lets it pass its own scan. Matching over `git ls-files` (CI) or staged files (hook) = exactly the bytes that will land, not working-tree noise. One node scanner is the single source of truth for both hook and CI. |
| DL-007 | 2 | Single-env-reader: BE consolidates app-config reads into `config.Settings`, FE into `lib/config/env.ts`, both with an explicit environmental allowlist. | MEASURE found 17 `os.environ`/`getenv` reads across 13 BE files plus scattered FE `process.env` reads; a renamed/duplicated key can silently diverge. Route app-config reads through the ONE typed home; `hani.py`/`dorgau.py` WRITE `SELOM_UMAP_ENGINE` as a per-run override, so `config.Settings` exposes a LIVE accessor that re-reads env at call time and the guard allowlists those writers; genuinely environmental probes (`AWS_LAMBDA_FUNCTION_NAME`, `LOCALAPPDATA`, `NODE_ENV`, next.config.ts, build scripts) are allowlisted so ENFORCE lands on zero. |
| DL-008 | 1 | SHA-pin + renovate + zizmor + least-privilege permissions are ported from Swordfish, not Thalon (attribution verified by direct `git ls-files`). | The audit prompt implied these were Thalon's, but Thalon has NONE and Swordfish has all four; citing Thalon would chase a non-existent file. Selom improves on both by putting least-privilege permissions on every workflow (Swordfish's own ci-guard omitted it). |
| DL-009 | 1 | M6 deploy/ops ratchets are deferred and adapted (principle, not machinery). | Swordfish is a self-managed VPS so its dead-man / restore-drill / cloud-init / provider-adapters are VPS-shaped; Selom is Vercel + Fargate/Aurora and its backend deploy is not live. Take the principle (external dead-man ping on any cron, content-verified restore rehearsal, OIDC not static keys) and record it for when AWS deploy lands. |
| DL-010 | 2 | Graphify wiring-role retirement = delete the two MIGRATED local hooks in `.githooks/`; gated on M-001..M-004 green in CI. | graphify's wiring value is replaced only once the ratchets asserting those boundaries are green IN CI, which needs M-004's `ci.yml` to run the guard jobs. M-001 migrated the two local hooks into `.githooks/` (untracked) so `core.hooksPath` didn't silently drop them; retirement deletes them AFTER the gate is green, keeping semantic-navigation use only if active. |
| DL-011 | 1 | Lean handoff = overwrite model; revise README hard-rule 1 from append to overwrite. | `CURRENT.md` is 436 lines / 16 sections with narrative-paragraph SESSIONS rows, contradicting the README's own thin slot-based shape; the append rule licensed the growth. Revise rule 1 to overwrite (narrative in commits + `archive/`, CURRENT carries only live slots) and compress CURRENT to ~60 lines, archiving the existing narrative once. |
| DL-012 | 1 | Worktree tooling placement: preinstall guard under `app/frontend/scripts`; operator setup script at repo-root `scripts/`. | `npm preinstall` runs relative to the owning package.json and Selom has NO root package.json (FE is the only npm package), so the guard lives under the FE package; the cross-cutting `worktree-setup.ps1` has no npm home, so it lives at repo-root `scripts/`. |
| DL-013 | 1 | Windows worktree teardown + hygiene landmines are encoded as load-bearing invariants in the tooling, not left to memory. | PowerShell `Remove-Item -Recurse` follows a junction and has wiped MAIN `node_modules`; teardown MUST use `cmd /c 'rmdir /s /q'` with a count snapshot before/after; junctions (not symlinks) need no admin; `.ps1` stays pure ASCII; a bg dev server is killed by its PORT LISTENER not a harness task-stop. |
| DL-014 | 1 | M2 required-check has a hard external dependency VERIFIED before ENFORCE; commits keep the Vercel-allowed git identity. | Making `ci` required needs branch protection, which on a private repo needs GitHub Pro, with `enforce_admins:false` so the solo owner keeps direct-push while PRs/others are gated; the ENFORCE step is preceded by a VERIFY and is owner-run. The git identity stays `282747725+steveneam@users.noreply.github.com` or Vercel blocks the deploy. |
| DL-015 | 1 | The LLM call-site inventory extends the chokepoint pin with a counted label set + a raw-client accessor allowlist. | The existing guard pins `routers/ai.py` as sole feeder of `stamp_ai_actions`, but a new site reusing an existing label, or a raw client constructed in a new file, would slip past a single-caller check. The inventory pins the exact guarded label set, COUNTS the stamp/gateway sites, and restricts raw construction to an explicit allowlist (asserting each path exists), so a new site forces an explicit EXPECTED update. |
| DL-016 | 1 | The port is its own milestone bundle sequenced BEFORE the parallel campaign (owner-locked). | Lanes are only safe on frozen contracts backed by executable guards, so the hardening + ratchet substrate must land and go green FIRST because the guards ARE the seam that makes lanes safe. Owner-locked: full M0-M4 bundle, M5 gated on green, M6 deferred; the parallel campaign runs AFTER and is out of scope here. |
| DL-017 | 1 | The required `ci` backend gate runs the STUB skills engine; real deg/gsea validation is a separate deferred job before the backend becomes a required DEPLOY gate. | The fast gate protects structure + API contract + provenance wiring, all of which the stub exercises at second-scale; real scverse deg/gsea in the required PR gate would make every PR slow/flaky and still not prove deploy-readiness. Keep the required gate on `SELOM_SKILLS_ENGINE=stub`; the real closure runs as a separate M6/deploy-time job. This stub scope is recorded in the gate-ledger so it is explicit. |
| DL-018 | 1 | The contract-window protocol is a first-class decision: freeze FE contract types + BE schema before lanes fork; additive-only within an open window; every invariant names the exact executable test to extend in the same change; one window per sprint with one owner. | Parallel lanes are only safe on a frozen contract, and "frozen" is meaningless unless the freeze rules are explicit and enforceable. Within a window, changes are ADDITIVE-only (never rename/remove/tighten a shared type or field), each new invariant names the exact ratchet test that asserts it in the SAME change, and exactly one window per sprint has one owner-merger -- turning the precondition into a checkable rule, mirroring the one-writer-per-row board discipline. |

## Rejected alternatives

| ID | Alternative | Why rejected | Ref |
|---|---|---|---|
| RA-001 | Attribute the SHA-pin / zizmor / renovate / permissions bundle to Thalon. | Direct `git ls-files` shows Thalon has none of them; all four are Swordfish's, so citing Thalon would chase a non-existent file. | DL-008 |
| RA-002 | Keep graphify for wiring integrity. | Owner-directed: executable ratchet tests replace the wiring role once green; Thalon + Swordfish did cross-code review with no graphify. | DL-010 |
| RA-003 | Keep the append-based handoff with a hard line cap. | Owner chose the lean overwrite model with history in git/archive; append is what let CURRENT.md bloat to 436 lines. | DL-011 |
| RA-004 | Shard the CI suite now. | The suite is not long enough to need sharding; adopt the stable aggregate name now and shard later without changing it. | DL-004 |
| RA-005 | Port Swordfish's VPS ops machinery verbatim (dead-man / restore-drill / cloud-init / provider-adapters). | Selom is Vercel + Fargate/Aurora, not a self-managed VPS; take the principle not the machinery, and defer until deploy is live. | DL-009 |
| RA-006 | Build a fresh guard framework for the new invariants. | Selom already has mature FE+BE guards; a parallel framework splits the source of truth, so extend the existing files. | DL-003 |
| RA-007 | Keep two path-filtered workflows and mark both as required checks. | A path-filtered required check never reports on an unrelated PR and blocks it forever; `needs:` cannot aggregate across workflows, so consolidation is required. | DL-004 |

## Constraints

| ID | Type | Source | Constraint |
|---|---|---|---|
| C-001 | technical | user-specified | Every enforcement gate ships 3-move: MEASURE (report-only + count) then CONFORM (repo to zero) then ENFORCE (blocking CI + pre-commit); a MEASURE task is sequenced first per gate. |
| C-002 | technical | user-specified | Never flip a blocking gate onto a non-conforming repo. |
| C-003 | technical | user-specified | Reuse/extend Selom's existing guards (FE structure.guard.test.ts, BE test_structure_guard.py with the AI-chokepoint pin + action-registry closed-set sync, provenance.stamp_ai_actions, the lane board, .worktreeinclude); do not rebuild. |
| C-004 | organizational | user-specified | Never modify, commit, or delete anything under `E:/thalon` or `E:/swordfish`; the reference repos are strictly read-only. |
| C-005 | organizational | doc-derived | No AI-authorship sign-offs on commits, PRs, or docs (owner rule; overrides harness defaults). |
| C-006 | organizational | user-specified | Plan only this session; the owner authorizes builds/pushes; launching worktree lanes needs fresh per-launch approval covering exactly the named runs (reviewer + fix-round resumes each count). |
| C-007 | organizational | user-specified | Owner-locked sequence: the port is its own milestone before the parallel campaign; full M0-M4 bundle; M5 graphify-retire gated on the ratchet suite green; M6 deferred until AWS deploy is live. |
| C-008 | technical | user-specified | Handoff uses the lean overwrite model (CURRENT.md ~60-line pointer, history in git) and revises README hard-rule 1 and its neighbors. |
| C-009 | technical | doc-derived | Windows M3 landmines: delete worktrees with `cmd /c 'rmdir /s /q'` never PS `Remove-Item -Recurse`; junctions not symlinks (no admin); a preinstall guard blocks `npm install` in a worktree; `.ps1` pure ASCII; kill bg servers by PORT LISTENER; single FE node_modules + a BE .venv analog. |
| C-010 | technical | doc-derived | Guard-gating: the pre-commit hook and any local guard chain must gate on the exit code (a `;`-chain leaked a token in Thalon). |
| C-011 | dependency | user-specified | M2 required-check needs GitHub Pro + branch protection with `enforce_admins:false` (solo owner keeps direct-push; PRs/others gated); VERIFY repo plan/visibility before ENFORCE; git identity must be `282747725+steveneam@users.noreply.github.com` (Vercel), not the Thalon hotmail address. |
| C-012 | technical | doc-derived | Env landmines: `:8000` is eamos (never kill); run the BE on `:8010` (uvicorn `--port`, no `--reload`); FE via `npx next dev --webpack` (Turbopack panics 0xc0000142); run BE python via the uv-3.12 interpreter + PYTHONPATH not `uv run` (EDR); set `PYTHONIOENCODING=utf-8`. |

## Risks & mitigations

| ID | Risk | Mitigation | Anchor | Ref |
|---|---|---|---|---|
| R-001 | Flipping a blocking gate onto a non-conforming repo turns every commit red and pressures a bypass. | 3-move: MEASURE + CONFORM to zero before ENFORCE; the ENFORCE task depends on a green CONFORM. | `docs/hardening-port/gate-ledger.md` | DL-002 |
| R-002 | A `;`-chained `guard; git commit` commits even when the guard fails (a real secret leak in Thalon). | Wire `.githooks/pre-commit` via `core.hooksPath` and gate on the exit code; main branch-protection blocks force-push so a leak cannot self-scrub. | `.githooks/pre-commit` | DL-005 |
| R-003 | Deleting a worktree with PowerShell `Remove-Item -Recurse` follows the node_modules junction and wipes the MAIN checkout's node_modules (data loss). | Teardown uses `cmd /c 'rmdir /s /q'`; snapshot the main node_modules file-count before/after as a guard. | `scripts/worktree-setup.ps1` | DL-013 |
| R-004 | A path-filtered required check never reports on an unrelated PR and blocks it forever (false-green / stuck PR). | Consolidated `ci.yml` with an always-run aggregate `ci` job (`if: always()`); a skipped job is treated as pass, only a FAIL blocks. | `.github/workflows/ci.yml` | DL-004 |
| R-005 | backend-ci runs the STUB engine (WS6 open item), so a green backend gate does not prove real science. | Keep the fast gate on the stub for structure/contract; defer the real deg/gsea closure job to M6/deploy-time before backend becomes a required DEPLOY gate; record in the gate-ledger. | `docs/hardening-port/gate-ledger.md` | DL-004 |
| R-006 | Making `ci` required needs GitHub Pro + branch protection; a wrong `enforce_admins` would lock out the solo owner's direct push, or the wrong git email blocks Vercel. | VERIFY repo plan/visibility before ENFORCE; `enforce_admins:false`; keep the Vercel noreply git identity. | `.github/workflows/ci.yml` | DL-014 |
| R-007 | Editing repo files via PowerShell 5.1 Get-Content/Set-Content corrupts UTF-8 (mojibake; a whole-file diff is the tell). | Use the harness Write/Edit tools; append to the board via a bash sed CRLF pipe, never PS string surgery. | `COORDINATION.md` | DL-013 |
| R-008 | The FE reads `process.env NODE_ENV` in framework/build contexts, so a naive single-env-reader guard would false-positive. | The FE guard allowlists `NODE_ENV` and build/framework readers (next.config.ts, scripts/, figure-canvas.tsx, params.ts); only app-config vars are forced through `lib/config/env.ts`. | `app/frontend/lib/structure.guard.test.ts` | DL-007 |
| R-009 | Removing the graphify hooks could orphan an active semantic-navigation use. | Gate removal on the ratchet suite green (M0a+M0b+M1) and confirm semantic-nav usage at execution; keep it only if used. | `.git/hooks/post-commit` | DL-010 |
| R-010 | The consolidated `ci.yml` moves the backend/frontend steps; a transcription error could silently drop a check (e.g. next build, ruff). | Move steps verbatim; assert on a docs/backend/frontend PR trio that each job runs the expected steps; keep timeout-minutes and cache keys. | `.github/workflows/ci.yml` | DL-004 |

## Invisible knowledge

### System

The ratchet substrate is: one node scanner (`scripts/guards/hygiene-scan.mjs`) invoked by BOTH a wired
`.githooks/pre-commit` (`core.hooksPath`, gated on exit code) AND a non-path-filtered CI job; extended
FE/BE structure guards that pin env-reader, import-boundary, and LLM-inventory invariants; and a
consolidated `ci.yml` whose always-run aggregate `ci` job is the single branch-protection required
check. These executable ratchets assert the wiring integrity graphify re-derived, which is why
graphify's two local hooks can retire once the suite is green.

### Invariants

- The ratchet strength ladder is the graphify-replacement doctrine: `executable > structural > config >
  documentary > memory`; leave the strongest expression, prune the weaker restatement.
- A guard is only a ratchet if the commit is gated on its exit code; a `;`-chain that ignores the exit
  code is not enforcement.
- The stable aggregate required-check is one `ci` job with `needs:[all shards]` + `if: always()`
  asserting each result is success-or-skipped; a SKIPPED required check blocks nothing so `if:
  always()` is mandatory, and `fail-fast:false` lets all shards report.
- The forbidden-token scanner assembles its patterns from fragments so it passes its own scan; matching
  runs over the git-tracked (CI) or staged (hook) set = the exact bytes that will land.
- Selom already refined Thalon's parallel model with a scope-leak check (`git diff --name-only
  main...lane`); the board-file conflict is the ONE expected conflict, any non-board conflict is a
  partition leak = stop.
- AI provenance is stamped only via `provenance.stamp_ai_actions`; `routers/ai.py` is the sole feeder
  of `ai_actions=`, and the LLM inventory COUNTS sites so a new caller reusing an existing label is
  still caught.
- The contract is frozen per sprint; one writer per board row; the lead is the sole merger; Mode B is
  "the vscode method".
- `graphify-out/` is gitignored (0 tracked files), so retiring graphify is deleting two LOCAL hooks,
  not an untrack, and only after the ratchet suite is green.

### Tradeoffs

- Consolidating the two path-filtered workflows into one `ci.yml` is more churn now, but it is the only
  way GitHub `needs:`-aggregation can produce a single always-reporting required check.
- The single-env-reader guard carries an explicit environmental allowlist rather than forcing every env
  read through settings; pragmatic over pure, because `AWS_LAMBDA_FUNCTION_NAME` / `LOCALAPPDATA` /
  `NODE_ENV` are environment detection, not app config.
- M6 deploy/ops ratchets are recorded but not built; the principle is captured now, the machinery waits
  for a live AWS deploy so it is not written against a non-existent target.
- The worktree preinstall guard lives under `app/frontend` (the only npm root) while the setup script
  lives at repo-root `scripts/`; the split reflects where `npm preinstall` actually runs versus where
  an operator script belongs.

## Notes on scope and paths

- This is the PLAN document. Implementation artifacts the milestones create -- the 3-move gate ledger,
  the deferred-ops record -- live under `docs/hardening-port/` (created during build), distinct from
  this plan at `docs/eng-practices-port/plan.md`.
- The reference repos `E:/thalon` and `E:/swordfish` are strictly read-only; nothing in this port
  writes to them.
- No milestone here is built this session; the owner authorizes each build and push. Launching
  worktree lanes (M-005 usage) needs fresh per-launch approval covering exactly the named runs.

## Getting started -- first three tasks + owner steps

Wave W-001 is a single milestone (M-001), the substrate every later gate reuses. The first three
tasks are its 3-move sequence; completing them unblocks all of W-002 (M-002..M-006 in parallel).

1. **M-001 MEASURE** -- build `scripts/guards/hygiene-scan.mjs` (fragment-assembled patterns:
   merge-conflict markers; forbidden tokens [secrets/keys, `dev:mock` ship-blockers, AGPL-tainted
   refs]; missing single trailing newline). Run `--all` report-only over the `git ls-files` set and
   record the baseline counts in `docs/hardening-port/gate-ledger.md`. No enforcement yet.
2. **M-001 CONFORM** -- drive any measured hits to zero, then add `.gitattributes` LF normalization
   so a CRLF line cannot smuggle a conflict marker past a carriage-return-naive matcher.
3. **M-001 ENFORCE** -- wire the tracked `.githooks/pre-commit` (runs the scanner `--staged`, aborts
   on non-zero exit) and set `core.hooksPath=.githooks`; in the SAME cutover migrate graphify's
   `post-commit` + `post-checkout` into `.githooks/` (gitignored, still firing) so the
   `core.hooksPath` switch does not silently retire graphify -- its gated retirement stays in M-007.

### Owner steps required

- **Approve the execution campaign** before any build; and each M-005 worktree-lane launch needs
  fresh per-launch approval covering exactly the named runs (reviewer / fix-round resumes each count).
- **M-004 required-check dependency:** confirm the GitHub plan -- the ENFORCE step needs branch
  protection with `enforce_admins:false` (GitHub Pro on a private repo, or a public repo) so the solo
  owner keeps direct-push to `main` while PRs / other actors are gated. Verify or enable before
  M-004's ENFORCE move.
- **M-007 gate:** confirm whether graphify's semantic-navigation is actually used; if not, the
  wiring-role retirement removes the two hooks once the ratchet suite is green (keep-if-used).
- Authorize each commit / push (named paths, no AI sign-off); the owner pushes.

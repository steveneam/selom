# Selom — CURRENT (Live State)

> ## ▶ BOOT: Steven types **`gogogo`** — that IS the whole resume prompt.
>
> **Agent, on `gogogo` (or any greeting with no task): do this, unprompted.**
> He cannot copy text out of the terminal, and he may be sending it from a
> Telegram topic on his phone (the swordfish hermes relay cold-starts this
> session in tmux — no one types `claude` first). So there is no prompt for him
> to paste: **the prompt is this file.** Read, in order, then act:
> 1. this whole file (newest SESSION slot → the live pointers below it)
> 2. `CLAUDE.md` + `agent_handoff/README.md` (the coordination home) and memory
> 3. `git log --oneline -8` and `git status` — trust the repo, not the stamp
>
> Then **state the next action in one sentence, say what you are starting, and
> start it.** Do not ask "shall I?" — the next action IS the standing approval.
> Stop only at a founder gate (spend · irreversible · anything the protocol
> names a founder decision).
>
> _Boot block added 2026-07-13 at the founder's direction, so a relay-cold-started
> session resumes with no chat history (mechanism: the Swordfish hermes relay).
> Keep it at the top when you overwrite this file in place._

> Thin, slot-based pointer — **overwrite in place, never append** (README "CURRENT.md shape" + hard
> rule 1). Per-session NARRATIVE lives in commit messages + `archive/`, not here. Pre-2026-07-09
> history: `archive/2026-07-09-current-history.md` + `git log`.

## ▸ SESSIONS  (newest first — scan here; detail = the commit range + git log)

| Tag | Date | SHA range | One-line |
|---|---|---|---|
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..HEAD` | First session on the new **Linux host (syd4)**. Removed every hardcoded Windows drive path: the three review workflows resolve `git` from cwd; `config.py` resolves the external datasets + papers corpora from **`SELOM_DATASETS_DIR` / `SELOM_PAPERS_DIR`** (no drive default; absent ⇒ the skipif-guarded tests skip), ~24 backend files repointed, proven by `tests/test_config_data_dirs.py`; `hygiene-scan.mjs` gains a **5th class** forbidding absolute drive paths in tracked code. Closed the eng-practices port: **M-007** graphify wiring-retirement (dropped the migrated-hook ignores + `.graphifyignore`) + **M-008** deferred-ops-ratchets doc → **W-003 COMPLETE**. Folded in two peer-repo hygiene practices (CI concurrency diet + a retro documented-command pass; [[selom-repo-hygiene-vs-peers]]). `review-gauntlet` ran clean over the diff (1 low finding fixed). BE fast **1209/16skip** · FE tsc+eslint+vitest green. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | Pushed `port/m001-repo-hygiene`, opened **PR #1**, `ci` green, **FF-merged to `main`** (linear, exact SHAs) + deleted the branch. Two trigger-event holes in M-004's `ci.yml`: `pull_request` needed `pull-requests: read` (`24c6797`); push-to-`main` needed `fetch-depth: 0` (`2cb4cb9`). Ratchet: [[verify-ci-in-its-target-event]]. |
| **ENG-PORT-W2** | 2026-07-09 | `4e4ad48..ba8856e` | Eng-practices port W-002: M-002 single-env-reader + router import-boundary · M-003 LLM call-site inventory · M-004 CI → one `ci.yml` · M-005 worktree tooling · M-006 lean handoff. |
| **ENG-PORT-M1** | 2026-07-09 | `945ac73..e9ba3ab` | Port plan + M-001 repo-hygiene scanner + wired `.githooks/pre-commit` (`core.hooksPath`) + ratchet doctrine. |
| older | — | `git log` / `archive/` | CI-GREEN · PARALLEL-SPRINT-1 · AI-DRAFT/HARDCODE-HUNT · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · HOST-PORTABILITY · 2026-07-19 · `main` @ `f305b04` (ahead of `origin/main@4dc51e4` by 8, **unpushed**) · Claude (FE+BE, solo)

- **State:** first session on syd4 (Linux). The repo arrived portable-but-unfixed; this session made it host-portable and **closed W-003** (the whole engineering-practices port). 7 atomic commits `b037f67..f305b04` on top of the prior boot-block `c512dbc`. Everything verified; the gauntlet ran clean (its running at all = the acceptance test for the workflow-path fix).
- **Gates (this host):** BE fast **1209 passed / 16 skipped / 0 failed** (`uv run pytest -m "not slow" -n auto`, full extras) + ruff clean; FE **tsc 0 · eslint 0-err · vitest 513**; `hygiene-scan --all`/`--staged` green (5 classes); zizmor clean. `test_config_data_dirs.py` is the executable proof of the resolver (the corpora never come to this host).
- **`selom-data` is NOT on this host and never will be** (employer-adjacent, fleet-wide). `$SELOM_DATASETS_DIR` / `$SELOM_PAPERS_DIR` stay unset → the guarded reproduction tests skip by design. Green with those skipped tells you nothing about the data path — never read it as "reproduction works".

## ▸ NEXT

- **Push (owner-gated):** `origin/main` is 8 commits behind. Owner authorises the push of `c512dbc..f305b04`.
- **Owner action — the ONLY blocker:** branch-protect `main` requiring exactly the check **`ci`** (`enforce_admins:false`, GitHub Pro). `ci` has run green on both a PR and a push, so the check name is proven.
- **Peer-hygiene follow-ups (queued, [[selom-repo-hygiene-vs-peers]]):** verify what M-002's single-env-reader already enforces before adding a thalon-style import-boundary guard; a short `SECURITY.md` leak runbook; `.dockerignore` when the BE containerizes (thalon's OIDC `deploy-infra.yml` is the reference for the pending GH→AWS OIDC cutover).
- **Then the parallel campaign** (owner-directed): survey the on-hold backlog (`docs/on-hold/README.md` + parked memories) + remaining launch work (WS3 dedup · owed WS1/restructure reviews · WS6 deploy) + Pillar-2; carve disjoint contract-separated buckets → forcing-Qs → fork lanes ([[parallel-agent-lanes]]).

## ▸ DEFERRED

- Owed reviews: WS1 boundary (gauntlet + fe-review G2 stub-banner) + the whole-restructure gauntlet/fe-review; a **live-gateway** spot-check of the AI surfaces (all prior verify was gateway-off).
- Server/deploy: 7c-(b) FE-3 upload wiring · step-8 split deploy (Lambda+Fargate+Aurora, GitHub→AWS OIDC, kill the static key) — `docs/aws-materialization/plan.md`.
- **`uv.lock` completion** — the committed lock does not fully cover the optional extras, so `uv sync`/`uv run` re-resolves + churns it; a deliberate `uv lock` refresh is a Codex-lane hygiene task (kept OUT of this milestone's commits).

## ▸ ENV / landmines (Linux · syd4 — the Windows rules are dead)

- **Backend:** `uv run uvicorn main:app --reload` on `:8000`. Fast gate: `uv run pytest -m "not slow" -n auto`. Full test extras (as CI): `uv sync --extra dev --extra db --extra jobs --extra scrna --extra pdf`. Ruff: `uv run ruff check .`. zizmor: `uv tool run zizmor@latest --persona=regular .github/workflows/`.
- **Frontend:** `npm install --legacy-peer-deps` then `npm run dev`. Turbopack no longer panics (that was Windows); `--webpack` not needed.
- **Shared multi-agent box:** every Next dev server defaults to `:3000` and the 2nd **silently** takes `:3001` (wrong-app-verify risk) — derive the lane (`~/work/swordfish/provisioning/workstation/dev-lane.sh`; Selom FE=3152) before `npm run dev`. NOT yet applied to `package.json` (still `next dev`) — a follow-up. Before anything that restarts services/apt: `who-is-live.sh --gate`.
- Every commit runs `.githooks/pre-commit` (`core.hooksPath`, hygiene-scan `--staged`, 5 classes). `git user.email` MUST stay the noreply (`282747725+steveneam@…`) or Vercel blocks deploys [[selom-git-commit-email-vercel]].
- **MCP env keys** (`CONTEXT7_API_KEY` / `RENDER_API_KEY` / `OBSIDIAN_API_KEY`) live in `~/.config/agent-env/selom.env`, sourced by the session launcher — present inside this session; a shell started elsewhere must source that file.
- Reviews (gauntlet/fe-review) bat at a phase/milestone boundary, not per task [[review-cadence-phase-not-task]]. Cross-agent live coordination = the **`live-comm`** skill (never hand-roll tmux send-keys); async = `agent_handoff/FROM-SWORDFISH.md` (in) / `ASK-BACKS-FOR-SWORDFISH.md` (out).

## ▸ READ FIRST

`docs/hardening-port/gate-ledger.md` (W-003 COMPLETE) · `docs/eng-practices-port/plan.md` · CLAUDE.md "Engineering ratchets" · `docs/restructure/plan.md` (the post-port launch tracker) · `docs/operating/{playbook,contract-window}.md`. Memory: [[executable-ratchets-over-implicit-wiring]] [[selom-repo-hygiene-vs-peers]] [[parallel-agent-lanes]] [[verify-on-real-data-not-mock]] [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = the restructure tracker (`docs/restructure/plan.md`) + `plans/v2-backend.md`.

# Selom — CURRENT (Live State)

> Thin, slot-based pointer — **overwrite in place, never append** (README "CURRENT.md shape" + hard
> rule 1). Per-session NARRATIVE lives in commit messages + `archive/`, not here. Pre-2026-07-09
> history: `archive/2026-07-09-current-history.md` + `git log`.

## ▸ SESSIONS  (newest first — scan here; detail = the commit range + git log)

| Tag | Date | SHA range | One-line |
|---|---|---|---|
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | Pushed `port/m001-repo-hygiene`, opened **PR #1**, got `ci` green, then **FF-merged to `main`** (linear, exact SHAs) + deleted the branch (1 branch, Thalon-style). Two trigger-event holes in M-004's `ci.yml`, each invisible until the real event ran: `pull_request` needed `pull-requests: read` for paths-filter's `pulls.listFiles` (`24c6797`); `push`-to-`main` needed `fetch-depth: 0` so paths-filter's git-diff doesn't hit a credential-less fetch under `persist-credentials:false` (`2cb4cb9`). Living contract `.github/workflows/README.md` + gate-ledger correction (`00a1026`). Ratchet: [[verify-ci-in-its-target-event]]. |
| **ENG-PORT-W2** | 2026-07-09 | `4e4ad48..ba8856e` (+this) | Eng-practices port **W-002**: M-002 single-env-reader + router import-boundary · M-003 LLM call-site inventory · M-004 CI → one `ci.yml` (SHA-pin/renovate/zizmor, aggregate `ci` check) · M-005 worktree tooling · M-006 lean handoff (this commit). Branch `port/m001-repo-hygiene`, **NOT pushed**. |
| **ENG-PORT-M1** | 2026-07-09 | `945ac73..e9ba3ab` | Port plan + M-001 repo-hygiene scanner + wired `.githooks/pre-commit` (`core.hooksPath`) + ratchet doctrine. |
| **CI-GREEN** | 2026-07-04 | `ff12198` | Fixed red backend-ci (S3 test tripped the WS1.1 stub guard on CI's light closure); reconciled WS2.7/2.8 → foundation (WS1+WS2) closed. |
| **PARALLEL-SPRINT-1 / -FIX** | 2026-07-04 | `4215365..1d76ae7` | 3 lanes (ENG·ERG·FIG) forked → built → merged via the delegated train; 0 code conflicts (partition held); milestone review fixes applied. |
| **AI-DRAFT / HARDCODE-HUNT** | 2026-07-02 | `cbbf803..452a7b0` | Layer A cross-stage AI build complete (methods/legend draft, grade advisory, ingest refiner, provenance chokepoint, gateway wiring). |
| **RESTRUCTURE 01–08** | 2026-07-02 | `1be60a5..e3e707f` | WS1 honesty (stub-engine prod guard) + WS2 ingest/QC robustness + run-path error taxonomy; tracker `docs/restructure/plan.md`. |
| older | — | `git log` / `archive/` | AI-Helpers · AWS materialization steps · 7c FE state → Postgres · structure refactor · deploy backbone. |

## ▸ LIVE · PORT-MERGED · 2026-07-09 · `main` @ `2cb4cb9` (or later `ci`-fix HEAD) · Claude (FE+BE, solo)

- **State:** the engineering-practices port (W-001+W-002, M-001..M-006) is **MERGED to `main`** — FF, linear, exact SHAs; PR #1 merged; branch deleted (1 branch). **`ci` is GREEN on `main` on BOTH trigger events** (pull_request + push). Read `945ac73..HEAD`.
- **CI hardening tail (all closed):** M-004's `ci.yml` had two event-specific holes, each invisible until the real event ran — PR path needed `pull-requests: read` (`24c6797`), push-to-main path needed `fetch-depth: 0` (`2cb4cb9`). The push-only requirement is now locked by an **executable guard** (`hygiene-scan.mjs` check #4, runs in the always-on `hygiene` job) because the PR gate can't self-catch it. Living contract: `.github/workflows/README.md`. zizmor still 0. [[verify-ci-in-its-target-event]]
- **Gates (last local run):** BE fast **1214/1skip** (+guards) + ruff clean; FE tsc + eslint 0-err + vitest **513**; wired hygiene pre-commit green every commit.

## ▸ NEXT

- **W-003 (port tail):** **M-007** graphify wiring-retirement — **gate MET** (M-001..M-004 green in CI on both events). Next action: **confirm with owner that graphify semantic-nav is unused**, then drop `.githooks/{post-commit,post-checkout}` + their `.gitignore` lines + repoint the graphify memory. **M-008** deferred deploy/ops ratchets — a docs-only record (`docs/hardening-port/deferred-ops-ratchets.md`), UNGATED, do anytime.
- **Owner action still open (the ONLY blocker):** branch-protect `main` requiring exactly the check **`ci`** (`enforce_admins: false`, GitHub Pro) — GitHub's "Protect this branch" button, or `gh api`. `ci` has run green on both a PR and a push-to-main, so the check name `ci` is proven. Minor: paths-filter@v3 throws a non-blocking Node-20-deprecation warning (renovate will bump it).
- **Then the parallel campaign** (owner-directed at CI-GREEN): survey the on-hold backlog (`docs/on-hold/README.md` + parked memories) + remaining launch work (**WS3 dedup** = lane 1 · owed WS1/restructure reviews · WS6 deploy) + **Pillar-2**; carve disjoint contract-separated buckets → forcing-Qs → fork lanes ([[parallel-agent-lanes]], now backed by M-005 tooling + `docs/operating/contract-window.md`).

## ▸ DEFERRED

- Owed reviews: WS1 boundary (gauntlet + fe-review G2 stub-banner) + the whole-restructure gauntlet/fe-review; a **live-gateway** spot-check of the AI surfaces (all prior verify was gateway-off).
- Server/deploy: 7c-(b) FE-3 upload wiring · step-8 split deploy (Lambda+Fargate+Aurora, GitHub→AWS OIDC, kill the static key) — `docs/aws-materialization/plan.md`.
- `uv.lock` full refresh (a clean `uv lock` bumps the whole tree; `pytest-xdist` is declared in pyproject and `uv sync` resolves it) — a Codex-lane hygiene task.

## ▸ ENV / landmines

- `:8000` = **eamos** — NEVER kill; BE on **:8010** (uv-3.12 PY + `PYTHONPATH="D:/selom/app/backend;D:/selom/app/backend/.venv/Lib/site-packages"`, NOT `uv run` — EDR; `PYTHONIOENCODING=utf-8`; run from `app/backend`). [[selom-backend-python-exec]]
- Fast gate = `pytest -m "not slow" -n auto` (pytest-xdist). Ruff via `./.venv/Scripts/ruff.exe` (the `python -m ruff` shim's bundled exe is EDR-blocked). Zizmor via `uv tool run zizmor@latest`.
- FE dev: `npx next dev --webpack` (Turbopack panics 0xc0000142). [[selom-turbopack-webpack-workaround]]
- Every commit runs `.githooks/pre-commit` (hygiene-scan `--staged`); graphify's "could not locate Python" post-commit warning is EXPECTED/harmless (graphify isn't installed).
- `git user.email` MUST stay `282747725+steveneam@users.noreply.github.com` or Vercel blocks deploys. [[selom-git-commit-email-vercel]]
- NEVER edit repo files via PS 5.1 Get-Content/Set-Content (UTF-8 mojibake) — use Write/Edit.
- Reviews (gauntlet/fe-review) bat at a phase/milestone boundary, not per task. [[review-cadence-phase-not-task]]

## ▸ READ FIRST

`docs/eng-practices-port/plan.md` (M-007/M-008) · `docs/hardening-port/gate-ledger.md` · CLAUDE.md "Engineering ratchets" · then `docs/restructure/plan.md` (the post-port launch tracker) · `docs/operating/{playbook,contract-window}.md` · `COORDINATION.md`. Memory: [[executable-ratchets-over-implicit-wiring]] [[parallel-agent-lanes]] [[verify-on-real-data-not-mock]] [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = the restructure tracker (`docs/restructure/plan.md`) + `plans/v2-backend.md`.

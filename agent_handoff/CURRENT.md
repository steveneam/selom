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
> rule 1). Per-session NARRATIVE lives in commit messages + `archive/`, not here.

## ▸ SESSIONS  (newest first — scan here; detail = the commit range + git log)

| Tag | Date | SHA range | One-line |
|---|---|---|---|
| **LAUNCH-CAMPAIGN** | 2026-07-23 | branch `campaign/parallel-lanes` `60df628..e90203a` (**unpushed**) | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · LAUNCH-CAMPAIGN · 2026-07-23 · branch `campaign/parallel-lanes` (**unpushed**) · Claude (FE+BE, solo)

- **State:** parallel launch campaign. **`main` untouched at `60df628`**; all work on `campaign/parallel-lanes` (10 commits). **FACS now shipped real in-process** (FlowKit pivot done, `e90203a`); **cloud/Nango foundation up**. Reviews (gauntlet + fe-review) **batch at the campaign milestone** before any merge to main.
- **NANGO IS LIVE** at `https://nango.swordfish.cfd` (syd2, swordfish; health 200, LE cert, callback `…/oauth/callback`). Owner override lifted the backup HOLD → **load Google/Dropbox integrations now.** `SELOM_NANGO_BASE_URL` set in `.env`. **BLOCKER:** the env **secret key** is behind the dashboard login (the `hosted` image uses email-account session auth; `selom-admin` isn't email-format, so I can't sign in headlessly). **Asked swordfish** (ASK-BACKS) to drop `SELOM_NANGO_SECRET_KEY` into `~/.config/agent-env/selom-nango.creds` — then I create both integrations via the server API (`POST /config`, Bearer) in seconds. Creds: `~/.config/agent-env/selom-nango.creds` (0600, never commit).
- **Gates:** each committed lane passed its own gate. FACS: 11 real-engine smoke + 12 engine-policy guard green. One **pre-existing, unrelated** full-tree failure: `test_ingest.py::test_ingest_h5ad_single_cell` (anndata ↔ pandas-3.0 h5ad write) — proven pre-existing (reproduces on clean HEAD), NOT campaign work.
- **selom-data IS on this host:** full corpus at `/home/deploy/migration/selom-migration-staging/selom-data/` → `SELOM_DATASETS_DIR`. [[selom-machine-migration]].

## ▸ NEXT  — run parallel work as ISOLATED worktree lanes, NOT in-context fan-out (last session's Mode-A default auto-compacted mid-sprint; [[parallel-agent-lanes]])

- **① MILESTONE REVIEW FIRST (gating — before any new build):** run `review-gauntlet` **+ `fe-review`** (it touches FE) over the whole `campaign/parallel-lanes` branch (`60df628..e90203a`, 11 commits) → fix findings → **owner merges to `main` + pushes**. Batch at this milestone per CLAUDE.md. Keep it lean — don't fan the review into the lead context.
- **② THEN the next sprint as PROPER worktree lanes (the run-model-dial (a), context-isolated):** scout (read-only fan-out, grounded globs) → propose disjoint partition → owner approves → fork **one isolated `claude` session per worktree** → serialized merge train (local merges autonomous, **push = owner gate**). Candidate disjoint buckets: **(a)** ERG figure/table wiring — OP/PhNR/flicker into figures + `companions/methods.py` (unblocked now the FACS lane landed); **(b)** public Selom backend on syd2 — backend **Dockerfile + GHCR image-CI** + the 5 data-plane answers (swordfish scoping note, `FROM-SWORDFISH.md` top); **(c)** Nango cloud FEATURE productization — FE import/export wiring + editor "export to Drive"; **(d)** Pillar-2 continued.
- **Cloud state:** both Nango integrations (`google-drive` + `dropbox`) are **created + verified** on `nango.swordfish.cfd`; the direct `…/oauth/connect/google-drive?connect_session_token=` flow reaches Google. Owner has **not** completed the Google consent (the OAuth app may still be in **Testing** — publish it / add the test user). `SELOM_NANGO_SECRET_KEY` + `_BASE_URL` in `.env`. **OneDrive/Microsoft ON HOLD.**
- **ERG Fig-1E delivery: DONE** — pushed to GitHub branch **`erg-fig1e-data`** (`Steven data/`), also at `/home/deploy/work/selom/Steven data` on the box, summary CSV in the owner's Drive "Selom" folder. Delivery lesson: [[selom-file-delivery-to-owner]].

## ▸ DEFERRED

- **OneDrive/Microsoft** cloud provider (owner on hold until a machine that logs into Azure cleanly).
- **Public Selom backend on syd2** (swordfish scoping note, FROM-SWORDFISH top): needs a backend **Dockerfile + GHCR image-CI** (mine) + 5 data-plane answers (DB/object-store/datasets-mount/heavy-jobs/auth). Owner-gated on any syd2 resize (spend). Reply in ASK-BACKS.
- WS6 AWS deploy — owner chose **"this box first, AWS later"**. Owed WS1/restructure reviews fold into the campaign milestone review.

## ▸ ENV / landmines (Linux · syd4)

- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → `SELOM_DATASETS_DIR`. **Docker installed** — in a fresh shell use `sudo docker` until the `deploy` docker-group login refreshes.
- Backend: `uv run uvicorn main:app --reload` on `:8000`; fast gate `uv run pytest -m "not slow" -n auto` + `uv run ruff check .`. Frontend: `npm install --legacy-peer-deps`; derive the FE dev-lane port (Selom FE=3152) to avoid the shared-box `:3000` collision.
- Every commit runs `.githooks/pre-commit` (hygiene-scan, 5 classes). `git user.email` MUST stay the noreply (`282747725+steveneam@…`) or Vercel blocks deploys [[selom-git-commit-email-vercel]].
- **Cloud OAuth creds** staged in `app/backend/.env` (gitignored): `GOOGLE_*` ✓ · `DROPBOX_*` ✓ · `MS_*` empty (on hold). Self-hosted **Nango** stack under `deploy/nango/`.
- **The agent cannot marshal binary/large files through chat** (base64 reproduction corrupts, even ~20 KB) — deliver files via a real channel (scp/SFTP/rclone/the cloud integration), never by pasting base64 into a tool call. Emailing via the Gmail MCP is draft-only + attachment-limited; Drive `create_file` needs valid inline base64 (same wall).

## ▸ READ FIRST

`docs/restructure/plan.md` (WS3 done) · `docs/fe-review/spec.md` (now impeccable-only) · CLAUDE.md · `deploy/nango/` (once built). Memory: [[parallel-agent-lanes]] · [[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] · [[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.

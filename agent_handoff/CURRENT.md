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
| **LAUNCH-CAMPAIGN** | 2026-07-23 | branch `campaign/parallel-lanes` `60df628..5ab0103` (**unpushed**) | Owner-directed parallel launch campaign (fanned out several build lanes). **Committed on the branch:** WS3.1 converge 6 skill runners → `engine.vocab`/`columns`, kill drifted forks (fixes a silent classify split, `7440f56`) · Pillar-2 slice-0 figure-editor **canvas shell** (4-region frame, relocate-not-rewrite, `3db8f0b`) · **ERG** OP extraction + PhNR + flicker-FFT + opt-in robust a/b, non-breaking (`a84636c`) · **fe-review drops `frontend-design`** → `impeccable` wins (`5ab0103`). **Held (uncommitted):** FACS `facs_gating` skill — built + verified, but **FlowKit ⊥ pandas-3.0** (needs out-of-process for prod, RISKS-worthy). **Building:** cloud-storage integrations (self-host **Nango** + Google/Dropbox/URL import+export → the existing intake pipeline; Docker installed). Also produced the **ERG Fig-1E n=5 mean±SEM** figure + data (real `erg_traces` engine; delivery pending the cloud channel). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · LAUNCH-CAMPAIGN · 2026-07-23 · branch `campaign/parallel-lanes` (**unpushed**) · Claude (FE+BE, solo)

- **State:** parallel launch campaign in flight. **`main` untouched at `60df628`**; all work is on `campaign/parallel-lanes`. 4 lanes committed there; **FACS held** (FlowKit reconciliation); **cloud/Nango foundation building** (a background dev). Reviews (gauntlet + fe-review) **batch at the campaign milestone** before any merge to main.
- **Gates:** each committed lane passed its own gate (BE fast pytest + ruff / FE tsc + eslint + vitest 513). One **pre-existing, unrelated** full-tree failure: `test_ingest.py::test_ingest_h5ad_single_cell` (anndata ↔ pandas-3.0 `ArrowStringArray` h5ad write) — not campaign work.
- **selom-data IS on this host** (corrects the old stamp): full corpus at `/home/deploy/migration/selom-migration-staging/selom-data/` — set `SELOM_DATASETS_DIR` there and the data-dependent tests RUN. [[selom-machine-migration]] corrected.
- **Docker installed** (Engine v29.6 + Compose v5.3) to self-host Nango; the "ask before Docker" rule was Windows-only [[ask-before-docker-wsl]] corrected.

## ▸ NEXT

- **Cloud integration (top):** finish the Nango foundation → wire **Google + Dropbox** (client IDs already in `app/backend/.env`, gitignored) → give the owner the **callback/redirect URLs** to paste into the two provider apps. Google app being **published to Production** (non-sensitive `drive.file` → no CASA). **OneDrive/Microsoft ON HOLD** (owner — Azure login/token trouble; resume on a better machine).
- **FACS reconciliation** (then commit the held lane): FlowKit ⊥ pandas-3.0 → move `flowkit` OUT of `REQUIRED_ENGINE_MODULES` to a per-skill/`find_spec` gate + document the **out-of-process-for-prod** path (RISKS #9 OmicVerse pattern) + add a RISKS.md entry. Prod-real FACS needs the isolated worker; interim real path is a flowkit-installed dev env, prod serves the WS1.1-labelled stub.
- **ERG figure/table wiring:** surface the new OP/PhNR/flicker metrics in the figures + `companions/methods.py` (the ERG lane left this — a table-structure decision; `methods.py` is also edited by the held FACS lane, so do it AFTER FACS lands).
- **ERG Fig-1E delivery:** figure + data zip at `selom-data/erg-fig1e/export/n5_sem_2026-07-23/` (PDF/PNG/TIFF + Excel/CSVs). Deliver via the cloud **export** once live; interim = scp/SFTP (the agent cannot hand-carry binary through chat — base64 corrupts).
- **Milestone:** run review-gauntlet + fe-review over the whole branch → **owner merges to `main` + pushes**.

## ▸ DEFERRED

- **OneDrive/Microsoft** cloud provider (owner on hold until a machine that logs into Azure cleanly).
- **FACS real path in PROD** → the out-of-process FlowKit worker (isolated env / thin RPC), RISKS #9 OmicVerse pattern.
- WS6 AWS deploy — owner chose **"this box first, AWS later"**. Owed WS1/restructure reviews fold into the campaign milestone review. `uv.lock` completion (Codex-lane).

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

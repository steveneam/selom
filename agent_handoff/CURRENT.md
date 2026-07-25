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
| **REVIEW-MERGE** | 2026-07-25 | `main` `60df628..bee9e66` (**22 unpushed**) | Milestone review of the whole campaign branch (`review-gauntlet` 30 confirmed / 3 blockers + `fe-review` 24 confirmed, 31 of 35 user tasks with no affordance) → fix pass → **owner approved → `main` FF-merged**, gates re-run on merged main. **Both blockers fixed:** WS3.1 had flipped DE significance from adjusted p to RAW p across 5 runners while the axis/table/methods still said "adjusted" (`b73bd9b`, 2835 vs 1008 significant genes on the real EYG_28 export; the guard test had been inverted to bless it) · a gene-label click deleted the user's annotation (`b1a49e8`). HIGH honesty set fixed (`1d2aa81`): FACS cites FlowIO+FlowUtils not the absent FlowKit + states the real compensation outcome · assemble records lineage · GSEA's bare `t` no longer matches `entrezgene_id` · Nango ELv2 recorded. **Annotation layer FLAGGED OFF** (owner call) → ~20 findings unreachable. **Google Drive + Dropbox cloud connections now LIVE + verified** end-to-end. |
| **LAUNCH-CAMPAIGN** | 2026-07-23 | `60df628..e90203a` — **merged into `main` 2026-07-25** | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · REVIEW-MERGE · 2026-07-25 16:35 +1000 · branch `main` (**22 commits unpushed**) · Claude (FE+BE, solo)

- **State:** the campaign is **merged**. `main` is at `bee9e66`, linear, 22 commits ahead of `origin/main`. `campaign/parallel-lanes` still exists at the merge point — **delete it only after the push**. Gates on merged main: BE **1277 passed** + ruff clean · FE **tsc 0 · eslint 0 err · vitest 541** · `hygiene-scan --all` 944 files / 0 hits.
- **⚑ THE ONE BLOCKING FOUNDER ACTION: push `main`** (`P0-01`). It also triggers the Vercel deploy. Nothing else waits on anyone.
- **Cloud channel is real:** Google Drive (`c878e8db…`, scope `drive.file`) + Dropbox (`5f45a106…`, 4 scopes) both connected on swordfish's syd2 Nango, refresh tokens verified, live API calls 200. **The cloud FEATURE is still unreachable** — `SELOM_CLOUD_*` flags absent from `app/backend/.env`, no providers endpoint, FE hardcodes `comingSoon` (three closed gates = Lane 2 next session).
- **TWO NANGO INSTANCES — never confuse them again:** LIVE = `nango.swordfish.cfd` on **syd2** (swordfish's, holds the integrations + connections); DEV = `127.0.0.1:3003` on **syd4** (`deploy/nango/`, own DB + key, used by nothing). Selom's secret key returns `unknown_account` on the wrong one — that one command is the tell. Run `bash deploy/nango/preflight.sh [BASE]` before ever asking a human to consent.
- **Gates:** one pre-existing unrelated failure remains — `test_ingest.py::test_ingest_h5ad_single_cell` (anndata ↔ pandas-3.0 h5ad write), reproduces on clean HEAD, tracked as `L1-10`.
- **selom-data IS on this host:** full corpus at `/home/deploy/migration/selom-migration-staging/selom-data/` → `SELOM_DATASETS_DIR`. [[selom-machine-migration]].

## ▸ NEXT  — **entry point = `docs/next-session-plan/plan.md`** (phased, ID-tracked). Run it as ISOLATED worktree lanes, never in-context fan-out (a prior Mode-A default auto-compacted mid-sprint; mechanics confirmed with thalon; [[parallel-agent-lanes]])

- **① MILESTONE REVIEW — RAN 2026-07-25. Branch is NOT mergeable yet.** `review-gauntlet` (30 confirmed, 3 blockers) + `fe-review` (24 confirmed; **31 of 35 user tasks have no affordance**). Durable backlog: **`docs/milestone-review-2026-07-25/findings.md`** (A = gauntlet, B = fe-review, C = the G1 task walkthrough, D = G2 layout predictions that still need a running-app check). **FIXED so far:** the worst blocker — WS3.1 had flipped DE significance selection from adjusted p to RAW p across 5 runners while the axis/table/methods still claimed "adjusted" (2835 vs 1008 "significant" genes on the real EYG_28 limma export, and the guard test had been inverted to bless it) → `b73bd9b`, adjusted-tier-first resolver + honesty following the tier + ratchets restored, verified on real data. **FIX PASS COMPLETE — see the Status ledger at the top of the findings doc.** Both blockers fixed (`b73bd9b` significance tiering · `b1a49e8` gene-label click no longer deletes a Selom annotation), the whole HIGH honesty set fixed (`1d2aa81`: FACS cites FlowIO+FlowUtils not the absent FlowKit and states the real compensation outcome · `/data/assemble-scrna` records lineage · GSEA's bare `t` can no longer match `entrezgene_id` · Connect buttons disabled with a visible chip · Nango ELv2 recorded in LAUNCH-GATES after verifying at source). **Owner decision taken (2026-07-25): the annotation layer is FLAGGED OFF** (`NEXT_PUBLIC_ANNOTATION_LAYER`, off by default) rather than finished under merge pressure — its ~20 findings are unreachable until the slice that adds a selection model, carry-through-re-run and the computed-p bracket path. **Verified live** (backend :8152 + FE :3152, both stopped after): 5 routes 200 with no SSR errors; both volcano paths driven end-to-end on real EYG_28 data — adjusted resolves FDR and plots 1008 = ground truth, raw-only prints "-log10 raw p" + `pvalue` column + no BH claim + a non-blocking `raw_pvalues_only` QC warn. **STILL OPEN (none are merge blockers):** A20 the FE↔BE cloud registry fork (needs a providers endpoint — cloud slice), A14–A19/A21/A23–A27/B13–B16, and the §D layout predictions which no browser could observe this session.
- **MERGED 2026-07-25 16:10 +1000:** owner approved → `main` fast-forwarded to `d950601` (20 commits, linear, no merge commit). Re-gated on merged main: BE 1277 passed + ruff clean · FE tsc 0 · eslint 0 err · vitest 541 · `hygiene-scan --all` 944 files / 0 hits. **`main` is 20 commits UNPUSHED — push is the founder gate** (it also triggers the Vercel deploy). Delete `campaign/parallel-lanes` after the push, not before.
- **⚑ NEXT SESSION: `docs/next-session-plan/plan.md`** — the honest remaining backlog (8 BE integrity · 5 reachability/seam · 4 FE polish · ~20 gated), three plans (A "make it reachable" · B "zero the review debt" · C "finish Pillar-2"), and a **3-lane isolated-worktree partition** with disjoint globs, the frozen `GET /cloud/providers` contract, merge order (Lane 1 BE → Lane 3 FE polish → Lane 2 seam) and the owner steps. Recommendation: run **B + A in parallel next session**, hold **C** for the session after behind a `spec`. [[parallel-agent-lanes]]
- **(superseded) the branch was ready for review + merge** (push is the founder gate). BE 1277 passed + ruff clean; FE tsc 0 · eslint 0 errors · vitest 541. The one failing test (`test_ingest.py::test_ingest_h5ad_single_cell`, anndata↔pandas-3.0 h5ad write) is proven pre-existing on clean HEAD, unrelated to the campaign.
- **Cloud feature is NOT reachable yet** even though both OAuth connections are live: `SELOM_CLOUD_GOOGLE`/`_DROPBOX` are absent from `app/backend/.env`, there is no endpoint reporting per-provider state, and the FE hardcodes `comingSoon`. Three closed gates → the natural next lane ([[selom-shipped-not-reachable]]).
- **② THEN the next sprint as PROPER worktree lanes (the run-model-dial (a), context-isolated):** scout (read-only fan-out, grounded globs) → propose disjoint partition → owner approves → fork **one isolated `claude` session per worktree** → serialized merge train (local merges autonomous, **push = owner gate**). Candidate disjoint buckets: **(a)** ERG figure/table wiring — OP/PhNR/flicker into figures + `companions/methods.py` (unblocked now the FACS lane landed); **(b)** public Selom backend on syd2 — backend **Dockerfile + GHCR image-CI** + the 5 data-plane answers (swordfish scoping note, `FROM-SWORDFISH.md` top); **(c)** Nango cloud FEATURE productization — FE import/export wiring + editor "export to Drive"; **(d)** Pillar-2 continued.
- **Cloud state — GOOGLE DRIVE IS CONNECTED + LIVE-VERIFIED (2026-07-25).** Connection `c878e8db-…` on `google-drive`; scope granted = `drive.file` only; refresh token present and a forced refresh works; a live `GET /proxy/drive/v3/about` returns the owner's account (200). The Google OAuth app was **already published** — publishing status was never the blocker, and the earlier failure's cause is **NOT established** (most likely never-completed or an expired connect-session token). It succeeded this time on a fresh link with no config change to the live broker.
- **TWO NANGO INSTANCES — do not confuse them** (this cost a diagnosis today): **LIVE = `https://nango.swordfish.cfd` on syd2**, swordfish-provisioned, holds the integrations + connections, is what `SELOM_NANGO_BASE_URL` points at; **DEV = `127.0.0.1:3003` on syd4** (`deploy/nango/docker-compose.yaml`), a separate stack with its own DB + secret key, used by nothing. Selom's secret key returns `unknown_account` on the wrong one — that one command is the tell. **`bash deploy/nango/preflight.sh [BASE]`** (exit-code gated) checks health + key-identity + a real connection refresh, and *skips* container checks unless the key authenticates on both, since a container's `NANGO_SERVER_URL` is only a claim. Run it before asking a human to consent. **Dropbox** integration is configured (4 scopes, preflighted clean) — connect link issued, **not yet confirmed connected**. **OneDrive/Microsoft ON HOLD.**
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

**`docs/next-session-plan/plan.md`** (the next-session entry: Phase 0 → 3 lanes → on-hold triage) · **`docs/milestone-review-2026-07-25/findings.md`** (54-finding backlog + status ledger) · `docs/next-session-plan/lane-mechanics-from-thalon.md` · `docs/restructure/plan.md` (WS3 done) · `docs/fe-review/spec.md` (now impeccable-only) · CLAUDE.md · `deploy/nango/` (once built). Memory: [[parallel-agent-lanes]] · [[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] · [[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.

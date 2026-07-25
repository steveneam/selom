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
| **SPRINT-2-MERGED** | 2026-07-25 | `main` `ba0de8c..27d8c07` | **Phase 0 done → 3 lanes forked, driven and MERGED in one session.** Owner cleared all four founder gates; `main` pushed (`60df628..dddf5d6`) and `campaign/parallel-lanes` deleted. Built the missing groundwork: **`scripts/verify.sh`** (first single gate of record — 7 gates at CI parity incl. the `fe-build` the plan omitted, ~70s) · **`scripts/worktree-setup.sh`** (lane provisioning was **PowerShell-only**, so no lane could have been forked on Linux) · the **frozen `GET /cloud/providers`** contract · **the reachability ratchet**, which found **17 of 61 routes with no FE call site** where the whole milestone review had found 2. Then **launched and drove all three lanes autonomously** (thalon's tmux procedure — the owner no longer drives) and ran the merge train `L1→L3→L2` myself: 16 lane commits, full gate **7/7 green on every rebased result**. Lane 2 found the sprint's worst bug: **`config.py` never read `app/backend/.env`**, so the server pointed at the dead `localhost:3003` while `preflight.sh` validated the live broker **from the same unread file** — a green guard checking a file the server never read. Reachability **17 → 16**. Also wrote the **annotation-layer remediation spec** (the owed plan) and recorded the icon decision + on-hold triage. |
| **REVIEW-MERGE** | 2026-07-25 | `main` `60df628..bee9e66` (**22 unpushed**) | Milestone review of the whole campaign branch (`review-gauntlet` 30 confirmed / 3 blockers + `fe-review` 24 confirmed, 31 of 35 user tasks with no affordance) → fix pass → **owner approved → `main` FF-merged**, gates re-run on merged main. **Both blockers fixed:** WS3.1 had flipped DE significance from adjusted p to RAW p across 5 runners while the axis/table/methods still said "adjusted" (`b73bd9b`, 2835 vs 1008 significant genes on the real EYG_28 export; the guard test had been inverted to bless it) · a gene-label click deleted the user's annotation (`b1a49e8`). HIGH honesty set fixed (`1d2aa81`): FACS cites FlowIO+FlowUtils not the absent FlowKit + states the real compensation outcome · assemble records lineage · GSEA's bare `t` no longer matches `entrezgene_id` · Nango ELv2 recorded. **Annotation layer DEFERRED pending a proper plan** (owner intent, clarified 2026-07-25 — *not* shelved: the flag `NEXT_PUBLIC_ANNOTATION_LAYER` is the holding mechanism while a real plan is written, and ~20 findings are parked with it, owed a plan not a flag flip). **Google Drive + Dropbox cloud connections now LIVE + verified** end-to-end. |
| **LAUNCH-CAMPAIGN** | 2026-07-23 | `60df628..e90203a` — **merged into `main` 2026-07-25** | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · SPRINT-2-MERGED · 2026-07-25 18:5x +1000 · branch `main` · Claude (FE+BE, solo, lead)

- **State: Sprint 2 is MERGED AND PUSHED.** `main` is linear and all three lanes landed via a lead-driven train (`L1 → L3 → L2`), **full `scripts/verify.sh` 7/7 green on each rebased result**. Pushed to `origin/main` 2026-07-25 (owner-authorized), which triggered the Vercel deploy. Worktrees removed, `agent/*` branches deleted, tmux sessions killed, dev servers stopped, tree clean. Always read the live count from `git rev-list --count origin/main..main`; never trust a literal here.
- **Lanes are fully torn down** — 3 worktrees removed, 3 `agent/*` branches deleted (all merged), 3 tmux sessions killed, main tree verified intact (39713 files, `.venv` present: `rm` does **not** follow the dep symlinks on Linux). **Lesson worth keeping: an idle Claude Code composer redisplays its last SUBMITTED message DIMMED (`ESC[2m`).** I read that as parked draft text in all three lanes and held teardown for it; the composers were empty. Check for the dim code before believing a pane has unsent input.
- **⚑ THE GATE OF RECORD IS `scripts/verify.sh`** — 7 gates, ~70s, raw + exit-code gated. **Never pipe it through `| tail`.** `--fast` skips `fe-build`; in a worktree `fe-build` is auto-`SKIP`ped (Turbopack rejects the out-of-root symlink) so **it and any browser check are merge-train-only, on the main checkout**.
- **⚑ CLOUD CONFIG — the bug that made the feature impossible, now fixed.** `app/backend/config.py` reads the **REPO-ROOT `.env`**; it never read `app/backend/.env`, where the creds had been staged. So `nango_base_url` silently fell back to `http://localhost:3003` (**dead**) and the secret key was empty — while `preflight.sh` read that same unused file and passed all five checks against the live broker. Migrated on this box and verified: backend now resolves `https://nango.swordfish.cfd` with Google + Dropbox **enabled**. Bound by `app/backend/tests/test_cloud_env_home.py`, which fails if the two homes diverge. **`app/backend/.env` now holds only the `GOOGLE_*`/`DROPBOX_*`/`MS_*` values for pasting into Nango's dashboard — read by nothing in this repo.**
- **Reachability ratchet is live** (`app/backend/tests/test_reachability_guard.py`, backlog `docs/reachability/backlog.md`): **16 unreachable routes remain**, each waived with an `R-xx` ID and a reason. **A stale waiver FAILS**, so the list can only shrink. Biggest rows: **R-01 the entire lit-synthesizer** (shipped, zero FE) and **R-02 the entire async job pipeline** — which *qualifies* the unparked `OH-01`, since that job-status store would ship with no reader.
- **Annotation layer: the owed plan EXISTS** — `docs/pillar-2-direct-manipulation/annotation-remediation-spec.md`. It is **deferred pending a proper plan, NOT shelved**; §6 states the exact flag-flip condition. Owner decisions in it: typed stars **allowed but marked `unverified`**; selection goes **full direct-manipulation**.
- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → export `SELOM_DATASETS_DIR` or real-data tests silently skip (`verify.sh` warns).

## ▸ NEXT  — **owner-directed 2026-07-25: "push, then d5, then real ui and anything you couldn't confirm — do these next session."** Push is DONE. Everything below is the next session's job, in this order.

### ① D-5 via a REAL UI RUN — the top item, and the blocker is already solved on paper

**Do the real run first; it is the key that unlocks every other browser check.** The figure editor renders **only** when the *live editor store* holds a spec — `components/project/views/figure-view.tsx:91` branches on `figure.spec`, **not** on the persisted figure record — and that store is seeded exclusively by `figure.init(spec)`, called from `openFigure` (`components/project/hooks/use-figure-crud.ts:55`) or automatically at the end of a run (`components/project/hooks/use-figure-run.ts:181`).

**Three approaches that DO NOT work — already tried, do not repeat:**
1. **The demo projects.** `demo-pbmc`'s seeded figure has **no `spec`**, so the editor shows *"Figure spec not stored"*. Same for the other two.
2. **Creating the project + figure via the API.** Works server-side (200), but the FE store is **localStorage-first**, so a project it never created renders **"Project not found"**. Projects/uploads also need a DB — start the backend with `SELOM_DATABASE_URL=sqlite:///<path>` + `SELOM_DB_AUTO_CREATE=true`, and put any such file **in the selom-data folder, not the repo** (owner-directed: all data lives in selom-data).
3. **Injecting into `localStorage['selom.projects.v1']`.** Does not survive the store's seed/reconcile on load.

**The path that WILL work:** a real run through the UI — new project → drop the CSV → run `volcano` → the completed run calls `figure.init(res.figure)` **itself** and opens the editor. Real data that is known-good for this: `…/selom-data/eyg28/raw/output_EYG_28_RO_human-RUVge-K4_20250602/DEG/EYG_28_RO_human-RUVge-K4_DEGs_All_PDE6B_FS_d180_vs_Control_d180.csv` — verified this session to return **200 with a RESPONSIVE spec** (3 traces, no `layout.width`), which is exactly the figure `D-5` requires. Budget the UI automation, or just do it by hand.

**Then run `D-5` (first) and `D-4`** from `agent_handoff/lane-wraps/lane3.md` — exact route, viewport and PASS/FAIL criteria are written out. `D-5` also asks for **one new number**: `stageClient` at both viewports, because Lane 3's new `min-h-[20rem]` (320px) floor is **wrong for real screens** if that value is ever near 352px.

### ② Everything else I could NOT confirm

| Item | State | Where |
|---|---|---|
| `D-1` · `D-3` · `D-6` · `D-7` · `D-10` · `D-11` | **unverified** — all need the editor open (① unlocks them) | `lane-wraps/lane3.md` |
| `D-2` | **unreachable by design** in a default build (annotation flag off) — anything checked with the flag ON is testing deferred Plan C territory; file against Plan C, do not close as shipped | `lane-wraps/lane3.md` |
| **Cloud round-trip end-to-end** — a real file imported from **Google Drive AND Dropbox** with `datasets.source` visible | **unverified.** This was Lane 2's own stated gate and no worktree could run a browser. It is now genuinely unblocked (below). | `lane-wraps/lane2.md` |
| `A25` | **only PARTIALLY fixed** — 3 of its 4 placeholders sat outside Lane 3's glob and were re-filed on the finding | `lane-wraps/lane3.md` |
| `L2-07` | **BLOCKED on swordfish** (public host for the Nango Connect UI). Not ours; the direct link flow works, so a *new* user cannot self-serve a connection until it lands. | ASK-BACKS |

**What IS confirmed, so do not redo it:** full-app smoke on merged `main` with real chromium — **10 routes × 2 desktop viewports, all 200, zero page errors, zero horizontal overflow**; and **`bash deploy/nango/preflight.sh` PASSES** post-merge, reading the *same* repo-root `.env` the server reads, with both connections refreshing (google-drive `c878e8db…`, dropbox `5f45a106…`). That last one matters: before the fix, preflight passed against the live broker **while the server pointed at a corpse**. They finally agree.

### ③ Then the reachability backlog — `docs/reachability/backlog.md`, 16 rows
**`R-02` first**, because it is a **precondition** for the unparked `OH-01` (arq + Redis job status), not a consequence: nothing in the FE polls a job, so that store would ship with **no reader**. Then `R-01`+`R-03` (largest user-visible loss, heavy overlap — the entire lit-synthesizer is shipped with zero FE), `R-04` (gates the proposal's `F1`), and `R-07` is a five-minute delete-or-use decision.

### ④ Then the annotation layer — `docs/pillar-2-direct-manipulation/annotation-remediation-spec.md`
Slices **C1 → C2 → C3 → C4**. `C1` first: it is the integrity defect *and* the cheapest, because it mostly **deletes** code (the server already computes stars from real data). Height-sensitive checks wait for ① — Lane 3 changed the artboard.

### ⑤ Still awaiting owner reaction
`docs/integration-robustness/proposal.md` — 4 proposed features, explicitly **no new analysis skills** (the constraint is reachability, not breadth). Plus the two unparked items (`OH-01` arq+Redis — sequence with `R-02`; `OH-07` journal style packs — the vehicle for `F3`).

## ▸ DEFERRED

- **OneDrive/Microsoft** cloud provider (owner on hold until a machine that logs into Azure cleanly).
- **Public Selom backend on syd2** (swordfish scoping note, FROM-SWORDFISH top): needs a backend **Dockerfile + GHCR image-CI** (mine) + 5 data-plane answers (DB/object-store/datasets-mount/heavy-jobs/auth). Owner-gated on any syd2 resize (spend). Reply in ASK-BACKS.
- WS6 AWS deploy — owner chose **"this box first, AWS later"**. Owed WS1/restructure reviews fold into the campaign milestone review.

## ▸ ENV / landmines (Linux · syd4)

- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → `SELOM_DATASETS_DIR`. **Docker installed** — in a fresh shell use `sudo docker` until the `deploy` docker-group login refreshes.
- **Gate of record = `scripts/verify.sh`** (7 gates, 70s, raw + exit-code gated). Do NOT hand-assemble gates and do NOT pipe it through `| tail` — a pipe returns tail's status and discards the failure [[read-gate-output-raw-not-piped]]. Servers: backend `uv run uvicorn main:app --reload`; frontend `npm install --legacy-peer-deps` **in the MAIN checkout only**. Derive the FE dev-lane port (Selom FE=3152) to avoid the shared-box `:3000` collision; `:8000` is eamos — never bind it.
- Every commit runs `.githooks/pre-commit` (hygiene-scan, 5 classes). `git user.email` MUST stay the noreply (`282747725+steveneam@…`) or Vercel blocks deploys [[selom-git-commit-email-vercel]].
- **Cloud OAuth creds** staged in `app/backend/.env` (gitignored): `GOOGLE_*` ✓ · `DROPBOX_*` ✓ · `MS_*` empty (on hold). The syd4 **Nango dev copy** (`deploy/nango/`) is **STOPPED** as of 2026-07-25 — containers + volumes intact, restart with `sudo docker compose -f deploy/nango/docker-compose.yaml start`. A dead `localhost:3003` is EXPECTED; the live broker is swordfish's on **syd2** (`nango.swordfish.cfd`) and is unaffected. Verify any time with `bash deploy/nango/preflight.sh`.
- **Worktree lanes share deps by SYMLINK** (`scripts/worktree-setup.sh`): never `npm install` in a lane (it writes through the link and clobbers the main tree — `guard-worktree-install.mjs` refuses it), and a lane needing a new BE dep **re-plans** rather than syncing, because `uv run` auto-syncs the SHARED `.venv`. Turbopack cannot run in a lane at all, so `next build`/`next dev` and browser checks belong on the main checkout.
- **The agent cannot marshal binary/large files through chat** (base64 reproduction corrupts, even ~20 KB) — deliver files via a real channel (scp/SFTP/rclone/the cloud integration), never by pasting base64 into a tool call. Emailing via the Gmail MCP is draft-only + attachment-limited; Drive `create_file` needs valid inline base64 (same wall).

## ▸ READ FIRST

**`docs/next-session-plan/plan.md`** (the entry point — **Phase 0 done, start at §Lanes**) · **`docs/integration-robustness/proposal.md`** (awaiting owner reaction) · **`docs/cloud-providers-contract/spec.md`** (the FROZEN cross-lane contract — read before touching cloud) · **`docs/milestone-review-2026-07-25/findings.md`** (54-finding backlog + status ledger) · `agent_handoff/DECISIONS.md` (#12 = lucide stays) · `docs/on-hold/README.md` (now the ONE on-hold register) · `docs/next-session-plan/lane-mechanics-from-thalon.md` · `docs/restructure/plan.md` (WS3 done) · `docs/fe-review/spec.md` (now impeccable-only) · CLAUDE.md · `deploy/nango/` (once built). Memory: [[parallel-agent-lanes]] · [[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] · [[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.

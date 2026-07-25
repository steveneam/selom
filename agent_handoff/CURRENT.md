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
| **EDITOR-ROOM** | 2026-07-25 | `main` `92d6f2e..f98bdbd` (**6 unpushed**) | **Worked the board top to bottom: `W-1` · `Q-1`/`Q-2` · `V-1` · `W-2` · `V-2` all DONE, browser-verify 14/14 and `verify.sh` 7/7.** **The 1280 width defect is fixed — the plotting area went 90px → 571px**, and every checked width clears §D's 506px target (1280→571, 1440→727, 1920→718), which turned the long-red `D-5 (also-confirm)` gate green. `W-1` first: a figure never reflowed when its CONTAINER resized (only the window), so collapsing a rail bought the plot **zero** pixels and every other remedy was invisible. Then the inspector dock got a collapse control + a tab-icon spine, both rails auto-collapse on a narrow viewport, and zoom/Fit landed in the strip that was an inert hint line. **Three findings the browser produced that no gate could:** `/extract`'s editor **overflowed its band and painted the figure through the Statistics table** while every per-element number read PASS (`EditorWorkspace` needs a flex parent; `CanvasShell` gave it one, `chart-extractor` did not) · the **OAuth cloud-import path was unreachable in the UI** — the menu's loader cancelled its own connections request, so no provider ever showed an import form · and the spec's own 1280 threshold was **wrong**, since at 1440 the plot was 247px, *worse than a collapsed 1280*. **⚑ FOUNDER DECISION OWED: Selom cannot see files the user already has** — Drive is `drive.file`-scoped and Dropbox is an App Folder, so it reads only what it created, and the menu's "copy the share link" hint is impossible to follow. Options + recommendation in `docs/cloud-providers-contract/spec.md` §Scope. |
| **BROWSER-VERIFY** | 2026-07-25 | `main` `ff9705d..b0fc61b` (**pushed**) | **Built the browser-verify harness and answered the §D list in a real browser.** `scripts/browser-verify.sh` boots a real backend + frontend and drives the one path that opens the editor (new project → real EYG_28 CSV → the engine's recommended skill); checks are specs, not scripts. **It found a blocking crash on the primary flow before running a single check** — `datasets.qc` holds two shapes and the mapper cast whichever arrived into the FE's `QcReport`, so **dropping any real file took the whole app to the error overlay**; invisible to every gate because `dev:mock` skips the upload path. **D-5: A24 confirmed FIXED** (`overflow=0`, `card = stageClient − 32` exactly at 1280/1440/1920); keep the `min-h-[20rem]` floor; the `88rem` cap is unreachable. **NEW FINDING: the hero is starved of WIDTH at 1280** — 90px of plotting area, not §D's assumed 506, because fixed columns take 70% of the viewport. D-4/D-1/D-7/D-3/D-9/D-10 all PASS (§D's "Legend overflows" prediction disproven); 2 founder calls. Gate 7/7. |
| **SPRINT-2-MERGED** | 2026-07-25 | `main` `ba0de8c..698381d` | **Phase 0 done → 3 lanes forked, driven and MERGED in one session.** Owner cleared all four founder gates; `main` pushed (`60df628..dddf5d6`) and `campaign/parallel-lanes` deleted. Built the missing groundwork: **`scripts/verify.sh`** (first single gate of record — 7 gates at CI parity incl. the `fe-build` the plan omitted, ~70s) · **`scripts/worktree-setup.sh`** (lane provisioning was **PowerShell-only**, so no lane could have been forked on Linux) · the **frozen `GET /cloud/providers`** contract · **the reachability ratchet**, which found **17 of 61 routes with no FE call site** where the whole milestone review had found 2. Then **launched and drove all three lanes autonomously** (thalon's tmux procedure — the owner no longer drives) and ran the merge train `L1→L3→L2` myself: 16 lane commits, full gate **7/7 green on every rebased result**. Lane 2 found the sprint's worst bug: **`config.py` never read `app/backend/.env`**, so the server pointed at the dead `localhost:3003` while `preflight.sh` validated the live broker **from the same unread file** — a green guard checking a file the server never read. Reachability **17 → 16**. Also wrote the **annotation-layer remediation spec** (the owed plan) and recorded the icon decision + on-hold triage. |
| **REVIEW-MERGE** | 2026-07-25 | `main` `60df628..bee9e66` (**22 unpushed**) | Milestone review of the whole campaign branch (`review-gauntlet` 30 confirmed / 3 blockers + `fe-review` 24 confirmed, 31 of 35 user tasks with no affordance) → fix pass → **owner approved → `main` FF-merged**, gates re-run on merged main. **Both blockers fixed:** WS3.1 had flipped DE significance from adjusted p to RAW p across 5 runners while the axis/table/methods still said "adjusted" (`b73bd9b`, 2835 vs 1008 significant genes on the real EYG_28 export; the guard test had been inverted to bless it) · a gene-label click deleted the user's annotation (`b1a49e8`). HIGH honesty set fixed (`1d2aa81`): FACS cites FlowIO+FlowUtils not the absent FlowKit + states the real compensation outcome · assemble records lineage · GSEA's bare `t` no longer matches `entrezgene_id` · Nango ELv2 recorded. **Annotation layer DEFERRED pending a proper plan** (owner intent, clarified 2026-07-25 — *not* shelved: the flag `NEXT_PUBLIC_ANNOTATION_LAYER` is the holding mechanism while a real plan is written, and ~20 findings are parked with it, owed a plan not a flag flip). **Google Drive + Dropbox cloud connections now LIVE + verified** end-to-end. |
| **LAUNCH-CAMPAIGN** | 2026-07-23 | `60df628..e90203a` — **merged into `main` 2026-07-25** | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · EDITOR-ROOM · 2026-07-25 23:18 +1000 (Sydney) · branch `main` `92d6f2e..f98bdbd` (**6 unpushed — owner pushes**) · Claude (FE+BE, solo, lead)

- **The whole board is worked: `W-1` · `Q-1`/`Q-2` · `V-1` · `W-2` · `V-2` all `DONE`.** Gates:
  **`scripts/verify.sh` 7/7** and **`scripts/browser-verify.sh` 14/14** — the first time the browser
  suite has been all-green, including the `D-5 (also-confirm)` gate that was deliberately red since
  it was written. Statuses + full detail live in `docs/next-session-plan/plan.md`; don't re-narrate.
- **The 1280 width defect is FIXED: 90px of plotting area → 571px**, and every checked width clears
  §D's 506px target (1280→**571**, 1440→**727**, 1920→**718**). Two changes did it: `W-1` made a
  figure reflow when its **container** resizes (before, collapsing a rail bought the plot *zero*
  pixels, so every other width remedy was invisible), and `W-2` gave the inspector dock a collapse
  control + tab-icon spine, auto-collapsed both rails on a narrow viewport, and put zoom/Fit in the
  strip that used to be an inert hint line.
- **⚑ FOUNDER DECISION OWED — Selom cannot see files the user already has.** Google's connection is
  `drive.file`-scoped ("only files you use with this app") and Dropbox's is an App Folder, so Selom
  reads **only what it created**. The menu's own hint — "Open the file in Drive → Share → Copy link"
  — describes a file it has no permission to read. `POST /export/cloud` is a stub for both OAuth
  providers, so export→re-import is not a workaround either. Options, trade-offs and a
  recommendation (**Google Picker** over broadening to the *restricted* `drive.readonly` scope, which
  carries an annual CASA assessment) are in `docs/cloud-providers-contract/spec.md` §Scope.
- **Three defects only a browser could find, each behind green gates.** `/extract`'s editor
  **overflowed its band and painted the figure through the Statistics table** — every per-element
  number still read PASS (`overflow=0`, `matches=1`); `EditorWorkspace` takes a definite height only
  from a flex parent, which `CanvasShell` gave it and `chart-extractor` did not. The **OAuth
  cloud-import path was unreachable in the UI**: the menu's loader listed `providers` as a dependency
  *and* as its guard, so setting it cancelled the in-flight connections request and no provider ever
  rendered an import form. And the editor-room spec's own **1280 threshold was wrong** — at 1440 the
  plot was 247px, *worse than a collapsed 1280* — so it is now derived from the target (1700).
- **The cloud round trip is verified end-to-end** against the live broker: a real CSV imported from
  **Google Drive** and **Dropbox** through the real UI, each landing with a source chip naming its
  provider and reference. The two seeded test files have been **deleted** from both accounts.
- **Harness got stronger, not just used:** a `warm-routes` globalSetup (a cold `next dev` compile was
  being charged to whichever check ran first — three false timeouts in three different checks), and
  `d5` now asserts the target at **every** viewport it measures, which is what would have caught the
  1440 hole immediately.

## ▸ PRIOR · BROWSER-VERIFY · 2026-07-25 21:20 +1000 (Sydney) · branch `main` `ff9705d..b0fc61b` (**pushed to origin/main**, 0 ahead) · Claude (FE+BE, solo, lead)

- **The harness exists and the §D list is answered.** `scripts/browser-verify.sh` boots a real
  backend (`:8152`, SQLite in the corpus dir) + a real frontend (`:3152`) and drives the ONLY path
  that opens the editor — new project → drop the real EYG_28 DE CSV → run the engine's recommended
  skill. Checks are specs under `app/frontend/e2e/browser-verify/`; adding one is a new `.spec.ts`,
  never another bespoke script. **Full gate 7/7 green.**
- **⚑ It found a blocking crash on the primary flow before running a single check** (`3e171e5`):
  `datasets.qc` holds TWO shapes and the mapper cast whichever arrived into the FE's `QcReport`. The
  real upload path stores the **engine's** report (no `nObs`/`nVar`); every consumer formats
  `qc.nObs.toLocaleString()` — so **dropping any real file took the whole app to the error overlay.**
  Invisible to every prior gate because `dev:mock` skips `uploadDataset` entirely.
- **D-5: A24 is FIXED, confirmed in a browser.** `overflow=0`, `card = stageClient − 32` exactly at
  1280/1440/1920. **Keep `min-h-[20rem]`** — the shortest real stage is 402px, 50px clear of the
  352px engagement point. The `88rem` cap is **unreachable** (stage is 938px even at 1920).
- **⚑ NEW FINDING — the hero is starved of WIDTH at 1280.** The plotting area is **90px**, not the
  ~506px §D assumed: fixed columns (sidebar 256 + workrail 256 + tools rail 48 + inspector 330) take
  **70% of the viewport**, leaving the hero 21% and the plot **7%**. Gene labels overlap into an
  unreadable cluster. Independent of `L3-01`. Fine at 1920. This is the largest open FE defect.
- **Everything else on §D that a default build can reach PASSED** — D-4 (palette retirement held;
  CommandBar wraps to 3 rows/74px at 1280), D-1 (§D's "Legend overflows" prediction **disproven** —
  13–26px of slack), D-7, D-3, D-9, D-10. Two founder calls: the tools rail ships as a **one-button
  48px column**, and **"Edit a copy" appears twice** on a frozen figure. Full table with the numbers:
  `agent_handoff/lane-wraps/lane3.md` §RESULTS.
- **Two traps pinned in the harness so nobody re-hits them:** serving the dev app on `127.0.0.1`
  **silently prevents React from hydrating** (Next 16 trusts only `localhost` for dev resources — no
  error, everything looks clickable, nothing works); and the harness **must reset its own store each
  run** or reconcile drags every prior figure spec in and blows the timeout.

## ▸ EARLIER · SPRINT-2-MERGED · 2026-07-25 19:46 +1000 (Sydney) · branch `main` · Claude (FE+BE, solo, lead)

- **State: Sprint 2 is MERGED AND PUSHED.** `main` is linear and all three lanes landed via a lead-driven train (`L1 → L3 → L2`), **full `scripts/verify.sh` 7/7 green on each rebased result**. Pushed to `origin/main` 2026-07-25 (owner-authorized), which triggered the Vercel deploy. Worktrees removed, `agent/*` branches deleted, tmux sessions killed, dev servers stopped, tree clean. Always read the live count from `git rev-list --count origin/main..main`; never trust a literal here.
- **Lanes are fully torn down** — 3 worktrees removed, 3 `agent/*` branches deleted (all merged), 3 tmux sessions killed, main tree verified intact (39713 files, `.venv` present: `rm` does **not** follow the dep symlinks on Linux). **Lesson worth keeping: an idle Claude Code composer redisplays its last SUBMITTED message DIMMED (`ESC[2m`).** I read that as parked draft text in all three lanes and held teardown for it; the composers were empty. Check for the dim code before believing a pane has unsent input.
- **⚑ THE GATE OF RECORD IS `scripts/verify.sh`** — 7 gates, ~70s, raw + exit-code gated. **Never pipe it through `| tail`.** `--fast` skips `fe-build`; in a worktree `fe-build` is auto-`SKIP`ped (Turbopack rejects the out-of-root symlink) so **it and any browser check are merge-train-only, on the main checkout**.
- **⚑ CLOUD CONFIG — the bug that made the feature impossible, now fixed.** `app/backend/config.py` reads the **REPO-ROOT `.env`**; it never read `app/backend/.env`, where the creds had been staged. So `nango_base_url` silently fell back to `http://localhost:3003` (**dead**) and the secret key was empty — while `preflight.sh` read that same unused file and passed all five checks against the live broker. Migrated on this box and verified: backend now resolves `https://nango.swordfish.cfd` with Google + Dropbox **enabled**. Bound by `app/backend/tests/test_cloud_env_home.py`, which fails if the two homes diverge. **`app/backend/.env` now holds only the `GOOGLE_*`/`DROPBOX_*`/`MS_*` values for pasting into Nango's dashboard — read by nothing in this repo.**
- **Reachability ratchet is live** (`app/backend/tests/test_reachability_guard.py`, backlog `docs/reachability/backlog.md`): **16 unreachable routes remain**, each waived with an `R-xx` ID and a reason. **A stale waiver FAILS**, so the list can only shrink. Biggest rows: **R-01 the entire lit-synthesizer** (shipped, zero FE) and **R-02 the entire async job pipeline** — which *qualifies* the unparked `OH-01`, since that job-status store would ship with no reader.
- **Annotation layer: the owed plan EXISTS** — `docs/pillar-2-direct-manipulation/annotation-remediation-spec.md`. It is **deferred pending a proper plan, NOT shelved**; §6 states the exact flag-flip condition. Owner decisions in it: typed stars **allowed but marked `unverified`**; selection goes **full direct-manipulation**.
- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → export `SELOM_DATASETS_DIR` or real-data tests silently skip (`verify.sh` warns).

## ▸ NEXT  — **the board is `docs/next-session-plan/plan.md`. Tracks W and V are DONE; start at Track R (`R-02`).**

> **Board state after EDITOR-ROOM:** `W-1` `W-2` `Q-1` `Q-2` `V-1` `V-2` are all **`DONE`**. The
> remaining order is the board's own: **Track R** (reachability, `R-02` first because it is a
> *precondition* for `OH-01`, not a consequence) → **Track C** (annotation, C1→C4, spec exists) →
> **Track O** as the owner reacts. The standing approval from 2026-07-25 still covers them.
>
> **Two things want the owner before code:**
> 1. **The cloud scope decision** (`docs/cloud-providers-contract/spec.md` §Scope) — Selom can only
>    read files it created, so the import feature is nearly useless as shipped. Recommendation:
>    the Google Picker, not a broader scope.
> 2. **6 commits are unpushed** — the owner pushes.
>
> Smaller, already-recorded: `/extract`'s stage is 279px at 1280×800, so the `min-h-[20rem]` floor
> engages there and 73px scrolls — reported, not filed, but it qualifies `D-5`'s "keep the floor"
> verdict, which was measured on the shell where the shortest stage is 402px.

<details><summary>Superseded — the original W-1-first instruction (kept for provenance)</summary>

> **⚑ THE WHOLE BOARD IS OWNER-APPROVED TO EXECUTE — owner, 2026-07-25: *"we do all those next
> session on gogogo"*.** So on `gogogo`: open the board and start `W-1`. Do **not** re-present the
> plan for approval and do not ask which item to begin — the approval is already given, and this
> line is it. Work the tracks in the board's stated order.
>
> **The one exception is `Q-1` + `Q-2`**, which are founder decisions by nature (a layout-model
> choice and two judgement calls). Put them to the owner **early, via `AskUserQuestion`**, so the
> answers arrive while `W-1` is being built — then carry on. Do not idle waiting on them: `W-1`,
> `V-1` and `V-2` need no decision, and only `W-2` is genuinely blocked on `Q-1`.

Owner-directed 2026-07-25: **run it SEQUENTIALLY — no worktree lanes.** The board carries every open
item with a stable ID, a status cell, acceptance criteria and its verify command; this slot stays a
pointer so there is one place to update, not two.

- **`W-1` is the first action** — a figure does not reflow when its CONTAINER resizes (only on a
  *window* resize), so collapsing the workrail buys the artboard 208px and the plot **zero**. Every
  other width fix is invisible to a user until this lands. Confirmed bug, small, regression test
  already written (`scripts/browser-verify.sh remedy-sizing`), needs no owner decision.
- **Ask `Q-1` + `Q-2` at the same time** so the answers are waiting: `Q-1` = which fixed chrome
  yields (the 330px inspector dock has no collapse control and is the largest remaining spender) —
  forcing questions → a spec, not code. `Q-2` = the two founder calls from the browser sweep.
- Then **`V-1`** (D-11 `/extract`, the last reachable §D bullet — needs canvas calibration),
  **`W-2`**, **`V-2`** (cloud round-trip + D-8), then **Track R** (reachability, 15 rows, `R-02`
  first because it is a *precondition* for `OH-01`), then **Track C** (annotation C1→C4, spec
  exists), then **Track O** as the owner reacts.

</details>

**Still true and not to be redone:** the full-app smoke on merged `main` (10 routes × 2 desktop
viewports, all 200, zero page errors) and `bash deploy/nango/preflight.sh` passing against the live
broker. The §D results are in `agent_handoff/lane-wraps/lane3.md` §RESULTS — re-run the specs rather
than re-reasoning them.

## ▸ DEFERRED

- **OneDrive/Microsoft** cloud provider (owner on hold until a machine that logs into Azure cleanly).
- **Public Selom backend on syd2** (swordfish scoping note, FROM-SWORDFISH top): needs a backend **Dockerfile + GHCR image-CI** (mine) + 5 data-plane answers (DB/object-store/datasets-mount/heavy-jobs/auth). Owner-gated on any syd2 resize (spend). Reply in ASK-BACKS.
- WS6 AWS deploy — owner chose **"this box first, AWS later"**. Owed WS1/restructure reviews fold into the campaign milestone review.

## ▸ ENV / landmines (Linux · syd4)

- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → `SELOM_DATASETS_DIR`. **Docker installed** — in a fresh shell use `sudo docker` until the `deploy` docker-group login refreshes.
- **Gate of record = `scripts/verify.sh`** (7 gates, 70s, raw + exit-code gated). Do NOT hand-assemble gates and do NOT pipe it through `| tail` — a pipe returns tail's status and discards the failure [[read-gate-output-raw-not-piped]]. Servers: backend `uv run uvicorn main:app --reload`; frontend `npm install --legacy-peer-deps` **in the MAIN checkout only**. Derive the FE dev-lane port (Selom FE=3152) to avoid the shared-box `:3000` collision; `:8000` is eamos — never bind it.
- **Browser checks = `scripts/browser-verify.sh`** (needs `SELOM_DATASETS_DIR`). It owns its servers
  (BE `:8152` + FE `:3152`) and stops them on exit, and **resets its own SQLite store each run** —
  without that, reconcile drags every prior figure spec in and the drive blows the 180s timeout.
  **Serve the dev app on `localhost`, NEVER `127.0.0.1`:** Next 16 blocks its own dev resources
  cross-origin and trusts only `localhost`, so on `127.0.0.1` the page renders and every control
  looks clickable but **React never hydrates** — no handler fires, no error, nothing works.
- Every commit runs `.githooks/pre-commit` (hygiene-scan, 5 classes). `git user.email` MUST stay the noreply (`282747725+steveneam@…`) or Vercel blocks deploys [[selom-git-commit-email-vercel]].
- **Cloud OAuth creds** staged in `app/backend/.env` (gitignored): `GOOGLE_*` ✓ · `DROPBOX_*` ✓ · `MS_*` empty (on hold). The syd4 **Nango dev copy** (`deploy/nango/`) is **STOPPED** as of 2026-07-25 — containers + volumes intact, restart with `sudo docker compose -f deploy/nango/docker-compose.yaml start`. A dead `localhost:3003` is EXPECTED; the live broker is swordfish's on **syd2** (`nango.swordfish.cfd`) and is unaffected. Verify any time with `bash deploy/nango/preflight.sh`.
- **Worktree lanes share deps by SYMLINK** (`scripts/worktree-setup.sh`): never `npm install` in a lane (it writes through the link and clobbers the main tree — `guard-worktree-install.mjs` refuses it), and a lane needing a new BE dep **re-plans** rather than syncing, because `uv run` auto-syncs the SHARED `.venv`. Turbopack cannot run in a lane at all, so `next build`/`next dev` and browser checks belong on the main checkout.
- **The agent cannot marshal binary/large files through chat** (base64 reproduction corrupts, even ~20 KB) — deliver files via a real channel (scp/SFTP/rclone/the cloud integration), never by pasting base64 into a tool call. Emailing via the Gmail MCP is draft-only + attachment-limited; Drive `create_file` needs valid inline base64 (same wall).

## ▸ READ FIRST

**`docs/next-session-plan/plan.md`** (the entry point — **the work board; start at `W-1`**) · **`agent_handoff/lane-wraps/lane3.md` §RESULTS** (what the browser actually measured) · **`docs/integration-robustness/proposal.md`** (awaiting owner reaction) · **`docs/cloud-providers-contract/spec.md`** (the FROZEN cross-lane contract — read before touching cloud) · **`docs/milestone-review-2026-07-25/findings.md`** (54-finding backlog + status ledger) · `agent_handoff/DECISIONS.md` (#12 = lucide stays) · `docs/on-hold/README.md` (now the ONE on-hold register) · `docs/next-session-plan/lane-mechanics-from-thalon.md` · `docs/restructure/plan.md` (WS3 done) · `docs/fe-review/spec.md` (now impeccable-only) · CLAUDE.md · `deploy/nango/` (once built). Memory: [[parallel-agent-lanes]] · [[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] · [[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.

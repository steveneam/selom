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
| **CLOUD-EXPORT** | 2026-08-02 | `main` `1c4a6f4..01e3736` (**pushed**) | **Track E built end-to-end: figures can be sent to Google Drive / Dropbox.** Spec first (`docs/cloud-export/spec.md`), then `E-1` real uploads (Drive resumable · Dropbox simple + chunked session above its 150 MB ceiling; both CREATE, never overwrite) · `E-2` `/export/cloud` takes **either** a `dataset_id` **or** a rendered figure · `E-3` "Save to Drive/Dropbox" in the export menu. Key design (D1): `push_path` became the connector primitive and `push_from_store` a shared wrapper — that is what let a figure export without inventing a scratch object in the store. **Three real defects found:** figure export required a DATABASE (`Depends(_uploads_repo)` at the signature, 503 on any box without one) · the export menu carried a hardcoded disabled "Coming soon", the exact client-side pattern the frozen contract forbids and the A20 failure it exists to stop · and Mobbin ruled a pattern OUT — Drive's own folder-picker modal is impossible under `drive.file`, so there is deliberately no picker. **⚑ `E-3` is BUILT, NOT DONE — every test is a mock and no byte has reached a real account.** Also wrote **`docs/build-plan-2026-08/plan.md`**, the master sequencing doc for the autonomous run. Gate 7/7 on every commit. |
| **ERG-MOCK** | 2026-08-02 | `main` `92d6f2e..288e07d` (**pushed**) | Owner-requested mock Fig 1E dataset for laying out the ERG intensity-response figure — `docs/records/erg-module/mock-fig1e/` (+ `n3/`). Simulated b-wave table (all 210 individual points, so mean/SEM is recomputable, not taken on trust) + a trace grid whose **waveform shapes are the real decoded recordings**. Three requested departures from the printed figure: CMV-GFP pulled to a clean null, RK-PDE6B a partial rescue, and the two rescue arms separated only *slightly* (`*`, p 0.02–0.03 at **both** 1.0 and 1.9 log). Plus the rd10 **threshold**: only the WT Control responds below flash 1.0. **The generator self-checks and exits non-zero WITHOUT writing if a retune breaks the biology** — it caught four real defects during the build (null curves running *downward* with intensity from a flat noise term; rescue arms flipping at the noise floor; a too-strict rank check below threshold; a monotonicity tolerance that did not scale with amplitude). Welch t-test is hand-rolled (stdlib has no t-distribution) and **validated against scipy to 1.5e-15**. Side effect worth knowing: pushing swept up **the 6 previously-unpushed EDITOR-ROOM commits**. Answered an owner question with code, not memory: **figures cannot be exported to Drive today** → new **Track E** on the board. |
| **EDITOR-ROOM** | 2026-07-25 | `main` `92d6f2e..f98bdbd` (**6 unpushed**) | **Worked the board top to bottom: `W-1` · `Q-1`/`Q-2` · `V-1` · `W-2` · `V-2` all DONE, browser-verify 14/14 and `verify.sh` 7/7.** **The 1280 width defect is fixed — the plotting area went 90px → 571px**, and every checked width clears §D's 506px target (1280→571, 1440→727, 1920→718), which turned the long-red `D-5 (also-confirm)` gate green. `W-1` first: a figure never reflowed when its CONTAINER resized (only the window), so collapsing a rail bought the plot **zero** pixels and every other remedy was invisible. Then the inspector dock got a collapse control + a tab-icon spine, both rails auto-collapse on a narrow viewport, and zoom/Fit landed in the strip that was an inert hint line. **Three findings the browser produced that no gate could:** `/extract`'s editor **overflowed its band and painted the figure through the Statistics table** while every per-element number read PASS (`EditorWorkspace` needs a flex parent; `CanvasShell` gave it one, `chart-extractor` did not) · the **OAuth cloud-import path was unreachable in the UI** — the menu's loader cancelled its own connections request, so no provider ever showed an import form · and the spec's own 1280 threshold was **wrong**, since at 1440 the plot was 247px, *worse than a collapsed 1280*. **⚑ FOUNDER DECISION OWED: Selom cannot see files the user already has** — Drive is `drive.file`-scoped and Dropbox is an App Folder, so it reads only what it created, and the menu's "copy the share link" hint is impossible to follow. Options + recommendation in `docs/cloud-providers-contract/spec.md` §Scope. |
| **BROWSER-VERIFY** | 2026-07-25 | `main` `ff9705d..b0fc61b` (**pushed**) | **Built the browser-verify harness and answered the §D list in a real browser.** `scripts/browser-verify.sh` boots a real backend + frontend and drives the one path that opens the editor (new project → real EYG_28 CSV → the engine's recommended skill); checks are specs, not scripts. **It found a blocking crash on the primary flow before running a single check** — `datasets.qc` holds two shapes and the mapper cast whichever arrived into the FE's `QcReport`, so **dropping any real file took the whole app to the error overlay**; invisible to every gate because `dev:mock` skips the upload path. **D-5: A24 confirmed FIXED** (`overflow=0`, `card = stageClient − 32` exactly at 1280/1440/1920); keep the `min-h-[20rem]` floor; the `88rem` cap is unreachable. **NEW FINDING: the hero is starved of WIDTH at 1280** — 90px of plotting area, not §D's assumed 506, because fixed columns take 70% of the viewport. D-4/D-1/D-7/D-3/D-9/D-10 all PASS (§D's "Legend overflows" prediction disproven); 2 founder calls. Gate 7/7. |
| **SPRINT-2-MERGED** | 2026-07-25 | `main` `ba0de8c..698381d` | **Phase 0 done → 3 lanes forked, driven and MERGED in one session.** Owner cleared all four founder gates; `main` pushed (`60df628..dddf5d6`) and `campaign/parallel-lanes` deleted. Built the missing groundwork: **`scripts/verify.sh`** (first single gate of record — 7 gates at CI parity incl. the `fe-build` the plan omitted, ~70s) · **`scripts/worktree-setup.sh`** (lane provisioning was **PowerShell-only**, so no lane could have been forked on Linux) · the **frozen `GET /cloud/providers`** contract · **the reachability ratchet**, which found **17 of 61 routes with no FE call site** where the whole milestone review had found 2. Then **launched and drove all three lanes autonomously** (thalon's tmux procedure — the owner no longer drives) and ran the merge train `L1→L3→L2` myself: 16 lane commits, full gate **7/7 green on every rebased result**. Lane 2 found the sprint's worst bug: **`config.py` never read `app/backend/.env`**, so the server pointed at the dead `localhost:3003` while `preflight.sh` validated the live broker **from the same unread file** — a green guard checking a file the server never read. Reachability **17 → 16**. Also wrote the **annotation-layer remediation spec** (the owed plan) and recorded the icon decision + on-hold triage. |
| **REVIEW-MERGE** | 2026-07-25 | `main` `60df628..bee9e66` (**22 unpushed**) | Milestone review of the whole campaign branch (`review-gauntlet` 30 confirmed / 3 blockers + `fe-review` 24 confirmed, 31 of 35 user tasks with no affordance) → fix pass → **owner approved → `main` FF-merged**, gates re-run on merged main. **Both blockers fixed:** WS3.1 had flipped DE significance from adjusted p to RAW p across 5 runners while the axis/table/methods still said "adjusted" (`b73bd9b`, 2835 vs 1008 significant genes on the real EYG_28 export; the guard test had been inverted to bless it) · a gene-label click deleted the user's annotation (`b1a49e8`). HIGH honesty set fixed (`1d2aa81`): FACS cites FlowIO+FlowUtils not the absent FlowKit + states the real compensation outcome · assemble records lineage · GSEA's bare `t` no longer matches `entrezgene_id` · Nango ELv2 recorded. **Annotation layer DEFERRED pending a proper plan** (owner intent, clarified 2026-07-25 — *not* shelved: the flag `NEXT_PUBLIC_ANNOTATION_LAYER` is the holding mechanism while a real plan is written, and ~20 findings are parked with it, owed a plan not a flag flip). **Google Drive + Dropbox cloud connections now LIVE + verified** end-to-end. |
| **LAUNCH-CAMPAIGN** | 2026-07-23 | `60df628..e90203a` — **merged into `main` 2026-07-25** | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ EARLIER · EDITOR-ROOM · 2026-07-25 23:18 +1000 (Sydney) · branch `main` `92d6f2e..f98bdbd` (**6 unpushed — owner pushes**) · Claude (FE+BE, solo, lead)

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

## ▸ LIVE · CLOUD-EXPORT · 2026-08-02 22:40 +1000 (Sydney) · branch `main` `1c4a6f4..01e3736` (**pushed, 0 ahead**) · Claude (FE+BE, solo, lead)

- **Track E is coded and green** (`E-1` 468886c · `E-2` 927107f · `E-3` ed3b435), `scripts/verify.sh`
  **7/7** on each. Detail is in the commits + `docs/cloud-export/spec.md`; don't re-narrate.
- **⚑ `E-3` is BUILT but NOT DONE.** Every test is a mock and **no byte has reached a real Drive
  account**. This is the FIRST action next session, before any new code. Two failure modes a mock
  cannot catch, both likely: Drive returns the resumable **session URI** in a `Location` header that
  a real client may see on a 200 *or* a 308, and Dropbox's `Dropbox-API-Arg` header **rejects
  non-ASCII** — a figure named with "µV" (very likely here) fails on a real call while every mock
  passes.
- **`docs/build-plan-2026-08/plan.md` is the master plan** for the autonomous run: five phases
  (P-A finish half-built work → P-B workspace UX audit → P-C landing page → P-D skill coverage →
  P-E platform), ~10–13 sessions, with the founder gates batched for the owner's return.
- **One measured correction worth carrying:** "not all the skills are working" is half wrong. **35 of
  36 skills have a real engine** (`run_real.py`; only `umap_scrna` is stub-only). What is actually
  broken is **reach and affordance** — ~15 routes have no FE call site, including the whole
  lit-synthesizer and the **Reproducibility Score**, a named part of the product thesis that cannot
  currently be shown for a paper. So the fix is wiring + audit, not rewriting skills.
- **The landing page is NOT Selom's work** (owner-directed 2026-08-02): delegated to **Thalon**.
  Selom's job is to be a complete product. Two things Selom owes that build and must not duplicate:
  the **public/private route split** (today `/` IS the dashboard, so a marketing site forces a
  decision about where the app moves) and the **parked hero animation** (`cb813cf`) — already built,
  currently unused.
- **⚑ The largest remaining "not actually a product" gap is AUTH, and it is one-sided.** The backend
  is ready — `auth/clerk.py` verifies the JWT, the tenant comes from the verified `sub`, every
  handler already resolves keys from the tenant's own row. The **frontend has nothing**: no
  `@clerk/nextjs`, no provider, no middleware, no sign-in, so `auth_mode=dev` means *every request
  is the same tenant*. Selom cannot have two users today. Now **P-E**, with the isolation proved by
  test (tenant A cannot read/list/export tenant B) rather than claimed.

## ▸ NEXT  — **master plan = `docs/build-plan-2026-08/plan.md`. Start at `P-A / A1`: the cloud-export REAL round trip.**

> **Owner is away several days and asked for autonomous build work** (2026-08-02): frontend,
> backend, flow, integrations, plus a Mobbin-driven UX audit. `docs/build-plan-2026-08/plan.md` is
> the sequencing doc; `docs/next-session-plan/plan.md` stays the per-row detail for Tracks R/C/O.
>
> **Order:** `A1` cloud-export real round trip (**first — it is owed, not optional**) → `A2` `R-02`
> job pipeline (**before `OH-01`**, or that store ships with no reader) → `A3` `R-01`+`R-03`
> lit-synthesizer + Reproducibility Score (spec the IA placement first) → `A4` `R-04`/`R-06`/`R-05`
> → **P-B** workspace audit (`fe-review` at workspace scale + Mobbin per surface) → **P-C** skill
> smoke matrix → **P-D** `OH-01` + journal style packs → **P-E** auth + real multi-tenancy.
>
> **The landing page is Thalon's**, not Selom's (owner-directed 2026-08-02) — this plan touches no
> marketing copy, positioning or pricing. **Nothing outward-facing ships autonomously**: no
> publishing, no public deploy. Founder gates batched in the plan §2 (only Clerk keys block P-E).

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

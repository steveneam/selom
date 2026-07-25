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
| **BROWSER-VERIFY** | 2026-07-25 | `main` `ff9705d..624cd89` (**2 unpushed**) | **Built the browser-verify harness and answered the §D list in a real browser.** `scripts/browser-verify.sh` boots a real backend + frontend and drives the one path that opens the editor (new project → real EYG_28 CSV → the engine's recommended skill); checks are specs, not scripts. **It found a blocking crash on the primary flow before running a single check** — `datasets.qc` holds two shapes and the mapper cast whichever arrived into the FE's `QcReport`, so **dropping any real file took the whole app to the error overlay**; invisible to every gate because `dev:mock` skips the upload path. **D-5: A24 confirmed FIXED** (`overflow=0`, `card = stageClient − 32` exactly at 1280/1440/1920); keep the `min-h-[20rem]` floor; the `88rem` cap is unreachable. **NEW FINDING: the hero is starved of WIDTH at 1280** — 90px of plotting area, not §D's assumed 506, because fixed columns take 70% of the viewport. D-4/D-1/D-7/D-3/D-9/D-10 all PASS (§D's "Legend overflows" prediction disproven); 2 founder calls. Gate 7/7. |
| **SPRINT-2-MERGED** | 2026-07-25 | `main` `ba0de8c..698381d` | **Phase 0 done → 3 lanes forked, driven and MERGED in one session.** Owner cleared all four founder gates; `main` pushed (`60df628..dddf5d6`) and `campaign/parallel-lanes` deleted. Built the missing groundwork: **`scripts/verify.sh`** (first single gate of record — 7 gates at CI parity incl. the `fe-build` the plan omitted, ~70s) · **`scripts/worktree-setup.sh`** (lane provisioning was **PowerShell-only**, so no lane could have been forked on Linux) · the **frozen `GET /cloud/providers`** contract · **the reachability ratchet**, which found **17 of 61 routes with no FE call site** where the whole milestone review had found 2. Then **launched and drove all three lanes autonomously** (thalon's tmux procedure — the owner no longer drives) and ran the merge train `L1→L3→L2` myself: 16 lane commits, full gate **7/7 green on every rebased result**. Lane 2 found the sprint's worst bug: **`config.py` never read `app/backend/.env`**, so the server pointed at the dead `localhost:3003` while `preflight.sh` validated the live broker **from the same unread file** — a green guard checking a file the server never read. Reachability **17 → 16**. Also wrote the **annotation-layer remediation spec** (the owed plan) and recorded the icon decision + on-hold triage. |
| **REVIEW-MERGE** | 2026-07-25 | `main` `60df628..bee9e66` (**22 unpushed**) | Milestone review of the whole campaign branch (`review-gauntlet` 30 confirmed / 3 blockers + `fe-review` 24 confirmed, 31 of 35 user tasks with no affordance) → fix pass → **owner approved → `main` FF-merged**, gates re-run on merged main. **Both blockers fixed:** WS3.1 had flipped DE significance from adjusted p to RAW p across 5 runners while the axis/table/methods still said "adjusted" (`b73bd9b`, 2835 vs 1008 significant genes on the real EYG_28 export; the guard test had been inverted to bless it) · a gene-label click deleted the user's annotation (`b1a49e8`). HIGH honesty set fixed (`1d2aa81`): FACS cites FlowIO+FlowUtils not the absent FlowKit + states the real compensation outcome · assemble records lineage · GSEA's bare `t` no longer matches `entrezgene_id` · Nango ELv2 recorded. **Annotation layer DEFERRED pending a proper plan** (owner intent, clarified 2026-07-25 — *not* shelved: the flag `NEXT_PUBLIC_ANNOTATION_LAYER` is the holding mechanism while a real plan is written, and ~20 findings are parked with it, owed a plan not a flag flip). **Google Drive + Dropbox cloud connections now LIVE + verified** end-to-end. |
| **LAUNCH-CAMPAIGN** | 2026-07-23 | `60df628..e90203a` — **merged into `main` 2026-07-25** | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · BROWSER-VERIFY · 2026-07-25 20:48 +1000 (Sydney) · branch `main` `ff9705d..624cd89` (2 unpushed) · Claude (FE+BE, solo, lead)

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

## ▸ PRIOR · SPRINT-2-MERGED · 2026-07-25 19:46 +1000 (Sydney) · branch `main` · Claude (FE+BE, solo, lead)

- **State: Sprint 2 is MERGED AND PUSHED.** `main` is linear and all three lanes landed via a lead-driven train (`L1 → L3 → L2`), **full `scripts/verify.sh` 7/7 green on each rebased result**. Pushed to `origin/main` 2026-07-25 (owner-authorized), which triggered the Vercel deploy. Worktrees removed, `agent/*` branches deleted, tmux sessions killed, dev servers stopped, tree clean. Always read the live count from `git rev-list --count origin/main..main`; never trust a literal here.
- **Lanes are fully torn down** — 3 worktrees removed, 3 `agent/*` branches deleted (all merged), 3 tmux sessions killed, main tree verified intact (39713 files, `.venv` present: `rm` does **not** follow the dep symlinks on Linux). **Lesson worth keeping: an idle Claude Code composer redisplays its last SUBMITTED message DIMMED (`ESC[2m`).** I read that as parked draft text in all three lanes and held teardown for it; the composers were empty. Check for the dim code before believing a pane has unsent input.
- **⚑ THE GATE OF RECORD IS `scripts/verify.sh`** — 7 gates, ~70s, raw + exit-code gated. **Never pipe it through `| tail`.** `--fast` skips `fe-build`; in a worktree `fe-build` is auto-`SKIP`ped (Turbopack rejects the out-of-root symlink) so **it and any browser check are merge-train-only, on the main checkout**.
- **⚑ CLOUD CONFIG — the bug that made the feature impossible, now fixed.** `app/backend/config.py` reads the **REPO-ROOT `.env`**; it never read `app/backend/.env`, where the creds had been staged. So `nango_base_url` silently fell back to `http://localhost:3003` (**dead**) and the secret key was empty — while `preflight.sh` read that same unused file and passed all five checks against the live broker. Migrated on this box and verified: backend now resolves `https://nango.swordfish.cfd` with Google + Dropbox **enabled**. Bound by `app/backend/tests/test_cloud_env_home.py`, which fails if the two homes diverge. **`app/backend/.env` now holds only the `GOOGLE_*`/`DROPBOX_*`/`MS_*` values for pasting into Nango's dashboard — read by nothing in this repo.**
- **Reachability ratchet is live** (`app/backend/tests/test_reachability_guard.py`, backlog `docs/reachability/backlog.md`): **16 unreachable routes remain**, each waived with an `R-xx` ID and a reason. **A stale waiver FAILS**, so the list can only shrink. Biggest rows: **R-01 the entire lit-synthesizer** (shipped, zero FE) and **R-02 the entire async job pipeline** — which *qualifies* the unparked `OH-01`, since that job-status store would ship with no reader.
- **Annotation layer: the owed plan EXISTS** — `docs/pillar-2-direct-manipulation/annotation-remediation-spec.md`. It is **deferred pending a proper plan, NOT shelved**; §6 states the exact flag-flip condition. Owner decisions in it: typed stars **allowed but marked `unverified`**; selection goes **full direct-manipulation**.
- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → export `SELOM_DATASETS_DIR` or real-data tests silently skip (`verify.sh` warns).

## ▸ NEXT  — **owner-directed 2026-07-25. RUN IT SEQUENTIALLY — no worktree lanes next session.**

The owner asked whether anything else needs doing and then directed: *"you can work on it sequentially next session."* So **do NOT fork lanes** — work the list below in order, in this checkout. (Lane tooling stays ready if a later sprint wants it: `scripts/worktree-setup.sh` to provision, `scripts/lane-status.sh` to drive/tear down.)

**Completeness audit ran 2026-07-25 — the list below is believed COMPLETE, and it found two gaps now closed:**
1. **`A23` was uncaptured by any lane or plan** — the inspector tab strip overflows at seven tabs (measured: 40.7px cells vs a 42.8px label, `whitespace-nowrap` with no `truncate`, so it spills into its neighbours). It is invisible **only** because Annotate is gated off, so it returns the instant the flag flips. Now a **blocking item on the annotation spec's flag-flip condition (§6)**, folded into `C1` because its own suggested fix — fold the annotation layer into the Marks tab — is the same fix as C1's "one object must not live in two tabs".
2. **`docs/milestone-review-2026-07-25/findings.md` had two contradictory statuses.** Its ledger was updated by the fix pass; the 43 per-finding `Status: OPEN` lines never were, and many are demonstrably fixed. The doc now says at the top that **the ledger is the only authoritative status** — deliberately not reconciled line-by-line, because that would create a second thing to keep in sync, which is the defect.

Everything below is the next session's job, in this order.

### ① ✅ DONE 2026-07-25 — harness built, D-5 + the reachable §D list answered. Next actions from it:

1. **The 1280 width defect** (above) — the hero gets 7% of the viewport for the plotting area. The
   candidates are all "which fixed column yields": collapse the project workrail in the figure view,
   make the 330px inspector dock collapsible, or fold the one-button tools rail away. **Wants a
   forcing-question + a spec before code** — it is a layout-model decision, not a tweak.
2. **`D-11` (`/extract`)** — the one reachable §D bullet still unrun: it needs canvas calibration
   (four reference-tick clicks + values) before the editor renders. Contained, now the harness exists.
3. **Two founder calls to put to the owner** — the one-button tools rail, and the duplicated
   "Edit a copy" on a frozen figure.
4. **Flag-on checks** (`ANNOTATION=on scripts/browser-verify.sh`) are **deferred Plan C** — file
   against the annotation remediation spec, never close as shipped-and-fine.

<details><summary>Original ① brief (kept for the reasoning; the work is done)</summary>

#### D-5 — INVESTIGATE THOROUGHLY (owner-directed 2026-07-25). Budget real time; do not shortcut it.

**Read this first, because the failure mode was mine, not the app's.** I burned most of a session on D-5 and never reached the editor, because I tried **four shortcuts in a row** instead of committing to the one path that works: demo projects → API-created project → localStorage injection → a half-driven UI run. The repo's own rule is *after two failed tries, build a helper* ([[step-back-build-helpers-when-stuck]]). I ignored it. **Do not repeat the shortcuts.**

**FIRST ACT — build the reusable harness, not another one-off script.** A small committed helper that boots the app and lands on **a real figure open in the editor**. It is the single dependency of D-5, `D-1`/`D-3`/`D-4`/`D-6`/`D-7`/`D-10`/`D-11`, the cloud round-trip, and every future browser verification — so it is worth building once properly instead of re-improvised each time ([[compound-capability-each-task]]). Suggested home: `scripts/browser-verify/` or a committed Playwright fixture. It must:
- start the backend with a DB (`SELOM_DATABASE_URL=sqlite:///…` + `SELOM_DB_AUTO_CREATE=true`) — **put that file in the selom-data folder, never the repo** (owner-directed) — and the FE with `API_PROXY_TARGET` pointed at it, on the derived lane ports (BE `:8152`, FE `:3152`; `:8000` is eamos, never bind it);
- drive a **real run through the UI** (new project → drop the CSV → run `volcano`), because a completed run calls `figure.init(res.figure)` itself and that is the ONLY thing that opens the editor;
- stop every server it started, and be re-runnable.

**Why the shortcuts fail** (so nobody re-tries them): the editor renders only when the *live editor store* holds a spec — `components/project/views/figure-view.tsx:91` branches on `figure.spec`, **not** on the persisted figure record — and that store is seeded solely by `figure.init(spec)` from `openFigure` (`components/project/hooks/use-figure-crud.ts:55`) or a completed run (`use-figure-run.ts:181`). So: **demo projects** show *"Figure spec not stored"* (their seeded figure has no spec) · an **API-created project** shows *"Project not found"* (the FE store is localStorage-first) · **localStorage injection** is lost to the store's seed/reconcile on load.

**Known-good real data** (verified this session to return HTTP 200 with a **responsive** spec — 3 traces, no `layout.width`, exactly what D-5 needs):
`…/selom-data/eyg28/raw/output_EYG_28_RO_human-RUVge-K4_20250602/DEG/EYG_28_RO_human-RUVge-K4_DEGs_All_PDE6B_FS_d180_vs_Control_d180.csv`

**Then work ALL 12 checks in `agent_handoff/lane-wraps/lane3.md`** — each has its exact route, viewport and PASS/FAIL criteria written out. D-5 first. Specifics not to lose:
- Viewports **1280×800, 1440×900 and 1920×1080** (the last for the `88rem` centring cap). **Desktop only** — Selom has no mobile.
- D-5's PASS is `overflow === 0` **and** `card ≈ stageClient − 32`; the **FAIL signature** of A24 returning is `card ≈ min(0.74 × innerHeight, 720)` with `stageScroll > stageClient`.
- **Report the new number D-5 asks for:** `stageClient` at both viewports. Lane 3's fix introduced a `min-h-[20rem]` (320px) floor, and if `stageClient` is ever near **352px** the floor is wrong for real screens and must be lowered. Only a browser can settle it.
- Confirm the figure's **x-axis title and legend are visible without scrolling inside the stage**, and that it stays legible at 1280 (~506px of plot width).
- Anything checked with `NEXT_PUBLIC_ANNOTATION_LAYER=on` is testing **deferred Plan C territory** — file it against the annotation spec, do **not** close it as shipped-and-fine.

**What is already confirmed, so do not redo it:** the full-app smoke on merged `main` with real chromium — 10 routes × 2 desktop viewports, all 200, zero page errors, zero horizontal overflow. Playwright 1.60.0 works with `executablePath: /home/deploy/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome` (the bare `playwright` package resolves a build that is not installed — pass the path explicitly).

</details>

### ② Everything else I could NOT confirm

| Item | State | Where |
|---|---|---|
| `D-1` · `D-3` · `D-6` · `D-7` · `D-10` | ✅ **VERIFIED 2026-07-25** — all PASS; 2 founder calls | `lane-wraps/lane3.md` §RESULTS |
| `D-11` | **still unrun** — needs `/extract` canvas calibration | `lane-wraps/lane3.md` §RESULTS |
| `D-2` | **unreachable by design** in a default build (annotation flag off) — anything checked with the flag ON is testing deferred Plan C territory; file against Plan C, do not close as shipped | `lane-wraps/lane3.md` |
| **Cloud round-trip end-to-end** — a real file imported from **Google Drive AND Dropbox** with `datasets.source` visible | **unverified.** This was Lane 2's own stated gate and no worktree could run a browser. It is now genuinely unblocked (below). | `lane-wraps/lane2.md` |
| `A25` | **only PARTIALLY fixed** — 3 of its 4 placeholders sat outside Lane 3's glob and were re-filed on the finding | `lane-wraps/lane3.md` |
| `L2-07` | **BLOCKED on swordfish** (public host for the Nango Connect UI). Not ours; the direct link flow works, so a *new* user cannot self-serve a connection until it lands. | ASK-BACKS |

**What IS confirmed, so do not redo it:** full-app smoke on merged `main` with real chromium — **10 routes × 2 desktop viewports, all 200, zero page errors, zero horizontal overflow**; and **`bash deploy/nango/preflight.sh` PASSES** post-merge, reading the *same* repo-root `.env` the server reads, with both connections refreshing (google-drive `c878e8db…`, dropbox `5f45a106…`). That last one matters: before the fix, preflight passed against the live broker **while the server pointed at a corpse**. They finally agree.

### ③ Then the reachability backlog — `docs/reachability/backlog.md`, 16 rows
**`R-02` first**, because it is a **precondition** for the unparked `OH-01` (arq + Redis job status), not a consequence: nothing in the FE polls a job, so that store would ship with **no reader**. Then `R-01`+`R-03` (largest user-visible loss, heavy overlap — the entire lit-synthesizer is shipped with zero FE), `R-04` (gates the proposal's `F1`), and `R-07` is a five-minute delete-or-use decision.

### ④ Then the annotation layer — `docs/pillar-2-direct-manipulation/annotation-remediation-spec.md`
Slices **C1 → C2 → C3 → C4**. `C1` first: it is the integrity defect *and* the cheapest, because it mostly **deletes** code (the server already computes stars from real data). §6 lists the flag-flip condition, which now includes **`A23`** (the seven-tab overflow the flag currently masks). Height-sensitive checks wait for ① — Lane 3 changed the artboard.

### ⑤ Still awaiting owner reaction
`docs/integration-robustness/proposal.md` — 4 proposed features, explicitly **no new analysis skills** (the constraint is reachability, not breadth). Plus the two unparked items (`OH-01` arq+Redis — sequence with `R-02`; `OH-07` journal style packs — the vehicle for `F3`).

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

**`docs/next-session-plan/plan.md`** (the entry point — **Phase 0 done, start at §Lanes**) · **`docs/integration-robustness/proposal.md`** (awaiting owner reaction) · **`docs/cloud-providers-contract/spec.md`** (the FROZEN cross-lane contract — read before touching cloud) · **`docs/milestone-review-2026-07-25/findings.md`** (54-finding backlog + status ledger) · `agent_handoff/DECISIONS.md` (#12 = lucide stays) · `docs/on-hold/README.md` (now the ONE on-hold register) · `docs/next-session-plan/lane-mechanics-from-thalon.md` · `docs/restructure/plan.md` (WS3 done) · `docs/fe-review/spec.md` (now impeccable-only) · CLAUDE.md · `deploy/nango/` (once built). Memory: [[parallel-agent-lanes]] · [[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] · [[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.

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
| **SPRINT-3** | 2026-08-02 | `main` `01e3736..<head>` (**unpushed — owner pushes**) | **`A1` closed for real, then Parallel Sprint 3 ran 3 lanes and the train.** `A1`: a figure exported from the editor's Export menu to a **real Google Drive and a real Dropbox**, each downloaded back and confirmed a valid 1600×1200 PNG, then deleted — and it found a live defect a mock cannot see: Drive returns the resumable session URI on a 200 **or a 308**, and with `follow_redirects=True` httpx **re-POSTs the 17-byte metadata** to the session URI in a loop, so the figure's bytes never left the box. Fixed + guarded. (The Dropbox non-ASCII fear does **not** fire — `json.dumps` already escapes; now executable.) Lanes: **A** `paper-outputs` (R-01+R-03 — the lit-synthesizer and the **Reproducibility Score** finally have a surface: a 4th `Write-up` stage in the Paper shell) · **B** `jobs` (R-02+R-06 — a run-activity dock; refused a progress bar because `Job.public()` carries no percentage) · **C** `skills` (the **36-skill smoke matrix**). Train run **B → A** with `verify.sh` **7/7 on each rebased result**; the expected `test_reachability_guard.py` waiver conflict resolved by hand. Also specced **P-E auth** (and found the plan's "backend is ready" is **half wrong** — 39 of 78 routes take no `AuthContext`, and `GET /artifacts/{id}/table` serves any tenant's matrix bytes to whoever has the id) and **Phase F**, the cnsplots figure-quality port. |
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

## ▸ LIVE · SPRINT-3 · 2026-08-03 04:13 +1000 (Sydney) · branch `main` (**unpushed — owner pushes**) · Claude (FE+BE, solo, lead)

- **`A1` is closed — the cloud round trip is real, not mocked**, and it found a defect worse than the
  one predicted (see the SESSIONS row). Locked in by `e2e/browser-verify/cloud-export.spec.ts`, which
  diffs the account by **file id** (never by name — Dropbox `autorename` would let a previous run's
  file pass) and **deletes what it created**, because these are the owner's real accounts.
- **Sprint 3 lanes A and B are merged**, `verify.sh` 7/7 on each rebased result. **Lane C
  (`agent/skills/coverage`) was still running its own gate at handoff — it is NOT merged.** Its work
  is complete on disk (`docs/skill-coverage/matrix.md` + `matrix.json` + `scripts/skill-smoke.sh`);
  finish it with: check the pane, let it commit + write `LANE-WRAP.md`, then rebase → `verify.sh` →
  merge. Worktrees are still forked at `/home/deploy/work/selom-lane-{a,b,c}`; **remove a/b** (merged)
  and c once it lands: `git worktree remove <path>`.
- **The skills question is now answered with evidence, not impression: 35 pass · 0 fail · 1 skipped**,
  every row the REAL engine against a real corpus file, 217s. **`umap_scrna` passes on the FULL
  scanpy pipeline** — the "last stub-only skill" line in the build plan is **superseded**. The single
  skip is **`facs_gating`: there is no `.fcs` file anywhere in `SELOM_DATASETS_DIR`**, so the flow
  engine has never been run on real input. That is a **corpus gap, not a code gap** — staging one
  `.fcs` unblocks it.
- **⚑ P-E is bigger than the plan said.** `docs/auth-multitenancy/spec.md`: **39 of 78 routes take no
  `AuthContext`**, so `SELOM_AUTH_MODE=clerk` would authenticate half the API and leave the rest
  **unscoped**. `GET /artifacts/{artifact_id}/table` returns the exact matrix a skill consumed to
  anyone holding the id. Also `lib/api/client.ts` has `setAuthHeader` but **no getter**, so Lane B's
  job SSE stream + its polling floor will 401 the day Clerk lands.
- **Phase F (cnsplots) is chartered** — `docs/cnsplots-port/{plan,spec}.md`. It is **BSD-3-Clause**,
  so **no clean room is needed** (that is the copyleft path, per the Harmony rule); we copy and
  credit. The port is at the **styling layer** — matplotlib render calls would produce figures that
  cannot enter the editor, but the visual quality lives in typography/ticks/spines/legend
  geometry/palettes, which move value-for-value into `theme.py`.

## ▸ NEXT — **finish Lane C, then Phase F (cnsplots figure quality). Nothing here needs the owner.**

> **Owner is away and everything founder-gated is BATCHED TO NEXT WEEK** (owner-directed
> 2026-08-02: *"anything that needs me gets deferred to next week"*). So: no Clerk keys, no route-split
> decision, no push. Build what does not need him.

1. **Finish Lane C** (`agent/skills/coverage`, worktree `/home/deploy/work/selom-lane-c`) — its work
   is done on disk but it was still running its own gate at handoff. Let it commit + write
   `LANE-WRAP.md`, then rebase → `scripts/verify.sh` → merge. Then `git worktree remove` all three
   lanes (a and b are already merged).
2. **Phase F — `docs/cnsplots-port/{plan,spec}.md`.** The owner's headline ask: *our plots look worse
   than cnsplots'*. Start at **F1, the parity audit** (five plot types, same real data, side by side)
   — it turns "looks better" into a checklist and makes F2 measurable. Then **F2, the theme port**,
   which finally forces the planned `theme.py` → **named style registry** refactor.
   **One cheap check owed first:** does Selom's Kaleido SVG export keep `<text>` as text or outline
   it? If it outlines, "editable vector export" is a claim the product does not meet.
3. **P-E backend half** (`docs/auth-multitenancy/spec.md` §4 steps 1–3) — deny-by-default + scope
   `/artifacts/*` and `/reproduction-runs/*` + the isolation test. **This needs no keys**, so it is
   autonomous; only the FE half and the route split wait for the owner.
4. **`OH-01`** (arq + Redis job store) — now unblocked: Lane B built the reader, and its wrap
   documents the contract the producer must meet (`docs/jobs-surface/spec.md` §4).

**Two owed follow-ups the lanes recorded, so they are not lost:** there is **no run-scoped legends
route** (`/papers/{slug}/legends` is published-paper scoped, so a user's own reproduction shows a
stated limit — `compose_ledger_legends(ledger)` already does the work), and **`mocks/handlers.ts`
has no handlers for Lane A's six new routes** (harmless — MSW bypasses — but a clean follow-up).

## ▸ DEFERRED

### ⚑ Batched for the owner — NEXT WEEK (owner-directed 2026-08-02: "anything that needs me")

- **Clerk keys** (publishable + secret + issuer URL) — the only thing blocking P-E's frontend half.
- **The route split** — does the app move to `/app` so `/` can be public? Recommended in
  `docs/auth-multitenancy/spec.md` D5; **owed to Thalon's landing-page build** and much cheaper
  before that ships.
- **A real `.fcs` file** staged into `SELOM_DATASETS_DIR` — the ONLY reason `facs_gating` is the one
  skill the smoke matrix cannot run. The engine is real; the corpus is the gap.
- **Push `main`** — every commit since `01e3736` is local.
- **Phase F, one product call:** should Selom ever add a *static-render* skill class for plots that
  are better as publication images, at the cost of editability? Recommendation is **no**
  (`docs/cnsplots-port/plan.md` §2). Nothing depends on the answer.
- **Selom cannot see files the user already has** — the `drive.file` / App-Folder scope decision
  (`docs/cloud-providers-contract/spec.md` §Scope), still open from EDITOR-ROOM.

### Standing

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

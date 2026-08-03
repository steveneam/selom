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
| **SLOW-GATE-LANE-B** | 2026-08-03 | `main` `ced7f31..454b974` (**2 commits, unpushed — owner pushes**) | **The slow lane is gated, then Lane B shipped its three plot types.** **STEP 0**: the `slow` lane was enforced NOWHERE — 385 of 1907 tests. The blocker was *assumed*: "slow" reads as "needs the real corpus", which would have made it a real question about what CI can run. Measured in a throwaway venv built with CI's own light closure, corpus-free: **352 pass / 21 skip / 0 fail in 16s** — the 21 skips are the omics-gated tests, and they skip cleanly rather than error. So it needed no new extras, no new job, no nightly, no self-hosted runner: one step in the existing backend job, plus `be-slow` in `verify.sh` (8 gates now, 70s → 95s), because gating only CI would leave the pre-commit gate of record still green on the exact class of breakage it exists to catch. **Proven to bite**: a failing assertion injected into a slow-marked test leaves the fast lane green at exit 0 (1511 passed) while `be-slow` goes red and `verify.sh` exits 1. `!cancelled()` on the CI step so a fast failure cannot hide a slow one. **Lane B**: `venn` · `forest` · `qq`, each closing all seven §5 wiring points. `venn` takes the SAME membership matrix as `upset` and draws circles as **filled traces, not `layout.shapes`** — a shapes-only diagram renders identically and fails `check_figure`'s non-empty-`data` rule, correctly, because it would be a picture rather than an editable figure; above 3 sets it refuses and names `upset`. `forest`'s interval IS the plot, so its provenance is never silent: explicit CI columns → standard error → **t-statistic (`se = effect/t`, the limma identity)**, with the table stating which, and a raise rather than an invented bar when none exist. `qq` carries λ + the Beta(i, n−i+1) null band and catches what a volcano *hides* — an inflated test makes a volcano look better. **λ forced the one real contract decision**: every DE runner wants the adjusted p and `resolve_significance` is tiered to guarantee it, but an adjusted p is a monotone transform whose quantiles are not uniform, so λ would read "conservative" no matter how inflated the test — the raw-first read went into `engine/columns.py` as `pick_raw_significance` beside its twin, not forked in the skill (the drift guard caught that fork and was right). **Rendering found what no assertion did**: `qq` drew `y = x` to `max(observed)`, so on real data (λ=2.14: observed 12.6 vs expected 4.5) the line trailed into an empty half and stretched the x-axis; and the first re-render looked byte-identical because **the C1 cache served the pre-fix figure** — `smoke.pin_process()` exists for exactly that. **Two pre-existing gaps found while wiring**: the golden list was hand-maintained *and duplicated* in `regen_golden.py` (a new skill could ship unpinned, silently) — it lives once now with a completeness test; and that test immediately found **`umap_scrna`, the flagship P0 skill, has never had a golden** (its own `SELOM_UMAP_ENGINE` selector was never pinned by the fixture, so it hit the real scanpy engine and raised). Gates: `verify.sh` **8/8**, **skill-smoke 38 pass / 0 fail** on the real corpus (was 35). |
| **LANE-A-C** | 2026-08-03 | `main` `3565e51..d75de27` (**pushed**) | **STEP 0 cleared, then Lane A and Lane C built solo on main — no worktree lanes, because Lane A turned out to be a shared-module change and Lane C is cross-cutting.** `0b`: the `slow` suite runs again — two lines in `conftest.py` (`string_storage="python"` + `allow_write_nullable_strings`); either alone still fails. **Lane A**: the board said `pairs=` is "nowhere", but `_charts.py` already had `sig_stars`/`compare_groups`/`sig_brackets` — ERG-scoped and *bar*-shaped (it derives the bracket baseline from `means`/`his`/`pt_y`, which a box has not). So it was a **generalization**, not a build: `skills/_stats.py` is now the leaf home for the statistics, the correction, the geometry, `n=` labels and the order contract; `_charts` imports FROM it and re-exports, so the ERG goldens are **byte-identical**. Two things the move made possible: `bracket_shapes` takes a **`span`** (sizing the gap off the data TOP is only right for a zero-anchored bar — a box of values around 100 has a span of ~1 and would have thrown brackets ~12 units off the plot), and **multiple-comparison correction** (bonferroni + BH, hand-rolled so a figure never needs scipy to be honest about its own multiplicity, **pinned against `scipy.stats.false_discovery_control`**). Correction drives the **drawn stars**, not just the table — correcting one and not the other makes the figure lie. **`composition` deliberately takes the ordering half only**: it holds ONE value per category×condition cell, so a pairwise test is n=1 vs n=1 and every bracket would read "ns" regardless of the data. The table contract needed a real decision — box/violin are declared L3 and the guard asserts native∩L3=∅, but a pairwise p exists nowhere in the figure except as a star, so a declared `NATIVE_L3_BOTH` now models "disjoint **runs**, not disjoint skills", with a guard that makes each entry PROVE it. **Reachability**: `boxplot` had **no FE overlay at all** (even `points`/`orientation` were API-only) — all three skills now carry one, mirrored into the `dev:mock` fixture, with tests that the merge YIELDS the controls. **Mobbin ruled the intended affordance OUT**: Rows/Glide/Databricks/Hex all use a repeatable row-list of typed selects with `+ Add`, never a typed mini-DSL — but `ParamField` has no list widget and a param control cannot see the dataset's categories at render time, so `pairs=` stays a text field and the gap is recorded where someone building the picker will look. **Lane C**: **deny-by-default** — `enforce_auth` on the app + a named public allow-list, so a route is private unless written down; a throwaway route is mounted in the guard to PROVE a new one is born private. No-op in `dev` (DevVerifier never raises), so 0 existing tests changed. Then the **actual leak**: `/artifacts/{id}/table` served the exact matrix a skill consumed to whoever held the id. Keys are now `artifacts/{owner}/{id}` — and the content-addressing trap is the subtle part: the id IS the content hash, so two tenants uploading the same table derive the same id and **cross-tenant dedup IS the leak**. Reproduction runs + `uploads/local` scoped too; the latter now **refuses to exist** on S3. **Two bugs the new tests caught while being written**: `_owner_seg("..")` passed through unchanged (dots are legal *inside* an id, so `..` fullmatched), and a blank owner **silently no-opped** because `put`/`get_meta` absorb `ValueError` by design. **⚑ And 7 broken tests read GREEN** — `test_reproduction_runs.py` matches the `test_reproduction` slow prefix, so `-m "not slow"` deselected it. **`verify.sh` AND CI both run only the fast lane, so ~280 slow tests are enforced NOWHERE** (the same blind spot that hid the h5ad breakage). Gates: `verify.sh` **7/7**, **full suite incl. slow 1895 pass / 0 fail**, `skill-smoke` **35 pass / 0 fail**. |
| **PHASE-F1-F2** | 2026-08-03 | `main` `8520466..5157733` (**unpushed — owner pushes**) | **The owner's "our plots look worse than cnsplots" is answered with a measurement, and the answer was not the one the charter predicted.** `F1`: five plot types through Selom's own skills on the real corpus, then the **identical arrays** fed to cnsplots 0.6.0 in a throwaway venv, both on one canvas (6×4.5in @ 200dpi — typography only compares in points). Result: 24 named differences with PORT/REJECT/CHECK verdicts (`docs/cnsplots-port/parity-audit.md`). **But three of the five plot types were BROKEN, not merely ugly**, so `F1.5` went first: `enrichment` passed the raw gene count to `marker.size` with `sizemode:"diameter"` → dots **1–3 PIXELS** across and no size key at all (matplotlib's `s` is an *area*, which is why it looked fine on the other side and hid the bug) · `heatmap`'s cluster axis was numeric-looking **strings in lexicographic order**, so Plotly inferred a LINEAR axis and **7 of 17 clusters were unreadable** with cluster 10 sitting between 1 and 11 · and the house font `Inter` was **bundled by nothing**, with the FE and BE stacks falling through to *different* faces (measured by ink width: 517px DejaVu vs 466px Liberation) — so the figure on screen and the figure exported were **different typefaces**. The axis-type bug was a *class*, so the sweep became a standing invariant in `smoke.check_figure` (every skill, real data, every run); it found exactly one more (`cluster`, where the 6-cluster stub renders identically either way and hid it perfectly). Then `F2` ported **10 of the 14 PORT rows** as style tokens — gridless, bold title, black spines/ticks at cnsplots' geometry, flattened title ramp, legend density, and diverging matrices finally putting HIGH at the **red** end (`heatmap`/`corr_heatmap`/`cepo` all had it inverted; verified by sampling rendered pixels). FE defaults moved in step so an editor-made figure matches a skill-made one. `verify.sh` **7/7**, full smoke **35 pass / 0 fail**, **browser-verify 14/14** (F2's D5 acceptance — a real figure restyled and still editable). |
| **SPRINT-3** | 2026-08-02 | `main` `01e3736..<head>` (**unpushed — owner pushes**) | **`A1` closed for real, then Parallel Sprint 3 ran 3 lanes and the train.** `A1`: a figure exported from the editor's Export menu to a **real Google Drive and a real Dropbox**, each downloaded back and confirmed a valid 1600×1200 PNG, then deleted — and it found a live defect a mock cannot see: Drive returns the resumable session URI on a 200 **or a 308**, and with `follow_redirects=True` httpx **re-POSTs the 17-byte metadata** to the session URI in a loop, so the figure's bytes never left the box. Fixed + guarded. (The Dropbox non-ASCII fear does **not** fire — `json.dumps` already escapes; now executable.) Lanes: **A** `paper-outputs` (R-01+R-03 — the lit-synthesizer and the **Reproducibility Score** finally have a surface: a 4th `Write-up` stage in the Paper shell) · **B** `jobs` (R-02+R-06 — a run-activity dock; refused a progress bar because `Job.public()` carries no percentage) · **C** `skills` (the **36-skill smoke matrix**). Train run **B → A → C** with `verify.sh` **7/7 on each rebased result**; the expected `test_reachability_guard.py` waiver conflict resolved by hand. Also specced **P-E auth** (and found the plan's "backend is ready" is **half wrong** — 39 of 78 routes take no `AuthContext`, and `GET /artifacts/{id}/table` serves any tenant's matrix bytes to whoever has the id) and **Phase F**, the cnsplots figure-quality port. |
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

## ▸ LIVE · SLOW-GATE-LANE-B · 2026-08-03 · branch `main` (**PUSHED — `origin/main` = `c8ddbbb`, nothing local, CI GREEN**) · Claude (FE+BE, solo, lead)

- **NEXT#0 and NEXT#1 from the last board are both DONE.** The slow lane is gated in CI *and* in
  `verify.sh`; `venn`/`forest`/`qq` are built, wired and reachable. Detail in the SESSIONS row.
- **The slow gate is verified in its target event** [[verify-ci-in-its-target-event]] — run
  `30834926456` on `c8ddbbb`, backend step 7 *"Slow test gate"* → **361 passed, 21 skipped in
  8.65s** (faster than the local 16s: CI runs `-n auto` on its own runner). Not inferred; read off
  the run.
- **⚑ `ci` was ALREADY RED on `main` before this session's work** — the two preceding doc-only
  commits (`ced7f31`, `8de5e39`) both failed, so the last board's "CI green" assumption was stale.
  Cause: **zizmor `ref-version-mismatch`** on all five `actions/checkout` uses. The SHA pins were
  correct — the SHA is an annotated-tag object dereferencing to the commit tagged **v5.0.1** while
  the comment said `# v5`. Fixed in `c8ddbbb`; `ci` is green now.
- **⚑ AND HOW IT HID, which is the durable part: `uv tool run zizmor@latest` runs OFFLINE by
  default**, and that audit needs the GitHub API to resolve tags → SHAs. A local run reports
  *"No findings. Good job!"* while CI (which sets `GH_TOKEN`) reports five. **Any local zizmor check
  must export a token or it is not the same gate:**
  `GH_TOKEN=$(gh auth token) uv tool run zizmor@latest --persona=regular .github/workflows/`
- **⚑ OWNER CALL OWED (small, no spend): the `workflow-lint` job runs `zizmor@latest`,** so a new
  audit in a new zizmor release turns `main` red with **no repo change** — which is exactly what
  happened here. Pinning it makes the gate reproducible but stops new audits arriving for free.
  Both are defensible; it is a policy choice, so it is not being made unilaterally.
- **Reachability was verified against a live backend, not inferred**: `GET /skills` serves all three
  as `verified`/`production` and `GET /skills/{id}` serves their `param_spec`, which is what the
  panel merges with the FE overlay. **I did not click through the Store in a browser** — the
  contract half is proven, the visual half is not.
- **The lesson worth carrying: a "cheap gate we can't afford" was never measured.** The slow lane
  was written off as corpus-dependent for long enough to hide a real breakage; it was 16 seconds.
  Measure the blocker before designing around it.

## ▸ (superseded) LIVE · LANE-A-C · 2026-08-03 21:55 +1000 (Sydney)

- **STEP 0 is cleared.** `0a`: the owner asked mid-session, so `main` was pushed —
  `46d5c6c..f608feb`, all 31 commits. Phase F, the ERG corrections and cloud-export are on
  `origin` now; that loss-risk is closed. `0b`: the `slow` suite runs (detail in the SESSIONS row).
- **The board's three-lane fork was NOT used, deliberately.** Lane A turned out to be a change to a
  shared module (`_charts.py` → `_stats.py`) and Lane C touches every router — both are the class
  of work that is *worse* in a worktree, and B depends on A's validators. Built sequentially on the
  main checkout instead. **Lane B (venn/forest/qq) is untouched and is the obvious next slice.**
- **Lane A is done, and its premise was wrong in a useful way.** `pairs=` was not "nowhere" — it
  existed, ERG-scoped and bar-shaped. The work was generalization, so the ERG figures are
  byte-identical and every categorical skill now speaks one vocabulary. Correction is default-`none`
  everywhere, so no existing figure moved.
- **Lane C steps 1–3 are done.** Deny-by-default + tenant-scoped artifacts / reproduction runs /
  `uploads/local`. **Authentication and authorization were closed separately and in that order** —
  step 1 alone would have reduced the artifact leak from "anyone on the internet" to "any logged-in
  user", which is a reduction, not a fix. Steps 4–7 (the frontend half) are **blocked on Clerk keys**
  and stay batched to the owner.
- **⚑ THE FINDING THAT OUTLIVES THIS SESSION: the `slow` test lane is enforced NOWHERE.**
  `.github/workflows/ci.yml` runs `pytest -m "not slow"` and `verify.sh` does the same, so **385 of
  the 1907 tests have no gate at all.** It is how the pandas-3/pyarrow h5ad breakage survived, and
  this session it let **7 tests broken by a signature change report PASS**.
  **Run `uv run pytest` with no `-m` before trusting a green gate on any signature change.**
- **The fix is small, and my first read of it was WRONG — measured 2026-08-03, trust the number.**
  I assumed "slow" meant "needs the real corpus", which would have made this a real decision about
  what CI can run. It does not. `env -u SELOM_DATASETS_DIR uv run pytest -m slow -n 2` gives
  **373 passed, 12 skipped, 0 failed in 16s** — the same 12 skips as with the corpus. The lane is
  mostly *heavy-import* tests (scanpy, pydeseq2), not *real-data* tests.
  **So: add a corpus-free `pytest -m slow` step to the EXISTING backend CI job** (which already has
  a 20-minute budget) — not a new job, not a nightly, not a self-hosted runner. It would have caught
  this session's 7 breakages exactly, since `test_reproduction_runs.py` needs no corpus.
  Be honest that it is a WEAKER gate: with the corpus that same lane takes ~7½ min because the real
  engines chew on real matrices, so this catches breakage, not numerical regression —
  `scripts/skill-smoke.sh` + a local full run stay the deeper check. CI triggers on `push: [main]`
  and `pull_request`, so it self-verifies on the next push [[verify-ci-in-its-target-event]].

## ▸ NEXT

0. ~~Gate the `slow` lane~~ · ~~Lane B (`venn`/`forest`/`qq`)~~ — **both DONE 2026-08-03.**
1. **Lane B continued — the next plot types**, source-review §3.2 rows 5-11, all size-S and each
   independently shippable: `scatter` (generic x/y/hue — the most-requested shape Selom cannot draw
   without a PCA) · `line` (generic, with `errorbar`; the ERG skills each hand-roll one) ·
   `confusion` · `ridge` · `strip` · `slope` · `lollipop`. The seven-point checklist (§5) is the
   contract, and its item 3 is now **enforced** rather than assumed — a new skill with no golden
   fails `test_every_installed_skill_has_a_golden`. Note `forest`'s `_pick` holds SE/CI/t column
   spellings **locally on purpose**: the shared resolver has no role for them and `forest` is the
   only consumer. **The second consumer moves it into `engine/columns.py`** — do not copy it.
2. **The isolation-coverage guard** — spec §5's strongest form, and the one piece of Lane C not
   built. It should enumerate private routes by AST, subtract the allow-list, and **fail on any
   private route with no isolation case**, carrying a NAMED shrinking backlog for the ones that do
   not have one yet (the `test_reachability_guard.py` waiver shape). That turns "39 unaudited
   routes" into a tracked list instead of a memory.
3. **The audit's open rows 21–23** — long category labels colliding with the axis title, point-label
   collision on scatter/volcano (neither side applies `adjustText`), axis title vs long ticks under
   `automargin`. Selom's own defects, which **cnsplots does not solve either** — where Selom can beat
   the reference rather than match it.
4. **F3 (the fit-scored picker)** — specced in source-review §6; Mobbin ruled OUT abstract
   illustration tiles. Run `fe-review` at the end. **F4** = the rest of the plot gaps.
5. **`OH-01`** (arq + Redis job store) — unblocked; contract is `docs/jobs-surface/spec.md` §4.

**Owed follow-ups still open:** the CI slow-lane decision above · the `pairs=` **pair-picker**
(a repeatable row-list of typed selects — blocked on a `ParamField` list widget AND on param
controls being able to see the dataset's categories; note left in `lib/catalog/params.ts`) · there
is **no run-scoped legends route** (`/papers/{slug}/legends` is published-paper scoped;
`compose_ledger_legends(ledger)` already does the work) · **`mocks/handlers.ts` has no handlers for
the six newer routes** (harmless — MSW bypasses) · the audit's CHECK rows 13/24 need **each
journal's own author guidelines**, not cnsplots.

## ▸ DEFERRED

### ⚑ Batched for the owner — NEXT WEEK (owner-directed 2026-08-02: "anything that needs me")

- **Clerk keys** (publishable + secret + issuer URL) — the only thing blocking P-E's frontend half.
- **The route split** — does the app move to `/app` so `/` can be public? Recommended in
  `docs/auth-multitenancy/spec.md` D5; **owed to Thalon's landing-page build** and much cheaper
  before that ships.
- **A real `.fcs` file** staged into `SELOM_DATASETS_DIR` — the ONLY reason `facs_gating` is the one
  skill the smoke matrix cannot run. The engine is real; the corpus is the gap.
- ~~Push `main`~~ **DONE 2026-08-03.** The 31-commit backlog *and* this session's Lane A + Lane C
  went to `origin` at the owner's direct request; `origin/main` = `d75de27`, working tree clean,
  nothing local. The long-standing unpushed-backlog risk is closed.
- ~~The CI slow-lane *decision*~~ — **BUILT 2026-08-03** (`6c2e334`), in CI and in `verify.sh`.
  Re-measured against CI's own light closure, not just the local full env: 352 pass / 21 skip /
  0 fail in 16s.
- **Phase F, one product call:** should Selom ever add a *static-render* skill class for plots that
  are better as publication images, at the cost of editability? Recommendation is **no**
  (`docs/cnsplots-port/plan.md` §2). Nothing depends on the answer.
- **Phase F, a second product call (audit row 17):** should a figure export on a **transparent**
  background (cnsplots' default — it composites cleanly into a multi-panel) or stay white (safer for
  someone who just downloads it)? Best answer is probably *offer both at export*; nothing is blocked
  on it. Row 2 (title centred vs left) is the same shape — a per-journal-pack decision, not a global
  one, and it lands with the journal packs.
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

**`docs/auth-multitenancy/spec.md`** (**the entry point — steps 1–3 of §4 are DONE; steps 4–7 are the
frontend half and are blocked on Clerk keys. §5's route-enumerating isolation guard is the one piece
NOT built — see NEXT#2**) · **`docs/cnsplots-port/parity-audit.md`** (F1+F2 ledger; its §3 table is
the remaining styling work, rows 21–23 are NEXT#3) · `docs/cnsplots-port/source-review.md` §3.2 +
§5 (**Lane B's three plot types and the seven-point wiring checklist they must close**) ·
`docs/cnsplots-port/{plan,spec}.md` · **`docs/skill-coverage/matrix.md`** (35/36, re-run with
`scripts/skill-smoke.sh`) · **`docs/reproduction-engine/skill-table-contract.md`** (now documents the
one declared native∩L3 overlap) · **`docs/jobs-surface/spec.md`** §4 (the contract `OH-01` must meet)
· `docs/paper-outputs/spec.md` · `docs/build-plan-2026-08/plan.md` (master sequencing) ·
`docs/next-session-plan/plan.md` (older board — Tracks W/Q/V/E DONE) ·
**`agent_handoff/lane-wraps/lane3.md` §RESULTS** · **`docs/integration-robustness/proposal.md`**
(awaiting owner reaction) · **`docs/cloud-providers-contract/spec.md`** (FROZEN — read before
touching cloud) · **`docs/milestone-review-2026-07-25/findings.md`** (54-finding backlog) ·
`agent_handoff/DECISIONS.md` (#12 = lucide stays) · `docs/on-hold/README.md` ·
`docs/next-session-plan/lane-mechanics-from-thalon.md` · `docs/restructure/plan.md` ·
`docs/fe-review/spec.md` · CLAUDE.md · `deploy/nango/`. Memory: [[parallel-agent-lanes]] ·
[[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] ·
[[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]] ·
[[verify-ci-in-its-target-event]] · [[selom-shipped-not-reachable]] ·
[[read-gate-output-raw-not-piped]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.

# Next-session plan — phases, lanes, tracking, and the on-hold register

_Written 2026-07-25 16:14 +1000 (Sydney) · 06:14 UTC. Updated 16:32 +1000 with the owner's decision
(**run Plan B + Plan A in parallel**), a trackable phase structure, and the on-hold triage._

**How this file is reached:** `agent_handoff/CURRENT.md` → ▸ NEXT points here, and it is in the
▸ READ FIRST list. A session that boots on `gogogo` lands on it without being told.

**How this file is tracked:** every work item below has a stable **ID** (`L1-03`, `L2-01`, …) and a
**Status** cell. The rule: *a fix and its status flip land in the SAME commit*, and the commit message
names the ID. `docs/milestone-review-2026-07-25/findings.md` stays the finding-level truth (its
Status ledger); this file tracks the *work*, which is not one-to-one with findings. At session start,
mirror the open rows into harness tasks (`TaskCreate`) so in-session progress is visible; the durable
record stays here, because harness tasks do not survive the session.

Status vocabulary: `TODO` · `WIP` · `DONE <sha>` · `BLOCKED <on what>` · `DROPPED <why>`.

---

## Decision taken

**Plan B (zero the review debt) + Plan A (make it reachable) run in parallel next session as isolated
worktree lanes. Plan C (finish Pillar-2) is held for the session after, entered through a `spec`.**
Owner-approved 2026-07-25. Rationale: B and A touch disjoint trees so they do not serialise; C needs
design decisions and touches the provenance chokepoint, and the annotation flag means nothing is
bleeding while it waits.

---

## Phase 0 — before any worktree is forked (sequential, blocking)

| ID | Item | Owner | Status |
|---|---|---|---|
| P0-01 | **Push `main`** — the merge + the review backlog + this plan. Count is whatever `git rev-list --count origin/main..main` says (do not trust a number written here). Triggers the Vercel deploy. | **founder gate** | TODO |
| P0-02 | Delete `campaign/parallel-lanes` — only after P0-01, so the work has a remote ref first | me | TODO |
| P0-03 | **Freeze the one cross-lane contract**: `GET /cloud/providers → { providers: [{ id, label, kind, provider_config_key, enabled }] }`. Written into `docs/figure-editor-contract/`-style form before Lane 2 starts; no other lane may define or consume it. | me | TODO |
| P0-04 | Confirm the lane mechanics with **thalon** (has run worktree lanes on this box repeatedly) | me | **DONE** — `docs/next-session-plan/lane-mechanics-from-thalon.md`, adopted in §Lane mechanics |
| P0-05 | Approve (or reshape) the lane partition in §Lanes | **founder gate** | TODO |
| P0-06 | **Icon decision (A30):** migrate to Phosphor, or record "lucide stays" as a decision so the finding stops recurring in every FE review | **founder gate** | TODO |
| P0-07 | Triage the on-hold register (§On-hold) — several items are parked on a gate that no longer exists | **founder gate** | TODO |
| P0-08 | **Build the one-command gate of record** — `scripts/verify.sh`: `hygiene-scan --all` + BE `pytest -m "not slow"` + `ruff check` + FE `tsc` + `eslint` + `vitest`, exit-code gated, **raw output**. Selom has no single verify command today, and the merge train needs one to run against each rebased result. Also the natural home for the `\| tail` fix below. | me | TODO |
| P0-09 | **Headroom check before forking 3 sessions — mostly already answered.** Confirmed on syd4 today: `agent-tmux.service` has `OOMPolicy=continue` (so thalon's fleet-killer mode is mitigated here), 6 vCPU / 15.99 GB with ~9.1 GB available, and five live agent sessions cost **~1.9 GB combined** — agents are cheap; a Next dev server is 1.4 GB and a browser ~1.5 GB. thalon's **measured** figure is **~2.26 GiB/lane** with 4 concurrent + lead fitting post-resize, and they have **retired stagger-launches** in favour of **staggering the SUITE RUNS** (reconciled via eamos 2026-07-25). Remaining action: **cap per-lane test parallelism at `-n 2`, not `-n auto`** — the real ceiling is CPU oversubscription (3 lanes x 6 workers on 6 vCPU), not RAM. | me | **DONE** (measured) — carry the `-n 2` cap into each lane's kickoff |

---

## Lane 1 — Backend integrity sweep (Plan B §1–4)

**Owns:** `app/backend/skills/**` · `app/backend/engine/{assemble,columns,vocab,ingest}.py` ·
`app/backend/companions/methods.py` · tests in `app/backend/tests/test_{volcano,gsea,flow,erg,assemble}*.py`
**Frozen (may extend, must not rename):** `resolve_significance` / `pick_significance` signatures
(`b73bd9b`); the `layout.meta` honesty keys `significance`, `compensation_applied`.
**Gate:** `pytest -m "not slow"` + `ruff check .` green, **and each fix verified against a real
dataset** under `SELOM_DATASETS_DIR` — not a fixture.

| ID | Finding | Work | Status |
|---|---|---|---|
| L1-01 | A10 (HIGH) | Give `GENE` the same tier treatment the p-value half got: a non-label column containing a gene token must not win. Same shape as `b73bd9b`, gene half. | TODO |
| L1-02 | A19 | Move the forked `_pick` out of 6 runners into `engine.columns` so the drift guard can see **one matcher**, not just one vocabulary. Do with L1-01 — same files. | TODO |
| L1-03 | A14 | Assembly zero-fills genes absent from a sample's reference → fabricated hard zeros. Emit an honest gene-overlap verdict; do not silently invent counts. | TODO |
| L1-04 | A21 | `engine/assemble.py` re-declares the 10x detector + re-implements unit loading → consult `engine/ingest`'s declared loader registry. Do with L1-03. | TODO |
| L1-05 | A15 | FACS gate bounds live in a transform space anchored to a data-dependent `t_top` that is never recorded → record it in provenance so the same gate spec reproduces. | TODO |
| L1-06 | A16 | FACS silently drops gates it cannot resolve → a verdict row, not a vanished population. Do with L1-05. | TODO |
| L1-07 | A17 | ERG oscillatory potentials report `0.0` for "not measurable" → `None`/`not_measurable`, so unmeasurable ≠ absent inner-retinal activity. | TODO |
| L1-08 | A18 | The opt-in robust a/b detector changes amplitudes without disclosure → disclose in methods via the same `layout.meta` channel the FACS/volcano fixes use. Do with L1-07. | TODO |
| L1-09 | — | **ERG figure/table wiring** (was candidate lane (a), unblocked when FACS landed): OP · PhNR · flicker-FFT into the figure/table surfaces + `companions/methods.py`. The measurements shipped in `a84636c`; nothing surfaces them yet — a shipped-not-reachable item, so it belongs in this sweep. | TODO |
| L1-10 | — | `test_ingest.py::test_ingest_h5ad_single_cell` (anndata ↔ pandas-3.0 h5ad write) has been red for the whole campaign, proven pre-existing. Fix it, or skip it with an honest reason + a pointer — a permanently-red gate trains everyone to ignore the gate. | TODO |

## Lane 2 — Cloud reachability across the FE↔BE seam (Plan A)

**Owns:** `app/backend/routers/cloud.py` · `app/backend/cloud/**` · `app/backend/routers/data.py` ·
`app/frontend/lib/cloud/**` · `app/frontend/components/intake/**` ·
`app/frontend/lib/projects/sync.ts` · `app/frontend/components/project/data-panel.tsx` ·
tests in `app/backend/tests/test_cloud*.py`
**Frozen:** the P0-03 contract — this lane is its only implementer and consumer.
**Gate:** a **real file imported from Google Drive AND Dropbox** into a project, with
`datasets.source` visible in the UI; the MSW mock updated in the *same* change as the contract.

| ID | Finding | Work | Status |
|---|---|---|---|
| L2-01 | A20 | `GET /cloud/providers` from `cloud/registry.py` + settings; the FE consumes it, static list survives only as an offline-dev fallback. Kills the FE↔BE fork. | TODO |
| L2-02 | — | Enable `SELOM_CLOUD_GOOGLE` + `SELOM_CLOUD_DROPBOX` in `app/backend/.env` (gitignored). Without this the live OAuth is still refused — one of the three closed gates. | TODO |
| L2-03 | B14 · B16 | Stop dropping backend-stamped `datasets.source` in the FE dataset mapper — a cloud-imported dataset currently looks hand-dropped. | TODO |
| L2-04 | B15 | Kill the fabricated `File` stand-in that becomes `lastFile` and can be POSTed as the run's actual data. Import by reference. [[mock-fallback-never-fabricates-data]] | TODO |
| L2-05 | A27 | A user-reachable surface for `/data/assemble-scrna` — it works and nobody can reach it. | TODO |
| L2-06 | B22 | Label the "Import" busy state (currently an unlabelled spinner). | TODO |
| L2-07 | — | swordfish: public host for the Nango **Connect UI** (`:3009`) if the FE wants the `@nangohq/frontend` widget rather than the direct-link flow. Asked 2026-07-25; **not blocking** — the direct flow works. | BLOCKED swordfish |

## Lane 3 — FE editor polish, reachable surfaces only (Plan B §5)

**Owns:** `app/frontend/components/figure/shell/{artboard-host,palette-strip}.tsx` ·
`app/frontend/lib/ui/**` · the icon decision's mechanics
**Must NOT touch:** `components/figure/{property-panel,figure-canvas}.tsx` or anything behind
`NEXT_PUBLIC_ANNOTATION_LAYER` — that is Plan C's territory.
**Gate:** `tsc` + `eslint` + `vitest`, **plus a real-app load at desktop widths** — these are layout
claims and the review's render gate never reached a browser.

| ID | Finding | Work | Status |
|---|---|---|---|
| L3-01 | A24 | The artboard hero is clipped inside its own stage (`height: min(74vh,720px)` vs ~150px of new fixed chrome). | TODO |
| L3-02 | A25 · B13 | The inert "coming soon" palette strip eats 64px of a height-constrained editor and asserts the colourway by colour alone, `aria-hidden`. Retire it or make it real + accessible. | TODO |
| L3-03 | A30 | Execute P0-06's icon decision (Phosphor migration, or record lucide as the decision). | BLOCKED P0-06 |
| L3-04 | §D | Observe the review's unverified layout predictions in a real browser at desktop widths and close or re-file them honestly. | TODO |

### Merge train

`Lane 1` → `Lane 3` → `Lane 2`. Rationale: pure-backend first (no cross-lane contract), pure-FE
presentational second (cannot conflict with Lane 1), seam-spanning last so it rebases onto both and
its end-to-end gate runs against the final tree. Local merges autonomous; **each merge is followed by
its own founder push** so a bad lane never rides in on another's push.
Shared-ground rule: `app/backend/tests/**` is touched by two lanes → each adds tests only in its own
named files listed above.

### Lane mechanics — confirmed (P0-04 DONE)

Confirmed 2026-07-25 against **thalon's lane experience** on this box (their Sprint-7/8 lanes plus the
incidents that became their ratchets). Durable copy: `docs/next-session-plan/lane-mechanics-from-thalon.md`.
Their verdict: this partition matches what works there almost exactly. What Selom adopts:

**Fork + drive.** One lane = one `git worktree` + one branch `agent/<bucket>/<slug>` + one `claude`
session in the **shared tmux server** (not a terminal owned by an editor process, or the session dies
with the editor). The kickoff is a **FILE the lane reads** — scope, contract pointer, definition of
done, verify command — never chat history. This matters doubly here: **a worktree is a separate memory
namespace**, so each kickoff must inline its landmines rather than assume recall.
[[parallel-agent-lanes]]

**Worktree dep prep is its own step, and it bites on Linux.** Node module *resolution* walks up to the
main checkout, so a half-broken link set passes tests while tools needing workspace-nested deps
(eslint) fail. Assert the link set at lane **setup**, never at merge time, and **never `npm install`
inside a worktree**. Consequence for Lane 3: **dev servers may not run in a lane at all** (Turbopack
fatals on out-of-root symlinks), so L3-04's real-browser check happens on the lead's main checkout
*after* rebase — not in-lane. Plan it there.

**The frozen contract is the real tripwire — and it must be executable.** Disjointness comes from
construction (the globs above) and the glob check at the train is only a backstop; nearly every
"collision" they saw was **contract drift**, not a glob violation. So P0-03 is not a doc: the
`/cloud/providers` shape ships with a **key-stability test pinned on main** before any lane forks. A
lane that "improves" the shared surface then goes red *in its own run*, days before the train would
catch it. A lane that genuinely needs a shared-surface change is a **re-plan**, never a wave-through.
Free bonus: box-level git hooks are shared across worktrees (common `.git`), so our
`hygiene-scan --staged` pre-commit fires in every lane automatically.

**Merge train: strictly serial and LEAD-driven — a lane never merges itself.** For each lane in order:
**rebase** onto current `main` (rebase, not merge — keeps history linear) → run the **full gate on the
rebased result** → merge → next lane rebases onto the new `main`. The gate must run **at the train**,
not only in-lane: lanes test against the `main` they forked from, and the rebased combination is what
ships. Stale lane: **the lead rebases it**, not the lane session. Mechanical conflicts, resolve and
continue; **contract-shaped conflicts mean the lane mis-consumed the freeze → send it back**, because
hand-resolving semantic drift at the train is how wrong code ships with a green gate. Dead lane
(crashed session): the **worktree survives** — inspect its `git status`/log/stash before redoing
anything.

**Approval boundary, stated explicitly** (thalon's protocol takes fresh approval per launch; ours is
looser, so it must be written down): once **P0-05** approves the partition, forking the worktrees,
building in them, and the local merges are all **autonomous**. **Each push is a separate founder
gate.** Anything that would change a frozen contract, unpark an on-hold item, or add a fourth lane
returns to the founder first.

---

### Two gotchas adopted from thalon's incidents

**1. The `| tail` swallow — we are already doing this.** Piping a gate through `tail`/`head`/`grep`
returns the *pipe's* exit status, so the gate's failure code is lost and the failure summary can be
cut off. It cost thalon two real incidents: a swallowed guard failure that let forbidden content reach
`origin` (history rewrite required), and a red suite read as green at a session close. **Every gate run
in this session was piped through `| tail`** — the failures were visible in the summary lines I read,
so nothing was misreported here, but the exit code was not being checked and that is luck, not method.
Fix: read gate output **raw**, or capture to a file and test `$?` *before* filtering. P0-08's
`scripts/verify.sh` is the durable home; the habit is recorded in memory
[[read-gate-output-raw-not-piped]]. This is the same principle CLAUDE.md's ratchet ladder already
states ("gated on its exit code, never a `;`-chain that ignores failure") applied to how *I* run the
gates, not just how CI does.

**2. The fleet dies with one lane.** If the session supervisor's `OOMPolicy` is `stop`, one oversized
lane takes down every agent session on the shared box — thalon lost the whole fleet mid-wrap to a
3.7 GiB lane. **Checked on syd4: `OOMPolicy=continue`, so we are not exposed to that mode here** (P0-09).
What remains is CPU, not RAM: stagger the **suite runs**, not the launches, and cap each lane's test
parallelism. Sizing basis — thalon's measured ~2.26 GiB/lane and today's per-process split of this box
(agents cheap, dev servers/browsers/test fan-out expensive); the same numbers eamos sized their 4-lane
backend window on, and the reason they adopted the `-n 2` cap too.

## On-hold register — nothing here is forgotten

Two homes exist and both were checked: **`docs/on-hold/README.md`** (the P6 parking lot, 17 items —
"parked, not deleted"; leaving requires an owner decision naming the pillar it rejoins) and
**`agent_handoff/on-hold/README.md`** (5 Docker/WSL-gated items). Neither is touched by the lanes
above. Triage below is for **P0-07**.

### ⚠ The gate on several items no longer exists

Both registers park work behind *"ASK before Docker/WSL"* and *"needs a running Redis (Docker/WSL on
Windows)"*. That premise is stale: the owner cleared Docker on this Linux VPS on 2026-07-23, Docker
Engine v29.6 + Compose are installed, **and a Redis is already running on this box** (`selom-nango-redis`
on `:6380`, stood up for Nango). So these items are no longer *infra-blocked* — several may still be
correctly parked for a different reason (off-thesis breadth), but the recorded reason is wrong and
should be restated so the register keeps meaning what it says. [[ask-before-docker-wsl]]

| ID | Item | Recorded reason | Reality | Recommendation |
|---|---|---|---|---|
| OH-01 | arq + Redis job-status store | "needs a running Redis (Docker/WSL on Windows)" | Redis is running; Docker cleared | **Unpark candidate** — cheap now, and it makes cross-process job status visible (a real gap in `jobs/worker.py`) |
| OH-02 | OmicVerse isolated worker | "pandas<3 conflict → must run out-of-process/containerised" | The *isolation* reason still holds; the *Docker* gate does not | Stays parked — but for the licence + thesis reasons (GPL-3, breadth), not infra. Restate. |
| OH-03 | Community skill sandbox | container sandbox | Docker cleared; still v2 scope | Stays parked (off-thesis until the Skill Foundry community tier). Restate. |
| OH-04 | Deploy image (B8) | the deployment Docker image | Docker cleared; this now overlaps the **public backend on syd2** work (Dockerfile + GHCR image-CI) | **Merge with the syd2 lane** rather than tracking twice |
| OH-05 | BAM ingest | "needs large-file/async infra (ASK before Redis/Docker)" | Infra gate cleared | Owner call: unpark, or restate as "not needed by a current product goal" |
| OH-06 | Accession AUTO-fetch (Slice 5 B2) | infra + owner chose the manual loop at s53 | Manual loop shipped; auto-fetch was a deliberate product decision, not an infra block | Stays parked — reason is sound. Revisit only if the manual loop proves slow. |
| OH-07 | Journal style packs | export polish, not engine | `docs/journal-styles/spec.md` **already written** | Cheapest unpark on the board (spec exists) — good candidate once the lanes land |
| OH-08 | Supabase / arq+Redis / Kaleido infra | ASK before Docker/WSL | Kaleido shipped 2026-06-15; Redis available | Split the row: Kaleido is DONE, Redis→OH-01, Supabase stays pre-launch |
| OH-09 | Ask-Selom AI chat · Command-center C/B · ClawBio HOST · external skill audit · metabolomics_de · reference-atlas reproductions · pdf.js region-capture · gene-set messy lists · OSCA Gap E · pipeline flow animation · "Digitize this panel" · external-tool builds | off-thesis / post-spine / licence | unchanged | **Stay parked** — correctly reasoned, no action |
| OH-10 | OneDrive/Microsoft cloud provider | owner on hold pending a machine that logs into Azure cleanly | unchanged | Stays parked. Lane 2 must keep its provider list flag-driven so OneDrive drops in without a code change. |
| OH-11 | Public Selom backend on syd2 | needs Dockerfile + GHCR image-CI (mine) + 5 data-plane answers + owner spend gate | Docker cleared; the 5 answers are still owed to swordfish | Own lane, **after** next session. Fold OH-04 in. |
| OH-12 | WS6 AWS deploy | owner chose "this box first, AWS later" | unchanged | Stays parked |

### Register hygiene found while checking

| ID | Item | Status |
|---|---|---|
| OH-13 | `agent_handoff/on-hold/README.md` still frames its gates as Windows Docker/WSL constraints; the box is Linux with Docker installed. Rewrite the "Why gated" column so the register states real reasons. | TODO |
| OH-14 | Memory `[[selom-multisample-scrna-assemble]]` said "parked, on-hold P1" — it **shipped** in `11a115f`. | **DONE** 2026-07-25 — memory + index corrected to SHIPPED-not-reachable, pointing at L2-05 / L1-03 / L1-04 |
| OH-15 | Two on-hold homes (`docs/on-hold/` = parking lot, `agent_handoff/on-hold/` = infra-gated) with overlapping rows (Redis, deploy image, BAM). Fold the infra register INTO the parking lot so there is one home, per the Ratchet's one-durable-home rule. | TODO |

---

## Explicitly out of scope next session

Plan C's build (annotation layer) · any flip of `NEXT_PUBLIC_ANNOTATION_LAYER` · the syd2 public
backend · OneDrive · everything in OH-09. If one of these becomes urgent, it displaces a lane rather
than being added to one — three lanes is the size that fit last time without compaction.

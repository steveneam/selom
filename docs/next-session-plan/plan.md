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

## Owner directive — 2026-07-25, at the Phase 0 gate

Alongside the on-hold triage the owner asked for two further things, verbatim: *"any more features or
things that you think selom could benefit from, as well as integration the current features and layout
and workflow and make sure it's tight and robust."*

Answered in **`docs/integration-robustness/proposal.md`** (a proposal, not yet a plan of record —
nothing in it is scheduled until the owner picks). Its three load-bearing conclusions:

1. **The "31 of 35 user tasks have no affordance" headline is mostly the annotation layer the owner
   just deferred pending a proper plan** (owner intent, clarified 2026-07-25 — deferred, *not* shelved; a plan is owed). Not bleeding on users. The reachability debt
   on *live* surfaces is narrower (cloud · assemble-scrna · ERG measurements · `datasets.source` ·
   editor chrome) and **every item of it is already inside the approved lanes.** The plan is pointed
   at the right work.
2. **What is missing is structural, not scheduled.** Nothing stops "shipped but unreachable" from
   recurring — each review re-discovers it at gauntlet cost. The proposal's top recommendation is a
   **reachability ratchet**: enumerate user-facing backend capabilities, assert each is either reached
   by a declared FE surface or explicitly waived with a reason + tracking ID, exit-code gated. It must
   ship **green**, with waivers for today's known set, each lane removing its own waiver as it lands —
   a guard that starts red is the trap `L1-10` just was. Note this is the remedy
   [[selom-shipped-not-reachable]] already named and that was never built, so today it survives only
   in memory, the weakest rung of the ladder.
3. **Features are gated behind that.** Four proposed (run-history/version-diff · cross-panel
   consistency audit · one-click regenerate-at-journal-spec, which is what makes the just-unparked
   `OH-07` worth doing · reachability dashboard). **No new analysis skills** — the constraint is
   reachability, not breadth, and adding skills while five shipped capabilities have no UI makes the
   ratio worse.

Sequencing recommendation: the 3 lanes → the ratchet (ideally *before* the lanes) → §3 layout/workflow
with Lane 3 → the unparked pair → Plan C's spec **led by** "re-run must not silently discard user
work" → the reproducibility features.

## Phase 0 — before any worktree is forked (sequential, blocking)

| ID | Item | Owner | Status |
|---|---|---|---|
| P0-01 | **Push `main`** — the merge + the review backlog + this plan. Count is whatever `git rev-list --count origin/main..main` says (do not trust a number written here). Triggers the Vercel deploy. | **founder gate** | **DONE** 2026-07-25 17:2x +1000 — owner authorized at the Phase 0 gate; pushed `60df628..dddf5d6` (27 commits). Vercel deploy triggered. |
| P0-02 | Delete `campaign/parallel-lanes` — only after P0-01, so the work has a remote ref first | me | **DONE** — verified contained in `main` (`merge-base --is-ancestor`) then deleted with the safe `-d`, after the push. Was `d950601`. |
| P0-03 | **Freeze the one cross-lane contract**: `GET /cloud/providers → { providers: [{ id, label, kind, provider_config_key, enabled }] }`. Written into `docs/figure-editor-contract/`-style form before Lane 2 starts; no other lane may define or consume it. | me | **DONE** — executable freeze `app/backend/tests/test_contract_cloud_providers.py` (10 assertions, verified to FAIL on a renamed FE key, an added BE key, and a leaked secret); declarations `app/backend/cloud/contract.py` + `app/frontend/lib/cloud/contract.ts`; `registry.list_providers()` makes menu order server-owned; doc `docs/cloud-providers-contract/spec.md`. Guard filename sits **outside** Lane 2's `test_cloud*.py` glob, so editing the freeze is a visible scope breach. Route-conformance test is dormant behind a skip naming `L2-01` and self-activates. |
| P0-04 | Confirm the lane mechanics with **thalon** (has run worktree lanes on this box repeatedly) | me | **DONE** — `docs/next-session-plan/lane-mechanics-from-thalon.md`, adopted in §Lane mechanics |
| P0-05 | Approve (or reshape) the lane partition in §Lanes | **founder gate** | **DONE** — owner **approved the 3-lane partition as planned** 2026-07-25. Forking, building in-lane and the local merges are now autonomous; **each push stays a separate founder gate.** |
| P0-06 | **Icon decision (A30):** migrate to Phosphor, or record "lucide stays" as a decision so the finding stops recurring in every FE review | **founder gate** | **DONE** — owner chose **"lucide stays; Phosphor not adopted"**. Recorded as binding **DECISIONS #12** (the durable home), so the finding cannot recur. `L3-03` is consequently **DROPPED** rather than implemented — no icon churn in Lane 3. |
| P0-07 | Triage the on-hold register (§On-hold) — several items are parked on a gate that no longer exists | **founder gate** | **DONE** — owner **unparked OH-01** (arq + Redis job-status, which executes locked decision #6) and **OH-07** (journal style packs, spec already written); both queued for the sprint **after** the 3 lanes, in no lane. Everything still parked had its reason **restated** (`OH-13`) and both registers were folded into one home (`OH-15`). Owner also issued a **broader directive** — see §Owner directive below. |
| P0-08 | **Build the one-command gate of record** — `scripts/verify.sh`: `hygiene-scan --all` + BE `pytest -m "not slow"` + `ruff check` + FE `tsc` + `eslint` + `vitest`, exit-code gated, **raw output**. Selom has no single verify command today, and the merge train needs one to run against each rebased result. Also the natural home for the `\| tail` fix below. | me | **DONE** — `scripts/verify.sh`, **7** gates (added `fe-build`, which CI has and this list omitted: it is the only gate that catches SSR/integration breaks, so a train without it can merge a broken app green [[full-app-smoke-test-before-handoff]]). Raw output, per-gate exit code, runs all gates then a ledger + non-zero exit; fails CLOSED on a missing tool; reports NOT-RUN as `SKIP`, never folded into a pass. **Whole gate is 70s on main** (`-n 2`). Flags `--fast` / `--be` / `--fe` / `--force-build` / `--list`. |
| P0-10 | **Lane provisioning did not exist on Linux — NOT in the original plan, found while building P0-08.** The only worktree provisioner was `scripts/worktree-setup.ps1`: PowerShell, NTFS junctions, `.venv\Scripts\python.exe`, `cmd /c rmdir`. The box is Linux, so **no lane could have been forked with working deps.** Ported to `scripts/worktree-setup.sh` (symlinks, `bin/python`, gitignore-subset `.worktreeinclude` copy, toolchain assertion at setup, main-tree file-count ratchet, landmines printed for inlining into a kickoff). **Validated end-to-end** on a real throwaway worktree: provisioned, gates run, torn down, main tree byte-count unchanged (39713 → 39713). Also corrected `.worktreeinclude`, which told you each worktree "installs its own" node_modules — the exact thing `guard-worktree-install.mjs` refuses. | me | **DONE** |
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
| L1-01 | A10 (HIGH) | Give `GENE` the same tier treatment the p-value half got: a non-label column containing a gene token must not win. Same shape as `b73bd9b`, gene half. | **DONE** — gene SELECTION is now tiered in `engine/columns.py` (`GENE_EXACT` exact-canonical tier → `GENE_STRONG` substring tier, `pick_gene`); `GENE` stays the substring PRESENCE set so the D1 fit gate is unnarrowed. `canon()` also folds separators + a leading BOM, so `Gene Symbol` / `gene.name` / `\ufeffexternal_gene_name` resolve. Verified on real data: the EYG_28 + ALPK1 exports resolve to the same columns as before (`GeneID` / `external_gene_name` / `logFC` / `FDR`), and the hazard built from those same rows (`gene_biotype,logFC,FDR`) now resolves to `None` → frame-index labels, where it used to put `protein_coding`/`lncRNA` on the figure. |
| L1-02 | A19 | Move the forked `_pick` out of 6 runners into `engine.columns` so the drift guard can see **one matcher**, not just one vocabulary. Do with L1-01 — same files. | **DONE** — `engine.columns.resolve(role, df_columns, override, extra=, cols=)` + `normalize()` own normalization, the override and each role's selection order; all six `skills/*/run_real.py::_pick` copies deleted. Ratchet: `engine/test_vocab_drift_guard.py` upgrades its identity lock from the VOCABULARY to the RESOLVER and adds an AST scan that fails on any re-forked matcher under `skills/**` (proven to fire against all three spellings of the deleted fork, and proven quiet on ordinary skill code). **Residue:** the finding also asks for `engine/qc.py:162` (exact-tuple p resolution) to route through `resolve` — `engine/qc.py` is outside this lane's territory glob, so it is NOT done here; see `LANE-WRAP.md`. |
| L1-03 | A14 | Assembly zero-fills genes absent from a sample's reference → fabricated hard zeros. Emit an honest gene-overlap verdict; do not silently invent counts. | **DONE** — `assemble_scrna(..., join=)` now defaults to **`inner`**, so every count in the assembled matrix is a measured count; `outer` stays opt-in and its zero-fill is stated. `engine.assemble.gene_overlap()` measures the axis BEFORE the concat and stamps the verdict into `uns['selom_gene_overlap']` (survives the .h5ad write); `summarize()` surfaces it plus the flat `n_genes_union` / `n_genes_shared` / `per_sample_n_genes`, so the endpoint's `X-Assemble-Summary` header carries it with no route change. `inner` is not allowed to be quiet either — a drop is reported the same way. WARN below 0.9 shared/union. Verified on the REAL Hani GSE201356 triplets: 2 real samples → identical result (48923 cells x 64591 genes) now labelled `ok`; the documented `GRCh38_`-prefix mismatch → **67 076 of 98 129 genes** would previously have been assembled as silent fabricated zeros. **Follow-up for Lane 2:** `routers/data.py` has no `join` form field, so `outer` is currently unreachable via the API (default-only). |
| L1-04 | A21 | `engine/assemble.py` re-declares the 10x detector + re-implements unit loading → consult `engine/ingest`'s declared loader registry. Do with L1-03. | **DONE** — `engine.ingest` exports `is_10x_dir` (an identity alias of the one `_is_10x`) and `load_unit(path)` (the load half of `ingest`, through `_pick_loader` + the same honest failure messages). `assemble._is_10x_dir` IS `ingest.is_10x_dir`; `_read_unit` calls `load_unit` and keeps only assemble's genuinely new logic (the canonical-name staging dir). Ratchet: `tests/test_assemble.py` asserts the detector identity, AST-asserts no `read_10x_mtx`/`read_h5ad` call survives in `engine/assemble.py`, and runs a registry-recognized 10x directory through assemble end-to-end. Verified on the real GEO triplets above — they are read through the registry. |
| L1-05 | A15 | FACS gate bounds live in a transform space anchored to a data-dependent `t_top` that is never recorded → record it in provenance so the same gate spec reproduces. | **DONE** — `t` is anchored to METADATA and always recorded. Resolution order: the new `transform_t` param (an operator pinning the gate space) → each channel's `$PnR` from the FCS (per channel, which is what FlowKit actually does — the old docstring's claim was wrong) → a fixed 262144. `layout.meta.transform` carries `{name, t_source, t_per_channel, t_default_channels, m/w/a or cofactor}` and the methods prose states it (`top of scale T = …, taken from each channel's $PnR …, m = 4.5, w = 0.5, a = 0`). arcsinh records `t_source: not_applicable` rather than a `t` it never used. **Measured on a synthetic FCS:** with the OLD data-anchored `t`, one saturating event moved the P1 count from **0 to 7**; with `$PnR` it is 7 on both files. **Real-data gap:** `SELOM_DATASETS_DIR` contains no `.fcs` — see `LANE-WRAP.md`. |
| L1-06 | A16 | FACS silently drops gates it cannot resolve → a verdict row, not a vanished population. Do with L1-05. | **DONE** — `_flow.parse_gates` returns `(gates, dropped)` with a reason + fix per drop; the population table gained a **`status`** column (appended last, leading columns unchanged) and every unresolvable gate is now a ROW with `count=None` and its reason (`no_geometry` · `fewer_than_3_vertices` · `non_finite_split` · `unknown_type` · `not_a_gate_object` · `channel_not_in_fcs` · `parent_unresolved`). The root-mask parent fallback is gone: a child of an unresolved gate is marked `parent_unresolved` instead of having its %-parent computed against ALL events. `layout.meta.gates_unresolved` + the methods prose say the same thing. Tolerance is kept — nothing raises. |
| L1-07 | A17 | ERG oscillatory potentials report `0.0` for "not measurable" → `None`/`not_measurable`, so unmeasurable ≠ absent inner-retinal activity. | TODO |
| L1-08 | A18 | The opt-in robust a/b detector changes amplitudes without disclosure → disclose in methods via the same `layout.meta` channel the FACS/volcano fixes use. Do with L1-07. | **DONE** — `landmarks()` returns `detector` and (robust only) `detector_gate` = `{a, b, threshold_uv}`; `_erg.detector_summary()` is the ONE aggregator (returns `None` for `windowed`, so every existing figure + golden is byte-identical); all three ERG runners write it to `layout.meta.ab_detector`, and `_erg_ab_detector()` adds the disclosure sentence to the `erg_traces` / `erg_bwave_bar` / `erg_intensity_response` methods templates — the SavGol construction, the 2×1.96×SD gate, the windowed fallback, and how many segments actually fell back. The construction sentence lands from the param alone (so a litsynth params-only replay still discloses); the gate outcome only when the runner recorded it. **Verified on the real CMRI `.iwxdata`:** robust vs windowed b-wave differs on **7 of 7** real segments (e.g. 157.8→192.5, 225.0→147.7 µV) and **7/7 a-waves + 5/7 b-waves** were measured by the near-floor fallback — none of which was visible before. |
| L1-09 | — | **ERG figure/table wiring** (was candidate lane (a), unblocked when FACS landed): OP · PhNR · flicker-FFT into the figure/table surfaces + `companions/methods.py`. The measurements shipped in `a84636c`; nothing surfaces them yet — a shipped-not-reachable item, so it belongs in this sweep. | **DONE** — three declared `param_spec` keys (the surface the FE renders): `erg_traces.oscillatory_potentials` → `ΣOP` / `OP RMS` / `OPs (n)`, `erg_traces.phnr` → `PhNR BT` / `PhNR trough t`, `erg_flicker.fourier` → `fundamental` / `phase` / `measured at (Hz)`. All land in the statistics table each figure ALREADY carries (no new output kind) and all three default **OFF**, so every existing figure, table, title and golden is byte-identical. The A17 invariant is carried to the surface: an unmeasurable segment prints its REASON, never a 0, and `layout.meta.oscillatory_potentials` records how many segments the group mean excluded. `companions/methods.py` describes each metric only when it ran. **Verified on real data:** the CMRI `.iwxdata` trace grid now reports ΣOP 201–451 µV / 4 OPs / PhNR BT 102–165 µV per segment with the a/b columns and the figure unchanged; the Diagnosys `full-txt-exp8` flicker export reports a 4.81 µV fundamental at 10.7 Hz and 1.05 µV at 28 Hz alongside its N1→P1. |
| L1-10 | — | `test_ingest.py::test_ingest_h5ad_single_cell` (anndata ↔ pandas-3.0 h5ad write) has been red for the whole campaign, proven pre-existing. Fix it, or skip it with an honest reason + a pointer — a permanently-red gate trains everyone to ignore the gate. | **DONE — pulled into Phase 0, no longer Lane 1's.** Fixed, not skipped. Root cause: the test built its fixture as `ad.AnnData(X)` with no obs/var, so anndata auto-generated indices that pandas-3 materializes as arrow-backed strings its h5ad writer has no method for (it raised on key `_index`); `allow_write_nullable_strings` does not cover that case. Fixture now names both indices `dtype=object` — the idiom already proven in `test_cepo.py` and the same coercion `assemble._prepare_for_write` does for the **production** write path, which was already correct. Write-side fixture only; the read path under test is unaffected. Done here because P0-08's gate of record is worthless while it is red on a clean tree. |

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
**Gate:** in-lane `scripts/verify.sh --fe` (hygiene + eslint + tsc + vitest — all three **measured to
resolve correctly** through the shared `node_modules` symlink), **plus a real-app load at desktop
widths** — these are layout claims and the review's render gate never reached a browser.
**Measured constraint (P0-10):** `fe-build` **cannot run in a lane** — Turbopack rejects the
out-of-root symlink (`Symlink node_modules is invalid, it points out of the filesystem root`).
`verify.sh` detects the worktree and reports it as `SKIP` with that reason rather than a misleading
`FAIL`. So **`fe-build` and the browser check are both merge-train steps on the lead's main checkout**,
after rebase — plan them there, not in-lane.

| ID | Finding | Work | Status |
|---|---|---|---|
| L3-01 | A24 | The artboard hero is clipped inside its own stage (`height: min(74vh,720px)` vs ~150px of new fixed chrome). | **DONE** — the stage sizes the card now (`items-stretch`, no inline height); the rule is one pure `artboardFrame(fixed)` in `app/frontend/lib/ui/artboard-frame.ts` that BOTH hosts consult, so CanvasShell and the classic EditorWorkspace cannot drift. Ratcheted by `lib/ui/artboard-frame.test.ts` (proven red when the `min(74vh,720px)` height is restored) — a browser gate was unavailable in-lane, so the invariant is executable instead. Browser confirmation is `D-5` in `LANE-WRAP.md`. |
| L3-02 | A25 · B13 | The inert "coming soon" palette strip eats 64px of a height-constrained editor and asserts the colourway by colour alone, `aria-hidden`. Retire it or make it real + accessible. | **DONE — retired.** Deleted `shell/palette-strip.tsx` + its call site in `canvas-shell.tsx`; the artboard gets its ~34px back. Chose retire over make-real because the accessible, spec-derived colourway control already exists three files away (Style tab, `style-panel.tsx:599-627`) — a second read-only copy would spend the same pixels to restate it, in the editor `L3-01` just proved is height-oversubscribed. **B13 closes; A25 is only PARTIALLY closed** — its other three placeholders (tool-context strip, the two dead rail tools, the disabled export-to-cloud row) are outside this lane's glob; re-filed on the finding for an owner. Ratcheted: `lib/ui/artboard-frame.test.ts` fails if any `shell/*` band renders "coming soon" again. |
| L3-03 | A30 | Execute P0-06's icon decision (Phosphor migration, or record lucide as the decision). | **DROPPED** — P0-06 decided **lucide stays**, recorded as binding DECISIONS #12. There is nothing to implement: the decision *is* the deliverable, and it closes A30 permanently. Lane 3 does no icon work. |
| L3-04 | §D | Observe the review's unverified layout predictions in a real browser at desktop widths and close or re-file them honestly. | TODO |

### Merge train

`Lane 1` → `Lane 3` → `Lane 2`. Rationale: pure-backend first (no cross-lane contract), pure-FE
presentational second (cannot conflict with Lane 1), seam-spanning last so it rebases onto both and
its end-to-end gate runs against the final tree. Local merges autonomous; **each merge is followed by
its own founder push** so a bad lane never rides in on another's push.

**The gate at each train step is `scripts/verify.sh` (no arguments) on the lead's main checkout** —
the full 7-gate run, ~70s, including the `fe-build` that no lane could run. Run it on the *rebased*
result before the merge, never only in-lane: lanes test against the `main` they forked from, and the
rebased combination is what ships.
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
inside a worktree**. `scripts/worktree-setup.sh` (P0-10) does both: it links and then *asserts* that
`next` and the `eslint` binary actually resolve through the link, failing the provisioning rather than
handing over a lane that breaks hours later at the train.

**Now measured rather than predicted** (P0-10, on a real throwaway worktree on this box): `eslint`,
`tsc` and `vitest` **all pass in a lane** — better than feared. What genuinely cannot run is anything
Turbopack drives: **`next build` and `next dev` both fatal** on the out-of-root symlink
(`Symlink node_modules is invalid, it points out of the filesystem root`). So the consequence for
Lane 3 is narrower but firmer than written above: its lint/type/unit gate runs in-lane, while
**`fe-build` *and* L3-04's real-browser check are merge-train steps on the lead's main checkout** after
rebase. A **shared** hazard the ported script also surfaces: the BE `.venv` is symlinked too, and
`uv run` auto-syncs — so a lane that edits `pyproject.toml`/`uv.lock` mutates **every** lane's
interpreter. A lane needing a new BE dep stops and re-plans; it does not sync the shared venv.

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
| OH-13 | `agent_handoff/on-hold/README.md` still frames its gates as Windows Docker/WSL constraints; the box is Linux with Docker installed. Rewrite the "Why gated" column so the register states real reasons. | **DONE** 2026-07-25 — every surviving row now states its **real** reason (OmicVerse = GPL + breadth, not Docker · deploy image = overlaps the syd2 work · community sandbox = v2 scope · BAM = no product need · accession auto-fetch = a product decision, never infra · ClawBio = off-thesis + no partner). Two further staleness bugs found while doing it: the parking lot still listed **multi-sample scRNA assemble as parked when it shipped** in `11a115f` (same error OH-14 fixed in memory), and its footer pointed at the pre-migration Windows memory path. Both corrected. |
| OH-14 | Memory `[[selom-multisample-scrna-assemble]]` said "parked, on-hold P1" — it **shipped** in `11a115f`. | **DONE** 2026-07-25 — memory + index corrected to SHIPPED-not-reachable, pointing at L2-05 / L1-03 / L1-04 |
| OH-15 | Two on-hold homes (`docs/on-hold/` = parking lot, `agent_handoff/on-hold/` = infra-gated) with overlapping rows (Redis, deploy image, BAM). Fold the infra register INTO the parking lot so there is one home, per the Ratchet's one-durable-home rule. | **DONE** 2026-07-25 — `docs/on-hold/README.md` is now the single home and gained a **Graduated** section so items that leave keep an audit trail (arq+Redis and journal styles unparked, Kaleido done, assemble shipped). `agent_handoff/on-hold/README.md` is a pointer stub recording where each of its five rows went and why its Docker/WSL premise was stale. |

---

## Explicitly out of scope next session

Plan C's build (annotation layer) · any flip of `NEXT_PUBLIC_ANNOTATION_LAYER` · the syd2 public
backend · OneDrive · everything in OH-09. If one of these becomes urgent, it displaces a lane rather
than being added to one — three lanes is the size that fit last time without compaction.

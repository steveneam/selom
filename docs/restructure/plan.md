# Restructure — architecture & process hardening (the tracker)

> **This is the live tracker for the 2026-07-02 architecture audit.** It is the ONE
> place the audit's task list is tracked to completion. It does **not** duplicate the
> detailed followups/specs it points at — it is the index + status + acceptance bar
> over them, so a 1–2-task-per-session cadence never loses the thread, ships nothing
> half-done, and adds no scope that isn't captured here first.
>
> Status stamped 2026-07-02 12:39 +10:00. Companions (the detailed homes each task
> points into): `docs/pillars/plan.md` · `docs/engine-spine/spec.md` ·
> `docs/intake-questionnaire/followups.md` · `docs/data-aware-routing/followups.md` ·
> `docs/auto-tune/followups.md` · `docs/aws-materialization/plan.md` ·
> `agent_handoff/CURRENT.md` (NEXT). Memory: [[unify-on-superior-framework]]
> [[mock-fallback-never-fabricates-data]] [[verify-on-real-data-not-mock]]
> [[review-cadence-phase-not-task]] [[selom-shipped-not-reachable]].

## Owner decisions (locked 2026-07-02)

1. **Focus first = harden Product A** (the own-data front door), not reproduction/moat.
2. **Clean the foundation before the AWS deploy** (WS1→WS4 precede WS6).
3. **Dedup posture = case-by-case** — the recommended posture is written per task below.
4. **Process = trim to solo reality** — one agent covers both lanes while Codex is away;
   slim the 2-agent lock ceremony, keep the mechanized guards.

## Sequence

**WS1 (honesty) → WS2 (Product A) → WS3 (dedup, pulled in where it serves WS2) → WS4
(structural, opportunistic) → WS6 (deploy).** **WS5 (process trim) runs in parallel** —
it touches only docs/handoff, never the code path, so it can fill any session.

---

## Status board (scan here; pick the top 1–2 `TODO` by Order)

Status: `TODO` · `WIP` (≤1 at a time) · `DONE — <sha>` · `BLOCKED — <why>` · `DEFERRED`.

| Order | ID | Task | Pri | Status | Home / pointer |
|---|---|---|---|---|---|
| 1 | **WS1.1** | `_stub_figure()` prod guard (no fabricated figures off-dev) | P0 | DONE — 1be60a5 | CURRENT NEXT#2 · RISKS #11 |
| 2 | **WS1.2** | Methods-text ↔ param_spec accuracy guard | P1 | DONE — 8c7f09b | pillars P4 · NEW test |
| 3 | **WS2.1** | Close upload→run→save loop (own-data run = Library artifact) | P1 | DONE — 9c9c382 | CURRENT DEFERRED 7c-(b) · pillars P4 · RISKS #8 |
| 4 | **WS2.2** | Intake "correct the detection" affordances | P1 | DONE — f51e0c2 | intake-questionnaire/followups.md #2,3,4,7,8 |
| 5 | **WS2.3** | Surface the data-fit verdict on own-data | P1 | DONE — 50c3bde | data-aware-routing/followups.md #1–4 |
| 6 | **WS2.4** | Ingest robustness for messy real inputs | P1 | DONE — 4ee6ab9 | pillars P3c + P1d |
| 7 | **WS2.5** | QC coverage vs deliberately-broken real data | P1 | TODO | pillars P1c (extension) |
| 8 | **WS2.6** | Unify the run-path error taxonomy | P2 | TODO | pillars P1/P4 · NEW |
| 8b | **WS2.7** | Gzip-wrapped table support (`.csv.gz`/`.tsv.gz`) | P2 | TODO | NEW (WS2.4 follow-up) |
| 9 | **WS3.1** | Converge the two ingest/classify paths (shared primitive) | P2 | TODO | CURRENT NEXT#6 + NEXT#1 |
| 10 | **WS3.2** | Column-override logic → one resolver | P2 | TODO | NEXT#1 (concrete) |
| 11 | **WS3.3** | Param validation → drop the redundant gate | P2 | TODO | NEXT#1 (concrete) |
| 12 | **WS4.1** | `routers/_run.py` contract-frozen decomposition | P3 | DEFERRED | NEW (only if WS2 forces it) |
| 13 | **WS4.3** | FE undo history survives reload | P3 | DEFERRED | Lane-P / pillar-2 |
| — | **WS5.1** | Slim `CURRENT.md` (archive old SESSIONS + strip commented tail) | P2 | TODO | CURRENT Housekeeping · prune_current_history.py |
| — | **WS5.2** | Declare "solo mode" in the handoff protocol | P2 | TODO | agent_handoff/README.md |
| — | **WS5.3** | Prune the docs load (consolidate ai-explain specs, stale banners) | P2 | TODO | repo-structure recs |
| — | **WS5.4** | Mechanize cheap gaps (md link-check + docs-index test) | P3 | DEFERRED | NEW (optional) |
| last | **WS6** | AWS deploy (step 8) | P1 | BLOCKED — after WS1+WS2 | CURRENT DEFERRED · aws-materialization/plan.md |

> **WS3.4** (Kind classification in two places) is folded into **WS3.1** (same shared
> primitive). **WS4.2** (`project-workspace.tsx`) is already DONE (REFACTOR `c41ad49`,
> 1347→734) — no action.

---

## Working agreement (the anti-half-done / anti-creep rules)

1. **One task = one commit** (named paths, no `git add -A`; no AI sign-off
   [[selom-authorship-no-ai-signoff]]) — **plus** at most one tiny follow-up *handoff-stamp*
   commit that fills the self-referential sha (see #3). A task is `DONE` only when its
   **Definition of Done** is met **and** its **Verify** passed on real data + a live backend
   [[verify-on-real-data-not-mock]] — not when the code merely compiles.
2. **Stay on the board.** Do only tasks listed here. If new work surfaces mid-task, **add
   a new `WSx.y` row first** (capture), then decide — never silently expand a task's scope.
   Each task's **Scope guard** names what is explicitly *out*.
3. **Cross the task off with the work; stamp the sha in a follow-up.** Your finishing commit
   flips the task's Status to `DONE — <sha>` (leave `<sha>` a literal placeholder), appends the
   Progress-log line, and refreshes the `CURRENT.md` LIVE pointer — **alongside the code**, so
   the board is never left un-updated. Then replace `<sha>` with the pushed commit's hash in ONE
   tiny follow-up commit — `docs(handoff): stamp <WSx.y> DONE (<sha>)`. A commit **cannot** carry
   its own hash, and an amended hash never reaches `origin`, so the stamp is what makes every
   `<sha>` actually resolve on the remote (matches this repo's `docs(handoff): record …`
   convention). Push both.
4. **Reviews at the VERY END, not per workstream** (owner directive 2026-07-02, RESTRUCTURE-04;
   supersedes the earlier per-workstream-boundary cadence) — run `review-gauntlet` (+ `fe-review` if
   FE) **once, after ALL restructure tasks are DONE**, not at each WS1/WS2/WS3 boundary. Rationale: a
   boundary review that finds something forces re-churn on a spot later tasks will touch again; one
   final pass over the whole diff stays faithful to the plan and the no-distractions concept. Still
   [[review-cadence-phase-not-task]] (never per small task) — just batched to the finish line. **Carry
   the owed reviews to that final pass:** WS1 boundary (gauntlet + fe-review over the WS1 diff + the
   WS1.1 `StubEngineBanner` G2 rendered-in-context, NEXT#R) and WS2.1's in-browser click-through fold
   into the single end-of-restructure review.
5. **Foundation before deploy** — do not start WS6 until every WS1 + WS2 task is `DONE`.

---

## WS1 — Honesty foundation (gates deploy)

### WS1.1 — `_stub_figure()` production guard · P0 · Status: DONE — 1be60a5
All 31 skills fall back to a fabricated synthetic figure when `use_real_engine()` is
false, served as HTTP 200 (only a faint "(stub)" title). A deploy missing the
scverse/pydeseq2 extras would ship fake science — a direct breach of the "no black box"
promise. Home: CURRENT NEXT#2; add a RISKS.md #11 next to the #8 upload landmine.
- **Definition of Done:** off-dev, the engine policy can't resolve to `stub` (fail loud at
  startup, not per-request); any stub figure that *does* render (dev/demo) carries
  `engine_policy:"stub"` through to a visible FE "example data — not your results" banner;
  a reachability test asserts the stub path is unreachable when extras are present.
- **Verify:** boot with extras missing off-dev → refuses to start; boot in dev without
  extras → stub renders *with* the banner; test green.
- **Scope guard:** do NOT delete the stubs (they're legit for dev/demo/tests) — only guard
  and label them. No new skill work.

### WS1.2 — Methods-text ↔ param_spec accuracy guard · P1 · Status: DONE — 8c7f09b
`companions/methods.py` (40+ template builders) can interpolate a param name that no longer
exists in a skill's `param_spec` → confidently wrong methods prose. Home: pillars P4.
- **Definition of Done:** a test asserts every param token a methods/legend template
  references resolves against the live `param_spec` for that skill.
- **Verify:** rename a param in one `skill.json` locally → the guard fails; revert → green.
- **Scope guard:** the guard only; do NOT rewrite the prose templates themselves.

## WS2 — Harden Product A (the focus; the umbrella that gathers scattered work)

### WS2.1 — Close the upload→run→save loop · P1 · Status: DONE — 9c9c382
The guided own-data path isn't wired end-to-end: 7c-(b) FE upload (intake → presigned PUT →
confirm → parse → run-from-`dataset_id`) is deferred, and an own-data run isn't yet a saved
Library artifact. Product A isn't *reachable* until this closes [[selom-shipped-not-reachable]].
Home: CURRENT DEFERRED "7c-(b)"; prod dependency = RISKS #8 (uploads off the in-memory proxy).
**Done (FE-only; the BE endpoints were already built + tested in 7c):** a fresh single-file drop
now runs the real upload handshake (`lib/uploads/api.ts` `uploadDataset`: intake → local PUT →
confirm → parse), giving a server-authoritative dataset with `uploaded:true` (`fromApiDataset`
derives it from `status=ready` + a stored key, so it survives reconcile). `runSkillByDataset`
POSTs `/skills/{id}/run-dataset`; `use-figure-run` routes a fresh run + all three re-run flavours
through it whenever the dataset is `uploaded` and the run carries no design sheet / AI actions (those
stay multipart) — so a run needs no re-upload and re-runs work after reload (`canRerun` +
`activeDataset.uploaded`). Fail-soft throughout (a failed upload or dev:mock degrades to the
metadata-only dataset + multipart). Verified live on real eyg28 DE data (see Progress log).
- **Definition of Done:** a real file dropped in the UI → parsed → a skill runs from its
  `dataset_id` (no multipart re-upload) → the resulting figure is saved as a Library artifact
  and survives reload.
- **Verify:** browser, live backend, a real dataset — upload → run → reload → the figure is
  still there as a Library artifact.
- **Scope guard:** reuse the built `run-dataset`/`jobs-dataset` endpoints; do NOT redesign
  the store or the upload contract. S3 wiring is WS6, not here (local PUT stand-in is fine).

### WS2.2 — Intake "correct the detection" affordances · P1 · Status: DONE — f51e0c2
**Already shipped pre-tracker; verified live + doc reconciled (no re-build).** The five affordances
(#2/#3/#4/#7/#8) landed in the Layer A ingest build — `6b84834` (reproducible design-edit
affordances) · `3743878` (honest inspect states) · `79db701` (reset/override) — all committed
*before* this tracker (`e9edf44`) existed, so the audit inherited the stale "Deferred #1–#8" list in
`docs/intake-questionnaire/followups.md` and minted WS2.2 as a phantom `TODO`. RESTRUCTURE-04
verified each on a **live backend + real data** and reconciled `followups.md` (Deferred → Shipped;
that stale doc was the root cause). Home + exact items: `followups.md` **#2** (excluded-level badge
on >2-condition designs), **#3** (prefill reason — `design.note`/`reference_guess`), **#4** (source
column with one candidate), **#7** (reset to detected), **#8** (skill/prompt when routing is null).
(#6 sample-col also shipped; #1 rename/merge + #5 auto-thread-sheet remain deferred, out of scope.)
- **Definition of Done:** each of #2/#3/#4/#7/#8 has a working affordance on the confirm card. **Met.**
- **Verify (PASSED — real data + live `/data/inspect` on :8010):** **#2** fires on real bulk
  `EYG_29…St7…rawCounts.csv` (6 conditions) **and** real scRNA assembled from Hani GSE201356 10x
  (`line` = 3 iPSC lines); **#3** `note` on rpgr + `reference_guess='Control'` on rpgr + design sheet;
  **#4** "Conditions from <label>" on rpgr/eyg29/Hani (all single-candidate); **#6** Hani → `sample_id`
  detected + candidates `['sample_id','line']`; **#8** all four real datasets route to a skill (null
  branch = FE else). #7 is pure FE state (Reset-to-detected on `designEdited`). Gates: BE
  `test_design_hints` **25/25** + FE tsc clean + intake vitest **53/53** + eslint 0 (no code changed).
- **Scope guard (honored):** surfacing only — **no code change** (affordances already present). The AI
  L4 refiner (followups #1) was not rebuilt; no rename/merge map (design-sheet is the repro path).

### WS2.3 — Surface the data-fit verdict on own-data · P1 · Status: DONE — 50c3bde
Home + items: `docs/data-aware-routing/followups.md` **#1** (fit verdict on intake), **#2**
(dataset-card fit band), **#3** ("not a fit — <reason>" trace), **#4** (route-composer "why
rejected" + a "checked against your data" affirmation). **#1/#2 shipped pre-tracker in `99bd6e4`**
(`data-panel.tsx` renders `DataFitVerdict` + a dataset-card `ConfidenceChip` off the persisted
`dataFit`) — the doc's "Deferred" list was stale (the same phantom-TODO pattern as WS2.2
[[verify-todo-not-already-shipped]]). **#3 built this session:** `quick-apply.notAFitSkills` surfaces
the routed-but-`compatible===false` analyses (previously dropped silently), and `workbench-panel.tsx`
renders a muted, struck "Not a fit for your data — <reason>" list with the engine's reason **visible**
(not tooltip-only). **#4 is OUT of this DoD** (a distinct AI route-composer surface needing a backend
gap-threading change) — deferred, tracked in "Open items" below.
- **Definition of Done:** an inspected dataset shows its fit verdict + band on the own-data surface
  (#1/#2); a dropped-as-not-a-fit skill is traceable, not invisible (#3). **Met.**
- **Verify (PASSED — real data + live `/data/inspect` on :8010):** #1/#2 render off the persisted
  `dataFit` (present in `data-panel.tsx`); **#3** — real bulk counts `rpgr_irpe_rawcounts.csv` route
  `[deg, volcano, enrichment]` → `deg` is a chip, **volcano + enrichment `compatible=false`** ("missing
  a fold-change / significance column") → the not-a-fit trace shows both with their reasons; the real
  eyg28 DE table routes only to fitting skills (nothing dropped — correct). Gates: FE tsc clean +
  eslint 0 + vitest **487** (+5 `notAFitSkills` cases, incl. the complement-of-chips test); BE
  untouched.
- **Scope guard (honored):** reused the existing verdict component + the server-computed `dataFit`;
  no new scoring logic; #3 is FE-only (no backend change). #4's backend gap-threading kept out.

### WS2.4 — Ingest robustness for messy real inputs · P1 · Status: DONE — 4ee6ab9
The layered classifier degrades honestly, but a real stranger's CSV crashed or collapsed to one
column on an odd encoding/delimiter, and a corrupt file 500'd (the router caught only `ValueError`,
while a `UnicodeDecodeError`/`ParserError`/`BadZipFile` bubbled up as a crash). The "here are options"
surface for `UNKNOWN`/`GENERIC_TABLE` already existed (`route.py` → pca/corr_heatmap + an honest note;
QC `unclassified`); the robustness gap was the load path. Home: pillars P3c + P1d.
**Done (BE-only, `engine/ingest.py` + `engine/qc.py`):** `_load_csv` now sniffs the **encoding**
(utf-8-sig ± BOM → cp1252 → latin-1 backstop) and the **delimiter** (`csv.Sniffer` over comma/tab/
semicolon/pipe, header-max-fields fallback), so a European semicolon export or a cp1252 file loads
into real columns instead of crashing/blobbing; an empty file is an honest `ValueError`. `ingest`
wraps `loader.load` so any parse failure becomes an actionable `ValueError` (`_load_failure_message`
per loader → the router's existing `except ValueError` returns a 400) — never a 500. QC gains a
`maybe_transposed` **wrong-orientation** warn for count/intensity matrices (numeric cols > rows and
≥ 12 → "samples as rows, genes as columns"), fired for bulk + proteomics.
- **Definition of Done:** UNKNOWN/GENERIC_TABLE routes to an honest "here are options" surface;
  encoding/delimiter sniffing + a wrong-orientation hint exist; a genuinely unloadable file fails
  with a clear reason, never a crash. **Met.**
- **Verify (PASSED — real data + live `/data/inspect` on :8010):** six messy files, **zero 500s**.
  A **semicolon**-delimited real rpgr counts CSV → 200 `bulk_counts`, 6 numeric cols (was a 1-column
  blob); a **cp1252 + µ-header** real counts → 200 `bulk_counts` (was a `UnicodeDecodeError` 500); a
  **transposed** real counts (6 rows × 60 gene cols) → 200 with `qc.maybe_transposed` (fires on the
  natural no-hint path too); a **real alpk1 `.xlsx`** gene list → 200 `generic_table` + the honest
  options note (pca/corr_heatmap, "pick a skill manually"); a **corrupt `.xlsx`** → **400** "couldn't
  open … as an Excel file … (BadZipFile)"; a real **`.csv.gz`** → **400** honest "no ingest loader".
  Gates: BE fast **1190/1** + ruff clean; FE untouched. (Unit tests: `test_ingest.py` +6,
  `test_qc.py` +2, `test_data_inspect.py` +6.)
- **Scope guard (honored):** no new modalities; no auto-fetch/accession. Detection + honest options
  only. **Gzip support** (`.csv.gz`/`.tsv.gz`, common for GEO count matrices) surfaced mid-task — a
  new work item, so it went to a new row (**WS2.7**), not silent scope creep; today it is an honest
  400, never a crash, which satisfies this DoD.

### WS2.5 — QC coverage vs deliberately-broken real data · P1 · Status: TODO
QC flags (pillars P1c) were built against curated data. Extend to messy inputs. Home:
pillars P1c extension slice.
- **Definition of Done:** all-NaN column, single-sample, non-integer "counts", all-zero
  features, and wrong-orientation each produce the right block/warn flag with a fix hint.
- **Verify:** a broken-fixture matrix hits each flag; a clean one stays `ok`.
- **Scope guard:** extend the existing `engine/qc.py` rule set; do NOT change the
  block-vs-override policy (D-e5 stands).

### WS2.6 — Unify the run-path error taxonomy · P2 · Status: TODO
Three inconsistent error styles (engine `None` / router `HTTPException` / skill `ValueError`).
A stranger needs one honest, actionable surface. Home: pillars P1/P4.
- **Definition of Done:** a single error taxonomy (bad-input vs unsupported vs internal) that
  all three layers map onto, with fix-hints, mirroring the QC-flag shape.
- **Verify:** each error class surfaces one consistent, actionable message in the UI.
- **Scope guard:** taxonomy + mapping only; no behavior change to successful runs.

### WS2.7 — Gzip-wrapped table support · P2 · Status: TODO
A `.csv.gz`/`.tsv.gz` (the near-universal shape of a GEO count matrix — e.g. dorgau
`GSM…_counts.csv.gz`) currently returns an honest 400 "no ingest loader" (never a crash), but a real
stranger downloading from GEO hits a wall. Surfaced during WS2.4; captured here rather than expanding
that task. Home: `engine/ingest.py` registry.
- **Definition of Done:** a gzipped delimited table (`.csv.gz`/`.tsv.gz`/`.txt.gz`) ingests as its
  decompressed table (reusing the WS2.4 encoding/delimiter sniffing), classified as its real modality.
- **Verify:** the real dorgau `*.csv.gz` → 200 with its true kind + routing, on live `/data/inspect`.
- **Scope guard:** gzip only (no zip/tar bundles, no auto-fetch); reuse `_load_csv`'s sniffing — don't
  fork a second CSV reader.

## WS3 — Dedup / parallel-representation (executes CURRENT NEXT#1; case-by-case)

### WS3.1 — Converge the two ingest/classify paths · P2 · Status: TODO
`engine.classify()` (full, layered) and `extract.ingest._classify()` (cheap sheet-inventory)
carry duplicate synonym sets (`_LOGFC`/`_PVAL`/`_METAB_TOKENS`) that can drift. Home:
CURRENT NEXT#6 (the "compare + recommend how to converge" task) + NEXT#1.
- **Posture (recommended): cross-pollinate, don't force-merge.** Extract one shared
  classify/synonym primitive both import; keep the two entry points (they differ in cost by
  design); add a drift-guard test.
- **Definition of Done:** one shared synonym/classify module; both callers import it; a
  drift-guard test fails if a synonym set forks.
- **Verify:** the 4 reproduction ledgers + the engine classify tests stay byte-identical/green.
- **Scope guard:** do NOT merge the two entry points or change the paper-side cheap inventory
  behavior.

### WS3.2 — Column-override logic → one resolver · P2 · Status: TODO
`routers/_run.py:186–227` reimplements what `engine/columns.py` already does. Home: NEXT#1.
- **Posture (recommended): converge** — the router calls the engine resolver.
- **Definition of Done:** one override resolver; the router delegates; existing override
  behavior unchanged (tests green).
- **Verify:** a column-override run still resolves + records in provenance identically.
- **Scope guard:** no change to the override semantics or the 400 contract.

### WS3.3 — Param validation → drop the redundant gate · P2 · Status: TODO
Validation happens in `contract.validate_param_ranges()`, again in `_run.py:138–146`, and
(legitimately) in each runner's coercion. Home: NEXT#1.
- **Posture (recommended): converge the two identical gates**, keep the runner coercion (it
  can't trust strings; already partly guarded by `test_ai_reuses_core_validation`).
- **Definition of Done:** the router re-check delegates to (or is removed in favour of)
  `validate_param_ranges`; the runner coercion stays, documented why.
- **Verify:** an out-of-range param still 400s at the same point; a valid run is unchanged.
- **Scope guard:** do NOT touch the AI-reuses-core-validation guard or runner coercion logic.

## WS4 — Structural hardening (opportunistic)

### WS4.1 — `routers/_run.py` decomposition · P3 · Status: DEFERRED
The 314-line `_execute_skill_run` orchestrates ingest/QC/gates/execute/synthesize/provenance.
Contract-frozen split into sub-orchestrators (twin of the shipped `project-workspace` refactor).
- **Definition of Done:** external contract byte-identical; sub-orchestrators unit-testable;
  the structure guard extended.
- **Scope guard:** behavior-preserving only; pull in ONLY if a WS2 task already edits this file.

### WS4.3 — FE undo survives reload · P3 · Status: DEFERRED
Persist `figureStore` history to localStorage. Minor UX. Rides a pillar-2 slice.

## WS5 — Trim the build process to solo (parallel; docs/handoff only)

### WS5.1 — Slim `CURRENT.md` · P2 · Status: TODO
417 lines, with paragraph-length "one-line" SESSIONS rows + ~40 lines of commented-out prior
state (lines ~93–133). Home: CURRENT "Housekeeping" bullet; tool `prune_current_history.py`.
- **Definition of Done:** SESSIONS rows collapsed to true one-liners; prior-state comment
  blocks swept to `archive/`; CURRENT back under ~150 lines.
- **Scope guard:** archive, never delete [[the-ratchet-durable-artifacts]]; keep ~2 sessions inline.

### WS5.2 — Declare "solo mode" in the handoff protocol · P2 · Status: TODO
Codex is away; the lock/section ceremony is overhead. Home: `agent_handoff/README.md`.
- **Definition of Done:** a "solo mode" note that suspends the lock ritual while one agent
  owns both lanes and preserves the full 2-agent protocol for Codex's return; CLAUDE.md points
  at it. Aligns [[claude-covers-both-selom-lanes]].
- **Scope guard:** don't remove the protocol; just gate it behind a mode.

### WS5.3 — Prune the docs load · P2 · Status: TODO
101 files / 20k lines. Concrete: consolidate the two **shipped-work** specs
`ai-explain-followups/spec.md` + `ai-explain-wiring/spec.md` into `ai-helpers/` (the
AI-explain work shipped — these are records, not live specs; **do not delete, consolidate**),
add internal stale-banners to `command-center/design.md` + `plans/v2-*.md`, keep
`docs/README.md` index accurate. *(Correction 2026-07-02: `ai-explain-followups/` was
mislabeled "empty orphan" in the audit — it holds a real 5 KB spec.md; verify-before-delete
[[the-ratchet-durable-artifacts]].)*
- **Definition of Done:** the two ai-explain specs consolidated into `ai-helpers/`, banners in
  place, the index updated.
- **Scope guard:** archive/consolidate, never delete durable records; don't touch live specs.

### WS5.4 — Mechanize cheap gaps · P3 · Status: DEFERRED
A markdown link-checker + a docs-index-completeness test. Skip the 2-agent automation
(scheduled retro, contract-immutability guard) until Codex returns.

## WS6 — AWS deploy (step 8) · P1 · Status: BLOCKED (after WS1+WS2)
Unchanged from `docs/aws-materialization/plan.md`: split deploy (Lambda API + Fargate
compute), Aurora min=0 ACU + Alembic head, live Clerk, S3→EventBridge→Step Functions, the
owner-pending GitHub→AWS OIDC role, kill the static `selom-dev` key, flip `API_PROXY_TARGET`.
- **Scope guard:** do not start until every WS1 + WS2 task is `DONE`.

---

## Open items that stay in their own homes (tracked elsewhere — NOT lost, NOT in scope here)

- **Auto-tune phases 2–4 + D4 surface** → `CURRENT NEXT#5` / `docs/auto-tune/followups.md`
  (ingest-auto-detect is *subsumed* by intake 2a/2b — don't rebuild).
- **NEXT#0 residuals** (methods/legend draft persistence, bulk-revert, dedup cue) +
  **s5-followups #4** (Activity/Gaps drill-through) → `CURRENT NEXT#0` / `s5-followups.md`.
- **Milestone-owed** live-gateway spot-check (`SELOM_AI_GATEWAY=gateway`, real Llama) → NEXT#0.
- **Reproduction + Extract-Skills moat** → deprioritized per decision #1; stays in pillars P5
  + on-hold (atlas reproductions).
- **Pre-launch license gates** (MSigDB/AGPL RISKS #6, gsea sensitivity #10) → `RISKS.md` +
  `LAUNCH-GATES.md`.
- **P6 parking lot** (BAM, command-center C/B, Supabase/arq/Kaleido [superseded by AWS], …)
  → `docs/on-hold/README.md`, untouched.
- **skill-gaps backlog** → a dogfooding feedback engine, not a task.
- **Route-composer transparency** (data-aware-routing followups **#4**) — the AI `select_skill`
  rejection shows a generic "no fitting skill" note; thread the specific incompatibility reason
  through the gap + add a "checked against your data" success signal. A distinct AI route-composer
  surface (BE gap-threading + `ask-ai.tsx`), deferred out of WS2.3 → `docs/data-aware-routing/followups.md`.

---

## Progress log (append one thin line per session; newest first)

| Date | Session | Task(s) | Result / sha |
|---|---|---|---|
| 2026-07-02 | RESTRUCTURE-06 | WS2.4 | **Genuinely unbuilt (not a phantom-TODO like WS2.2/2.3) — real robustness work shipped.** BE-only: `_load_csv` now sniffs **encoding** (utf-8-sig ± BOM → cp1252 → latin-1 backstop) + **delimiter** (`csv.Sniffer` over `,\t;|`, header-max-fields fallback) so a semicolon/cp1252 real export loads into columns instead of crashing/blobbing; empty file → honest `ValueError`. `ingest` wraps `loader.load` → any parse failure becomes an actionable `ValueError` (`_load_failure_message` per loader) so the router returns **400, never a 500**. QC gains a `maybe_transposed` wrong-orientation warn (numeric cols > rows and ≥ 12) for bulk + proteomics. **Verified live on :8010 `/data/inspect` with REAL data** [[verify-on-real-data-not-mock]] — 6 messy files, **0 × 500**: semicolon real rpgr counts → 200 `bulk_counts` (6 cols, was a blob); cp1252 + µ header → 200 (was a `UnicodeDecodeError` 500); transposed real counts → 200 + `maybe_transposed` (fires on the no-hint path too); real alpk1 `.xlsx` gene list → 200 `generic_table` + honest options note; corrupt `.xlsx` → 400 friendly "…(BadZipFile)"; real `.csv.gz` → 400 honest "no ingest loader". The `UNKNOWN`/`GENERIC_TABLE` options surface already existed (`route.py` pca/corr_heatmap + note; QC `unclassified`) — the gap was the load path. Gzip support surfaced mid-task → captured as **WS2.7** (a new row, not scope creep; honest 400 today satisfies the DoD). Files: `engine/ingest.py`, `engine/qc.py`, `tests/test_ingest.py` (+6), `tests/test_qc.py` (+2), `tests/test_data_inspect.py` (+6). Gates: BE fast **1190/1** + ruff clean; FE untouched. `4ee6ab9` |
| 2026-07-02 | RESTRUCTURE-05 | WS2.3 | **#1/#2 were shipped pre-tracker (`99bd6e4`); built #3; #4 deferred.** Same phantom-TODO check as WS2.2 [[verify-todo-not-already-shipped]]: `data-panel.tsx` already renders `DataFitVerdict` (own-data fit verdict, #1) + a dataset-card `ConfidenceChip` off the persisted `dataFit` (#2) — the followups "Deferred" list was stale. **#3 (the genuinely-open item) built:** `recommendedFromRoute` silently dropped `compatible===false` skills; added `quick-apply.notAFitSkills` (returns the routed-but-mismatched analyses resolved to catalog skills + reason + band) and a muted, struck **"Not a fit for your data — <reason>"** list in `workbench-panel.tsx` with the engine's reason **visible** (not tooltip-only), non-interactive (they can't run). **Verified live on :8010 `/data/inspect` with REAL data** [[verify-on-real-data-not-mock]]: `rpgr_irpe_rawcounts.csv` (bulk counts) routes `[deg, volcano, enrichment]` → `deg` compatible (chip), **volcano + enrichment `compatible=false`** ("missing a fold-change column, a significance (p/padj) column") → the not-a-fit trace shows both with their reasons; the eyg28 DE table routes only to fitting skills (`volcano/enrichment/gsea`, nothing dropped — correct). **#4 (route-composer "why rejected" + "checked against your data") kept deferred** — a distinct AI route-composer surface needing a backend gap-threading change, not the own-data verdict surface + outside WS2.3's DoD; captured in data-aware-routing/followups.md + "Open items". Files: `lib/catalog/quick-apply.ts` (+`notAFitSkills`/`NotAFit`), `components/project/workbench-panel.tsx` (the trace), `lib/catalog/quick-apply.test.ts` (+5). Gates: FE tsc clean · eslint 0 · vitest **487** (+5); BE untouched. `50c3bde` |
| 2026-07-02 | RESTRUCTURE-04 | WS2.2 | **Verified + closed (no re-build) — the affordances shipped pre-tracker.** Reading `intake-questionnaire.tsx` showed all five WS2.2 items (#2 excluded-level badge · #3 prefill reason · #4 single-source column · #7 reset-to-detected · #8 routing-null copy) already implemented, each tagged with its followups number; `git blame` placed them in `6b84834` (07-01 21:33) / `3743878` (07-02 01:21) / `79db701` (07-02 02:14) — **all before this tracker (`e9edf44`, 07-02 12:51)**. The audit had inherited the stale "Deferred #1–#8" list in `followups.md` (never updated after those commits) and minted WS2.2 as a phantom `TODO`. Confirmed the wire both sides (`engine/questionnaire.py` always sets `note`, sets `reference_guess`/`group_candidates`/`sample_col_candidates`; `lib/intake/design.ts` mirrors them). **Verified live on :8010 `/data/inspect` with REAL data** [[verify-on-real-data-not-mock]]: real bulk `rpgr_irpe_rawcounts.csv` (2-cond → #3 note, #4 single-candidate, #8 routes to deg) + `+ rpgr_irpe_design.csv` (→ `source=design_sheet`, `reference_guess='Control'` → the #3 control-guess line) + `EYG_29…St7…rawCounts.csv` (**6 conditions → #2 badge fires**); real scRNA **assembled from Hani GSE201356 10x** (the GEO deposit has no per-cell obs design — it's in the GSM filenames — so built a faithful 2000-cell AnnData: obs `line`=3 iPSC lines → **#2 fires**, obs `sample_id`=4 GSM samples → **#6** sample-col picker with real replicate counts). `jev/retina_fadl.h5ad` correctly returns `needs_design=False` (only `n_genes`/`leiden`, no condition col). #7 is pure FE state; #8's null branch is the FE else (routing resolved on all real data). Reconciled `followups.md` (Deferred #2/#3/#4/#6/#7/#8 → **Shipped**, root-cause doc fix; #1/#5 kept deferred). **No code changed.** Gates: BE `test_design_hints` **25/25** + FE tsc clean + intake vitest **53/53** + eslint 0. Working Agreement #4 updated per owner directive (reviews deferred to the VERY END, after all tasks — not per-workstream). `f51e0c2` |
| 2026-07-02 | RESTRUCTURE-03 | WS2.1 | Closed the upload→run→save loop (FE-only; the BE intake/confirm/parse/run-dataset endpoints were already built + tested in 7c). New `lib/uploads/api.ts` `uploadDataset` drives the real handshake (`/uploads/intake` → local PUT of the bytes → `/uploads/{id}/confirm` → `/uploads/{id}/parse`) and returns a server-authoritative `Dataset` with `uploaded:true`; `fromApiDataset` derives `uploaded` from `status=ready` + a stored upload/parsed key (self-heals across reconcile). `data-panel.ingest` runs it on a fresh single-file drop (gated `!mockMode`, with an "Uploading…" cue), inserting via a new `projectStore.addUploadedDataset` (no `/datasets` re-POST — intake already persisted the row). `runSkillByDataset` POSTs `/skills/{id}/run-dataset`; `use-figure-run` routes the fresh run + all 3 re-run flavours through it whenever the dataset is `uploaded` AND the run has no design sheet / AI actions (run-dataset carries neither → those stay multipart); `canRerun` gains `activeDataset.uploaded` so re-run works after reload. Fail-soft everywhere (upload failure / dev:mock → metadata-only dataset + multipart). Gates: FE tsc clean · eslint 0 err (1 pre-existing set-state-in-effect warning, untouched) · vitest **482** (+ uploads happy/fail-soft, runSkillByDataset wire+422, addUploadedDataset no-POST, `uploaded` mapping); BE untouched (no BE change). **Verified LIVE on real eyg28 DE CSV** (RPGRIP1_cpdHet d210, TMM-K0; :8010 SQLite + LocalObjectStore + dev auth): intake → PUT 2.4 MB → confirm(ready) → parse(real sha) → **run-dataset produced a 16,760-gene volcano with NO multipart** → saved figure → a fresh `GET /figures` (=reload) still returns it with its spec → dataset row → `uploaded=true`. (HTTP-level e2e drove the exact FE wire path — no browser MCP in this env, as at WS1.1; the in-browser click-through is the one lighter item owed to the WS2 boundary review.) `9c9c382` |
| 2026-07-02 | RESTRUCTURE-02 | WS1.2 | Methods/legend ↔ `param_spec` accuracy guard: `tests/test_methods_param_spec_guard.py` statically reads every param token each `companions/methods.py` + `companions/legends.py` template pulls off its resolved-params dict (direct `p[...]`/`p.get(...)` **and** through same-module helpers that receive the dict — `_erg_adaptation(p)`, legends' `_contrast(p)`) and asserts each ∈ the live `param_spec`; a `test_extractor_is_not_vacuous` pins the reader so the guard can't pass hollow. 64 template cases + 1 meta, all green; templates untouched (Scope guard). Verify passed: renamed `volcano.top_n`→`n_top` in `skill.json` → 2 cases fail; revert → 65 green. Makes WS1 (honesty) **code-complete**; the WS1 boundary reviews (gauntlet + fe-review + WS1.1-owed StubEngineBanner G2) were **deferred this session by owner directive** — owed before WS1 is fully closed (CURRENT NEXT#R). `8c7f09b` |
| 2026-07-02 | RESTRUCTURE-01 | WS1.1 | Stub-engine honesty guard: prod boot guard (`config.is_production` refuses a stub-resolving engine off-dev, fail-loud at startup) + resolved `engine_policy` in provenance + FE "example data — not your results" banner + `test_engine_policy_guard` (reachability + drift). RISKS #11 added. Verified live: real DE CSV→`real`, stub→`stub`, prod+stub refuses boot. `1be60a5` · then reworded Working Agreement #3 (self-ref sha → a follow-up `docs(handoff)` stamp commit — owner-directed). |
| 2026-07-02 | RESTRUCTURE-PLAN | (planning) | Audit + this tracker written; CURRENT NEXT re-ranked to point here. |

---

## Next-session prompt (tailored — RESTRUCTURE-07 · WS2.5; supersedes the generic template below until stamped done)

Paste this to start the next session; re-stamp the header line with the real clock. When WS2.5 is
`DONE`, rewrite this block for the next top-`TODO` (like the CURRENT.md LIVE pointer).

```
# Selom — Restructure · 2026-07-02 HH:MM +10:00 · Claude (FE+BE, solo mode)
(re-stamp this line with the real clock at session start)

Read first: docs/restructure/plan.md (the tracker) → Status board + Progress log + the
Working Agreement. Confirm git: `git fetch && git status` — origin/main should be in sync at the
RESTRUCTURE-06 stamp commit.

State: WS1 CODE-COMPLETE (1be60a5 + 8c7f09b). WS2.1 (9c9c382), WS2.2 (f51e0c2), WS2.3 (50c3bde),
WS2.4 (4ee6ab9) DONE. WS2.4 shipped real robustness (BE-only): CSV encoding+delimiter sniffing in
`engine/ingest.py::_load_csv`, an `ingest` error-wrap so a parse failure → 400 not 500, and a
`maybe_transposed` QC warn in `engine/qc.py` (bulk+proteomics). New follow-up **WS2.7** (gzip
`.csv.gz`/`.tsv.gz`) captured from mid-task. **NOTE the recurring pattern:** WS2.2 + WS2.3 were both
already-shipped (stale "Deferred" docs); WS2.4 was genuinely unbuilt. **Before building any WS TODO,
read + git-blame the target first** [[verify-todo-not-already-shipped]]; if already there, verify-live
+ reconcile-doc + stamp, don't re-build. **Reviews deferred to the VERY END** (Working Agreement #4):
one review-gauntlet + fe-review pass over the whole restructure diff after ALL tasks are DONE (carries
the owed WS1 boundary NEXT#R + WS2.1's in-browser click-through). Do NOT run them per-workstream.

Do: proceed to the top TODO by Order — WS2.5 (QC coverage vs deliberately-broken real data; Order 7,
P1). Home: pillars P1c extension. **First read `engine/qc.py` — several flags already exist**
(non_integer_counts, negative_counts, all_zero_features, too_few_samples, proteomics all_missing_rows/
high_missingness, DE pvalue_out_of_range/nan_pvalues, empty, and the WS2.4 `maybe_transposed`); WS2.5
is verify-coverage-on-broken-REAL-data + fill the gaps. DoD: all-NaN column, single-sample,
non-integer "counts", all-zero features, and wrong-orientation each produce the right block/warn flag
with a fix hint. Verify: a broken-fixture matrix (build from a REAL dataset) hits each flag; a clean
one stays `ok`. Scope guard: extend the existing `engine/qc.py` rule set; do NOT change the
block-vs-override policy (D-e5 stands). BE task — run the BE fast pytest + ruff gate.

Rules (the anti-half-done contract):
- Stay on the board. New work surfaced mid-task → add a WSx.y row FIRST, don't expand scope.
- Honor each task's Definition of Done + Verify + Scope guard. DONE only when Verify passes on
  REAL data + a LIVE backend [[verify-on-real-data-not-mock]]. Gates: BE fast pytest + ruff ·
  FE tsc + eslint + vitest.
- One task = one commit (named paths, no `git add -A`, no AI sign-off) + one tiny follow-up
  handoff-stamp commit for the sha. You commit AND push (owner authorized).
- On finishing: flip Status to `DONE — <sha>` (literal placeholder) + Progress-log line +
  refresh CURRENT LIVE, all WITH the code; then `docs(handoff): stamp <WSx.y> DONE (<sha>)`.
  Push both. Careful stamping the sha: the legend / Working-Agreement / this resume prompt keep
  `<sha>` as literal placeholders — only the board row + section header + progress-log line get
  the real hash (a blind sed -g clobbers the templates).
- Reviews at the VERY END, not per workstream (Working Agreement #4, owner directive).
- Foundation before deploy: no WS6 until every WS1 + WS2 task is DONE.

Env / landmines (unchanged): :8000 = eamos, NEVER kill → BE on :8010 (`uvicorn main:app --port
8010`, no --reload; the uv-3.12 PY at C:\Users\seamegdool\AppData\Roaming\uv\python\
cpython-3.12.13-windows-x86_64-none\python.exe + PYTHONPATH="D:/selom/app/backend/.venv/Lib/
site-packages;." run from app/backend, NOT `uv run` — EDR; set PYTHONIOENCODING=utf-8 for non-ASCII
in probe output; ruff may hit WinError-5 first spawn, retry once). Broken-fixture inputs for WS2.5:
build from a REAL base (e.g. `D:/selom-data/rpgr/rpgr_irpe_rawcounts.csv`) — inject an all-NaN column,
a single-sample slice, non-integer "counts", all-zero rows, a transpose. FE = `npx next dev
--webpack`. git user.email stays 282747725+steveneam@users.noreply.github.com. Kill every dev server
you start before ending. Proceed to WS2.5.
```

## Resume prompt (persistent — the generic template; the tailored block above supersedes it until stamped done)

```
# Selom — Restructure · <YYYY-MM-DD HH:MM +zzz> · Claude (FE+BE, solo mode)

Read first: docs/restructure/plan.md (the tracker) → Status board + Progress log.
Confirm git: git fetch && git status (origin/main sync).

Do: pick the top 1–2 `TODO` by Order from the Status board. For each — work it per the
Selom Playbook (spec only if the task says so → build → VERIFY on real data + live backend
[[verify-on-real-data-not-mock]] → gates: BE fast pytest + ruff / FE tsc + eslint + vitest).

Rules (the anti-half-done contract):
- Stay on the board. New work surfaced mid-task → add a WSx.y row FIRST, don't expand scope.
- Honor each task's Definition of Done + Verify + Scope guard. DONE only when Verify passes.
- One task = one commit (named paths, no AI sign-off) + one tiny follow-up handoff-stamp commit
  for the sha. Owner pushes (unless the session prompt authorizes you to).
- On finishing: flip Status to `DONE — <sha>` (literal placeholder), append a Progress-log line,
  refresh the CURRENT.md LIVE pointer — with the code. A commit can't name its own resolvable
  hash, so fill `<sha>` in a follow-up `docs(handoff): stamp <WSx.y> DONE (<sha>)`. Push both.
- Reviews (gauntlet/fe-review) at a WORKSTREAM boundary, not per task.
- Foundation before deploy: no WS6 until every WS1+WS2 task is DONE.

Env/landmines (unchanged): :8000 = eamos, never kill (run BE on :8010); FE = next dev
--webpack; BE tests via the uv-3.12 PY + PYTHONPATH (not uv run); dev.db quota UPDATE before
dogfood; git user.email stays the steveneam noreply. Detail: agent_handoff/CURRENT.md ENV.
```

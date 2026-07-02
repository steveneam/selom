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
| 2 | **WS1.2** | Methods-text ↔ param_spec accuracy guard | P1 | DONE — <sha> | pillars P4 · NEW test |
| 3 | **WS2.1** | Close upload→run→save loop (own-data run = Library artifact) | P1 | TODO | CURRENT DEFERRED 7c-(b) · pillars P4 · RISKS #8 |
| 4 | **WS2.2** | Intake "correct the detection" affordances | P1 | TODO | intake-questionnaire/followups.md #2,3,4,7,8 |
| 5 | **WS2.3** | Surface the data-fit verdict on own-data | P1 | TODO | data-aware-routing/followups.md #1–4 |
| 6 | **WS2.4** | Ingest robustness for messy real inputs | P1 | TODO | pillars P3c + P1d |
| 7 | **WS2.5** | QC coverage vs deliberately-broken real data | P1 | TODO | pillars P1c (extension) |
| 8 | **WS2.6** | Unify the run-path error taxonomy | P2 | TODO | pillars P1/P4 · NEW |
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
4. **Reviews at the milestone, not per task** [[review-cadence-phase-not-task]] — run
   `review-gauntlet` (+ `fe-review` if FE) when a workstream (WS1 / WS2 / WS3) completes,
   not on each 1–2-task session.
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

### WS1.2 — Methods-text ↔ param_spec accuracy guard · P1 · Status: DONE — <sha>
`companions/methods.py` (40+ template builders) can interpolate a param name that no longer
exists in a skill's `param_spec` → confidently wrong methods prose. Home: pillars P4.
- **Definition of Done:** a test asserts every param token a methods/legend template
  references resolves against the live `param_spec` for that skill.
- **Verify:** rename a param in one `skill.json` locally → the guard fails; revert → green.
- **Scope guard:** the guard only; do NOT rewrite the prose templates themselves.

## WS2 — Harden Product A (the focus; the umbrella that gathers scattered work)

### WS2.1 — Close the upload→run→save loop · P1 · Status: TODO
The guided own-data path isn't wired end-to-end: 7c-(b) FE upload (intake → presigned PUT →
confirm → parse → run-from-`dataset_id`) is deferred, and an own-data run isn't yet a saved
Library artifact. Product A isn't *reachable* until this closes [[selom-shipped-not-reachable]].
Home: CURRENT DEFERRED "7c-(b)"; prod dependency = RISKS #8 (uploads off the in-memory proxy).
- **Definition of Done:** a real file dropped in the UI → parsed → a skill runs from its
  `dataset_id` (no multipart re-upload) → the resulting figure is saved as a Library artifact
  and survives reload.
- **Verify:** browser, live backend, a real dataset — upload → run → reload → the figure is
  still there as a Library artifact.
- **Scope guard:** reuse the built `run-dataset`/`jobs-dataset` endpoints; do NOT redesign
  the store or the upload contract. S3 wiring is WS6, not here (local PUT stand-in is fine).

### WS2.2 — Intake "correct the detection" affordances · P1 · Status: TODO
The deterministic skeleton computes/persists the design but can't always let the user *fix*
it. Home + exact items: `docs/intake-questionnaire/followups.md` **#2** (excluded-level
badge on >2-condition designs), **#3** (surface *why* the design was prefilled — the
`design.note`/`reference_guess` are already on the wire), **#4** (show the source column with
one candidate), **#7** (reset design edits to the detected prefill), **#8** (show the
resolved skill when routing is null). (#1 override + #5/#6 sample-col/sheet already shipped.)
- **Definition of Done:** each of #2/#3/#4/#7/#8 has a working affordance on the confirm card.
- **Verify:** browser, real bulk + real scRNA obs — mis-grouping is correctable, exclusions
  are visible, the prefill reason shows, routing-null shows the skill/prompt.
- **Scope guard:** surfacing + light edit only; the AI L4 refiner (followups #1 primary) is
  already shipped — do NOT rebuild it. No rename/merge map (design-sheet is the repro path).

### WS2.3 — Surface the data-fit verdict on own-data · P1 · Status: TODO
`DataFitSummary` is computed + persisted but never shown on own-data intake. Home + items:
`docs/data-aware-routing/followups.md` **#1** (fit verdict on intake — reuse
`components/reproduction/data-fit-panel.tsx`), **#2** (dataset-card fit band), **#3**
("hidden: not a fit — <reason>" trace), **#4** (route-composer "why rejected" + a
"checked against your data" affirmation).
- **Definition of Done:** an inspected dataset shows its fit verdict + band on the own-data
  surface; a dropped-as-not-a-fit skill is traceable, not invisible.
- **Verify:** browser, a real inspected dataset — verdict + band render; a non-fitting skill
  shows the muted reason.
- **Scope guard:** reuse the existing verdict component; no new scoring logic (the verdict is
  server-computed already).

### WS2.4 — Ingest robustness for messy real inputs · P1 · Status: TODO
The layered classifier degrades honestly, but the "we're not sure → here are options" path
(pillars P3c) is unfinished and real strangers bring malformed CSV / odd Excel / wrong
orientation. Home: pillars P3c + P1d.
- **Definition of Done:** UNKNOWN/GENERIC_TABLE routes to an honest "here are options"
  surface; encoding/delimiter sniffing + a wrong-orientation hint exist; a genuinely
  unloadable file fails with a clear reason, never a crash.
- **Verify:** feed 3–4 deliberately messy real files → each yields options or an honest
  error, never a 500.
- **Scope guard:** no new modalities; no auto-fetch/accession work (parked). Detection +
  honest options only.

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

---

## Progress log (append one thin line per session; newest first)

| Date | Session | Task(s) | Result / sha |
|---|---|---|---|
| 2026-07-02 | RESTRUCTURE-02 | WS1.2 | Methods/legend ↔ `param_spec` accuracy guard: `tests/test_methods_param_spec_guard.py` statically reads every param token each `companions/methods.py` + `companions/legends.py` template pulls off its resolved-params dict (direct `p[...]`/`p.get(...)` **and** through same-module helpers that receive the dict — `_erg_adaptation(p)`, legends' `_contrast(p)`) and asserts each ∈ the live `param_spec`; a `test_extractor_is_not_vacuous` pins the reader so the guard can't pass hollow. 64 template cases + 1 meta, all green; templates untouched (Scope guard). Verify passed: renamed `volcano.top_n`→`n_top` in `skill.json` → 2 cases fail; revert → 65 green. Completes WS1 (honesty). `<sha>` |
| 2026-07-02 | RESTRUCTURE-01 | WS1.1 | Stub-engine honesty guard: prod boot guard (`config.is_production` refuses a stub-resolving engine off-dev, fail-loud at startup) + resolved `engine_policy` in provenance + FE "example data — not your results" banner + `test_engine_policy_guard` (reachability + drift). RISKS #11 added. Verified live: real DE CSV→`real`, stub→`stub`, prod+stub refuses boot. `1be60a5` · then reworded Working Agreement #3 (self-ref sha → a follow-up `docs(handoff)` stamp commit — owner-directed). |
| 2026-07-02 | RESTRUCTURE-PLAN | (planning) | Audit + this tracker written; CURRENT NEXT re-ranked to point here. |

---

## Resume prompt (persistent — paste to start a restructure session)

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

# Layer A cross-stage AI entry points — BUILD SPEC (full remainder)

_2026-07-01 +10:00 (Australia/Sydney) · concrete build plan for the **remaining** Layer A phases
(ingest · grade · methods · polish), turning the design spec (`spec.md`) into reviewable slices.
**Status: written — PAUSED for owner review before any code.** No author sign-off (owner's work)._

> This is the build-spec peer of `spec.md` (the design/rationale). `spec.md` stays the "why + the
> apply-discipline contract"; this file is the "what files change, in what order, with what tests."
> Mirrors the `docs/intake-questionnaire/{spec,build-spec}.md` split.

## What the owner locked (forcing-Qs, 2026-07-01)

1. **Scope = the full Layer A remainder** — ingest (Phase 2) + grade (Phase 3) + methods (Phase 4) +
   AI-helper polish (Phase 5), in one spec. Built as sequenced slices; reviewed at **milestone**
   boundaries (not per slice — [[review-cadence-phase-not-task]]).
2. **Ingest surface = deterministic edit first, AI pre-fills.** Build the manual-edit affordance on the
   questionnaire (rename/merge/exclude a condition · name the scRNA sample column · reset-to-detected)
   so it is fully correctable by hand **with the gateway off**, then `<AskAi stage=ingest>` pre-fills /
   proposes **into** that editable form (L4 over L1–L3, [[layered-deterministic-extraction]]).
3. **Detection breadth = time-course now, ERG later.** Extend `engine.questionnaire.suggest_design_hints`
   to detect an ordered-timepoint (time-course) design; defer ERG-specific design detection to a
   dedicated ERG slice.
4. **AI verify path = operator recording + live spot-check.** Author a zero-credit operator recording for
   the ingest refiner + methods draft (the build/demo default) and spot-check once on the live
   `SELOM_AI_GATEWAY=gateway`. Deterministic path stays primary (gateway-off works).

## Reconciliation with what already shipped (READ THIS — the seed is partly stale)

- **Phase 0 (the reusable `<AskAi>` composer)** — SHIPPED (`e642ebe`). `components/ai/ask-ai.tsx` handles
  `staged` (analyze) + `select` (route) + the Auto-tune button. `ingest`/`grade`/`output`/`draft` are
  declared in the type union but **fall through silently** in `send()` (line 231). This spec wires
  `ingest` + `advisory` (grade) + `draft` (methods).
- **Phase 1 (route · SELECT)** — SHIPPED (`ad453fe` + the recommended-chips work).
- **Phase 2 (ingest) — the DETERMINISTIC skeleton is SHIPPED** (`99bd6e4`/`52a0e70`): the layered
  confirm-card (`components/intake/intake-questionnaire.tsx`), `engine.questionnaire.suggest_design_hints`
  (bulk + scRNA + design-sheet), `design` on `/data/inspect`, persistence via `mergeDatasets`. **What's
  left = the edit affordance + the AI refiner + time-course detection** (this spec).
- **Phase 3 (grade) reachability is DONE** (`a7d477c`, AI-EXPLAIN): `explain_score` is on `ScoreReport`
  (`showExplain`) and `propose_sweep` is on `SweepForm` ("Suggest"). The seed's "wire the
  already-built-but-unreachable explain_score" is **already shipped** — s5-followups #2 is CLOSED. Phase 3
  here re-scopes to the **advisory composer** only.
- **The ingest gateway ACTIONS are backend-wired already** (registry.py): `set_profile` ·
  `set_design {condition, batch?, control?, treatment?}` · `map_columns {role: column}` ·
  `apply_cleaning_step {step_id, enabled?}`. **The gap is FE-side**: no helper maps a `set_design`
  proposal onto the questionnaire's `DesignChoice`. Phase 2 builds that mapper — **no new backend action
  types** are needed for ingest.

## Invariants (all seven spine invariants hold — re-stated for this build)

1. **Render = f(spec)** — no AI output bypasses the spec/param path.
2. **AI compiles away** — every AI suggestion becomes a deterministic param/override a human could type;
   a gateway-off re-run reproduces it. The ingest refiner's output lands as **editable questionnaire
   answers** → the same `deg` params the runner already records; methods draft seeds from the run's own
   deterministic methods text.
3. **One provenance chokepoint** — any AI-assisted *figure-producing* run routes through `/ai/apply`
   → `provenance.stamp_ai_actions` (server derives actor/model/approved_by/approved_at). The FE posts
   only the `{action_id, type, target, prompt}` delta. No parallel attribution path.
4. **Apply-discipline by consequence** — ingest = STAGED (confirm-then-run); grade = ADVISORY
   (propose-only, never mutates); methods = DRAFT (AI-marked, editable prose); nothing new is auto-applied.
5. **Deterministic path primary** — every stage is fully usable with the gateway OFF. The AI renders
   *into* the manual controls (the questionnaire form, the methods textarea, an advisory card), never as
   a separate artifact.
6. **One pending queue** — ingest STAGED changes join the existing shared pending banner (partitioned by
   author + stage); one re-run commits them.
7. **Honesty** — `tier` is registry-derived, never trusted from a proposal; an AI delta is emitted only
   when the confirmed value **still equals** what the AI proposed (the `approvedActions` honesty check);
   unfulfillable-but-coherent intents → gaps, never a registry widen; ✨ only when the output is truly AI
   (source == "ai"), never on the deterministic fallback.

---

## Phase 2 — INGEST (the milestone; biggest slice: FE + BE)

**Goal.** The intake questionnaire becomes fully **correctable by hand** (gateway-off), and an
`<AskAi stage=ingest>` refiner pre-fills / proposes a design **into** it (✨-attributed via the
chokepoint only when confirmed unchanged). Plus deterministic **time-course** detection.

### 2a — Deterministic edit affordance (no AI; ships + is reviewable on its own)

Closes the **reproducible** G1 gaps in `docs/intake-questionnaire/followups.md` #2/#3/#4/#5/#6/#7/#8.

> **Reproducibility scope correction (found by reading `skills/deg/run_real.py` at build time — this
> spec's risk #3).** The `deg` runner derives bulk condition labels from **column names** (`re.sub(
> group_regex or DEFAULT_REP_REGEX, "", column)`) or a **design-sheet `group_col`** (source of truth),
> and scRNA labels from **obs values** (`condition_col`) — **there is NO label-rename map param.** So a
> free-text **rename / merge** of a condition label would NOT compile into a runnable param (invariant:
> AI compiles away): setting `treatment="Mutant"` when the runner derives `"PDE6B"` from the columns just
> errors. **Rename/merge are therefore DEFERRED** to a slice that adds a backend mapping primitive (an
> explicit sample→condition map, or exposing `group_regex`). The **reproducible** corrections that 2a
> ships: designate the scRNA sample column · choose / exclude the contrast levels (a non-selected level is
> inherently excluded from the pairwise contrast) · **attach a design sheet** (the runner's source of
> truth — the honest fix for a mis-grouping) · reset-to-detected. The AI refiner (2b) is likewise bound:
> it proposes only params the runner reads.

**FE — `components/intake/intake-questionnaire.tsx`** (the reproducible corrections + surfacing):
- **scRNA sample-col picker** when `sample_col` is undetected (followups #6, real DE-validity impact) —
  a select over the obs id-like columns (needs them on the wire; see §2a-be).
- **Exclusion badge on non-selected levels** in a >2-level design (followups #2): "not in this
  comparison" on pills that are neither reference nor treatment (surfaces the inherent pairwise exclusion).
- **Surface the `design.note` + that "control" was a guess** (followups #3): a one-line caption under the
  design block ("Inferred 3 conditions from the sample column names · 'WT' guessed as control").
- **Show the source column read-only when there's one candidate** (followups #4).
- **"Reset to detected"** control after any contrast edit (followups #7) — re-seed from the prefill.
- **Routing-null skill surface** (followups #8): when `routing` is null, show a "pick a skill" prompt
  instead of the silent "ready to analyze".
- Fix the pre-existing Radix "uncontrolled→controlled" `Select` warning (followups residual) — seed
  `value` to a defined string from first paint.

**BE — `engine.questionnaire` + the `/data/inspect` route** (§2a-be):
- scRNA design hints carry the **candidate obs id columns** so the FE sample-col picker has options.
  Add `sample_col_candidates: list[str]` to `DesignHints` (obs columns matching `_SAMPLE_FALLBACKS` or
  low-uniqueness id-like columns). Additive, fail-soft. Mirror the field on the FE `DesignHints` type.
- **Thread an attached design/sample sheet into `inspect`** (followups #5 — the reproducible mis-grouping
  fix): `suggest_design_hints` already accepts `design_path`; the `/data/inspect` route accepts an
  optional `design` multipart field → `suggest_design_hints(bundle, design_path=…)`, and
  `inspectData(file, override, design?)` sends it, so attaching a sheet updates the confirm-card (today it
  only matters at run time).

**Tests (2a):** BE — `sample_col_candidates` populated for a scRNA obs frame (empty/fail-soft otherwise);
the design-sheet path through `/data/inspect` yields a `design_sheet` source. FE — `inspect.ts` sends the
design file; a questionnaire render test for the sample-col picker + exclusion badge + reset + routing
prompt.

### 2b — The AI ingest refiner (`<AskAi stage=ingest>`; needs the gateway)

**FE — `lib/ai/proposals.ts`**: add `designFromIngestActions(turn: HelperTurn): DesignPatch | null`
(peer of `selectedSkillFromTurn`). Reads the turn's `set_design {condition, control, treatment, batch?}`
+ `map_columns` results and produces a **`DesignPatch`** = `{ groupKey?, reference?, treatment?,
sampleCol?, renamed?: Record<from,to> }` to pre-fill the editable questionnaire. **Bridge the naming
mismatch**: `set_design.condition → DesignChoice.groupKey/condition_col`, `set_design.control →
reference`, `set_design.treatment → treatment`. Never invents a level not in the detected `levels`
(coherent-but-absent → a gap, per invariant 7).

**FE — `components/ai/ask-ai.tsx`**: implement the `ingest` branch in `send()` (currently falls through).
Add an `onIngest?(patch: DesignPatch, rationale: string)` callback; `stage="ingest"` posts
`proposeActions({ stage:"ingest", goal, data_columns, params })` (forward the sample column names +
detected levels as context so the gateway maps messy names → conditions), maps via
`designFromIngestActions`, and calls `onIngest`. Gateway-off → the honest "gateway off, nothing changed"
note (unchanged degrade pattern).

**FE — `components/intake/intake-questionnaire.tsx` / `components/project/data-panel.tsx`**: mount
`<AskAi stage="ingest" mode="staged">` **inside** the design block (an "Ask AI to read my sample names"
affordance). `onIngest` applies the `DesignPatch` to the editable `DesignChoice` (pre-fill, never
silent) — the user then confirms/edits. Track whether the confirmed design **still equals** the AI
patch (the honesty flag).

**Provenance path (invariant 3 + 7).** On "Confirm & run":
- If the confirmed design **still matches** the AI patch (unedited) → route the run through **`/ai/apply`**
  with the `set_design` (+ `map_columns`) `ai_actions` delta → `provenance.stamp_ai_actions` stamps it →
  the figure carries a ✨ ingest action. (`applyAiActions` in `lib/ai/api.ts` already does the multipart
  design-aware apply.)
- If the user **edited** the AI-proposed design → route the **normal** run (`onAnalyze` → `runSkill`),
  human-attributed. (Mirrors `approvedActions`' "staged still equals proposed" check.)
- No AI involvement → the current normal-run path, unchanged.

**BE — operator recording (verify path decision 4).** Author a zero-credit **operator plan recording**
for the ingest refiner keyed on a dogfood paper (messy bulk sample names → a `set_design` plan). NB the
propose path uses the operator gateway's **`plans[]`** (empty today) — confirm the
`OperatorActionGateway.propose()` plan schema/keying at build time (the recordings seam mirrors
`explain.json`'s `explanations[]`; `plans[]` is its propose peer). A `test_recordings_file_is_well_formed`
peer validates the new plan entry.

**Tests (2b):** `proposals.test.ts` — `designFromIngestActions` maps set_design/map_columns → a
`DesignPatch`, bridges control→reference, never invents an absent level. `ask-ai` ingest branch +
gateway-off degrade. The honesty flag (matches→/ai/apply; edited→normal run). MSW: an ingest propose
turn (a `set_design` plan). BE: the operator plan recording validates.

### 2c — Time-course detection (deterministic; extends the engine)

> **Constraint (from `run_real.py._timecourse`): the runner REQUIRES a design sheet** (`_design_path`
> with a sample-id column + a `time_col`) — "column-name inference can't recover timepoints." So
> detection-from-column-names alone is not runnable. 2c therefore **auto-synthesizes a design sheet** from
> the detected timepoints (sample id = the count column name, `time` = the parsed numeric time) and passes
> it as the design file → `_timecourse` consumes it reproducibly. (When a real design sheet is attached,
> that stays the source of truth.)

**BE — `engine/questionnaire.py`**:
- Detect an **ordered-timepoint** design: bulk column labels (or an obs column) that parse as timepoints
  (`0h/24h/48h`, `day0/day3`, `t0/t1`, numeric+unit) via `run_real._numeric_time` (import directly, no
  shadow copy — DETECTED == CONSUMED, needs ≥3 distinct timepoints per the runner) → tag the candidate
  `kind="time_course"` (add `kind: "categorical" | "time_course"` to `GroupCandidate`, default
  `"categorical"`) with the levels **sorted by numeric time**, not alphabetically.
- Fail-soft (E4): any parse ambiguity / <3 timepoints → fall back to a categorical candidate (no worse
  than today).

**FE — `lib/intake/design.ts`** + **`data-panel.tsx`**: `DesignChoice` gains `kind?: "categorical" |
"time_course"` + the ordered `timepoints`; a time-course confirm **synthesizes a design-sheet CSV**
(sample-id + time columns) as the `designFile` for the run, and `designRunParams` sets `mode=timecourse` +
`time_col=time` (+ `group_col`/`covariate_col` if a stratum/batch factor was detected). This reuses the
existing `designFile` multipart path (`AnalyzeArgs.designFile`), so the run is reproducible with no runner
change.

**FE — questionnaire**: a time-course design renders an **ordered timeline** (levels in time order, a
baseline marker) rather than the two contrast selects; the confirm copy reads "time-course across N
timepoints".

**Tests (2c):** BE — ordered timepoints (`0h/24h/48h`) → `kind=time_course`, time-sorted levels via the
reused `_numeric_time`; a non-time factor stays categorical; <3 timepoints → categorical. FE — the
synthesized design-sheet CSV shape + `designRunParams` emits `mode=timecourse`/`time_col`; the
questionnaire renders the timeline branch.

### Phase 2 milestone gate
tsc/eslint/vitest + BE fast gate + a **real-data browser verify** (live uvicorn non-:8000, gateway off
for the deterministic edit path; one live `=gateway` spot-check for the refiner) on a **real bulk deg**
dataset (messy sample names) **and** a **scRNA** dataset (sample-col picker). Then **one**
`review-gauntlet` + `fe-review` pass at the Phase-2 boundary (it's a milestone-scale FE+BE change).

---

## Phase 3 — GRADE · ADVISORY (thin; reachability already shipped)

**Goal.** An advisory `<AskAi stage=grade mode=advisory>` on the Statistics/scorecard stage that answers
"which test / correction, and what does it assume?" — **propose-only, never mutates** (a true
apply-a-different-test needs new grade actions → still deferred, its own backend spec).

**BE — `routers/ai.py`**: extend `ExplainRequest.request` with `grade_advice` (informational, like
`explain_score`/`propose_sweep`; NOT a mutating action). Deterministic fallback = a grounded card from
the scorecard (the current test's assumptions + when to switch), so gateway-off is useful and honest
(`source="deterministic"`). Operator recording keyed by skill_id/goal.

**FE — `lib/ai/api.ts`**: widen `explain()`'s request union to include `grade_advice`.

**FE — `components/reproduction/score-report.tsx`** (the Statistics/scorecard surface): add
`<AskAi stage="grade" mode="advisory">` → `explain({request:"grade_advice", scorecard})`; render the
advice with the existing `ExplainSourceBadge` (ai/deterministic). Reuse the `showExplain` gating so the
public showcase stays clean.

**Tests:** `api.test.ts` explain(grade_advice) wire; a score-report render test for the advisory card;
MSW `grade_advice` branch (deterministic). BE: the deterministic grade_advice fallback + operator key.

---

## Phase 4 — METHODS · DRAFT

**Goal.** A one-click "Draft methods" + chat-polish `<AskAi stage=methods mode=draft>` on the
`PublishConfidence` card. The **deterministic draft** is the run's own methods text (already computed via
`methods.build_body` and shown on the card); the AI **polishes** it (AI-marked, fully editable).

**BE — `routers/ai.py`**: add `ExplainRequest.request = "draft_methods"` (or a sibling `/ai/methods` —
prefer extending `/ai/explain` for reuse) taking `{skill_id, goal, base_text}` → polished prose.
**Deterministic fallback = `base_text` verbatim** (the run's `methods.build_body` output), so gateway-off
returns the deterministic draft honestly (`source="deterministic"`, no ✨). Operator recording keyed by
skill_id/goal.

**FE — `lib/ai/api.ts`**: `draftMethods(req)` (or the widened `explain()` union).

**FE — `components/project/publish-confidence.tsx`**: add `<AskAi stage="methods" mode="draft">` — a
"Draft methods" button seeds from the card's existing deterministic methods text; chat refines ("match
Nature's format", "add the FDR threshold"). The polished text is **AI-marked** (✨ only when
`source=="ai"`) and **editable** in place; the deterministic text is always the fallback + the base.

**Migration note:** when pillar-2 splits out a dedicated Methods & Legend stage (pillar-2 slice 6), this
composer moves there unchanged (this layer owns the content generation, pillar-2 owns the stage/IA).

**Tests:** `api.test.ts` draft_methods wire (ai vs deterministic-fallback source); a publish-confidence
render test for the draft button + AI-mark only on source=="ai"; MSW branch. BE: fallback = base_text
verbatim + operator key.

---

## Phase 5 — AI-HELPER POLISH (FE-only; the explain/marker backlog)

From `docs/ai-helpers/s5-followups.md` — surface-quality, no new stages:
- **#11** sweep AI-prose **Copy** (carry `[AI-generated]`) — `components/project/sweep-form.tsx` (symmetry
  with the explain Copy).
- **#12** `approved_by` in the ✨ marker tooltip — `components/ai/ai-marker.tsx` (server-trusted approver;
  cheap in the tooltip, Activity feed is a bigger later add).
- **#13** staged-vs-committed model cue — label the staged preview's model **"proposed by"**
  (`ai-marker.tsx`; the documented propose→apply drift).
- **#14** "updated for the re-scored run" cue — `score-report.tsx`/`ExplainScore` (a brief signal when an
  open explanation auto-swaps on rescore; today only the spinner flashes).
- **#1** bulk **Accept all / Dismiss all** in the pending banner (the AI banner component).
- **#5** re-ask **dedup** — `lib/ai/proposals.ts` `addAiProposals` (replace previous suggestions for a
  param instead of concatenating).
- **#6** changed-control highlight on the **Marks/Threshold** editors — `figure-data-panel.tsx` (extend
  the amber/fuchsia ring to the bespoke figure-data controls for one changed-state language).

**Tests:** `proposals.test.ts` dedup (#5); marker tooltip approver/"proposed by" (#12/#13); the rest are
render/interaction covered by the fe-review at the milestone.

---

## Sequencing & review cadence

Build order: **2a → 2b → 2c → 3 → 4 → 5.** 2a ships the deterministic edit affordance on its own
(reviewable, gateway-independent); 2b layers the AI refiner on top; 2c is an additive engine slice.

Per-slice = tsc/eslint/vitest + BE fast gate + a targeted real-data verify. **Milestone reviews**
(gauntlet + fe-review, [[review-cadence-phase-not-task]]):
- **Milestone A = Phase 2 complete** (ingest edit + refiner + time-course) — FE+BE, milestone-scale.
- **Milestone B = Phases 3+4+5 complete** (grade + methods + polish) — batch the smaller AI-surface
  slices into one review.

## Verification plan (decision 4)

- **Deterministic paths** (2a edit affordance, 2c time-course, the methods/grade deterministic fallbacks):
  verify with `SELOM_AI_GATEWAY` OFF on a live uvicorn (non-:8000) + real data — the questionnaire is
  fully correctable and the run reproduces from the recorded design params ([[verify-on-real-data-not-mock]]).
- **AI paths** (2b refiner, grade advisory, methods draft): build/demo on the **operator** recording
  (`SELOM_AI_GATEWAY=operator`, zero credit) + **one live spot-check** on `SELOM_AI_GATEWAY=gateway`
  (real Llama) on a real dataset, confirming ✨ appears only when `source=="ai"` and the chokepoint
  stamps a server-trusted actor. NOT dev:mock alone (mock proves the wire, not content —
  [[selom-mock-is-wire-only-verify-real]]).

## Risks / open items to confirm at build time

1. **Operator `plans[]` propose schema** — `explain.json` today holds only `explanations[]`; the propose
   recording (`plans[]`) is empty. Confirm `OperatorActionGateway.propose()`'s plan schema + keying
   before authoring the ingest recording (mirror the `explanations[]` shape; add a well-formed test).
2. **`set_design` payload ↔ `deg` param naming** — the action carries `{condition, control, treatment}`;
   the runner reads `{condition_col, reference, treatment}`. The `designFromIngestActions` mapper must
   bridge this exactly (and it's the reason the refiner pre-fills the questionnaire rather than posting
   raw params). Cover with a test.
3. **Time-course reuse point — RESOLVED (read `run_real.py`):** `_timecourse` **requires a design sheet**
   (sample id + `time_col`); it rejects column-name inference. 2c therefore auto-synthesizes a design
   sheet from the detected timepoints (§2c), reusing `_numeric_time` directly (DETECTED == CONSUMED). No
   runner change.
3b. **Rename/merge reproducibility — DEFERRED (read `run_real.py`):** no label-rename map param exists;
   the reproducible mis-grouping fix is a design sheet (2a followups #5) or a future `group_regex`/mapping
   primitive. 2a ships only reproducible corrections (see §2a scope note).
4. **`/ai/apply` for ingest** — the ingest-assisted run reuses the existing multipart `applyAiActions`
   (design-file aware). Confirm a `set_design`-only action list is accepted and stamped (the chokepoint
   already handles arbitrary action deltas).
5. **Scope guard for 2a §sheet-through-inspect (followups #5)** — if threading the design sheet through
   `/data/inspect` widens 2a too far, split it to a 2a-follow; it's additive, not a blocker.

# Live reproduction drive — spec (umbrella step c)

> Status: **SIGNED OFF (s40, 2026-06-21) — build next session, FULL scope.** Owner picked step (c) and
> signed off "do all of it next session" = the deterministic floor (D-c1) + inline/no-new-infra (D-c2) +
> auto-extracted goldens AND the user-supplied-golden fast-follow (D-c3) + heuristic data-matching AND the
> per-panel data-picker fast-follow (D-c4) + the ledger-derived skill set (D-c5). Build deferred to the
> next session; this spec is the agreed design. The backend contract that makes the staged **"Run
> reproduction"** button + the **Score** stage real. Cross-lane (BE is normally Codex's lane; Claude covers both while Codex is away
> — [[claude-covers-both-selom-lanes]]). This spec is the design + the decisions to sign off BEFORE code.
> Companions: `docs/workspace-library/umbrella-shell.md` (the FE shell this fills), the figure-repro SOP
> (`docs/reproduction-engine/figure-repro-sop.md`), [[selom-figure-repro-mission]] [[selom-repro-edge-cases]].

## 1. Why

The umbrella shell ships a per-paper workspace with a **Reproduce** stage (supplementary intake) and a
**Score** stage (a faithful but *ghosted* skeleton). The trigger — "Run reproduction" — is disabled,
waiting on a backend that takes a user's paper + supplements and **grades it**. This spec defines that
contract: drop a paper, add its supplements, hit Run → Selom runs the matched skills, sweeps parameters
toward the paper's printed numbers, and fills the Score stage with a real two-axis scorecard + heatmap +
golden-vs-computed evidence — the same artifacts the showcase papers already render.

## 2. The honest scope (read this first)

This is the moonshot from [[selom-figure-repro-mission]], and it has a **real ceiling**. v1 is NOT
"perfect automatic reproduction of any paper." It is: *run the matched skills on the user's data, search
the parameter space toward the paper's printed numbers where we extracted them, grade what reproduces,
and **honestly report the rest**.* The split (from the resolved AI-gating decision, spec §10 / D in
[[selom-workspace-library]]):

- **The deterministic engine is the moat and ships free** — run skills · the parameter **sweep** · the R
  oracle · the score. It is strong because **the printed numbers are the oracle to search against**
  (the sweep recovered RPGRIP1's "numbers only reconcile at *unadjusted* p" with zero semantics). It is
  **never gated.**
- **Recipe inference has a floor and a ceiling.** Floor (default params + sweep) reproduces
  well-specified single-number figures. Ceiling = vague/complex pipelines (design formula, contrasts,
  ordering, subsetting) that need reading comprehension — across all 4 hand ledgers that reading was done
  by a human/agent, not a deterministic extractor. **v1 ships the floor.** The ceiling is the legitimate
  **Pro/AI gate** (AI *proposes* the recipe → the engine *validates* against the printed numbers) — a
  later tier, out of scope here.

**The two-axis credibility guard (load-bearing, [[selom-reproducibility-score]]).** A figure we can't
reproduce because of the *paper or its data* (irreproducible, structural-limit, no golden printed,
data-not-matched, needs-recipe) must score on the **reproducibility** axis and **never** as a
**Selom-confidence** defect. The Score stage already separates these two axes; the drive must classify
honestly so a hard paper never reads as a Selom failure. Greyed/excluded > falsely-failed.

## 3. What already exists (reuse, don't rebuild)

The pieces are mostly built — v1 is **orchestration**, not new engine:

| Need | Existing piece |
|---|---|
| Read main PDF + N supplements | `extract/ingest.py` `ingest_paper(main, supplements)` → `PaperBundle` (`.text`, `.tables`, `.find_table`) |
| Figure → skill skeleton | `extract/routing/engine.py` `build_auto_ledger(text)` → `Ledger` of figure-panels w/ `skill_id` |
| Extract printed numbers (goldens) | `extract/golden.py` `build_extracted_spec(...)` + `to_engine_panels(spec, feasibility=fmap)` → panels w/ `Golden` |
| Run one panel's skill + validate + blame | `reproduction.py` `run_panel(ledger, panel, data_path, extractor=…)` → drives run → compute → validate → rebuild scorecard |
| Score | `reproduction.py` `build_scorecard(ledger)` → `Scorecard` (panel_scores + dual-axis rollup + findings) |
| Async/streamed execution | `jobs/queue.py` `submit(...)` (**inline** by default — no infra; arq/Redis is opt-in) + `GET /jobs/{id}/events` SSE |
| Serve a driven ledger to the FE | `GET /papers/{slug}` already returns `Ledger` → the Score stage reuses the showcase components |

**The genuine gaps v1 must fill** (the orchestration + two honest limits):
1. **Merge** routing skill_ids + extracted goldens into one driven-able ledger (both producers exist;
   nothing composes them yet).
2. **Data matching** — which uploaded supplement/sheet feeds which panel's skill. v1 = heuristic
   (a designated/most-matrix-like data file per modality) + **honest "data not matched"** when ambiguous.
3. **The per-panel extractor** (skill output → the panel's metric) is hand-written in the 4 ledgers. v1 =
   a **generic extractor** (read the skill's Statistics `table`/figure by metric name) + sweep-to-golden
   where goldens exist; panels with no usable extractor are "computed, not auto-validated" (not a defect).

## 4. The pipeline (orchestration)

A `reproduce(paper_id, main_path, supplement_paths, params)` orchestration, runnable as one job:

1. **Ingest** — `ingest_paper(main_path, supplement_paths)` → `PaperBundle` (bytes already saved to a
   per-run temp dir).
2. **Skeleton + goldens** — `build_auto_ledger(bundle.text)` (skill_ids) merged with
   `build_extracted_spec(bundle.main) → to_engine_panels(feasibility=fmap)` (goldens) → one `Ledger`
   whose in-scope panels carry both a `skill_id` and any `Golden` the paper printed.
3. **Match data** — for each in-scope panel, resolve a `data_path` from the supplements (heuristic by
   modality + sheet name; `bundle.find_table` for ST2/ST6). Unmatched → panel marked `data_unmatched`.
4. **Drive** — for each in-scope panel WITH data: `run_panel(ledger, panel, data_path, params=defaults
   (+sweep where a golden exists), extractor=generic)`. Heavy skills go through `jobs.queue` so progress
   streams; light skills run inline.
5. **Score** — `build_scorecard(ledger)`. Out-of-scope / no-golden / data-unmatched / needs-recipe panels
   are greyed + excluded from the reproducibility rollup and contribute **zero** Selom-confidence defects.
6. **Persist + return** — store the driven `Ledger` keyed by `run_id`; the Score stage fetches it.

## 5. The endpoint contract

- **`POST /papers/{paper_id}/reproduce`** — multipart: `main` (the paper PDF) + `supplements[]`
  (xlsx/csv/pdf) + optional `design` sheet. Saves bytes to a per-run temp dir, submits a **reproduce
  job** (reusing `jobs.queue`), returns `{ run_id, status: "queued" }`. (Default inline → the job is
  already terminal on return for light papers; heavy ones stream.)
- **`GET /reproduction-runs/{run_id}`** — `{ status, progress?, ledger?, scorecard? }`. On `succeeded`,
  the driven `Ledger` (same shape as `GET /papers/{slug}`) so the Score stage reuses every showcase
  component (heatmap, dual-axis score, golden-vs-computed).
- **`GET /reproduction-runs/{run_id}/events`** — SSE progress (per-panel: routing → matching → running
  `<skill>` → scoring), so "Run reproduction" shows a live sweep, then the Score stage fills.

The reproduce job is a **new job type** alongside the per-skill job (it orchestrates many `run_panel`s);
it reuses `jobs.store` states (`queued/running/succeeded/failed`, `TERMINAL`) and the SSE emitter.

## 6. Infra posture (the decision to flag)

- **v1 needs NO new infrastructure.** `jobs.queue.submit` runs **inline** by default (`settings.queue !=
  "arq"`); SSE resolves in one event for inline jobs. Uploaded bytes live in a per-run temp dir, cleaned
  on completion/expiry. A configurable size cap rejects oversized uploads (413).
- **The arq/Redis async worker is the SCALE path only** — for slow multi-skill drives that shouldn't
  block a request. It already exists as an opt-in (`settings.queue == "arq"` → Redis). **Per
  [[ask-before-docker-wsl]] I will ASK before enabling Redis/arq or any Docker/WSL** — v1 deliberately
  stays on the inline path so this isn't forced now.
- **Large files / BAM etc.** are explicitly out of v1 (separate large-file infra, [[selom-bam-ingest]]).

## 7. FE wiring (the shell's Run reproduction)

- **The bytes problem (I5).** `SavedPaper` stores supplement **metadata only, no bytes**, and no PDF
  bytes (session-only object URLs). To run, the drive needs the actual file bytes. v1: the Reproduce
  stage holds the dropped `File` objects in session memory (the dropzone already receives them); "Run
  reproduction" uploads them. **Constraint:** a reload before running loses the bytes → the stage
  re-prompts to re-attach (honest banner). (Relaxing I5 to persist bytes = a later call; localStorage
  can't hold them — would need the backend store.)
- **Flow:** Run reproduction (enabled once ≥1 data supplement is attached) → `POST
  /papers/{id}/reproduce` (main PDF re-read from the session File + supplements) → SSE progress on the
  Reproduce stage → on `succeeded`, stamp `SavedPaper.reproductionRunId` (already reserved on the anchor)
  and switch to the **Score** stage, which fetches `GET /reproduction-runs/{run_id}` and renders the real
  scorecard into the skeleton (zero reflow — U6 already guarantees the layout matches).

## 8. Invariants

- **L1 — Engine never gated.** Run/sweep/oracle/score are free. Only AI *recipe proposal* (a later tier)
  is Pro.
- **L2 — Two-axis honesty.** paper-irreproducible / structural-limit / no-golden / data-unmatched /
  needs-recipe ⇒ reproducibility-axis only, **0 Selom defects** ([[selom-scrna-batch-genotype-confound]],
  [[selom-repro-edge-cases]]).
- **L3 — Digitize ≠ reproduce.** Recovered/digitized values never feed the score
  ([[selom-extract-reproduction-bridge]]).
- **L4 — No silent caps.** If the drive skips a panel (no data, no extractor, no golden), it is *shown*
  as that, never quietly dropped.
- **L5 — No new infra without a gate.** v1 = inline jobs + temp dir; arq/Redis/Docker only after an ASK.

## 9. Decisions to confirm (owner)

- **D-c1 — v1 = the deterministic floor, honestly scoped** (run matched skills on provided data + sweep
  toward extracted goldens; grade what reproduces; flag the rest). *Recommended.* The AI recipe-proposal
  ceiling is a later Pro tier, not v1. Confirm we ship the honest floor rather than wait for the moonshot.
- **D-c2 — Stay on the inline jobs path (no new infra) for v1.** *Recommended.* arq/Redis async is
  deferred behind an explicit ASK ([[ask-before-docker-wsl]]). Confirm.
- **D-c3 — Golden source.** v1 auto-extracts printed numbers via `extract.golden`; where the paper prints
  none, that panel is "no-golden / not auto-validated" (computed shown, not scored). *Alternative:* also
  let the user type/confirm a golden target per panel (a small FE add). *Recommended:* auto-only for v1,
  user-supplied goldens as a fast-follow.
- **D-c4 — Data-matching aggressiveness.** v1 heuristic-matches one data file per modality and is honest
  when ambiguous (`data_unmatched`). *Alternative:* a per-panel "which file feeds this?" picker (more
  control, more UI). *Recommended:* heuristic + honest-unmatched for v1; the picker as a fast-follow.
- **D-c5 — Scope: which skills drive in v1.** Start with the data-shaped skills that already drive live in
  the ledgers (deg/umap_scrna/integration/markers/composition/enrichment/volcano/pca…). Visual-only or
  fundamentally hand-extracted panels are "computed, not auto-validated." Confirm the starting set or let
  me derive it from the 4 ledgers' live-drive coverage.

## 10. Build plan (phased — each its own scoped commit, gated)

1. **Orchestration core** — `reproduce()` composing ingest → auto-ledger+goldens → match → drive → score,
   with the generic extractor + the honest classification (data_unmatched / no_golden / needs_recipe).
   Unit-tested on the staged ledgers' data (we have RPGRIP1/JEV/Hani/Dorgau real data) so the auto path's
   scorecard can be checked against the hand ledgers' known scores.
2. **Endpoints** — `POST /papers/{id}/reproduce` + `GET /reproduction-runs/{id}` + SSE, on the inline jobs
   path; per-run temp dir + size cap + cleanup.
3. **FE wiring** — enable "Run reproduction" (session File bytes), SSE progress on the Reproduce stage,
   stamp `reproductionRunId`, fill the Score stage from the run.
4. **Honest-edge hardening** — verify the two-axis guard on a deliberately-irreproducible input (no
   golden / unmatched data / batch≈genotype) → reproducibility low, **0 Selom defects**.

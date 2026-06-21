# Reproduction — dogfood-ready (phase spec + agile task plan)

> Status: **APPROVED (owner, 2026-06-22, session 50) — go with the recommended D1–D5 defaults;
> building Slice 0 this session.** The next phase, picked by the owner: *"get the reproduction
> one done well so I can dogfood more papers, because I don't have a lot of my own omics data to
> train the engine."*
> Parent: `docs/pillars/plan.md` (this phase = **P5 b/c/d + P2 2d + P3 3c**; that doc stays the
> roadmap-of-record, this is the focused execution plan for one phase).
> Companions: `docs/reproduction-engine/live-reproduction-spec.md` (the floor this builds on),
> `docs/table-synthesis/spec.md` (L3), [[selom-figure-repro-mission]], [[selom-repro-edge-cases]],
> [[layered-deterministic-extraction]], [[compound-capability-each-task]], [[step-back-build-helpers-when-stuck]].

## What

Make the paper-reproduction loop smooth enough that the owner can **drop many papers at it and
each one auto-grades and teaches the engine — without a hand-built ledger per paper**. The
floor already runs (`reproduce()` → graded two-axis scorecard); this phase raises *cold-drive
recall* (how much of a never-seen paper grades automatically) and turns every gap into a signal
that improves the next paper. Reproduction is the engine's **training-data loop**: more papers
in → more real failure modes surfaced → a better engine, which Product A inherits.

## Context

**Why reproduction is the lever (owner's reason).** The owner has limited personal omics data,
but unlimited published papers (10 staged today, see `docs/...` / [[selom-staged-pdf-data]]).
Each paper is a free, oracle-bearing test case: the printed numbers are the golden targets. So
"dogfood more papers" is literally "grow the engine's test corpus," and the bottleneck is the
cost of onboarding each paper.

**What exists today (reuse, do not rebuild).**
- `app/backend/reproduction_drive.py` — `reproduce(main, supplements)` / `drive_bundle(bundle)`:
  ingest → `engine.match.merge_ledger` (route + extract goldens → one ledger) → `match_data`
  (a file per panel) → run skill → `extract.readers` read the golden back → grade. Returns a
  `DriveResult { ledger, panel_drives: list[PanelDrive], summary }`.
- **Honest classification (load-bearing).** Per-panel status is one of `driven`, `no_golden`,
  `data_unmatched`, `needs_recipe`, `no_skill`, `run_failed`, `out_of_scope`. Everything except
  `driven` is **grey, excluded from the reproducibility rollup, and contributes ZERO
  Selom-confidence defects** — a hard paper never reads as a Selom failure, and no panel is
  silently dropped.
- Layered read-back: `extract/readers.py` (L1 skill-specific / L2 generic) + `extract/synthesize.py`
  (L3, 16-skill set) + `extract/golden.py` (printed-number extraction).
- **4 hand-built validated ledgers** as tests: `test_reproduction_{rpgrip1,jev,hani,dorgau}.py`
  (94–100/100). Plus `test_reproduction_drive.py`, `_drive_honest.py`, `_sweep.py`.
- s46 **metric-type tolerance grader** (`resolve_tolerances` / `metric_type` on `Golden`) — an
  engine delta (gseapy↔fgsea, Melody↔Harmony) is not graded as irreproducible.

**The gap.** The 4 graded papers were all hand-authored. The auto-drive's recall on a *cold*
paper (no hand ledger) is **unproven** — it was live-smoked once on JEV, never measured across
papers. We don't know, quantitatively, what fraction of a new paper grades automatically or
*why* the rest doesn't. That measurement is Slice 0, and it drives the rest.

## Requirements

R1. A repeatable **cold-drive diagnostic**: given a staged paper, run `reproduce()` with no hand
ledger and emit a structured **gap report** — per panel: status, skill, data file matched,
goldens expected vs read, and the *reason* it didn't grade — plus a rollup and an
"auto-grade rate."

R2. The diagnostic is **honest and non-destructive**: it never invents a golden, never turns a
gap into a Selom defect, and never crashes the run (a panel that raises is `run_failed`, not an
exception). Same guard as the live floor.

R3. **Extractor recall rises measurably** on real papers: after Slice 1, the auto-grade rate on
the diagnostic paper(s) goes up, with no regression on the 4 hand ledgers (they grade
byte-identically or better).

R4. A **per-panel data picker**: a `data_unmatched` panel can be pointed at the right supplement
file (the `data_map` override already exists in the drive — this surfaces it), so a dogfooded
paper is recoverable, not a dead end.

R5. A **skill-gap signal**: every `out_of_scope` / `needs_recipe` across dogfooded papers
accumulates into a prioritized "Selom can't do X yet" backlog — each paper makes the next
decision sharper.

R6. **Regression fixtures**: each paper the owner blesses becomes a fixture over the auto-drive
so a future engine change that silently regresses an earlier win fails CI.

## Design

### The dogfood loop (the thing we are making smooth)

```
  drop paper + supplements
        │
        ▼
   reproduce()  ──►  GAP REPORT  ──►  owner reads it
        │            (Slice 0)            │
        │                                 ├─► extractor miss?  → Slice 1 (widen readers/golden)
        │                                 ├─► data unmatched?  → Slice 2 (point at the file)
        │                                 └─► skill missing?   → Slice 3 (backlog → build later)
        ▼
   "auto-gradable enough?" ──yes──►  Slice 4 (freeze as a regression fixture)
```

Every slice is one scoped commit/session, independently shippable, and ordered so that **we
measure before we build**.

### Slice 0 — Cold-drive diagnostic  *(SHIPPED s50–51)*

> **Done.** Built `app/backend/reproduction_diagnose.py` and ran it cold on **two** calibration
> papers: Harmony (`findings-harmony.md`, s50) and Yoshimura (`findings-yoshimura.md`, s51, chosen
> for deposited tabular data). Both: 0 goldens, 0 driven, **0 Selom defects** — the gap is recall +
> data-availability, not credibility. Two baselines → two independent confirmations of the same
> extractor + matcher gaps, which drove Slices 1 + 5.


- **Goal:** run `reproduce()` on **Harmony** (Korsunsky 2019; staged `…/Data/Harmony` — main PDF
  + `NIHMS1539299-supplement-8.xlsx` + supplement zips/htmls) **cold**, and emit a gap report.
  Harmony is the owner-chosen calibration target: in-scope (Selom `integration` + clean-room
  **Melody**, [[selom-harmony-reimplementation]], validated against this exact paper), so the
  gaps it surfaces are *extractor/matching* gaps, isolated from skill-coverage gaps.
- **Build:** a thin `reproduction_diagnose.py` (or a `scripts/` entry) that wraps `reproduce()`
  and projects `DriveResult` → a `DiagnosticReport` (see D1). Unzip supplement archives to feed
  `tabular_paths`. Output JSON **and** a markdown table for human reading; write under
  `graphify-out/scratch/` (not committed) + a short findings note committed to this folder.
- **Acceptance:** running it on Harmony prints, per panel: status · skill · data file (or "—") ·
  goldens expected/read · reason; plus rollup counts and `auto_grade_rate = driven / (in-scope
  panels with ≥1 golden)`. No crash; 0 Selom defects regardless of outcome.
- **DoD:** the report exists, is committed as a findings note, and names the top 3 concrete fixes
  for Slice 1 (which metrics/captions the extractor missed and why).
- **Depends on:** nothing. **Size:** ~1 session (most code is projection over `panel_drives`).

### Slice 1 — Extractor recall (P5b)  *(SHIPPED s51 — `n_cells` family)*

> **Done (first family).** `extract.golden.extract_dataset_size` lifts the analyzed dataset size
> (`n_cells`) on tight result/QC anchors ("resulted in 56,865 cells after filtering") — calibrated
> 0-false-positive against Harmony's 28 benchmark cell-counts. Closed end-to-end: backfill
> `n_cells → umap_scrna` (`engine.match`), L1 read-back `extract.readers._read_umap` (UMAP point
> count). 4 hand ledgers byte-identical (30/30). `n_clusters`/correlation deferred (no clean signal
> in the 2 calibration papers — measure-before-build). Numbers in `findings-yoshimura.md`.

- **Goal:** widen `extract/readers.py` (L1/L2) and/or `extract/golden.py` for the *specific*
  gaps Slice 0 surfaces, so more printed numbers auto-grade with no hand ledger. THE scaling
  lever.
- **Acceptance:** Harmony's `auto_grade_rate` rises vs the Slice-0 baseline; the 4 hand ledgers
  grade **byte-identically or better** (no regression); each new reader has a unit test over the
  real output shape it reads.
- **DoD:** baseline→after numbers recorded in the findings note; tests green; ruff clean.
- **Depends on:** Slice 0. **Size:** ~1 session per gap cluster (may be 1–2 commits).

### Slice 2 — Data-fit scoring + matcher honesty + per-panel picker (P2 2d)

> **Scope enriched by the owner (s52).** Two owner asks fold into this slice because they are the
> same lever: (a) *"rank/score the data dropped into the supplementary box so we know if it's
> compatible / good data or not — we have a filter for this, our own engine should recognize if the
> dropped data is good or not"*; (b) *"the score must be visible **before** a user clicks Run (so
> they can drop different data) **and** after."* Matcher honesty IS that score, made the gate.
>
> **SHIPPED.** s52: `engine/compat.py` (the data-fit scorer) + matcher honesty + the before/after
> data-fit panel (Product B). **s53: the per-panel data PICKER (R4) + the Product-A data-fit band.**
> The picker surfaces `panel_drives` on the run contract, offers a file Select for each
> `data_unmatched` panel, persists the choice on the paper (`SavedPaper.dataMap`), and re-runs with a
> `data_map` override (filename → saved path, resolved server-side in `POST /papers/{id}/reproduce`).
> Verified: `match_data` honours the override end-to-end on the real Yoshimura paper (an unmatched
> `umap_scrna` panel left `data_unmatched`, was fed the picked file, `run_failed` honestly, **0 Selom
> defects** — a compatible pick would `drive`). Product A: `POST /skills/{id}/run`'s `data_fit` now
> renders a `DataFitVerdict` band on the own-data figure (same engine, same band vocabulary).
> Fix folded in: uploads now save into a per-file subdir keeping the ORIGINAL name, so the data-fit
> filenames the user sees (and the picker round-trips) match what they dropped — no uuid prefix.

**The bridge being built.** The engine already has the two halves of the owner's "filter":
`engine.classify` (what modality is this file) + `engine.qc.run_qc` (is it clean). What's missing
is the bridge that scores a dropped file against *what a panel's skill actually needs*. New
`engine/compat.py` is that bridge — one rankable **data-fit score (0–100)** per (file, skill),
composed of modality compatibility × data cleanliness. It is surfaced before a run (a pre-run
`assess` endpoint so the user can swap a bad file) and after (in the gap report + run contract),
and it drives the matcher.

- **Matcher honesty (the load-bearing gate).** `match_data` stops force-feeding the lone tabular
  onto a skill whose modality it can't be. The honest, *certain* gate: a flat table (xlsx/csv, the
  only thing `tabular_paths` yields) loads as a DataFrame and can **never** be `sc_counts` (that
  needs AnnData/10x) — so a single-cell panel fed a QC table is a determined payload-class mismatch
  → `data_unmatched`, **not** a forced `run_failed`. This is what flips Yoshimura's QC-table panels
  from a misleading crash to an honest "this file isn't the single-cell matrix this analysis needs."
  Honesty rule: gate **only** on a *positively-determined* incompatibility (file loads AND its
  payload class conflicts) — an unloadable/unclassifiable file stays optimistic (never gate on a
  guess; this is also why every existing fake-path drive test is unaffected).
- **The data-map override** ({panel_key: path}) already exists in the drive and still wins; this
  surfaces it on the run contract (BE) and as a per-panel "which file feeds this?" picker (FE).
  Auto-heuristic first, ask only on the gap (D3).
- **Acceptance:** (1) a Yoshimura/Harmony single-cell panel whose only supplement is a QC table
  classifies `data_unmatched` with an honest modality reason, not `run_failed`; (2) a pre-run
  `assess` returns each dropped file's kind + QC verdict + a 0–100 fit score per relevant analysis,
  ranked, so a wrong file is visibly poor *before* Run; (3) the data-map override makes a panel
  `driven` when pointed at a compatible file and the choice persists; an un-picked panel stays
  honestly grey (no silent guess); (4) the 4 hand ledgers grade **byte-identically** (no regression).
- **DoD:** `engine/compat.py` + tests (fit scoring + the certain/optimistic gate); `match_data`
  honesty test; pre-run `assess` endpoint + run-contract surfacing tests; FE data-fit panel
  (before + after) + per-panel picker browser-verified vs the live BE.
- **Depends on:** Slice 0 (to know which panels need it). **Size:** ~1–2 sessions (BE the engine +
  endpoint this session; FE the panel/picker next).

### Slice 3 — Skill-gap signal (P3 3c)

- **Goal:** turn every `out_of_scope` / `needs_recipe` into a durable, prioritized "Selom can't
  do X yet" backlog, so dogfooding becomes a feedback engine, not just a score.
- **Build:** the diagnostic appends gaps (paper · panel · skill/analysis · reason · frequency) to
  a committed `docs/skill-gaps.md` (the durable home — the Ratchet; not chat memory). Per-run the
  report shows the run's own gaps; the doc accumulates across papers and ranks by frequency.
- **Acceptance:** after dogfooding ≥2 papers, `docs/skill-gaps.md` lists the missing
  analyses ranked by how many papers hit them, with a one-line "what skill would close this."
- **DoD:** the doc exists and is updated by the diagnostic (idempotent — re-running a paper
  doesn't double-count).
- **Depends on:** Slice 0. **Size:** ~1 session.

### Slice 4 — Regression fixtures (P5c)

- **Goal:** each paper the owner **blesses** becomes a fixture over the auto-drive so engine
  growth never silently regresses an earlier win.
- **Build (two tiers, D5):** (a) a **classification-shape** fixture — snapshot each panel's
  `status` + driven metric values from the `DriveResult`; the test re-drives and asserts the same
  panels reach the same status and the same metrics within `resolve_tolerances` (s46). Runs in
  normal CI for papers whose data is small/committed. (b) a **real-data re-drive** marked slow /
  opt-in for large-supplement papers. The 4 hand ledgers stay as-is (already fixtures); this adds
  the *auto-drive* fixtures.
- **Acceptance:** a deliberately-broken reader change flips a blessed paper's fixture red; a
  tolerated engine delta (within the metric-type band) stays green.
- **DoD:** Harmony (once Slices 1–2 make it auto-gradable) is the first auto-drive fixture; the
  pattern is documented so each future blessed paper is a copy-paste.
- **Depends on:** Slices 1–2. **Size:** ~1 session.

### Slice 5 — Accession recognizer (data-side; P1 ingest)  ·  *SHIPPED s51 (Phase A)*

> **Done (Phase A).** `extract/accessions.py` — deterministic recognizer over `bundle.text`
> (availability-section weighted) → `Accession{repo, id, access: open|raw|controlled, ingestable,
> url, section, note}`. All listed repos (GEO/SRA/ENA/ArrayExpress/GSA/PRIDE/MetaboLights+MW/
> Zenodo/Figshare/Dryad/dbGaP/EGA). Validated on Yoshimura's real availability statement (3 GEO,
> citation-marker + `ST`-table traps handled). Surfaced in the diagnostic gap report (header line +
> Cited-datasets table). 10 unit tests. **Phase B (fetch) remains GATED** (D6). `findings-yoshimura.md`.


- **Goal:** recognize dataset **accessions** in the paper text (esp. the *Data/Code Availability*
  statement) and classify each by repository + access type, so a paper whose data is *cited not
  attached* (the Harmony meta-finding — papers deposit code/`.rda`/accessions, not tabular
  supplements) gets honest, actionable data provenance instead of a mis-matched supplement.
  **Owner-originated (s50).** The data-side sibling of Slice 1 (extractor-side) — orthogonal, both
  needed.
- **Build — Phase A (do now, no network, license-clean):** `extract/accessions.py` — deterministic
  regex over `bundle.text` (weight the availability section) → typed
  `Accession{repo, id, access: open|raw|controlled, ingestable, url}`. Repos: GEO (`GSE/GSM/GPL`) ·
  SRA (`SRR/SRP/PRJNA`) · ENA (`PRJEB/ERR`) · ArrayExpress (`E-MTAB-`) · **GSA** (`CRA/PRJCA/HRA`,
  NGDC/CNCB) · PRIDE (`PXD`) · MetaboLights/MW (`MTBLS/ST`) · Zenodo/Figshare/Dryad DOIs. URLs built
  deterministically (no dependency — avoid GEOparse on the shipped path unless its license is
  verified). Surface in the diagnostic gap report **and** Product A's `data_check`.
- **Phase B — deposit-data HANDOFF (link + download instructions; do now, NO infra) — owner
  decision s53.** Instead of auto-fetching, surface for each recognized accession a **direct link +
  concrete per-repo download instructions** (which file to grab, how) so the user fetches it
  themselves and drops it into the **per-panel picker** (Slice 2, shipped s53). Deterministic, no
  network on the shipped path → **NOT gated**. This closes `data_unmatched` via *the user + the
  picker* with zero fetch infra. The recognizer (Phase A) already builds the `url`; Phase B adds the
  per-repo "how to download the right file" copy + the FE surface (in the gap report / Reproduce
  stage, next to the Cited-datasets table) that hands the user to the link and back to the picker.
- **Phase B2 — auto-fetch + ingest (ON HOLD, P6).** The original network/large-file/async
  auto-download (open/processed GEO-suppl / Zenodo / Figshare → `engine.ingest` → feed the matcher).
  The hard part is GEO-supplement heterogeneity (tar / mtx-triplet / per-sample). **Parked** in
  `docs/on-hold/README.md` — the manual handoff (B) makes it non-urgent; revisit only if the manual
  loop proves too slow ([[ask-before-docker-wsl]]).
- **Phase C:** per-accession → per-panel (folds into Slice 2's picker — the picker already takes a
  per-panel file, so a downloaded accession file just becomes another pickable supplement).
- **Honest rules (load-bearing):** raw-reads (`SRA/ENA/GSA-CRA`) → "needs quantification" (the parked
  BAM-ingest, [[selom-bam-ingest]]); controlled (`dbGaP/EGA/GSA-HRA`) → "requires application,
  cannot auto-fetch" — never a silent failure.
- **Acceptance (Phase A):** on Harmony, the recognizer finds the paper's availability-statement
  accessions and labels each (repo + access + ingestable); the diagnostic shows data provenance
  instead of 8× mis-matched `run_failed`. Unit tests over real availability-statement strings (GEO /
  SRA / GSA / a controlled one).
- **DoD:** `extract/accessions.py` + tests green; wired into the diagnostic report.
- **Depends on:** Slice 0 (done). Feeds Slice 2. **Size:** ~1 session (Phase A).

## Decisions (for owner review)

**D1 — Gap-report schema.** *Recommend:* a thin `DiagnosticReport` projected from the existing
`DriveResult` — don't add a heavy model. Per panel: `{panel_key, figure, status, skill_id,
data_ref, goldens_expected, metrics_read, reason}`; rollup: the existing `summary` (status→count)
+ `auto_grade_rate`. Emit JSON + a markdown table. *Why:* `panel_drives` already carries almost
all of it; this is presentation, not new engine. *Reversible:* yes.

**D2 — "Auto-gradable enough" line.** *Recommend:* the phase target is to **raise the median
auto-grade rate across dogfooded papers**, not to hit 100% on any one. A hand ledger stays the
escape hatch for hard papers but is **never required to get an honest report**. A paper is
"blessable" (Slice 4) when it grades ≥1 panel cold with 0 Selom defects and the rest classify
honestly. *Why:* matches the floor's honest ceiling — recall is a curve, not a pass/fail.
*Reversible:* yes.

**D3 — Data matcher: auto vs ask.** *Recommend:* **auto-heuristic first** (`match_data` runs
unchanged), **ask only on `data_unmatched`** via the per-panel picker. Never block the report or
silently guess. *Why:* keeps the common case zero-click and the gap recoverable. *Reversible:* yes.

**D4 — Skill-gap signal home.** *Recommend:* a committed **`docs/skill-gaps.md`** (durable,
ranked, the Ratchet) + the per-run report for the immediate run. *Not* chat memory (too churny /
unbounded). *Why:* the backlog must outlive the session and rank across papers. *Reversible:* yes.

**D5 — Fixture mechanism + tolerance.** *Recommend:* snapshot the **graded output**
(status-shape + driven metric values) and re-drive to assert it reproduces within the **s46
metric-type tolerance**; two tiers (cheap classification-shape in CI, slow real-data re-drive
opt-in). *Why:* catches silent regressions without making CI re-run heavy science every push, and
reuses the tolerance grader so engine deltas don't flap. *Reversible:* yes.

**D6 — Accession fetch is gated.** *Original (s50):* ship Phase A (recognize + classify + link, no
network) freely; defer the fetch behind an explicit owner ask. **UPDATED (owner, s53):** don't build
the auto-fetch at all for now — ship a **manual handoff** instead (Phase B: per-accession link +
download instructions → the user downloads → drops the file into the per-panel picker). That is
deterministic, no-infra, and **un-gated**; the network/large-file/async **auto-fetch (Phase B2) goes
on hold** (`docs/on-hold/README.md`). *Why:* the picker (Slice 2) already accepts a per-panel file,
so the cheap manual loop closes `data_unmatched` end-to-end without paying the infra cost; revisit
auto-fetch only if the manual loop proves too slow. *Reversible:* yes.

*Assumption:* Harmony's supplement zips contain the tabular data the integration panels need; if
the deposited data is a processed embedding rather than raw counts, Slice 0 will report
`data_unmatched`/`needs_recipe` honestly and we pick a second calibration paper (Yoshimura) —
this does not block the diagnostic.

## Invariants

- **Honest classification holds (load-bearing).** No diagnostic or recall change may turn a
  paper/data gap into a Selom-confidence defect, invent a golden, or silently drop a panel. Check:
  `test_reproduction_drive_honest.py` stays green; the 4 hand ledgers grade byte-identically.
- **The floor never blocks on the new parts.** `reproduce()` works with no diagnostic, no picker,
  no skill-gap doc. The diagnostic is additive.
- **Determinism.** Same paper + same data + same engine → same gap report (no `Date.now`/random in
  the report; stamp times outside).

## Error Behavior

- Unreadable/exotic supplement → that panel is `data_unmatched` with an honest note; the run
  completes.
- Skill raises on matched data → `run_failed` with the exception text in the note; **never** an
  uncaught exception, **never** a defect.
- Zero in-scope panels with goldens → `auto_grade_rate` is reported as "n/a (no gradable panels)",
  not a divide-by-zero.

## Testing Strategy

- Slice 0: a unit test that feeds a constructed `DriveResult` (stub runner, no PDF) and asserts
  the `DiagnosticReport` projection (statuses, counts, `auto_grade_rate`). Plus the real Harmony
  run, recorded as a committed findings note (not a CI test — too heavy).
- Slice 1: a unit test per new reader over its real output shape; the 4 ledgers as the regression
  guard.
- Slice 2: a `data_map` round-trip BE test + FE browser-verify.
- Slice 3: an idempotency test on the `docs/skill-gaps.md` updater.
- Slice 4: the new auto-drive fixtures themselves, + a "break a reader → fixture goes red" check.

## Remaining phases (roadmap, re-cast as agile tasks)

Kept here so the *next* phases are focused, not ad-hoc. Parent: `docs/pillars/plan.md`.

| Task | Pillar | Goal | Acceptance |
|---|---|---|---|
| **Contract uniformity audit** | P4a | Every in-scope skill emits `{figure, table}` (via L3 where native absent); fill only the gaps the two products hit | A checked list of all in-scope skills with table-source (native / L3 / L4-only); no surprise tableless skill in a graded path |
| **Generic-extractor coverage** | P5b | (folds into Slice 1 above, then continues) more metrics readable without a hand ledger | auto-grade rate rises across ≥3 dogfooded papers |
| **Live-repro edge hardening** | P5d | `data_unmatched`/`needs_recipe` honesty under more real papers | each new dogfooded paper either grades or classifies honestly with 0 defects |
| **Pro/AI legend-polish tier** | P4c / wkspc §11 | an AI pass that polishes the deterministic methods/legend draft | opt-in; deterministic draft unchanged when AI off |
| **Own-data run → Library artifact** | Product A | a `POST /skills/{id}/run` result can be saved to the Workspace Library like a paper/gene-set | an own-data figure persists + reopens from `/library` |
| **Async `…/jobs` QC gate** | P1c | the async job path enforces the same is-my-data-clean guardrail as `/run` | a `block`-severity upload via `…/jobs` is blocked unless `override=true` |

## Out of Scope

- The **Pro/AI recipe-inference** tier (AI proposes a recipe → engine validates). The phase is the
  deterministic floor's *recall*, not the AI ceiling.
- Parameter-sweep expansion beyond what the floor already does.
- New analysis skills themselves (Slice 3 produces the *backlog*; building a skill is its own task).
- Any Redis/arq/Docker/WSL infra (ASK-gated, [[ask-before-docker-wsl]]).
- Product-A FE polish beyond the two follow-ups listed in the roadmap.

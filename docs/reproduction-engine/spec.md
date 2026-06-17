# Reproduction Engine — spec

> Selom's 4th pillar. Status: **APPROVED (owner, 2026-06-17) — R0+R1+R2+R3 + the Reproducibility Score SHIPPED; R4 substantially shipped** (X1 slice-1+2 incl. the vision layer with Claude-as-gateway, E7 two-input ingest, and X2 Track-B reconstruction+SSIM — see the sub-spec; X3/X4 + SSIM-band calibration pending; R5 FE view deferred per D12). 3 real ledgers span the score spectrum (RPGRIP1 63 / JEV 86 / Hani 96). R3 oracle+sweep verified live on real GSE293982/GSE293984 — revised against **two completed
> real dogfoods** (RPGRIP1 Fig 5 bulk on GSE293982 + Fig 6 scRNA on GSE293984, both 2026-06-17). The
> pillar process: research → interview → design → **saved spec** → plan → build (memory
> `selom-prism-pillar-phases`). Cross-lane (backend + frontend); Codex away, Claude covering both.
> Figure-extraction detail is split into `figure-extraction-subsystem.md`. The manual procedure this
> engine automates is `figure-repro-sop.md` (10 steps + 14 edge-case guards).

## What

A pipeline that takes **just a paper's PDF + Selom's skills + public raw data** (e.g. GEO) and
reproduces the paper's figures **and their underlying numbers**, recording every reproduced value
against the paper's printed "golden" value, and — crucially — **assigning blame when a number doesn't
match** (Selom-engine bug · engine substitution delta · upstream-step delta · paper-irreproducible ·
structural data limit · out-of-scope). It produces two grades of figure output — a **vector-faithful
copy** (pixel-identical, lifted from the PDF) and an **editable reconstruction** (Plotly,
SSIM-validated) — and emits, per paper, the skills it exercised plus the gaps (Skill Foundry backlog).
The backbone is a typed, per-paper **Reproduction Ledger** (JSON).

The engine is the **automation of the manual SOP** (`figure-repro-sop.md`). Every SOP step maps to an
engine stage; every SOP edge-case guard becomes a first-class check.

## Context

**Why it matters.** Reproducing a paper's figures + data exactly from only its PDF + our tool is the
differentiating capability (mission: memory `selom-figure-repro-mission`) and the dogfooding engine.
It is the concrete realization of the "Extract-Skills moat" in `docs/command-center/design.md`
§6.3/§6.5 and the roadmap's `v2 — LLM Foundry`. The two dogfoods proved the *value* is as much in the
**blame assignment** (the engine's verdict that the *paper itself* is irreproducible — RPGRIP1 78/181/49
— or that a gap is a *batch artifact*, not biology — Fig 6D) as in the pixel match.

**What exists today (reuse, don't duplicate):**
- `app/backend/papers.py` — durable PDF reader (pypdfium2 text+raster, pypdf metadata/embedded
  images; avoids AGPL `fitz`; `uv sync --extra pdf`). Anticipates `POST /papers/extract`.
- `app/backend/provenance.py` — per-figure reproducibility bundle → `ReproRun.provenance`.
- `app/backend/methods.py` — deterministic per-skill methods prose + citations (no LLM) → methods text.
- `app/backend/contract.py` — `run_skill_with_table(skill_id, path, params) → (figure, table)` (the
  Statistics-table path, S2.1); skills registry; routes `/skills`, `/skills/{id}/run|jobs`, `/jobs/...`;
  `jobs/queue.py` (heavy/async). Figure export + central theme (`skills/theme.py`).
- The editor's Plotly spec (layout/data split + JSON-Patch; memory `selom-figure-editor-architecture`)
  = the `figure_spec`.
- **R validation oracle** — R 4.6 + edgeR + fgsea installed locally (`selom-r-validation-oracle`),
  validation-only (ADR 0002). The blame-assignment instrument (see §Validation & Blame). NOT shipped.

**Prior art (research subagents) — reuse vs reverse-engineer:**
- **ClawBio** (MIT): `data-extractor` + `article-data-fetcher` — clean-room as blueprints, not drop-ins.
- **bioSkills** (MIT): deep DE/GSEA/single-cell method-correctness *reference text* → validation oracle
  + auto-methods grounding.
- **OmicVerse** (GPL-3.0 + PyTorch): broadest runnable algo lib → isolated GPL/PyTorch validation
  worker only (`ask-before-docker-wsl`); off the shipped permissive path.
- **Decisive gap:** no source has an end-to-end "PDF → reproduced figure + matched numbers + blame
  assignment" engine. That orchestration is **Selom's whitespace**.

## Requirements

1. **Ingest** a paper PDF → page text + rasterized figure pages + embedded vectors/bitmaps (`papers.py`);
   resolve GEO/accession from the Data-Availability text; download raw data.
2. **Extract** (Figure Extraction Subsystem, own sub-spec) → per figure: panels, chart form, **scope
   tag** (transcriptomic vs wet-lab), golden-target table, methods digest, + two figure grades.
3. **Map** each panel to a Selom skill + params (or flag a gap), **recording method substitutions**
   where the paper's R tool isn't shippable (D5).
4. **Anchor** — reproduce the deterministic ID-set parts first (gene-set universes, overlaps) and
   assert **exact** before any stochastic/threshold work (SOP rule 3).
5. **Prepare** — run the data guards that bound or invalidate a target *before* compute: species
   filter on combined-genome deposits (guard 13), filter-ceiling computation (guard 4), scRNA batch
   integration before any abundance claim (guards 10/11).
6. **Run** the mapped skill on the resolved dataset (sync, or jobs queue for heavy work) → editable
   `figure_spec` + `table` + `provenance` + computed values.
7. **Oracle** (dev/validation profile, gated) — recapitulate the authors' *actual* tool (edgeR /
   Seurat / fgsea) on the same data to measure Selom's delta and **disambiguate blame** (§below).
8. **Validate** computed vs golden per metric → `verdict` (`exact|close|fail`) + delta + **blame** +
   note; **run the guard registry**; structural impossibilities recorded as `fail`+reason, never passed.
9. **Sweep** — on a count miss, sweep contrast × stat(raw/adj) × threshold × direction × filter to find
   which setting reproduces the printed number (pins the authors' *undocumented* choice), or prove it
   irreproducible (SOP step 9 / guard 1).
10. **Report** — persist the typed Reproduction Ledger; emit a **scorecard** + a skill-coverage report
    (skills exercised + gaps → Skill Foundry backlog).
11. **Surface** ledger + scorecard + both figure grades to the frontend (read-only v1).

## Figure Extraction Subsystem

The world-class front-half (PDF → panel inventory + methods digest + golden-target table) **and** the
two reconstruction tracks (A = vector-faithful pixel-identical; B = editable Plotly, SSIM-scored) have
their **own sub-spec**: `figure-extraction-subsystem.md`. Summary of the honest ceiling (must always be
surfaced): vector panels → pixel-identical only via Track A; raster panels → never vector-faithful;
Track B → visually equivalent, SSIM-scored, never pixel-identical; dense scatter clouds → unrecoverable
as data for everyone (lift vectors or keep as image; do not trust LLM-fabricated coords).

## Design — the Reproduction Ledger + loop

### Data model (Pydantic; JSON per paper)
```
Paper      { id, slug, title, doi, pdf_path, geo[], methods_digest, inconsistencies[], created_at }
Panel      { paper_id, figure, panel, chart_form, scope: transcriptomic|wet_lab|data_not_deposited,
             data_source, skill_id, params, weight,
             method_subs[]: { paper_tool, selom_tool, reason, delta_measured? },
             sources[]: { ref, faithful, note },     # source provenance +/− (D14): "ST6+ Fig4e−"
             golden[]: { metric, value, unit, source: figure|legend|methods|extracted, confidence, note,
                         inconsistency_ref? },
             vector_copy_ref, status: pending|extracted|mapped|anchored|run|validated|blocked }
ReproRun   { id, panel_id, skill_id, params, dataset_ref, computed[]: {metric,value},
             figure_spec, table, provenance, methods_text, ssim, ts }
Oracle     { run_id, tool, version, computed[]: {metric,value}, agrees_with_selom?, agrees_with_paper?,
             note }                                            # dev/validation profile only
Sweep      { panel_id, axes[], grid[]: { setting, value }, reproducing_setting?, irreproducible: bool }
Validation { run_id, results[]: { metric, golden, computed, oracle?, delta, verdict, blame, note },
             panel_verdict, guards_fired[] }
PanelScore { panel_key, reproducibility: 0–100|null, selom_confidence: 0–100|null, tier, color,
             attribution: selom|engine|paper|data, provenance, in_scope, weight }   # D15
PaperScore { paper_id, reproducibility, selom_confidence, tier, color,
             n_scored, n_in_scope, n_out_of_scope, n_form_only, coverage }
Scorecard  { paper_id, totals_by_verdict, totals_by_blame, n_panels, n_in_scope,
             provenance_divergences[], panel_scores[]: PanelScore, score: PaperScore, generated_at }
```
**Reproducibility Score (D15)** — the graded 0–100 layer over verdict/blame/provenance, derived
by `score_panel(panel, validation, sweep)` + the weighted `score_paper` rollup (Selom-unique: no
tool grades *figure* reproducibility from raw data). **Two axes kept SEPARATE** so a
paper-irreproducible figure (a WIN to detect) never reads as a Selom failure: `reproducibility`
("can the figure be regenerated?", the heatmap headline) vs `selom_confidence` ("is Selom's
reconstruction trustworthy?"). Tiers (red→green): **Verified** 95–100 · **Reproduced** 80–94 ·
**Recoverable** 65–79 (engine-recovered setting / engine-delta) · **Deposit-faithful** 50–64
(reproduces the deposit, the figure diverges — JEV 4e) · **Irreproducible** 30–49 (paper-side or
structural) · **Discrepant** 1–29 (Selom defect) · **Out-of-scope** grey (excluded). Plus an
attribution chip (✓ Selom / ⚙ engine / 📄 paper / 🗄 data) + the provenance badge. Heart panels
outweigh form re-plots via `Panel.weight`. Backfilled fixtures: **JEV 86/100 (Reproduced, 100
confidence)**, **RPGRIP1 63/100 (Deposit-faithful, 92 confidence, 0 Selom defects)**.
`verdict`: **exact** (ints equal / floats within declared rel-tol) · **close** (right direction/
magnitude, within a stated band, delta recorded) · **fail** (outside band or structurally impossible).

### The loop (engine = automated SOP)
```
 1 ingest    papers.* + accession resolve           -> Paper + pages/ + raw data        [reuse]
 2 extract   Figure Extraction Subsystem            -> Panel[] (+golden, +scope, +subs)  [novel]
 3 map       chart_form+data_source -> skill+params  -> Panel.skill_id (+method_subs)     [glue]
 4 anchor    deterministic ID-sets, assert exact     -> anchored facts (universe=1,133)   [glue]
 5 prepare   species filter / ceiling / integrate    -> guarded dataset                   [glue+guards]
 6 run       run_skill_with_table(...)               -> ReproRun (+table,+provenance,+ssim)[reuse]
 7 oracle    authors' actual tool (R), measure delta -> Oracle (blame instrument)         [dev/gated]
 8 validate  computed vs golden + guards -> verdict  -> Validation (+blame)               [glue+guards]
 9 sweep     on count-miss, scan the setting grid    -> Sweep (reproducing setting | irrep)[glue]
10 report    aggregate -> Scorecard + Reproducibility Score + skills-report -> scorecard   [glue]
```
Steps 1, 6 reuse existing modules; 3, 4, 5, 8, 9, 10 are deterministic glue + guards; 2 is the
subsystem; 7 is the gated oracle.

### File layout (storage = typed JSON per paper)
```
app/backend/storage/repro/<paper-slug>/
  ledger.json   panels/<fig><panel>.svg   pages/*.png   runs/<id>.json
  oracles/<id>.json   sweeps/<panel>.json   skills-report.md
```
New `app/backend/reproduction.py` owns models + load/save + validation + blame + scorecard; **composes**
`papers.py`, `contract.run_skill_with_table`, `provenance.build`, `methods.build`, the extraction
subsystem (`extract/`), and the gated oracle runner.

### Endpoints (mirror `main.py` style)
`POST /papers/extract` (1–2) · `POST /papers/{slug}/panels/{fig}/{panel}/run` (4–6,8) ·
`POST /papers/{slug}/panels/{fig}/{panel}/sweep` (9) · `GET /papers/{slug}/ledger` ·
`GET /papers/{slug}/scorecard`. Oracle (7) is a **dev/validation CLI**, not a product endpoint (ADR
0002). Frontend v1: read-only Reproduction view (scorecard + panel table golden-vs-computed verdict +
**blame** chips + both figure grades via the editor).

## Validation & Blame Assignment (the R-oracle pattern)

The dogfoods proved that "computed ≠ golden" is **not** automatically "Selom is wrong." Every `fail`
(and every notable `close`) carries a `blame`, assigned by this decision procedure:

| `blame` | Meaning | How assigned | Dogfood example |
|---|---|---|---|
| `selom-engine` | Selom genuinely computed wrong — a real bug to fix | oracle **and** paper agree; Selom differs | (none surfaced — the engines validated) |
| `engine-delta` | Selom's substituted engine differs but isn't *wrong* (sensitivity/method) | oracle ≈ paper, **Selom differs from oracle**; delta measured | **6E counts**: gseapy 24/36/1 vs fgsea 62/95/85 ≈ paper 102/119/74 (RISKS #10) |
| `upstream-delta` | A difference in an upstream step propagates downstream | oracle **also** fails to reproduce with the right engine ⇒ not the final engine | **6E 52-shared core = 0 even with fgsea** ⇒ rod-subtype definition upstream |
| `paper-irreproducible` | The authors' own tool can't reproduce the printed number on the deposited data | **oracle misses the golden too** | **Fig 5 78/181/49**: edgeR itself only hits them at *unadjusted* thresholds, not the stated adj-p<0.05 |
| `structural-limit` | The deposited data cannot reach the number | ceiling/confound computed in `prepare` | **6D ≥2×-in-both**: 1-control deposit ⇒ batch≈genotype; **Fig 5** 882/1,133 survive CPM filter |
| `out-of-scope` | Not derivable from the sequencing data | scope-classify (guard 7) | 5D/5E/5F IHC/qPCR/PROTEOSTAT |

**The instrument is the R oracle** (step 7): it splits `engine-delta` from `upstream-delta` from
`paper-irreproducible`. It is **validation-only (ADR 0002), gated, never shipped**. In the product
profile where no oracle runs, blame is reported honestly as `delta-unmeasured (substitution X applied)`
rather than guessed — and as Selom's own Python engines close the gap to the oracle (e.g. an
fgsea-equivalent multilevel-GSEA path, RISKS #10), more blame becomes assignable in-product. This is
the "build now, gate/replace before launch" posture (memory `commercial-gated-tools-build-now-gate-later`).

**Method-substitution discipline (D5, hardened by the dogfoods):** when the paper's R tool isn't
shippable, map to the closest Python equivalent, **record the substitution on the panel**, and
**measure the delta against the oracle — never assume it.** The prior assumption "edgeR-LRT vs
pyDESeq2-Wald = big gap" was *wrong* (measured: near-exact); the assumption "fgsea≈gseapy" was *also
wrong* (measured: gseapy far more conservative). Measure, then record `close` with the real residual.

## Guards (edge-case registry) — first-class checks

The 14 SOP edge-case guards become explicit, named checks the engine runs (each annotated with the
loop stage that runs it and the `blame`/action it produces). A repro is **not allowed to report a
verdict until the applicable guards have run.** Full prose: `figure-repro-sop.md` §Edge cases.

| # | Guard | Stage | Produces |
|---|---|---|---|
| 1 | methods text ≠ reported numbers | 9 sweep | `Inconsistency` + sweep; never silently adopt the threshold that "works" |
| 2 | figures ≠ methods (same paper) | 2 extract | `Inconsistency`; figure number = panel target |
| 3 | authors' own tool can't reproduce either | 7 oracle | `blame: paper-irreproducible` (the headline finding) |
| 4 | filters cap the achievable count | 5 prepare | ceiling; if ceiling<golden → `blame: structural-limit` before chasing |
| 5 | mild contrasts clear few/zero significant terms | 8 validate | report NES asymmetry, don't read 0 as "no signal" |
| 6 | deposited data ≠ figure data | 1 ingest / 5 prepare | `blame: structural-limit`, never force a match |
| 7 | wet-lab panels out of scope | 2 extract (scope-classify) | `scope: wet_lab` → excluded from scorecard denominator |
| 8 | R→Python deltas usually small — measure, don't assume | 7 oracle | measured delta on the panel's `method_subs` |
| 9 | tooling gotchas (encoding / Rscript redirect / R not on PATH) | env | engine runs in the EDR-workaround + `PYTHONIOENCODING=utf-8` profile |
| 10 | batch ≈ genotype confound (composition/abundance killer) | 5 prepare | batch-purity check; if replication can't separate → `structural-limit` |
| 11 | naïve scRNA subclustering is batch-confounded | 5 prepare | Harmony integration + shared-subtype check before believing subtypes |
| 12 | GSEA-engine sensitivity is NOT interchangeable | 7 oracle | run fgsea on the same ranking → `engine-delta` vs `upstream-delta` |
| 13 | combined-genome deposits (GRCh38+mm10) | 5 prepare | species filter before gene-count QC; off-species fraction as QC metric |
| 14 | annotation-substitution gaps | 8 validate | report the cell-type **set** delta ({missing}↔{spurious}); set is the target, method differs |

## Decisions

- **D1 — Storage = typed JSON per paper** (owner). Reversible → SQLite on cross-paper query need.
- **D2 — `repro/` under `app/backend/storage/repro/`.** Reversible.
- **D3 — Two extraction tracks + human-confirm QA gate on low-confidence/vision-only goldens** (not
  manual transcription). Goldens come from the PDF. Reversible toward full automation.
- **D4 — Verdict tolerances declared per metric** (CONFIRMED owner 2026-06-17): **ints/IDs always
  strict-exact; floats default rel-tol 1%, per-metric override.** Honest given pyDESeq2 ≠ DESeq2
  bit-for-bit (RISKS #7) + the measured engine deltas; a metric may declare a tighter/looser tol. Reversible.
- **D5 — R-only methods → closest Python equivalent, substitution recorded, delta *measured* against
  the oracle (not assumed).** Deterministic parts (MSigDB-C5 RPGRIP1 universe = 1,133) stay **exact**.
  edgeR→pyDESeq2 (measured near-exact); Seurat-label-transfer→scanpy marker-scoring (report set delta,
  guard 14); fgsea→gseapy (measured **engine-delta**, RISKS #10); GLM-PCA→Harmony (guard 11). Reversible per skill.
- **D6 — Commercially-gated sources allowed in dev, tagged** `commercial_restriction`, gated before
  launch (memory `commercial-gated-tools-build-now-gate-later`). MSigDB C5 is the worked example.
- **D7 — Clean-room ClawBio `data-extractor`/`article-data-fetcher` (MIT) as blueprints**; build native
  to Selom's `input→plotly_spec` contract; do not vendor the unverified scaffold.
- **D8 — License posture:** shipped path = permissive only (Apache/MIT/BSD/MPL). AGPL/GPL tools
  (DocLayout-YOLO, PyMuPDF, poppler, WebPlotDigitizer, OmicVerse) are dev/validation-only, gated.
- **D9 — The oracle stage is pluggable and dev/validation-only (ADR 0002).** In dev it runs R
  (edgeR/fgsea/Seurat) to assign blame; the product profile reports `delta-unmeasured` honestly where
  no oracle is available, and grows in-product blame as Selom's Python engines reach oracle parity.
- **D10 — Blame is a first-class field** on every `Validation.result` (taxonomy above); the scorecard
  reports `totals_by_blame`, not just `totals_by_verdict`. **Scorecard framing = FINDINGS-FIRST
  (CONFIRMED owner 2026-06-17):** the headline is *"what the engine found"* — the `paper-irreproducible`
  + `structural-limit` tallies elevated as **discoveries** — with exact/close/fail as the secondary
  breakdown. These are the mission's differentiating outputs, not failures of Selom.
- **D11 — The guard registry is mandatory.** A panel verdict is invalid until its applicable guards
  (table above) have run; `guards_fired[]` is recorded on the `Validation`.
- **D12 — v1 audience = INTERNAL dogfood/validation tool first (CONFIRMED owner 2026-06-17).** You run
  the engine on papers to validate Selom + surface findings; the R-oracle is therefore **always
  available**, so blame is always fully assignable (no `delta-unmeasured` degradation in v1). The
  frontend Reproduction view (R5) is **deferred** until the headless engine proves out. Matches the
  staged mission (personal tool → engine → SaaS). Reversible toward customer-facing as the Python
  engines reach oracle parity.
- **D13 — Reproduction Engine is a sibling pillar that *feeds* the Skill Foundry (CONFIRMED owner
  2026-06-17)** — it reproduces + reports skill gaps as a backlog the Foundry consumes; it is **not** a
  sub-phase of the Foundry.
- **D14 — Source-provenance (+/−) tagging over accusation (CONFIRMED owner 2026-06-17).** When a
  reconstructed panel faithfully matches its deposited source but diverges from the published figure
  (commonly a different biological/experimental replicate), reproduce the DEPOSIT faithfully (the win)
  and record the figure divergence as neutral provenance (`SourceTag`, e.g. `ST6+ Fig4e−`) +
  `Scorecard.provenance_divergences` — **never a paper-error blame**. JEV Fig 4e is the worked example.
- **D15 — Reproducibility Score = the graded 0–100 headline (owner-agreed 2026-06-17).** A
  Selom-unique score per panel→figure→paper over the existing verdict/blame/provenance (`score_panel`
  + weighted `score_paper`). **Two axes kept SEPARATE** (the design's load-bearing rule):
  `reproducibility` (paper+data property — the heatmap) vs `selom_confidence` (our-tool property), so a
  paper-irreproducible figure scores LOW reproducibility but HIGH confidence — a discovery, never a
  Selom failure. Named tiers + colors + an attribution chip (✓/⚙/📄/🗄) + the provenance badge; heart
  panels outweigh form re-plots via `Panel.weight`. Natural headline for the deferred FE view (R5).

## Invariants

- A `golden` value originates only from the PDF (figure/legend/methods/extracted) + its `source` +
  `confidence`; no external result table is silently substituted.
- Every `ReproRun` has `provenance` + `methods_text`; `figure_spec` stays pure `{data, layout}` (theme
  central); `table` is the Statistics-table (S2.1), separate from the figure.
- Every `fail` (and notable `close`) carries a `blame`; a structural impossibility is `fail`+reason,
  never `exact`/`close`. A method substitution carries a *measured* delta or an explicit
  `delta-unmeasured` flag — never an assumed one.
- Track B output is never labelled pixel-identical; Track A is the only "pixel-faithful" claim, vector
  panels only. The R oracle never appears on the shipped path.
- Ledger is source of truth; scorecard (incl. `totals_by_blame`, `panel_scores`, the Reproducibility
  `score`) is derived. The score never invents signal — it is a pure function of verdict/blame/
  provenance/sweep, so a low reproducibility with high `selom_confidence` is a discovery, not a defect.

## Error Behavior
- Missing `--extra pdf` deps → `papers.py`'s actionable message. Unmappable panel → `status: blocked` +
  Skill Foundry gap (not an error). Skill run failure → no `ReproRun`, panel stays `mapped`, error in
  `skills-report.md`. Heavy runs (e.g. Cepo+GSEA over 37k cells) → jobs queue; ledger references the job.
  Oracle unavailable (no R) → blame degrades to `delta-unmeasured`, not a crash. Vision-LLM/extractor
  low confidence → human-confirm QA gate (D3).

## Testing Strategy
- Unit: ledger round-trip; verdict logic + tolerances; **blame decision procedure** (synthetic
  oracle/paper/Selom triples → correct blame); scorecard `totals_by_blame` math; guard registry (each
  guard fires on its trigger fixture); vector-XObject lift on a fixture PDF.
- Composition: fake skill + fixture Panel (golden values) + fixture Oracle → run → validate → blame →
  scorecard (no network/heavy deps).
- Extraction: synthetic scanpy/matplotlib panels with known ground truth → recovered values + SSIM band.
- Integration (RPGRIP1, slow/manual): universe 1,133 asserts **exact**; Fig 5 78/181/49 assert
  `blame: paper-irreproducible` (oracle misses too); 6D ≥2×-in-both asserts `blame: structural-limit`;
  6E counts assert `engine-delta`, 52-core asserts `upstream-delta`; 5D/5E/5F assert `out-of-scope`.
- Guard: `figure_spec` stays pure `{data, layout}` (mirrors existing skill tests).

## Build plan (phased) — present scope before coding

The engine automates the SOP loop. Build in dependency order; each phase is independently shippable and
testable, and **deterministic glue + guards come before the novel extraction subsystem** (which has its
own X1–X4 phasing in the sub-spec). **Spec approved 2026-06-17; R0+R1+R2+R3 shipped.** v1 is the internal
dogfood tool (D12), so **R5 (frontend) is deferred** and R3's oracle is always available.

| Phase | Scope | Reuses | New | Verifies on |
|---|---|---|---|---|
| **R0 — Ledger + verdict + blame core** | `reproduction.py`: Pydantic models, JSON load/save, verdict logic + tolerances (D4), **blame decision procedure** (D10), scorecard incl. `totals_by_blame`. No extraction, no live skills. | provenance/methods shapes | models, validate, blame, scorecard | unit + composition (fake skill + fixture oracle) |
| **R1 — Guard registry** | The 14 guards (table above) as named, testable checks wired into stages 5/8/9; `guards_fired[]` + `Inconsistency` capture. | — | `extract/guards.py` (or `reproduction/guards.py`) | each guard's trigger fixture |
| **R2 — Run + validate, real skills** | Stages 4–6,8: anchor (deterministic ID-sets) → prepare (guards) → `run_skill_with_table` → validate+blame, end-to-end on a **mapped** panel. | `contract.run_skill_with_table`, jobs queue | map glue, anchor, prepare | RPGRIP1 Fig 5 panels (skills already exist) |
| **R3 — Oracle + sweep (dev profile)** ✅ SHIPPED | Stage 7 oracle runner (R edgeR/fgsea, gated `SELOM_ORACLE`, ADR 0002) + stage 9 sweep; `oracle_agreement` + `revalidate_panel` wire blame disambiguation (`engine-delta`/`upstream-delta`/`paper-irreproducible`). Running gated+isolated, parsing+verdict pure (fast suite has no R). | R oracle (`selom-r-validation-oracle`) | `oracle.py` (+`oracle_templates/*.R`, dev CLI), `sweep.py`, typed `Sweep` model | **VERIFIED LIVE:** edgeR on real GSE293982 → 19/125/13 (golden 181/78/49) ⇒ paper-irreproducible; fgsea on real Rod1/2/3 rankings → 62/95/85 + 52-core 0 ⇒ engine/upstream split |
| **R4 — Extraction subsystem X1** | Target-extraction MVP (sub-spec X1): ingest → classify → golden-target table + methods digest + inconsistencies. Replaces SOP steps 1–4. | `papers.py`, AI gateway | `extract/` (ingest/detect/classify/golden) | RPGRIP1 PDFs → golden table matches the hand-written spec |
| **R5 — Frontend read-only view + reconstruction** _(DEFERRED — internal-first, D12)_ | Read-only Reproduction view (scorecard + panel table + verdict/blame chips + figure grades); extraction X2 (Track B + SSIM), then X3 (Track A). | editor, theme | FE Reproduction route; `reconstruct.py` | browser-verify on the RPGRIP1 ledger |

**First buildable slice = R0 + R1 + R2** (the deterministic engine over existing skills, validated on
Fig 5 where the skills already exist) — this turns the manual loop into a repeatable pipeline without
needing the novel extraction subsystem yet. R3 adds the blame instrument; R4 removes the manual
front-half; R5 is the product surface.

## Out of Scope
- Auto-generating a *new* Selom skill from a paper (Skill Foundry §6.3; this pillar *reports gaps*).
- Multi-paper cross-query analytics (await SQLite). Fine-tuning extractor models on scverse panels (later).
- Shipping the R oracle (validation-only, ADR 0002) or any AGPL/GPL tool on the product path (D8/D9).
- The figure-extraction subsystem's detailed sub-spec lives in `figure-extraction-subsystem.md` (split out).
- A *third* RPGRIP1 reproduction; Fig 5 + Fig 6 are done (this engine's first two dogfoods) and are the
  integration-test fixtures, not new work.

## Resolved (owner, 2026-06-17)
1. **First buildable slice = R0+R1+R2** ✓ (deterministic engine over existing skills, on Fig 5, before
   the extraction subsystem).
2. **Oracle (R3) = dev-only CLI** ✓ (ADR 0002). The blame taxonomy ships regardless; only the
   *instrument* is gated. (Internal-first v1 → the oracle is always available, D12.)
3. **Reproduction Engine = sibling pillar that feeds the Skill Foundry** ✓ (D13).
4. **Scorecard = findings-first** ✓ — `totals_by_blame` (paper-irreproducible / structural-limit) is the
   headline "what the engine found," exact/close/fail secondary (D10).
5. **v1 audience = internal dogfood/validation tool first** ✓ — frontend Reproduction view (R5)
   **deferred** until the headless engine proves out (D12).

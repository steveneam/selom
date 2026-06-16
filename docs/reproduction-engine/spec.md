# Reproduction Engine — spec

> Selom's 4th pillar. Status: **spec, pending owner approval** (pillar process:
> research → interview → design → **saved spec** → plan → build; memory `selom-prism-pillar-phases`).
> Cross-lane (backend + frontend); Codex away, Claude covering both. Research phase used two
> subagents (prior-art in ClawBio/bioSkills/OmicVerse/Hermes; figure-extraction SOTA) — findings folded in.

## What

A pipeline that takes **just a paper's PDF + Selom's skills + public raw data** (e.g. GEO) and
reproduces the paper's figures **and their underlying numbers**, recording every reproduced value
against the paper's printed "golden" value so the match is auditable. It produces two grades of
figure output — a **vector-faithful copy** (pixel-identical, lifted from the PDF) and an **editable
reconstruction** (Plotly, SSIM-validated) — and emits, per paper, the skills it exercised plus the
gaps (Skill Foundry backlog). The backbone is a typed, per-paper **Reproduction Ledger** (JSON).

## Context

**Why it matters.** Reproducing a paper's figures + data exactly from only its PDF + our tool is the
differentiating capability (mission: memory `selom-figure-repro-mission`) and the dogfooding engine.
It is the concrete realization of the "Extract-Skills moat" in `docs/command-center/design.md`
§6.3/§6.5 and the roadmap's `v2 — LLM Foundry`.

**What exists today (reuse, don't duplicate):**
- `app/backend/papers.py` — durable PDF reader (pypdfium2 text+raster, pypdf metadata/embedded
  images; avoids AGPL `fitz`; `uv sync --extra pdf`). Already the "extract skills from papers" step;
  anticipates `POST /papers/extract`. **Replaces the throwaway `D:/tmp-thl` `fitz` scratch.**
- `app/backend/provenance.py` — per-figure reproducibility bundle (skill+version, resolved params,
  input SHA-256, stack versions) → `ReproRun.provenance`.
- `app/backend/methods.py` — deterministic per-skill methods prose + citations (no LLM) → methods text.
- Skills registry + `contract.py`; routes `/skills`, `/skills/{id}/run`, `/skills/{id}/jobs`,
  `/jobs/...`; `jobs/queue.py` (heavy/async). Figure export + central theme (`skills/theme.py`).
- The editor's Plotly spec (layout/data split + JSON-Patch; memory `selom-figure-editor-architecture`)
  = the `figure_spec`. Implied `figures` table in design.md.

**Prior art (research subagents) — reuse vs reverse-engineer:**
- **ClawBio** (local `…\Temp\ClawBio\`, **MIT**): `data-extractor` (figure-image → numbers via panel-
  detect + OpenCV axis-calibration + Claude-vision + validation, 26+ plot types) and
  `article-data-fetcher` (DOI/PMID → GEO/Zenodo/ENA accession resolve + download + checksums). Both
  `planned`/scaffold (mature spec, unverified code) → **clean-room as blueprints**, not drop-ins.
- **bioSkills** (local `…\Temp\bioSkills\`, **MIT**): deepest DE/GSEA/single-cell method-correctness
  *reference text* (not runnable) → **validation oracle + auto-methods grounding**.
- **OmicVerse** (not local; **GPL-3.0 + PyTorch**): broadest runnable algo lib + an
  `omicverse-reproducibility` notebook repo → **isolated GPL/PyTorch validation worker only**
  (memory `ask-before-docker-wsl`); off the shipped permissive path.
- **Decisive gap:** no source has an end-to-end "PDF → reproduced figure + matched numbers" engine.
  That orchestration is **Selom's whitespace**.

**The gap this pillar fills:** there is no structure tying *paper → panel → golden target → reproduced
value → verdict*, no world-class figure-extraction subsystem, and no orchestration of the loop.

**Proving ground (running example):** RPGRIP1 (Loi et al. 2025, *Stem Cell Reports*). Golden targets in
`D:/tmp-thl/rpgrip1_target_spec.md` — e.g. 6E Venn = Rod-1 27 / Rod-2 52 / Rod-3 10 / all-three 52
(+13/10/2) at adj-p<0.05; 9 cell types; signature 78 (results) vs 181 (methods inconsistency); RHO −71%/−34%.

## Requirements

1. **Ingest** a paper PDF → page text (markers) + rasterized figure pages + embedded figure
   vectors/bitmaps, via `papers.py`.
2. **Figure Extraction Subsystem** (see its own section): per figure → split panels → classify each →
   extract its golden values + structure, and produce both a vector-faithful copy and an editable spec.
3. **Map** each panel to a Selom skill + params (or flag a skill gap).
4. **Run** the mapped skill on the resolved dataset (sync, or async jobs queue for heavy work) →
   editable `figure_spec` + `provenance` + computed values.
5. **Validate** computed vs golden per metric → `verdict` (`exact|close|fail`) + delta + note;
   structural impossibilities recorded as `fail` with reason, never silently passed.
6. **Persist** as a typed Reproduction Ledger (JSON per paper, version-controlled); emit a **scorecard**.
7. **Emit** per paper a skill-coverage report (skills exercised + gaps → Skill Foundry backlog).
8. **Surface** ledger + scorecard + both figure grades to the frontend (read-only v1).

## Figure Extraction Subsystem (the pixel/bit-identical engine)

The world-class piece. **Two parallel tracks** with different guarantees — never conflate them:

- **Track A — Vector-faithful copy (pixel-identical).** Lift the panel's embedded vector content
  (Form XObject / content-stream region) from the PDF and re-emit it (SVG / Plotly shapes),
  *copying* the original draw operators. The only path to true pixel identity. Works for vector
  panels (Cell/Elsevier mandate vector); **impossible** for raster panels (microscopy, scatter-as-PNG).
- **Track B — Editable reconstruction (data-faithful).** Recover the numbers → redraw an editable,
  themed Plotly spec; **validate by SSIM/structural diff** against the original raster and attach a
  confidence score. Visually equivalent, **explicitly not pixel-equal**. The product target.

**Stage pipeline** (`figure-detect → panel-segment → chart-classify → data/value-extract → reconstruct+validate`):

| Stage | Approach | Reuse (license-clean) | Dev-only (gated) | Build |
|---|---|---|---|---|
| figure-detect | figure box + caption bind | PDFFigures2 (Apache) / layout-parser (Apache) | DocLayout-YOLO (AGPL) | — |
| panel-segment | split A/B/C… | — | SimCFS (research) | **vector-gutter + panel-label anchor** (highest-leverage build) |
| chart-classify | type per panel | — | — | **Vision LLM (Claude)** structured JSON |
| value/label extract | exact text, semantics | **PDF text layer (pypdfium2/pypdf) — EXACT chars+coords**; PaddleOCR/docTR (Apache) fallback | — | **per-type semantic readers** (Venn→count, dotplot→{term,gene,p}, stacked-bar→%) via text-layer + vision LLM |
| chart→data (bar/line) | recover series | DePlot/MatCha (Apache), UniChart (MIT), LineFormer (MIT, multi-line) | — | type-routing dispatcher |
| reconstruct A | vector copy | pikepdf/qpdf (MPL/Apache) XObject lift; svgpathtools (MIT) | PyMuPDF (AGPL), poppler pdftocairo (GPL, external binary) | **XObject lifter + re-emitter** |
| reconstruct B | editable redraw | Plotly + `skills/theme.py`; skimage SSIM (BSD) | — | **reconstruction validator (SSIM+confidence)** |

**Where the vision LLM (Claude) wins:** chart-type classification (incl. split-violin/dotplot/Venn),
reading + *semantically associating* labels (legend↔color, Venn-region↔count, dotplot-cell↔{term,gene,p}),
low-cardinality value extraction (stacked-bar %, Venn counts, dot-plot rows), and self-QA of the redraw.
**Where it loses (use PDF-native/specialized):** exact tick/value readout (use the text layer — no
hallucination), dense scatter coordinates (UMAP/tSNE — **not data-recoverable by anyone**; lift vectors
or keep as image), pixel geometry (Track A's job), many-series lines (LineFormer).

**Honest ceiling (must be surfaced, never overclaimed):**
1. Vector panels → pixel-identical *only* via Track A (embedded-vector lift).
2. Raster panels → never vector-faithful; best is image-identical crop re-placement.
3. Editable redraw (Track B) → visually equivalent, SSIM-scored, **never** labelled pixel-identical.
4. Dense scatter point clouds → unrecoverable as data for everyone; do not trust LLM-fabricated coords.

This subsystem is large enough to get its own implementation sub-spec
(`docs/reproduction-engine/figure-extraction-subsystem.md`) when this pillar spec is approved.

## Design — the Reproduction Ledger + loop

### Data model (Pydantic; JSON per paper)
```
Paper      { id, slug, title, doi, pdf_path, geo[], methods_digest, created_at }
Panel      { paper_id, figure, panel, chart_form, data_source, skill_id, params,
             golden[]: { metric, value, unit, source: figure|legend|methods|extracted, confidence, note },
             vector_copy_ref, status: pending|extracted|mapped|run|validated|blocked }
ReproRun   { id, panel_id, skill_id, params, dataset_ref, computed[]: {metric,value},
             figure_spec, provenance, methods_text, ssim, ts }
Validation { run_id, results[]: { metric, golden, computed, delta, verdict, note }, panel_verdict }
Scorecard  { paper_id, totals_by_verdict, n_panels, generated_at }
```
`verdict`: **exact** (ints equal / floats within declared rel-tol), **close** (right direction, within a
stated band, delta recorded), **fail** (outside band or structurally impossible, with reason).

### File layout (storage = typed JSON per paper — owner decision)
```
app/backend/storage/repro/<paper-slug>/
  ledger.json   panels/<fig><panel>.svg(vector copy)   pages/*.png   runs/<id>.json   skills-report.md
```
New `app/backend/reproduction.py` owns models + load/save + validation + scorecard; **composes**
`papers.py`, `contract.run_skill_with_table`, `provenance.build`, `methods.build`, and the extraction
subsystem. The new figure-extraction code lives under `app/backend/extract/` (its own sub-spec).

### The loop
```
1 ingest    papers.*                                  -> Paper + pages/
2 extract   Figure Extraction Subsystem               -> Panel[] (+golden, +vector_copy_ref)   [novel]
3 map       chart_form+data_source → skill+params/gap -> Panel.skill_id
4 run       run_skill_with_table(...)                 -> ReproRun (+provenance,+methods,+ssim)
5 validate  computed vs golden → verdict+delta        -> Validation
6 report    aggregate → Scorecard + skills-report.md  -> scorecard, backlog
```
Steps 1,4 reuse existing modules; 3,5,6 are deterministic glue; 2 is the subsystem above.

### Endpoints (mirror `main.py` style)
`POST /papers/extract` (1–2) · `POST /papers/{slug}/panels/{fig}/{panel}/run` (4–5) ·
`GET /papers/{slug}/ledger` · `GET /papers/{slug}/scorecard`. Frontend v1: read-only Reproduction view
(scorecard + panel table golden-vs-computed verdict chips + both figure grades via the editor).

## Decisions

- **D1 — Storage = typed JSON per paper** (owner). Reversible → SQLite on cross-paper query need.
- **D2 — `repro/` under `app/backend/storage/repro/`.** Reversible.
- **D3 — Two extraction tracks (Track A vector-faithful + Track B editable), not human-entry.** Golden
  values come from the PDF (text-layer exact where possible, vision-LLM semantics elsewhere), with a
  **human-confirm QA gate** on low-confidence/vision-only values — not manual transcription. Supersedes
  the earlier "human-confirms v1". Reversible toward full automation as confidence rises.
- **D4 — Verdict tolerances declared per metric** (ints exact; floats rel-tol 1% default). Reversible.
- **D5 — R-only methods get closest Python equivalent in a Selom skill**, residual recorded as `close`,
  deterministic parts (e.g. MSigDB-C5 RPGRIP1 universe = 1,133 genes) **exact**. edgeR→pydeseq2/limma-ish;
  Seurat-label-transfer→scanpy/CellTypist; fgsea→gseapy; GLM-PCA→glmpca-py. Reversible per skill.
- **D6 — Commercially-gated sources allowed in dev, tagged** `commercial_restriction`, surfaced via
  `GET /skills`, gate before launch (memory `commercial-gated-tools-build-now-gate-later`).
- **D7 — Clean-room ClawBio `data-extractor`/`article-data-fetcher` (MIT) as design blueprints**, build
  native to Selom's `input→plotly_spec` contract; do not vendor the unverified scaffold code.
- **D8 — License posture:** shipped path = permissive only (Apache/MIT/BSD/MPL). AGPL/GPL tools
  (DocLayout-YOLO, PyMuPDF, poppler, WebPlotDigitizer, OmicVerse) are **dev/validation-only**, gated.

## Invariants
- A `golden` value originates only from the PDF (figure/legend/methods/extracted) + its `source`+`confidence`;
  no external result table is silently substituted.
- Every `ReproRun` has `provenance` + `methods_text`; `figure_spec` stays pure `{data, layout}` (theme central).
- Track B output is never labelled pixel-identical; it carries an SSIM/confidence score. Track A is the
  only "pixel-faithful" claim, and only for embedded-vector panels.
- A structurally impossible match is `fail`+reason, never `exact`/`close`. Ledger is source of truth; scorecard derived.

## Error Behavior
- Missing `--extra pdf` deps → `papers.py`'s actionable message. Unmappable panel → `status: blocked` +
  Skill Foundry gap (not an error). Skill run failure → no `ReproRun`, panel stays `mapped`, error in
  `skills-report.md`. Heavy runs (e.g. 83k-cell Cepo+GSEA) → jobs queue; ledger references the job.
  Vision-LLM/extractor low confidence → routed to the human-confirm QA gate (D3).

## Testing Strategy
- Unit: ledger round-trip; verdict logic + tolerances; scorecard math; vector-XObject lift on a fixture PDF.
- Composition: fake skill + fixture Panel (golden values) → run → validate → scorecard (no network/heavy deps).
- Extraction: synthetic scanpy/matplotlib panels with known ground truth → assert recovered values + SSIM band.
- Integration (RPGRIP1, slow/manual): 1,133-gene universe asserts **exact**; 6E Venn / 6C proportions assert
  recorded verdicts; structural-limit panels assert `fail`+reason.
- Guard: `figure_spec` stays pure `{data, layout}` (mirrors existing skill tests).

## Out of Scope
- Auto-generating a *new* Selom skill from a paper (that's the Skill Foundry §6.3; this pillar *reports gaps*).
- Multi-paper cross-query analytics (await SQLite). Fine-tuning extractor models on scverse panels (later, D8-clean).
- The full RPGRIP1 Fig 5/6 reproduction itself (separate execution task; this engine's first dogfood).
- The figure-extraction subsystem's own detailed implementation spec (separate doc once approved).

## Open questions for review
1. **Extraction ambition for v1** — full two-track subsystem, or ship Track B (editable + SSIM) first and
   add Track A (vector-faithful lift) second? Recommend **Track B first, Track A fast-follow** (Track A is
   the differentiator but Track B unblocks validation + the product loop).
2. **Where `repro/` lives** — `app/backend/storage/repro/` (D2) vs top-level. Recommend D2.
3. **Frontend in v1** — read-only Reproduction view, or backend ledger + CLI scorecard only first? Recommend thin read-only view.
4. **Reproduction Engine vs Skill Foundry** — sibling pillar that *feeds* the Foundry (recommend) vs sub-phase of it.
5. **Split the figure-extraction subsystem into its own sub-spec now** (recommend yes, on approval).

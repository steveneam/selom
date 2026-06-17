# Figure Extraction Subsystem — sub-spec

> Sub-spec of the **Reproduction Engine** pillar (`spec.md`). Status: **X1 (slice-1+2 + E7), X2,
> and X3 SHIPPED 2026-06-18** (`app/backend/extract/`); X4 pending. Split out from `spec.md` 2026-06-17 per the
> owner steer. Cross-lane (backend-led extraction + thin frontend surfacing). Grounded in two
> completed real dogfoods — RPGRIP1 Fig 5 (bulk, GSE293982) + Fig 6 (scRNA, GSE293984) — whose
> front-half (PDF → panel inventory → methods digest → golden-target table) was run **by hand** and
> is the thing this subsystem automates. The manual procedure is `figure-repro-sop.md` steps 1–4.

## What

Turn **just a paper's PDF** into the four structured artifacts the rest of the engine consumes:

1. **Panel inventory** — every figure split into labelled panels (`Fig 6E`…), each classified by
   chart form (Venn / dotplot / PCA / heatmap / stacked-bar / violin / UMAP / IHC / qPCR …) and
   tagged in-scope (transcriptomic, reproducible) vs out-of-scope (wet-lab: IHC / qPCR / staining-dye).
2. **Methods digest** — the STAR-Methods paragraph per panel, parsed to the tool + thresholds +
   contrasts + filters + normalization that define how the number was produced (`edgeR`, `TMM`,
   `CPM<2 in smallest group`, `glmLRT`, `BH adj-p<0.05`, `fgsea`, `Seurat label-transfer`, …).
3. **Golden-target table** — every printed number (counts, %, Venn cells, gene-set sizes, fold
   changes, thresholds) with its `source` (figure | legend | methods | extracted) + `confidence`,
   and **flagged inconsistencies** where the paper does not self-reconcile.
4. **Two figure grades** — a **vector-faithful copy** (Track A) and an **editable reconstruction**
   (Track B). These are the *output* figures; the first three artifacts are the *inputs to validation*.

The first three are the high-value, novel front-half (no prior-art tool produces a typed golden-target
table). The two figure grades are the visible product surface.

## Two jobs — never conflate

| Job | Output | Guarantee | Drives |
|---|---|---|---|
| **Target extraction** | panel inventory + methods digest + golden-target table | structured, source-tagged, confidence-scored | the **validate** stage (golden side) |
| **Figure reconstruction** | Track A vector copy · Track B editable Plotly | A = pixel-identical (vector panels only) · B = SSIM-scored, never pixel-equal | the **product** surface + Track-B self-QA |

Target extraction is what makes the numbers matchable. Figure reconstruction is what the user sees.
The mission ("reproduce figures **and** numbers exactly") needs both, but target extraction is the
part that has no off-the-shelf equivalent.

## Stage pipeline

`ingest → figure-detect → panel-segment → chart-classify → scope-classify → value/golden-extract → methods-digest → reconstruct(A|B)+validate`

| Stage | Approach | Reuse (license-clean, shipped) | Dev-only (gated) | Build |
|---|---|---|---|---|
| ingest | PDF → page text (exact chars+coords) + page rasters + embedded vectors/bitmaps | **`app/backend/papers.py`** (pypdfium2 text+raster, pypdf metadata/images; BSD; `--extra pdf`) | — | reuse (anticipates `POST /papers/extract`) |
| figure-detect | figure box + caption bind | PDFFigures2 (Apache) / layout-parser (Apache) | DocLayout-YOLO (AGPL) | — |
| panel-segment | split A/B/C… | — | SimCFS (research) | **vector-gutter + panel-label anchor** (highest-leverage build) |
| chart-classify | type per panel | — | — | **Vision LLM (Claude)** → structured JSON |
| scope-classify | transcriptomic vs wet-lab | — | — | **rule + vision** (IHC/qPCR/dye → out-of-scope) — guard 7 |
| value/golden-extract | exact text + semantics | **PDF text layer (pypdfium2/pypdf) — EXACT chars+coords**; PaddleOCR/docTR (Apache) fallback | — | **per-type semantic readers** (Venn→count, dotplot→{term,gene,p}, stacked-bar→%) via text-layer + vision LLM |
| methods-digest | tool/threshold/contrast/filter | PDF text layer + a tool/threshold lexicon | — | **grep-then-vision** extractor → typed `methods_digest` |
| chart→data (bar/line) | recover series | DePlot/MatCha (Apache), UniChart (MIT), LineFormer (MIT) | — | type-routing dispatcher |
| reconstruct A | vector copy | pikepdf/qpdf (MPL/Apache) XObject lift; svgpathtools (MIT) | PyMuPDF (AGPL), poppler pdftocairo (GPL, external binary) | **XObject lifter + re-emitter** |
| reconstruct B | editable redraw | Plotly + `skills/theme.py`; skimage SSIM (BSD) | — | **reconstruction validator (SSIM + confidence)** |

## Where the vision LLM (Claude) wins / loses

- **Wins:** chart-type classification (incl. split-violin / dotplot / Venn), reading + *semantically
  associating* labels (legend↔colour, Venn-region↔count, dotplot-cell↔{term,gene,p}), low-cardinality
  value extraction (stacked-bar %, Venn counts, dot-plot rows), scope classification, and **self-QA of
  the Track-B redraw**.
- **Loses (use PDF-native / specialized, never the LLM):** exact tick/value readout (use the text
  layer — no hallucination), **dense scatter coordinates** (UMAP/tSNE — not data-recoverable by anyone;
  lift vectors or keep as image), pixel geometry (Track A's job), many-series lines (LineFormer).

## Honest ceiling (surface, never overclaim)

1. Vector panels → pixel-identical **only** via Track A (embedded-vector lift).
2. Raster panels (microscopy, scatter-as-PNG) → never vector-faithful; best is image-identical crop re-placement.
3. Editable redraw (Track B) → visually equivalent, SSIM-scored, **never** labelled pixel-identical.
4. Dense scatter point clouds → unrecoverable as data for everyone; do **not** trust LLM-fabricated coords.

## Key artifact — the golden-target table (typed)

The structured form of `<slug>_target_spec.md` (today hand-written). One row per printed value:

```
GoldenTarget {
  paper_id, figure, panel,
  metric,            # "venn.unique.Rod-2", "proportion.Rod-2.MS-VUS", "signature.count", "RHO.delta_pct"
  value, unit,
  source: figure | legend | methods | extracted,
  confidence: 0..1,  # 1.0 for text-layer-exact ints; lower for vision-only reads
  note,              # context / how read
  inconsistency_ref  # → an Inconsistency when the paper disagrees with itself
}
Inconsistency {
  paper_id, kind: methods_vs_numbers | figures_vs_methods | deposit_vs_figure,
  printed_in[], conflicting_value[], note
}
```

Two inconsistency kinds are mandatory captures (both seen in RPGRIP1):
- **methods ≠ numbers** — the printed count isn't reproducible at the methods-stated threshold
  (Fig 5: methods say adj-p<0.05 → 19, but 78/181/49 only appear at *unadjusted* cuts). Guard 1.
- **figures ≠ methods** — same paper prints two values (Fig 5 signature = 78 in results, 181 in
  methods). Capture **both**; the figure number is the panel target. Guard 2.

A golden value originates **only** from the PDF — never silently substituted from an external result
table (invariant inherited from `spec.md`).

## Scope classification (guard 7)

Classify each panel **early** as transcriptomic (reproducible from the sequencing data) vs wet-lab
(IHC / RT-qPCR / staining-dye / microscopy = structurally out-of-scope). Out-of-scope panels are
recorded `out-of-scope`, **excluded from the scorecard denominator**, and never chased. RPGRIP1
5D/5E/5F (PRPH2 IHC / RT-qPCR / PROTEOSTAT) are the worked example.

## Decisions

- **E1 — Ingest = `papers.py` (PDFium/pypdf, BSD).** Never poppler (GPL external binary) or
  PyMuPDF/`fitz` (AGPL) on the shipped path; both are dev-only if ever needed. Replaces the throwaway
  `D:/tmp-thl` `fitz` scratch.
- **E2 — Text-layer-exact before vision.** Numbers that exist as selectable PDF text are read from the
  text layer at `confidence: 1.0`; the vision LLM is used for *semantics/association* and for
  low-cardinality reads, never to re-read a number the text layer already gives.
- **E3 — Two tracks, both honest.** Track A = the only "pixel-faithful" claim, vector panels only.
  Track B carries an SSIM/confidence score and is never labelled pixel-identical.
- **E4 — Human-confirm QA gate on low-confidence / vision-only goldens** (inherited D3). Not manual
  transcription — confirmation of machine reads below a confidence threshold.
- **E5 — License posture = permissive only on the shipped path** (Apache/MIT/BSD/MPL). AGPL/GPL tools
  (DocLayout-YOLO, PyMuPDF, poppler, WebPlotDigitizer) are dev/validation-only, gated (inherited D8).
- **E6 — Clean-room ClawBio `data-extractor` (MIT) as a blueprint** for chart→data, built native to
  Selom's contract; do not vendor the unverified scaffold (inherited D7).
- **E7 — Intake = a MAIN-paper drop + a SEPARATE supplementary drop (owner 2026-06-18).** Two inputs,
  human-designated, until auto-detection improves: the main PDF carries the figures + text counts; the
  supplement (PDF *or* xlsx) carries the golden result tables (JEV ST2/ST6) + the extended methods.
  Some papers combine both in one file (RPGRIP1 `…/Data/THL/mmc1.pdf` = main + supplement) — so the
  contract accepts 1..N documents tagged ``main`` / ``supplementary``, not a single fixed PDF. Slice-1
  ``ingest_pdf`` is single-file; generalize the ingest signature (``ingest_paper(main, supplements=[])``)
  before the R5/FE intake. Phrasing note: slice-1's text-layer DE-count reader is tuned to the common
  *"N differentially expressed (X up, Y down)"* form (JEV) — papers using bespoke wording (RPGRIP1's
  *"signature"* genes) need the vision/semantic layer (X1 slice-2); the methods-digest lexicon already
  generalizes cross-paper (RPGRIP1 recipe recovered from `mmc1.pdf`).

## Module layout

New code under `app/backend/extract/` (its own package), composed by `reproduction.py`:
```
extract/
  ingest.py        # thin wrapper over papers.py → pages + text + embedded objects
  detect.py        # figure-detect + panel-segment (vector-gutter + label anchor)
  classify.py      # chart-classify + scope-classify (vision LLM, structured JSON)
  golden.py        # value/golden-extract + methods-digest → GoldenTarget[] + Inconsistency[] + MethodsDigest
  reconstruct.py   # Track A (XObject lift) + Track B (Plotly redraw via skills/theme.py)
  validate_redraw.py  # SSIM + confidence for Track B
```

## Testing

- Unit: vector-XObject lift on a fixture PDF (Track A); golden-target round-trip; inconsistency capture
  on a synthetic two-threshold figure (guard 1) and a two-value figure (guard 2).
- Extraction: synthetic scanpy/matplotlib panels with **known ground truth** → assert recovered Venn
  counts / stacked-bar % / dotplot rows + Track-B SSIM band.
- Scope: a fixture with mixed transcriptomic + IHC panels → assert wet-lab tagged out-of-scope.
- Integration (RPGRIP1, slow/manual): Fig 5 + Fig 6 PDFs → assert the golden-target table matches the
  hand-written `rpgrip1_target_spec.md` (universe 1,133, 6E Venn 27/52/10 + 52 triple, RHO −71%/−34%)
  and that the two inconsistencies (78-vs-181, adj-p-stated-but-unreachable) are flagged.

## Build phases

- **X1 — Target-extraction MVP (highest value first).** ingest (reuse) → manual-assist panel-segment
  → chart-classify + scope-classify (vision) → golden-extract (text-layer + vision) + methods-digest
  → emit the typed golden-target table + inconsistencies. This alone replaces SOP steps 1–4 and feeds
  the whole engine; **no reconstruction yet.**
  - **X1 slice-1 — SHIPPED 2026-06-18** (`app/backend/extract/`, pytest +14): the **text-derivable
    core, no live vision** — `ingest.py` (papers.py wrapper) · `models.py` (GoldenTarget /
    MethodsDigest / PanelDraft / ExtractedSpec) · `golden.py` (**text-layer-exact** DE-count
    extraction E2 — sentence-bounded, `total = up+down`; the methods-digest lexicon, word-boundary
    matched; guard-2 inconsistency capture; `to_golden`/`to_engine_panels` bridge) · `classify.py`
    (rule scope-classify guard 7 + a pluggable `Classifier`; vision **gated** = `VisionUnavailable`).
    Verified on the real JEV PDF: recovers Fig 1 12/23/35 + Fig 4 61/119/180 + the recipe
    (edgeR/limma/fgsea/TMM). **Open-Q#1 → manual-assist first** (panel-letter assignment is
    best-effort text-only; segmentation deferred). **Open-Q#2 → the vision LLM is gated** (no gateway
    wired; degrades to the rule classifier, R-oracle pattern).
  - **X1 slice-2 — SHIPPED 2026-06-18** (`extract/vision.py`, pytest +8): the live vision layer with
    **Claude acting as the gateway** for the dev/dogfood profile (open-Q#2 resolution). `VisionGateway`
    Protocol + `OperatorVisionGateway` (replays operator reads deterministically → CI-safe; degrades
    to `VisionUnavailable`, drops in behind the existing `VisionClassifier`) + `associate_counts` /
    `augment_with_vision` (add goldens for counts stated only graphically) + `venn3_totals` (per-set
    totals from a 3-set Venn's seven regions) + `PanelBox`/`segment_panels` (manual-assist, **open-Q#1**).
    **Verified live acting as the gateway on the real RPGRIP1 Fig 6E Venn:** read the seven region
    counts off the raster (unique 27/52/10, pairwise 13/10/2, all-three 52) — slice-1's text reader is
    silent on the panel, the pairwise overlaps are **pixel-only**, and reconstructing per-rod totals
    gives **102/119/74**, the exact GO-term targets the GSEA panel is judged against.
  - **E7 — two-input intake — SHIPPED 2026-06-18** (`extract/ingest.py`): `ingest_paper(main,
    supplements=[...])` → `PaperBundle` (main PDF + N human-designated PDF/xlsx/csv supplements);
    `build_extracted_spec` reads DE counts from the main figures, the methods digest from the whole
    corpus. Verified on real JEV (main + xlsx) and Hani (main + csv).
- **X2 — Track B (editable reconstruction + SSIM) — slice SHIPPED 2026-06-18** (`extract/reconstruct.py`,
  pytest +10): pure-numpy SSIM core (CI-safe) + `reconstruct_panel` (editable Plotly redraw via
  skills.theme) + `self_qa` (SSIM vs original raster → `ReconstructionQA`) + gated Kaleido `render_spec`.
  Verified live: redraw → Kaleido render (no Docker) → SSIM self-QA = 1.0 identity / 0.924 vs a blurred
  copy. The render→SSIM-vs-original-scan calibration (acceptance band, open-Q#3) is the owner dogfood.
- **X3 — Track A (vector-faithful lift) — SHIPPED 2026-06-18** (`extract/lift.py`, pytest +9):
  built on **pypdf** (BSD, already shipped via the `pdf` extra — no pikepdf/PyMuPDF/poppler needed).
  Two honest tiers: `lift_panel_region(pdf, page, bbox)` clips a page to the panel's bounding box
  (sets `MediaBox`+`CropBox`, content stream untouched) → a standalone 1-page PDF that renders
  **pixel-identical** to the source region at any DPI (vector content is `scalable`); and
  `extract_raster_panel` pulls an Image XObject's bytes exactly (image-identical, not scalable,
  honest ceiling #2). `page_is_vector` + `list_page_xobjects` route the two. **Verified live:** lifted
  a vector region → rendered (PDFium) → **SSIM(registered)=1.0** vs the same region of the source —
  the registered regime where SSIM is valid (the open-Q#3 finding). SVG re-emit (svgpathtools) is a
  future extension; the PDF crop is the faithful artifact.
- **X4 — chart→data recovery** (bar/line via DePlot/LineFormer) for panels where the data must be
  recovered rather than recomputed from raw inputs.

## Open questions

1. **Panel-segment automation depth for X1** — ship manual-assist (operator confirms panel boxes)
   first, automate (vector-gutter + label anchor) in X2? Recommend manual-assist first.
   _Resolved: manual-assist SHIPPED (`PanelBox`/`segment_panels`, slice-2); vector-gutter/label-anchor
   automation still deferred (a fast-follow)._
2. **Vision-LLM provider boundary** — the engine calls the shared AI gateway (backend); confirm the
   gateway is available in the dev/dogfood profile, not just the product runtime.
   _Dev/dogfood resolution (owner-directed 2026-06-18): the live gateway is **not built yet** — **Claude
   acts as the gateway** (real vision via operator inspection of panel rasters), slotting behind
   `VisionClassifier`. A **PoC stand-in for building, NOT the product runtime path**; the formal
   `VisionClassifier(gateway=…)` adapter lands in X1 slice-2._
3. **Track-B SSIM acceptance band** — what SSIM counts as "visually equivalent"? Calibrate on the
   RPGRIP1 panels during X2.
   _**RESOLVED 2026-06-18** by calibration on real RPGRIP1 Fig-6 panels (Selom redraw vs publisher-
   scan crop). The result is a **correction**, not a threshold: SSIM is a **registered** (pixel-
   aligned) metric, and a fresh Plotly redraw is not registered to a scan. Measured — equivalent
   pairs 0.66–0.76 (venn .758 / dotplot .741 / violin .696 / comp .687) but **different-panel**
   controls 0.74–0.78, i.e. NEG scored ABOVE EQ; content-variance-weighting and content-bbox cropping
   did not separate them (gaps −0.097 / −0.078). Whole-panel SSIM-vs-scan is dominated by shared
   whitespace + gross layout, not figure identity, so it **cannot gate** a redraw. Shipped:
   `reconstruct.py` bands recalibrated to the **registered** regime where SSIM is valid (equivalent
   ≥0.95, plausible ≥0.80; anchored by controls identity=1.00, blur-3px=0.85), and `self_qa(...,
   registered=False)` returns an **advisory** verdict (`accepted=None`) for scan comparisons.
   `reconstruct_and_qa` defaults `registered=False`. Faithfulness of a redraw to the authors' figure
   is decided by the **golden-target match** (counts/%/gene-set sizes — the engine's job), never pixels._

# Figure Extraction Subsystem — sub-spec

> Sub-spec of the **Reproduction Engine** pillar (`spec.md`). Status: **spec, pending owner
> approval** (split out from `spec.md` 2026-06-17 per the owner steer + the parent spec's flagged
> action). Cross-lane (backend-led extraction + thin frontend surfacing). Grounded in two completed
> real dogfoods — RPGRIP1 Fig 5 (bulk, GSE293982) + Fig 6 (scRNA, GSE293984) — whose front-half
> (PDF → panel inventory → methods digest → golden-target table) was run **by hand** and is the
> thing this subsystem automates. The manual procedure is `figure-repro-sop.md` steps 1–4.

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
- **X2 — Track B (editable reconstruction + SSIM).** Redraw via the existing skills + theme; validate
  by SSIM; attach confidence. Unblocks the product figure surface and self-QA.
- **X3 — Track A (vector-faithful lift).** XObject lifter + re-emitter for vector panels — the
  differentiator; fast-follow after Track B proves the loop.
- **X4 — chart→data recovery** (bar/line via DePlot/LineFormer) for panels where the data must be
  recovered rather than recomputed from raw inputs.

## Open questions

1. **Panel-segment automation depth for X1** — ship manual-assist (operator confirms panel boxes)
   first, automate (vector-gutter + label anchor) in X2? Recommend manual-assist first.
2. **Vision-LLM provider boundary** — the engine calls the shared AI gateway (backend); confirm the
   gateway is available in the dev/dogfood profile, not just the product runtime.
3. **Track-B SSIM acceptance band** — what SSIM counts as "visually equivalent"? Calibrate on the
   RPGRIP1 panels during X2.

# Extract ↔ Reproduction bridge — spec (★D)

> Status: **Phase 1 (BE) + Phase 2 (FE) SHIPPED** — owner picked **Option A (staged assets)** at the
> §4 fork. Phase 3 (automated panel segmentation) remains a fast-follow. Stamped 2026-06-19 +10:00.
> Owner steer: memory `selom-extract-reproduction-bridge` (2026-06-18).
>
> **Shipped:** `PanelLift` + `repro_assets.attach_lifts` + `/repro-assets` static mount +
> `scripts/stage_panel_assets.py` (3 real Hani thumbnails: 2A/2C/4C) + the digitize≠reproduce
> invariant (mechanically tested); FE thumbnails + the "Digitize this panel" entry (gated to
> traceable forms) + the picker's lifted-image preload + not-scored banner. Browser-verified at
> desktop 1440. Commits: `fc4b23f`/`886394b` (BE) · `3c6c8f7` (FE).

## 1. Goal

In the read-only Reproduction view (R5), surface each paper panel as a **thumbnail**, and add an
in-paper **"Digitize this panel"** action that opens the existing chart-extractor picker on the
**X3-lifted panel** (no manual screenshot) — so a reader can pull the underlying numbers out of a
published panel *without leaving the paper's reproduction page*.

This closes the loop: today `/extract` is a standalone surface (drop your own image); the bridge
makes it reachable in-context from a specific panel, pre-loaded with that panel's pixels.

## 2. The load-bearing invariant — digitize ≠ reproduce

**Digitized data NEVER counts toward the Reproducibility Score.** This is the whole reason the
feature is safe. The two-axis credibility (reproducibility vs Selom-confidence,
[[selom-reproducibility-score]]) depends on the score reflecting *Selom regenerating the figure from
the data*, not *a human tracing pixels off the printed figure*. Tracing the printed panel and
"matching" it would be circular — it would inflate reproducibility using the very figure we claim to
reproduce.

Concretely:
- Digitized output is tagged `source: "digitized"` (distinct from the X4 `source: "extracted"`),
  carries the originating `panel_key`, and is **never** fed to `validate_panel` / `build_scorecard`.
- The UI labels it unmistakably: a "Digitized — vision-grade, not scored" banner, visually separate
  from the golden-vs-computed evidence table.
- An automated guard test asserts no digitized artifact can reach a score path.

## 3. What already exists (reused, not rebuilt)

- **R5 view** — `/reproduction/[slug]`, driven by `GET /papers/{slug}` → `Ledger` (paper + panels +
  validations + scorecard). Panels carry `figure`/`panel`/`chart_form`/`golden` but **no image and
  no bbox** today. (`components/reproduction/paper-detail.tsx`, `panel-table.tsx`.)
- **The picker** — `ChartExtractor` (`components/extract/chart-extractor.tsx`): takes a dropped image
  `File`, guided 2-ticks-per-axis calibration, `POST /extract/chart` → editable figure + Statistics
  table landing in the real editor (`useFigureStore().init`). Already vision-grade-gated.
- **X3 lift** — `extract/lift.py`: `lift_panel_region(pdf, page_index, bbox)` clips a page to a panel
  bbox → a **pixel-identical** standalone PDF (vector) or `extract_raster_panel` → image-identical
  bytes (raster). Built on pypdf (BSD). Verified SSIM(registered)=1.0.
- **`POST /extract/chart`** — image + calibration → recovered series/table/figure (vision-grade 0.7).

## 4. The central fork — where does the panel image come from? (NEEDS A DECISION)

X3 lifts a panel from a **source PDF + page_index + bbox**. Two facts block the naive path:
1. The paper PDFs live **outside the repo**, on the owner machine — not in the deploy image.
2. Ledger panels carry **no bbox** (panel segmentation was R4 open-Q#1, deferred).

So "show the X3-lifted panel" requires staging, per panel, a `(page_index, bbox)` and producing a
served raster. Three ways to get the image, in increasing faithfulness / infra:

- **Option A — Staged panel assets (faithful, the owner's stated target).** An offline/dev step (on
  the owner machine, which has the PDFs) records each panel's `(page_index, bbox)` and runs X3 to
  emit a raster thumbnail, written as a **served static asset** keyed by `panel_key`. R5 reads
  `panel.thumbnail_url` + lift metadata; the picker opens on the lifted raster. Deploy-safe (assets
  are committed/served, no PDF at runtime). Cost: a per-panel bbox-staging step (manual now; the
  automated segmenter is a later fast-follow). Matches "no screenshot, reuse the X3-lifted panel."
- **Option B — On-demand dev lift endpoint.** A dev-only `POST /papers/{slug}/panels/{key}/lift`
  that reads the PDF from a local path and lifts on the fly. Simplest, but **not deploy-safe** (needs
  the PDF at runtime) — a dogfood tool, not product.
- **Option C — Drop-your-own-panel in context.** "Digitize this panel" just opens the picker with an
  empty dropzone, pre-tagged with the `panel_key`; the user supplies the screenshot. Lowest infra,
  no thumbnails, **but contradicts the owner's "no screenshot" preference.**

**Recommendation:** **Option A, phased** — it is the only faithful, deploy-safe, owner-aligned path.
Phase 1 stages just the handful of **Hani** panels that have a real chart form (the bridge's first
demo); Phase 2 automates panel segmentation to scale to every ledger.

## 5. Proposed phased plan (assuming Option A)

### Phase 1 — model + integrity + one staged paper (BE-first, then FE)
1. **Data model.** Add an optional `Panel.lift: PanelLift | None` to `reproduction.py`:
   `PanelLift{ page_index, bbox, kind ("vector"|"raster"), thumbnail_url, digitizable: bool }`.
   `None` ⇒ the panel renders as today (no thumbnail, no digitize button). Purely additive; the
   scorecard path ignores it entirely (invariant §2).
2. **Asset staging script** (`scripts/stage_panel_assets.py`, dev/owner-only, ADR-0002 spirit —
   never in the shipped runtime): reads a per-paper bbox table + the local PDF, runs X3
   `lift_panel_region` / raster render → writes `repro-assets/{slug}/{panel_key}.png` + a
   `panels.json` of lift metadata. Committed assets are served read-only.
3. **Serve assets.** `GET /papers/{slug}` populates `panel.lift` from the staged `panels.json` when
   present; thumbnails served as static files (a `repro-assets` mount or Next `public/`).
4. **Integrity guard (BE).** A `digitized_series(...)` helper that stamps `source: "digitized"` +
   `panel_key`; a test asserting `build_scorecard` and `validate_panel` never consume a digitized
   artifact (no path from digitize → score).

### Phase 2 — FE bridge (needs the 3 design skills + desktop browser-verify)
5. **Panel thumbnails in R5.** Render `panel.lift.thumbnail_url` as a thumbnail in the panel table /
   a small panel gallery, only where `lift` is present. Read-only, no layout regressions.
6. **"Digitize this panel".** A button on a digitizable panel opens the picker pre-loaded with the
   lifted raster. Extend `ChartExtractor` to accept an **optional initial image** (a Blob/URL it
   fetches into a `File`) + a `panelKey` context, instead of only an empty dropzone. The recovered
   figure lands in the editor exactly as today.
7. **"Not scored" framing.** The digitize surface wears a "Digitized — vision-grade, not part of the
   Reproducibility Score" banner; entered from the panel, returns to the panel. No score mutation.

### Phase 3 — automation (fast-follow, out of this spec's build)
8. Automated panel segmentation (R4 open-Q#1) to emit bboxes for every ledger panel, removing the
   manual staging step. Tracked, not built here.

## 6. Data-model & API summary
- `reproduction.Panel.lift: PanelLift | None` (additive; default `None`).
- `PanelLift{ page_index:int, bbox:[f,f,f,f], kind:str, thumbnail_url:str, digitizable:bool }`.
- `GET /papers/{slug}` — unchanged shape except panels may now include `lift`.
- Static thumbnails under `repro-assets/{slug}/{panel_key}.png`.
- No new score/ledger fields; the scorecard is byte-identical for un-staged papers.

## 7. Testing / integrity
- Unit: staging script lift mechanics (renderer-free, reuse X3's test seams).
- Unit: `digitized_series` stamps `source:"digitized"` + `panel_key`.
- **Guard**: a test that fails if any digitized artifact is reachable by `validate_panel` /
  `build_scorecard` (the invariant, mechanically enforced).
- FE: vitest for the picker's initial-image adapter; desktop browser-verify of the thumbnail +
  "Digitize this panel" → editor round-trip (Selom is desktop-only).

## 8. Open questions (for owner)
1. **§4 fork** — confirm Option A (staged assets), or prefer B (dev-only) / C (drop-your-own)?
2. **Asset location** — commit thumbnails into the repo (`repro-assets/` served by FastAPI) vs Next
   `public/`? (Leaning FastAPI mount, so it travels with the ledger API.)
3. **First staged paper** — Hani (the current ★ focus) for the demo subset? Which panels
   (2B pvca / 2C boxplot / 3B upset / 4C regression are the chart-form ones)?

## 9. Out of scope
Automated panel segmentation (Phase 3), digitizing schematics/IHC/micrographs (no chart to trace),
and any path that lets digitized data influence the score (forbidden by §2).

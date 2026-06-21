# Slice 0/1/5 findings — Yoshimura cold drive (Wu & Little 2023, kidney organoid multiome)

> Session 51, 2026-06-22. The **second** calibration paper (`docs/reproduction-dogfood/spec.md`),
> chosen for deposited tabular data to separate the *extractor* gap from the *data* gap. Tool:
> `reproduction_diagnose.diagnose_paper`. Inputs: the staged main PDF + the SI Appendix PDF +
> `pnas.2219699120.sd01.xlsx`. Raw reports: `graphify-out/scratch/s51-yoshimura-gap.{md,json}`
> (gitignored scratch). Paired with Harmony (`findings-harmony.md`) this gives two cold baselines.

## Headline — the gap reproduces, and two slices move it

| | Slice 0 baseline (extractor = DE-counts only) | After **Slice 1** (n_cells) + **Slice 5** (accessions) |
|---|---|---|
| panels | 4 | 5 (the n_cells golden rode in as its own panel) |
| in-scope | 3 | 4 |
| **goldens extracted** | **0** | **1 — `n_cells` = 56,865** |
| gradable (in-scope + golden) | 0 | **1** |
| auto-grade rate | n/a (no gradable panels) | 0% (0/1) — a gradable *target* now exists |
| **cited data (provenance)** | *(not surfaced)* | **4 GEO accessions, all open + fetchable** |
| status rollup | `run_failed×3`, `out_of_scope×1` | `run_failed×4`, `out_of_scope×1` |
| **Selom-confidence defects** | **0** | **0** (the two-axis guard held through both slices) |

The honest engine still grades nothing **driven** (the deposited supplement is a QC table, not a
matrix — same wall as Harmony), but the report is no longer blank: it now says *what number each
panel should reproduce* and *where the real data is*. That is the dogfood signal the phase exists to
produce.

## What the second baseline confirmed (Slice 0)

Yoshimura reproduces Harmony's two root causes **with a second, independent data point** —

1. **0 goldens extracted.** The cold-paper extractor only knew DE up/down/total counts. Yoshimura
   prints **"resulted in 56,865 cells after filtering"** (the atlas size), **"9.1% of the
   population"** (an *epidemiology* stat, a trap), and CRISPRi knockdown %s (wet-lab) — none in the
   golden vocabulary. So every panel was `no_golden`/blank.
2. **The lone tabular was force-fed to every skill.** The single supplement (`sd01.xlsx`, sheet
   `QC_matrics`, "related to Figure 1") was matched to all in-scope panels; `umap_scrna`/`trajectory`
   tried to open it as a matrix → h5py *"file signature not found"* → `run_failed`. The honest status
   is `data_unmatched` (a QC table is not a counts matrix). **This is the Slice 2 matcher-honesty
   fix** — now sharper, because the n_cells panel carries a golden the picker can aim at a real file.
3. **Meta-finding (reinforced).** The real data is **not** deposited as tables — it is **GEO:
   GSE213152 / GSE227061 / GSE151302** (the availability statement). Two famous papers, same shape:
   *deposit accessions, attach a QC table.* This is exactly why Slice 5 exists.

## Slice 1 — extractor recall (`n_cells`) — SHIPPED

`extract.golden.extract_dataset_size` lifts the analyzed dataset size (`n_cells`) from the text
layer, gated on **tight result/QC anchors** ("resulted in N cells", "N cells after filtering", "a
dataset of N cells"), never a bare "N cells". Calibrated against **both** papers:

- **Yoshimura** → `n_cells = 56,865` (text-layer-exact, confidence 1.0).
- **Harmony** (a benchmark paper with **28** cell-count mentions — down-sampling sizes, per-replicate
  sizes, the "293T" cell line, "100 cells" thresholds) → **0 false positives.** Precision-first (E2):
  a benchmark size is a *parameter*, not the analyzed atlas.

Closed end-to-end: the golden is backfilled to `umap_scrna` (`engine.match._METRIC_SKILL`), and a new
L1 reader (`extract.readers._read_umap`) reads `n_cells` back as the UMAP's plotted-point count — so
when the matrix is matched (Slice 2 picker or Slice 5 Phase-B fetch), the panel **drives and grades**.
A drive test proves the loop (`test_drive_n_cells_closes_the_loop_extractor_to_grade`). The 4 hand
ledgers grade **byte-identical** (30/30); `n_clusters`/correlation were **not** added — neither
calibration paper prints a clean integer for them (measure-before-build; next extractor target when a
paper surfaces one).

## Slice 5 — accession recognizer (Phase A) — SHIPPED

`extract.accessions.find_accessions` reads the datasets a paper *cites but does not attach*,
deterministically (regex, no network, no new dependency), classified by repository + **access
class** (the honesty axis):

- **open** (GEO series/sample, ArrayExpress, PRIDE, MetaboLights/Workbench, Zenodo/Figshare/Dryad) →
  `ingestable` → a gated Phase-B fetch *could* feed the matcher.
- **raw** (SRA/ENA/GSA-CRA) → not ingestable: "needs quantification" (parked BAM-ingest).
- **controlled** (dbGaP/EGA/GSA-Human HRA) → not ingestable: "requires an application; cannot
  auto-fetch" — never a silent failure.

On Yoshimura it recovers all 4 GEO accessions, ignoring the `(77)/(78)/(79)` citation markers, and
correctly does **not** mistake supplementary-table refs ("Table ST6/ST2") for Metabolomics-Workbench
studies (those are `ST` + ≥6 digits). Surfaced in the gap report header + a **Cited datasets** table.
**Phase B (fetch + ingest) is GATED** (network / size-cap / cache / async — ASK first, D6).

## What this validates about the plan

- **Two baselines, one gap.** Harmony and Yoshimura independently show the *extractor* gap (now
  partly closed by Slice 1) and the *data* gap (Slice 2 matcher honesty + Slice 5 provenance).
- **The data-side is the binding constraint for `driven`.** Slice 1 creates the gradable target;
  `auto_grade_rate` only moves off 0% once the real matrix is in hand — i.e. **Slice 2 (point the
  picker at the right file) and Slice 5 Phase B (fetch the open GEO data)** are the next levers, not
  more extractor families.
- **Honesty held throughout:** 0 Selom-confidence defects across both slices, on both papers.

## Next

1. **Slice 2 — matcher honesty + per-panel picker.** Stop force-feeding a QC table to a matrix skill
   → `data_unmatched`; let the user (or Slice 5 Phase B) point the n_cells/UMAP panels at the GEO
   matrix. This is what flips Yoshimura's `auto_grade_rate` off 0%.
2. **Slice 5 Phase B (GATED).** Fetch the open GEO-supplement processed files for `ingestable`
   accessions → `engine.ingest` → close `data_unmatched`. ASK before any network/large-file/async.
3. Extractor: add the next golden family **when a dogfooded paper prints it** (cluster/cell-type
   count, correlation r) — not speculatively.

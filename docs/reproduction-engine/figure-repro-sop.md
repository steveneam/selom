# Figure-Reproduction SOP (manual loop)

> **Standard operating procedure** for reproducing a paper's figures **and numbers** from just its
> PDF + Selom + public raw data. This is the **manual precursor** to the automated Reproduction
> Engine pillar (`spec.md`) — the engine automates these same steps. Build-phase: today it's run by
> hand; every step here maps to a future engine stage.
>
> Grounded in the first end-to-end dogfood: RPGRIP1 / Loi 2025 Fig 5 (`../rpgrip1-figrepro.md`).
> Owner-requested 2026-06-17 ("write an SOP/script so the process is faster").

## Governing rules (non-negotiable — from memory)

1. **Order = figures → methods → everything.** LOOK at each panel image *first*; READ the STAR
   methods *before* building. Never infer the pipeline from the legend or the skill name.
   ([[figure-repro-look-at-figures-first]])
2. **Match the numbers, not just the chart form.** Faithful = the VALUES match (counts, proportions,
   gene-set sizes, thresholds, fold-changes). Reproduce the authors' exact methods/thresholds; prefer
   their result tables; **report every delta + structural limit honestly**. ([[figure-repro-match-numbers-exactly]])
3. **Reproduce deterministic parts first** (gene-set universes, ID overlaps) — these must be EXACT and
   anchor confidence before the stochastic/threshold-dependent parts.
4. **Use R as a validation oracle, never the shipped path.** Most of these papers ship R pipelines
   (edgeR/Seurat/fgsea). Recapitulate the authors' *actual* tool in R 4.6 to (a) get the true target
   and (b) measure Selom's Python delta. R is validation-only (ADR 0002). ([[selom-r-validation-oracle]])
5. **Verdicts are explicit:** `exact` (ints equal / floats within rel-tol) · `close` (right
   direction/magnitude, delta recorded) · `fail` (outside band or structurally impossible, with reason).
   A structural impossibility is `fail`+reason, never a silent pass.

## Environment (copy-paste)

```bash
# Selom backend Python (EDR workaround — NOT plain `uv run`)
PY="/c/Users/seamegdool/AppData/Roaming/uv/python/cpython-3.12.13-windows-x86_64-none/python.exe"
export PYTHONPATH='D:/selom/app/backend;D:/selom/app/backend/.venv/Lib/site-packages'
export PYTHONIOENCODING=utf-8           # Windows console chokes on ∩/− etc.
cd /d/selom/app/backend
# run scripts: SELOM_SKILLS_ENGINE=real "$PY" <script.py>

# R validation oracle (registry-registered, not on PATH)
RS="/c/Users/seamegdool/AppData/Local/Programs/R/R-4.6.0/bin/Rscript.exe"
# Bioc installs: "$RS" -e 'BiocManager::install("edgeR", update=FALSE, ask=FALSE)'  (writes a log; pipe-to-grep can swallow output → redirect to a file)
```

## The loop (10 steps)

| # | Step | How (this run's tooling) | Output |
|---|---|---|---|
| 0 | **Scratch** | one dir per paper, e.g. `D:/tmp-thl/<slug>/` (deletable; keep `*_target_spec.md`). | workspace |
| 1 | **Acquire** | PDF → `app/backend/papers.py` (`uv sync --extra pdf`; PDFium text+render, BSD — **not** fitz). Resolve GEO accessions from the Data-Availability text; download counts/matrices. | PDF text, page renders, raw data |
| 2 | **Deconstruct figures** | LOOK at each panel render. Classify form (dotplot/PCA/heatmap/Venn/violin…). Separate **transcriptomic** panels (reproducible) from **wet-lab** (IHC/qPCR/dye = structural out-of-scope). | panel inventory |
| 3 | **Read methods** | grep the extracted text for the method paragraph (`edgeR`, `featureCounts`, `TMM`, `fgsea`, `Seurat`, thresholds). Capture exact filters/contrasts/thresholds. | methods digest |
| 4 | **Extract golden targets** | write `<slug>_target_spec.md`: every printed number (counts, %, Venn, gene-set sizes) + its source (figure/legend/methods) + flagged inconsistencies. | golden spec |
| 5 | **Map panels → skills** | each panel → a Selom skill + params, or a **gap**. (`gsea`, `deg`, `pca`, `heatmap`, `composition`, `upset`, `violin`, `cepo`…) | map + gap list |
| 6 | **Deterministic first** | reproduce ID-set parts (e.g. MSigDB-C5 RPGRIP1 universe = 1,133). Assert **exact**. | anchored facts |
| 7 | **Run via Selom skills** | drive the real `run_real.py` engines (`SELOM_SKILLS_ENGINE=real`). For DE, mirror the paper's exact filter (e.g. CPM<2-in-smallest-group) + normalization (`deg normalization=tmm`). | computed tables/specs |
| 8 | **Validate vs R oracle** | run the authors' actual tool in R (edgeR/Seurat/fgsea) on the same data + filter; compare Selom↔R across the threshold curve, then both vs golden. | oracle table, deltas |
| 9 | **Sweep when counts miss** | if a count ≠ golden, sweep contrast × stat(raw/adj) × threshold × direction × filter. Find which setting yields the printed number — that pins the authors' *undocumented* choice (or proves it's irreproducible). | sensitivity table |
| 10 | **Build panels + record** | render panels through the real skills; **verify visually** vs the paper; write verdicts (exact/close/fail) + deltas + structural limits to the figrepro record. | panels, record |

## Reusable scripts (this run, in `D:/tmp-thl/fig5-real/`)

- `de.py` — paper-faithful bulk DE (TMM via Selom `deg.run_real` helpers + CPM filter + pyDESeq2),
  emits full per-contrast results tables. *(template for any bulk-DE paper)*
- `edger_oracle.R` — the authors' actual edgeR pipeline (TMM→glmLRT→BH) as the validation oracle.
- `fig5_sweep.py` / `fig5_sweep2.py` — threshold/filter sensitivity sweep to hunt printed counts.
- `fig5A_gsea.py` — gseapy.prerank over MSigDB C5, ranked by logFC; negative-in-both selection.
- `build_panels.py` — renders 5A/5B/5C by driving the real `pca`/`heatmap` skills + GSEA dotplot.

These are the seed of the engine's `extract/` + `reproduction.py` modules. Generalize per-step into the
typed loop (`spec.md` §The loop) when the pillar is built.

## Edge cases & failure modes (ALWAYS check — observed in real dogfoods)

These are the traps that make a repro *look* done when it isn't, or make Selom *look* wrong when the paper
is the problem. Check every one before declaring a verdict. (Fold each into the engine as an explicit guard.)

1. **Methods text ≠ reported numbers (the paper doesn't self-reconcile).** A printed count may not be
   reproducible at the threshold the methods *state*. RPGRIP1 Fig 5: methods say adj-p<0.05 → that yields
   19, but the printed 78/181/49 only appear at *unadjusted* p cuts (~0.022 / 0.04 / 0.1) — **three
   different thresholds, none the stated one.** → Sweep, report which threshold reproduces each number,
   and flag the inconsistency. Never silently adopt the threshold that "works."
2. **Figures ≠ methods within the same paper.** RPGRIP1: results/figures say 78 signature genes; methods
   say 181. Capture *both* in the golden spec as a flagged inconsistency; pick the figure number as the
   panel target.
3. **The authors' own tool can't reproduce their number either.** Run the R oracle (step 8). If edgeR/
   Seurat/fgsea *also* miss the printed value on the deposited data, the verdict is **"paper
   irreproducible," not "Selom wrong."** This is the single most important guard — it reassigns blame
   correctly and is the differentiating finding the mission exists to surface.
4. **Filters cap the achievable count.** Count-based goldens are bounded by how many target genes survive
   the expression filter (RPGRIP1: only 882/1,133 universe genes pass CPM<2). Compute and report this
   ceiling *before* chasing a count — if the ceiling < golden, the count is structurally unreachable.
5. **Mild contrasts clear few/zero significant terms.** GSEA on the milder line (MS-VUS) cleared 0 GO
   terms at FDR<0.05 while the severe line (LCA-1) cleared 17. Don't read "0 significant" as "no signal" —
   check NES direction/magnitude and report the asymmetry (it's often the paper's actual point).
6. **Deposited data ≠ the data behind the figure.** GEO may hold a different/dedup/re-quantified matrix,
   or fewer samples than the figure (RPGRIP1 scRNA: 1 control deposited vs the figure's 3). Record as a
   **structural limit** (`fail`+reason), never force a match.
7. **Wet-lab panels are out of scope.** IHC / RT-qPCR / staining-dye panels (5D/5E/5F) aren't derivable
   from the sequencing data — classify them out early so the scorecard isn't penalized.
8. **R→Python method deltas are usually small — measure, don't assume.** The prior assumption "edgeR-LRT
   vs pyDESeq2-Wald = big gap" was *wrong*: measured against the edgeR oracle they agreed near-exactly.
   Quantify the delta before declaring a gap or building a replacement skill.
9. **Tooling gotchas:** `PYTHONIOENCODING=utf-8` (Windows console dies on ∩/−); redirect Rscript/long
   output to a file then read it (pipe-to-grep can return empty); R is registry-registered, **not on PATH**.

# P1 skill-breadth — scope for sign-off

> **Status: DRAFT for owner approval** (charter rule: new skills get a plan before they're
> built). Implements the competitor-driven **DECISIONS #10** P1 priorities. Non-Docker.
> _Filed 2026-06-13 · Claude (acting FE+BE) · companion to `docs/records/competitors/omicsbox.md` §7._

## Why this doc (the dogfooding finding that reshaped P1)

Building "no-API P1 breadth" started with `enrichment` on the real **EYG_28** DE results.
It runs, but the **bundled gene-set library is a 10-set / 102-gene sample** (immune-themed,
left over from the pbmc demo). The 1,173 significant RPGRIP1_cpdHet genes overlap only **14**
of those 102, so it returns biologically irrelevant pathways (Interferon signaling, NK-cell
cytotoxicity, …) for a *retinal-organoid* study. **Conclusion: enrichment's real breadth gap
is gene-set coverage, not input handling** — and that's a data-sourcing + licensing decision,
which is why it's scoped here rather than guessed.

(Already shipped, decision-free: `enrichment` + `volcano` now detect real DE-table gene
columns like `GeneID` — so EYG_28 ingests cleanly.)

## Decision #1 (the crux): gene-set / pathway data source

License is the constraint — **DECISIONS #9** keeps us off gseapy/MSigDB (AGPL/MSigDB gate,
RISKS #6). GO + Reactome are openly licensed; **KEGG is the watch-out** (free for academic
web use, but its FTP/REST bulk access is commercially licensed — must clear the launch gate).

| Option | What | Pros | Cons |
|---|---|---|---|
| **A. Primary-source GMT bundle** (recommend for GO/Reactome) | Build term→gene sets from GO GAF+OBO and Reactome's `NCBI2Reactome` / pathway TSVs; bundle as data | Fully license-clean, offline, reproducible, versioned | A small ingest pipeline (download + parse + GO propagation) |
| **B. Prebuilt CC-licensed GMT** | Drop in a clearly CC-licensed GMT | Fast | Must verify the specific file's license; provenance/versioning weaker |
| **C. Live API per query** | KEGG REST · Reactome ContentService · QuickGO at run time | No bundling; always current | Network + rate limits on the hot path; KEGG license; offline breaks |

**Recommendation:** **A** for `enrichment` gene-sets (GO+Reactome, bundled, license-clean) →
replaces the 102-gene sample with real coverage. Use **C** (live API) only for the `pathway`
*map rendering* (Reactome ContentService is open; gate KEGG).

## P1 items (pending the Decision-#1 answer)

1. **`enrichment` full gene-sets** — swap the bundled sample for the real GO+Reactome library
   (Decision #1A). The ORA math + dotplot already work; this is a data + ingest-script change.
   *Validation:* re-run on EYG_28 RPGRIP1_cpdHet — expect eye/neuronal/cilia terms (RPGRIP1 is
   a ciliopathy gene), not immune pathways.
2. **`pathway`** (new skill) — colored KEGG/Reactome pathway map from a gene list + fold-change.
   Reactome ContentService (open) first; KEGG behind the licence gate. `reactome2py` or REST.
3. **`go-graph`** (new skill) — GO BP/MF/CC DAG for a set of annotated terms; `obonet` + `networkx`
   (+ graphviz layout) over the GO OBO / QuickGO. Editable Plotly node-link output.
4. **`deg` time-course + no-replicate** — maSigPro-style (linear-trend-over-time) mode. ✅ **DONE
   2026-06-14** (commit `8700937`) — UNBLOCKED by the ALPK1 mouse P14/P30/P90 set once its design
   sheet was recovered (`RUV_K2_variates`; see `real-datasets.md`). `mode=timecourse` fits time as a
   continuous covariate in pyDESeq2 and Wald-tests the time coefficient (0.5.4 has no LRT), optionally
   covariate-adjusted; validated on 39 NR mouse samples (10,458 genes FDR<0.05). Also landed: robust
   bulk group inference + explicit `reference`/`treatment` contrast selection + a design-sheet input.
   *Still TODO:* NOISeq-style **no-replicate** mode (no fitting dataset yet) — deferred.
5. **Niceties surfaced by dogfooding** (small, decision-free, can do anytime):
   - **DE-table import** — point `volcano`/`enrichment` at a multi-contrast DE folder (EYG_28),
     pick a contrast, derive the gene list by FDR/FC cutoff.
   - **use-existing-embedding** — `umap`/scatter that plots a stored UMAP/t-SNE from `obsm`
     instead of recomputing (the rpgrip1 ShinyCell data already carries embeddings).

## Recommended sequence
Decision #1 → (1) enrichment full gene-sets [highest value, unblocks honest enrichment on both
real datasets] → (5) DE-table import + use-existing-embedding [quick wins] → (2) `pathway` →
(3) `go-graph` → (4) `deg` time-course/no-rep when count+time data exists.

**Asks for the owner:** (i) approve Decision #1 (recommend A for gene-sets, C for pathway maps);
(ii) confirm KEGG is academic-use-only for now (gate commercial at launch); (iii) confirm the
sequence (or re-rank).

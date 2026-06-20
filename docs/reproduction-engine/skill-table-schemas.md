# Skill output schemas — the generic-extractor reference

> Built s41 (2026-06-21) by fan-out inventory of **every** skill's `run.py` + `run_real.py`, then
> verified by direct grep of all `spec["table"] = …` / `de_table(` / `return table(` call sites.
> This is the contract the **live-reproduction generic extractor** (`docs/reproduction-engine/
> live-reproduction-spec.md` gap #3) reads against: given a panel's golden metric (e.g. `de_total`,
> `pc1_var`, a named cell-type %), where does the skill's output actually carry that number?

## The headline finding

A skill's quantitative result lives in **one of three places**, and only the first is a clean read:

1. **The Statistics `table`** (`spec["table"]` = `{columns, rows, title?}`, popped by
   `run_skill_with_table`). **Only 10 of ~30 skills emit one.**
2. **Figure strings** — `layout.title.text` / `…subtitle.text` / axis `title.text` /
   `layout.annotations[*].text`. Stats are *formatted into prose* (e.g. PCA variance `PC1 (39.7%)`,
   regression `R² = 0.97   slope = 0.0186   p = 1.3e-04`). Read by regex.
3. **Trace arrays** — `data[*].x/y/z/value`. Composition %, correlation r, sankey flows, UpSet
   sizes. Read by indexing the trace by label.

⇒ The generic extractor is **multi-source** (table → figure-string regex → trace lookup), not a
table reader. Where none of the three yields the metric, the panel is honestly **`needs_recipe`**
(computed, *not* auto-validated) — reproducibility-axis only, **0 Selom-confidence defects** (L2/L4).

## The 10 table-emitting skills (exact columns)

| skill | call site(s) | columns (exact) | row = | golden metrics readable | caps / caveats |
|---|---|---|---|---|---|
| **volcano** | `run.py:47`, `run_real.py:73` (`de_table`) | `["gene","log2FC","padj","direction"]` | gene | **`de_up`=Σ`direction=="up"`, `de_down`=Σ`"down"`, `de_total`=up+down** (or title TOTAL). Named gene logFC/padj. | capped **300** rows, sorted by padj; title `"… (top 300 of TOTAL by adjusted p)"` where TOTAL = genes *tested* (finite logFC), **not** genes passing. `direction` depends on caller `fc_threshold`/`fdr_threshold` ⇒ counts only match the paper at the paper's thresholds. **Best DE-count source.** |
| **deg** | `run.py:69`, `run_real.py:463` | `["gene","log2 fold-change"]` | gene | named gene's effect (top-`top_n` only). | **No padj, no direction** ⇒ **cannot** give DE counts. scRNA value is a Wilcoxon *score* mislabelled "log2 fold-change". No table on the **time-course** path. ⇒ for DE-count goldens, **prefer `volcano`**. |
| **diff_abundance** | `run_real.py:81` (real only) | `["cluster","log2FC abundance","adj p","cells","direction"]` | cluster | per-cluster abundance logFC + adj-p; `direction` ∈ expanding/shrinking ⇒ expand/shrink counts. | not capped. stub emits none. |
| **markers** | `run_real.py:127` | `["cluster","gene",<"Cohen's d"\|"AUC">,"frac expressing"]` | (cluster, gene) | named marker effect size + frac. n_clusters = distinct `cluster`. | **only when `rank_by`∈{cohens_d,auc}**; default `wilcoxon` ⇒ **no table**. 3rd col header is the interpolated rank label. stub none. |
| **normalization_qc** | `run_real.py:90/96/102` | filter+dbl: `["group","cells","kept","QC outliers","QC %","doublets","doublet %"]`; filter: `["group","cells","kept","removed","removed %"]`; dbl: `["group","cells","doublets","doublet %"]` | group (+ `"all"` row when >1 group) | per-group/overall kept/removed/doublet counts + %. | **only when `filter=true` and/or `doublets=true`**; default ⇒ **no table**. counts are pre-subsample. stub none. |
| **pseudotime_genes** | `run_real.py:68` (real only) | `["gene","Spearman rho","p","adj p","trend"]` | gene | named gene rho/p/adjp; `trend`∈up/down. | capped `top_n` (≤50). stub none. rho is rank-corr, *not* a slope. |
| **gsea** | `run_real.py:242` (`_results_table`), `run.py:88` | `["gene set","NES","NOM p","FDR q"]` | gene set | named term NES/p/FDR. **n_sets = title `len(res)`; n_sig = title `… at FDR<=0.25`** (NOT row count). | **library mode only** (`lib_mode`); explicit `gene_set`/`inhouse`/stub ⇒ **no table** (lead-term ES/NES/p/FDR in figure title). rows capped **25**. |
| **ssgsea** | `run.py:60`, `run_real.py` (`_assemble`) | `["gene set", *sampleNames]` (dynamic) | gene set | per-(set,sample) **raw NES** (z only affects the heatmap, not the table). | capped `top_n` by across-sample variance; true total only in figure title. no p-values by design. |
| **enrichment** | `run.py:91` (combined), `run.py:147` (split) | combined `["pathway","-log10 padj","overlap genes"]`; split `["pathway","direction","-log10 padj","overlap genes"]` | (pathway[,direction]) | n_terms ≈ row count (capped `top_n`); overlap count; **padj = 10^(−col)** back-transform. | capped `top_n` (≤40). raw p/padj/set_size dropped before the table. |
| **cepo** (proprietary) | `run.py:80` (`_ds_table`), `run_real.py:179` | `["cell type","gene","DS","detection"]` | (cell type, gene) | named (type,gene) DS + detection; n markers/type ≈ `n_genes`. | top `n_genes`/type only (full DS matrix not emitted). **both stub + real emit it.** table title fixed `"Cepo differential stability"` (≠ figure title). |

## The purely-visual skills — where their numbers actually live (no table)

| skill | metric class | source (read by regex / trace index) |
|---|---|---|
| **pca** | `pc1_var`/`pc2_var` | axis titles `xaxis.title.text = "PC1 (39.7%)"` → regex `\(([\d.]+)%\)` (1 dp). |
| **cluster** | n_clusters, silhouette | `layout.title.subtitle.text` = `"{n} clusters · silhouette {s:.2f} …"`; per-cluster counts = bar `y`. |
| **umap_scrna** | n_clusters | one trace per `color_by` level ⇒ `len(fig.data)`. real engine is **`run_scanpy.py`** (not `run_real.py`). |
| **annotate** | n_types, n_clusters | subtitle `"{n_types} types assigned across {n_clusters} clusters · …"`. |
| **integration** | batch-mixing | title `<sub>` `"batch mixing {b:.2f} → {a:.2f} (kNN entropy, 1=fully mixed)"` — **kNN entropy, not iLISI**. |
| **composition** | cell-type % per condition | **trace arrays**: trace named `<condition>`, value at index of `<category>` on the opposite axis. *(this is how JEV Fig 6 Müller % is read.)* |
| **trajectory** | n clusters/edges/lineages | subtitle `"… {n} clusters · {e} edges (≥thr) · {l} lineage(s)"`. |
| **regression** | slope, R², p | `layout.annotations[0].text` = `"R² = {r2:.2f}   slope = {s:.3g}   p = {p}"`. |
| **pvca** | variance fraction / factor | bar trace: `x`=factor labels, `y`=fractions (4 dp), `text`=`"{%:.1f}%"`; PCs/total% in title. |
| **boxplot** | (none server-side) | raw per-group values in box traces; quartiles computed client-side. |
| **violin** | PubMed hit count (annotate=pubmed) | `layout.annotations[-1].text` `"<b>{gene}</b> — {n:,} PubMed hits … {known\|novel}"`; one gene/run. |
| **corr_heatmap** | named-pair r | trace `z[y.index(a)][x.index(b)]` (use emitted x/y order — clustering reorders). |
| **sankey** | flow A→B | `link.value[k]` keyed by `node.label[link.source/target[k]]`. |
| **upset** | intersection / set sizes | intersection size = top bar `y`/`text`; set size = `setbars.x`; **members not extractable** (only counts survive). |
| **scorecard** | (condition,metric) score | radar `scatterpolar` `r` at `theta` index, or heatmap `z[i][j]` — **min-max normalized**, raw not recoverable. |
| **go_graph / pathway / string_network** | per-node p/FDR/overlap/logFC | node `hover` text + marker color/size only (live Reactome/STRING calls for real). |

### Known gaps (surfaced for the Skill Foundry backlog)
- **`proteomics_de` computes real per-protein logFC+padj but attaches NO table** — DE counts are
  *not* machine-readable from its output (figure title `keep.sum()` = proteins *tested*, easily
  mistaken for a DE total). For proteomics DE-count goldens, route through `volcano` on its results,
  or patch `proteomics_de` to attach a `de_table` (recommended fast-follow).
- **`deg` cannot yield DE counts** (no significance columns) — the router's top skill for a DE figure
  may be `deg`; the extractor must prefer `volcano` when the golden is a DE count.

## Generic-extractor strategy (what the live-repro orchestration builds on)

1. **DE counts** (`de_total`/`de_up`/`de_down` — the dominant auto-extracted golden from
   `extract.golden.extract_de_counts`): run **`volcano`** on the matched DE data, count `direction`
   rows in `de_table` (read TOTAL from the title when capped). This is the v1 floor's primary path.
2. **Single named statistics in a table** (cepo DS, gsea NES, pseudotime rho, enrichment overlap):
   match the golden's metric/entity name against the table's key column → value column.
3. **Figure-string metrics** (pca variance, cluster/integration/regression/pvca): regex the
   relevant title/subtitle/axis/annotation string.
4. **Trace metrics** (composition %, corr r, sankey, upset): index the trace by emitted label.
5. **No source ⇒ `needs_recipe`** — surfaced honestly, never a Selom-confidence FAIL (L2/L4).

Every table is `top_n`/300/25-capped, so **a row count is a truncated count** — read true totals from
the title string, never from `len(rows)`.

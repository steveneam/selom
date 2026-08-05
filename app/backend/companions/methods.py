"""Auto methods-text (charter B4 — publish-confidence).

Turns the skill that ran + its resolved parameters into a publication-ready methods
paragraph and the canonical tool citations. Deterministic templates keyed by skill id
(no LLM): the prose names the exact method and the parameter values a reader needs to
reproduce it. ``provenance.py`` records the machine-checkable half; this is the human
half — together they answer "is THIS figure trustworthy and reproducible?".

Each builder returns ``(text, citations)``; ``build`` appends a standard Selom
attribution sentence and returns ``{"text", "citations"}``.
"""

from __future__ import annotations

from skills import _erg, _stats
from skills._engine import to_bool
from skills.contract import SkillSpec, resolved_params

# --- Canonical citations, referenced by the per-skill templates -----------------

SCANPY = "Wolf, F.A., Angerer, P. & Theis, F.J. SCANPY: large-scale single-cell gene expression data analysis. Genome Biology 19, 15 (2018)."
UMAP = "McInnes, L., Healy, J. & Melville, J. UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction. arXiv:1802.03426 (2018)."
LEIDEN = "Traag, V.A., Waltman, L. & van Eck, N.J. From Louvain to Leiden: guaranteeing well-connected communities. Scientific Reports 9, 5233 (2019)."
SILHOUETTE = "Rousseeuw, P.J. Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. Journal of Computational and Applied Mathematics 20, 53-65 (1987)."
PYDESEQ2 = "Muzellec, B., Telenczuk, M., Cabeli, V. & Andreux, M. PyDESeq2: a python package for bulk RNA-seq differential expression analysis. Bioinformatics 39, btad547 (2023)."
DESEQ2 = "Love, M.I., Huber, W. & Anders, S. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. Genome Biology 15, 550 (2014)."
SQUAIR = "Squair, J.W. et al. Confronting false discoveries in single-cell differential expression. Nature Communications 12, 5692 (2021)."
SCATER = "McCarthy, D.J., Campbell, K.R., Lun, A.T.L. & Wills, Q.F. Scater: pre-processing, quality control, normalization and visualization of single-cell RNA-seq data in R. Bioinformatics 33, 1179-1186 (2017)."
SCRUBLET = "Wolock, S.L., Lopez, R. & Klein, A.M. Scrublet: Computational Identification of Cell Doublets in Single-Cell Transcriptomic Data. Cell Systems 8, 281-291 (2019)."
BH = "Benjamini, Y. & Hochberg, Y. Controlling the false discovery rate: a practical and powerful approach to multiple testing. Journal of the Royal Statistical Society B 57, 289-300 (1995)."
GO = "Ashburner, M. et al. Gene Ontology: tool for the unification of biology. Nature Genetics 25, 25-29 (2000)."
REACTOME = "Milacic, M. et al. The Reactome Pathway Knowledgebase 2024. Nucleic Acids Research 52, D672-D678 (2024)."
SCIPY = "Virtanen, P. et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. Nature Methods 17, 261-272 (2020)."
PAGA = "Wolf, F.A. et al. PAGA: graph abstraction reconciles clustering with trajectory inference through a topology preserving map of single cells. Genome Biology 20, 59 (2019)."
DPT = "Haghverdi, L., Büttner, M., Wolf, F.A., Buettner, F. & Theis, F.J. Diffusion pseudotime robustly reconstructs lineage branching. Nature Methods 13, 845-848 (2016)."
TIROSH = "Tirosh, I. et al. Dissecting the multicellular ecosystem of metastatic melanoma by single-cell RNA-seq. Science 352, 189-196 (2016)."
SKLEARN = "Pedregosa, F. et al. Scikit-learn: Machine Learning in Python. Journal of Machine Learning Research 12, 2825-2830 (2011)."
UPSET = "Lex, A., Gehlenborg, N., Strobelt, H., Vuillemot, R. & Pfister, H. UpSet: Visualization of Intersecting Sets. IEEE Transactions on Visualization and Computer Graphics 20, 1983-1992 (2014)."
STRING = "Szklarczyk, D. et al. The STRING database in 2023: protein-protein association networks and functional enrichment analyses for any sequenced genome of interest. Nucleic Acids Research 51, D638-D646 (2023)."
SMYTH = "Smyth, G.K. Linear models and empirical Bayes methods for assessing differential expression in microarray experiments. Statistical Applications in Genetics and Molecular Biology 3, Article 3 (2004)."
GSEA = "Subramanian, A. et al. Gene set enrichment analysis: a knowledge-based approach for interpreting genome-wide expression profiles. PNAS 102, 15545-15550 (2005)."
GSEAPY = "Fang, Z., Liu, X. & Peltz, G. GSEApy: a comprehensive package for performing gene set enrichment analysis in Python. Bioinformatics 39, btac757 (2023)."
BLITZGSEA = "Lachmann, A., Xie, Z. & Ma'ayan, A. blitzGSEA: efficient computation of gene set enrichment analysis through gamma distribution approximation. Bioinformatics 38, 2356-2357 (2022)."
SSGSEA = "Barbie, D.A. et al. Systematic RNA interference reveals that oncogenic KRAS-driven cancers require TBK1. Nature 462, 108-112 (2009)."
CEPO = "Kim, H.J., Wang, K., Chen, C. et al. Uncovering cell identity through differential stability with Cepo. Nature Computational Science 1, 784-790 (2021)."
PVCA = "Boedigheimer, M.J. et al. Sources of variation in baseline gene expression levels from toxicogenomics study control animals across multiple laboratories. BMC Genomics 9, 285 (2008)."
HARMONY = "Korsunsky, I. et al. Fast, sensitive and accurate integration of single-cell data with Harmony. Nature Methods 16, 1289-1296 (2019)."
ENTREZ = "Sayers, E.W. et al. Database resources of the National Center for Biotechnology Information. Nucleic Acids Research 50, D20-D26 (2022)."
ISCEV = "Robson, A.G. et al. ISCEV Standard for full-field clinical electroretinography (2022 update). Documenta Ophthalmologica 144, 165-177 (2022)."
NAKA_RUSHTON = "Naka, K.I. & Rushton, W.A.H. S-potentials from luminosity units in the retina of fish (Cyprinidae). Journal of Physiology 185, 587-599 (1966)."
# FlowIO + FlowUtils are the actual dependencies. There is deliberately NO FlowKit citation: the
# high-level FlowKit toolkit pins pandas<3 and is not installed (RISKS #12) — citing it would credit
# software that never ran (milestone review 2026-07-25, findings A7/A22/A28).
FLOWIO = "White, S. et al. FlowIO: a pure-Python FCS file reader/writer. https://github.com/whitews/FlowIO (BSD-3-Clause)."
FLOWUTILS = "White, S. et al. FlowUtils: numpy/C utilities for flow cytometry — compensation and GatingML transforms. https://github.com/whitews/FlowUtils (BSD-3-Clause)."
LOGICLE = "Parks, D.R., Roederer, M. & Moore, W.A. A new 'Logicle' display method avoids deceptive effects of logarithmic scaling for low signals and compensated data. Cytometry Part A 69A, 541-551 (2006)."
GATINGML = "Spidlen, J. et al. Gating-ML 2.0: International Society for Advancement of Cytometry (ISAC) standard for representing gating descriptions in flow cytometry. Cytometry Part A 87, 683-687 (2015)."


def _umap(p: dict):
    emb = (p.get("embedding") or "").strip()
    if emb:
        text = (
            f"Cells were displayed on a precomputed {emb} embedding provided with the dataset "
            f"and coloured by {p['color_by']} (Scanpy for I/O); no re-embedding was performed."
        )
        return text, [SCANPY]
    if p.get("normalize", True):
        prep = "Gene counts were normalized to 10,000 counts per cell and log1p-transformed, "
    else:
        prep = "The provided log-normalized expression was used directly, and "
    n_hvg = int(p.get("n_hvg", 0) or 0)
    hvg = f"the top {n_hvg} highly variable genes were selected, " if n_hvg > 0 else ""
    text = (
        "Single-cell RNA-seq data were processed with Scanpy. "
        f"{prep}{hvg}principal-component "
        f"analysis was computed, and a nearest-neighbour graph was built on the top {p['n_pcs']} "
        f"principal components using {p['n_neighbors']} neighbours. The graph was embedded in two "
        f"dimensions with UMAP, and cells were coloured by {p['color_by']} cluster."
    )
    return text, [SCANPY, UMAP]


def _integration(p: dict):
    batch = str(p.get("batch_key") or "").strip() or "the library/batch covariate"
    if p.get("normalize", True):
        prep = "Counts were normalized to 10,000 per cell and log1p-transformed, "
    else:
        prep = "The provided log-normalized expression was used directly, and "
    color = str(p.get("color_by") or "").strip() or batch
    n_hvg = int(p.get("n_hvg", 0) or 0)
    hvg = f"the top {n_hvg} highly variable genes were selected, " if n_hvg > 0 else ""
    text = (
        "Multiple single-cell libraries were integrated with Scanpy and Harmony. "
        f"{prep}{hvg}principal-component analysis was computed, and batch effects across "
        f"{batch} were corrected by running Harmony on the top {p['n_pcs']} principal "
        f"components (diversity penalty theta = {float(p.get('theta', 2.0)):g}, up to "
        f"{int(p.get('max_iter_harmony', 10))} iterations). A nearest-neighbour graph "
        f"({p['n_neighbors']} neighbours) was built on the Harmony-corrected embedding, "
        "Leiden-clustered, and embedded in two dimensions with UMAP; cells are coloured "
        f"by {color}. Integration quality was assessed as the change in the mean per-cell "
        "k-nearest-neighbour batch-mixing entropy before versus after correction."
    )
    return text, [SCANPY, HARMONY, LEIDEN, UMAP, SKLEARN]


def _cluster(p: dict):
    text = (
        f"Cells were clustered by Leiden community detection at resolution {p['resolution']}, "
        f"applied to a nearest-neighbour graph built on the top {p['n_pcs']} principal components "
        f"with {p['n_neighbors']} neighbours (Scanpy). Cluster-separation quality was quantified by "
        "the mean silhouette coefficient on the PCA embedding."
    )
    return text, [SCANPY, LEIDEN, SILHOUETTE]


def _grouping_phrase(p: dict, requested: str) -> str:
    """The grouping a figure was ACTUALLY drawn by.

    ``violin`` (and its siblings) fall back to clustering the cells themselves when the requested
    ``groupby`` column is absent from the data, and then group by Leiden. The figure discloses the
    substitution in its title and axis; the paragraph named the column the user asked for. Whether
    the fallback fired is a fact about the DATA, so the runner records it (``layout.meta.clustered``,
    lifted by ``build_body``) — and that record is also the only place the ``resolution`` that
    produced those clusters appears.
    """
    c = p.get("_clustered")
    if not isinstance(c, dict):
        return f"grouped by {requested}"
    res = c.get("resolution")
    at = f" at resolution {float(res):g}" if isinstance(res, (int, float)) else ""
    asked = str(c.get("requested") or "").strip()
    instead = (f" — the requested '{asked}' was not present in the data" if asked
               and asked != "leiden" else "")
    return f"grouped by Leiden clusters computed on the data{at}{instead}"


def _violin(p: dict):
    gene = p.get("gene") or "the selected marker gene"
    # `normalize=False` skips both `normalize_total` and `log1p` — the paragraph (and, until this
    # change, the figure's own value axis) called the plotted values log1p-normalized regardless.
    scale = ("log1p-normalized" if to_bool(p.get("normalize", True))
             else "already-normalized (no further scaling applied)")
    text = (
        f"Per-group expression of {gene} was visualized as {scale} violin "
        f"distributions {_grouping_phrase(p, str(p['groupby']))} (Scanpy)."
    )
    # The category order, the n= labels and the significance brackets are the same vocabulary
    # `boxplot` uses (`skills._stats`) — and the stars were drawn with no test named anywhere.
    named = [s.strip() for s in str(p.get("order") or "").split(",") if s.strip()]
    if named:
        text += (f" {', '.join(named)} lead in that order, with the remaining groups in the order "
                 "they occur in the data.")
    if to_bool(p.get("add_count", False)):
        text += " Each group label carries its n."
    sig, sig_cites = _pairwise_prose(p.get("pairs"), p.get("sig_test"), p.get("correction"))
    text += sig
    citations = [SCANPY] + sig_cites
    if str(p.get("annotate") or "none").lower() == "pubmed":
        context = str(p.get("context") or "").strip()
        scope = f" co-occurring with '{context}'" if context else ""
        text += (
            f" Each marker's literature support was assessed by querying PubMed (NCBI E-utilities) "
            f"for the gene symbol{scope} in the title/abstract; markers with at least "
            f"{int(p.get('known_min', 5))} matching records were annotated as known and the "
            "remainder as novel."
        )
        citations.append(ENTREZ)
    return text, citations


def _deg(p: dict):
    mode = str(p.get("mode") or "auto").lower()
    if mode in ("pseudobulk", "pseudo-bulk", "pseudo_bulk"):
        sample_col = str(p.get("sample_col") or "sample")
        reference, treatment = str(p.get("reference") or "").strip(), str(p.get("treatment") or "").strip()
        contrast = f" ({treatment} versus {reference})" if reference and treatment else ""
        label = str(p.get("label") or "").strip()
        within = f" within {label}" if label else ""
        text = (
            f"Differential expression between conditions{contrast} was assessed with a pseudo-bulk "
            f"approach to avoid pseudoreplication: single-cell raw counts were summed per biological "
            f"replicate ({sample_col}){within} to form one expression profile per sample, which were "
            "then modelled as bulk RNA-seq with PyDESeq2 (a Python reimplementation of DESeq2) and "
            "tested with the Wald test. Aggregating to the replicate level treats samples — not "
            "individual cells — as the unit of replication, the statistically valid design for "
            f"multi-sample comparisons. The top {p['top_n']} genes are reported, with p-values "
            "corrected by the Benjamini-Hochberg procedure."
        )
        return text, [SCANPY, PYDESEQ2, DESEQ2, SQUAIR, BH]
    if mode in ("timecourse", "time-course", "time_course"):
        text = (
            "Time-course differential expression was assessed by modelling raw counts against the "
            f"sampling time as a continuous covariate in PyDESeq2 (a Python reimplementation of DESeq2) "
            "and Wald-testing the time coefficient, identifying genes with a significant linear "
            f"expression trend over time. The top {p['top_n']} trending genes are shown as mean "
            "log2-CPM trajectories, with p-values corrected by the Benjamini-Hochberg procedure."
        )
        return text, [PYDESEQ2, DESEQ2, BH]
    reference, treatment = str(p.get("reference") or "").strip(), str(p.get("treatment") or "").strip()
    contrast = f" for the {treatment}-versus-{reference} contrast" if reference and treatment else ""
    text = (
        f"Differential expression was assessed{contrast}. For single-cell data, marker genes were "
        f"ranked per {p['groupby']} group with the Wilcoxon rank-sum test (Scanpy rank_genes_groups); "
        "for bulk RNA-seq, raw counts were modelled with PyDESeq2 (a Python reimplementation of DESeq2) "
        "and tested with the Wald test. The "
        f"top {p['top_n']} genes per contrast are reported, with p-values corrected for multiple "
        "testing by the Benjamini-Hochberg procedure."
    )
    return text, [SCANPY, PYDESEQ2, DESEQ2, BH]


def _volcano(p: dict):
    # Honest about which significance value was actually plotted: the source DE table may carry only
    # a raw p-value, in which case claiming BH correction would be a printed-vs-computed lie.
    if p.get("_significance_adjusted", True):
        text = (
            "Differential-expression results were displayed as a volcano plot of -log10 adjusted "
            f"p-value against log2 fold change. Genes with |log2FC| >= {p['fc_threshold']} and FDR <= "
            f"{p['fdr_threshold']} were highlighted, and the top {p['top_n']} by significance were labelled. "
            "Adjusted p-values reflect Benjamini-Hochberg correction."
        )
        return text, [BH]
    text = (
        "Differential-expression results were displayed as a volcano plot of -log10 RAW (uncorrected) "
        f"p-value against log2 fold change. Genes with |log2FC| >= {p['fc_threshold']} and raw p <= "
        f"{p['fdr_threshold']} were highlighted, and the top {p['top_n']} by significance were labelled. "
        "The source table carried no multiple-testing-corrected column, so no correction was applied "
        "and this threshold does not control the false-discovery rate."
    )
    return text, []


def _heatmap(p: dict):
    cluster = str(p.get("cluster") or "none").lower()  # none | row | column | both
    cols = (
        " Samples were likewise clustered (correlation distance, average linkage) and a column "
        "dendrogram is drawn above the columns."
        if cluster in ("column", "both") else ""
    )
    tree = (
        " and the clustering dendrogram is drawn alongside the rows"
        if cluster in ("row", "both") else ""
    )
    text = (
        f"Expression of the top {p['n_genes']} genes was z-scored per gene and displayed as a heatmap "
        f"grouped by {p['groupby']}. Rows were ordered by hierarchical clustering (correlation distance, "
        f"average linkage; SciPy){tree}.{cols}"
    )
    return text, [SCIPY]


def _enrichment(p: dict):
    split = str(p.get("direction") or "combined").lower() == "split"
    scope = (
        "the up- and down-regulated significant genes were tested separately"
        if split else "the input gene list was tested"
    )
    shown = (
        f"The top {p['top_n']} enriched sets per direction are drawn as a diverging dotplot "
        "(up-regulated to the right, down-regulated to the left)."
        if split else f"The top {p['top_n']} enriched sets are shown."
    )
    text = (
        f"Pathway enrichment was computed by over-representation analysis: {scope} for overlap with each "
        "GO and Reactome gene set using the hypergeometric distribution, and p-values were corrected "
        f"across gene sets by the Benjamini-Hochberg procedure. {shown}"
    )
    return text, [GO, REACTOME, BH]


def _pathway(p: dict):
    text = (
        "Differentially expressed genes were mapped to Reactome pathways and tested for "
        "over-representation with the Reactome Analysis Service (identifier projection to human "
        "orthologs; pathway p-values corrected by the Benjamini-Hochberg procedure). The top "
        f"{p['top_n']} enriched pathways are drawn in the Reactome event hierarchy as a node-link "
        "graph, each pathway coloured by the mean log2 fold change of its member genes."
    )
    return text, [REACTOME, BH]


def _markers(p: dict):
    scaled = " (scaled to [0,1] per gene)" if p.get("standard_scale", True) else ""
    # `normalize=False` skips both `normalize_total` and `log1p`, so the values the dot colour
    # encodes are the supplied ones — "mean log1p expression" described a transform that was
    # skipped, and the same word is in the legend and on the colour-bar label.
    scale = "log1p" if to_bool(p.get("normalize", True)) else "supplied"
    dotplot = (
        f"Expression is summarized as a dotplot in which colour encodes the mean {scale} "
        f"expression within each group{scaled} and dot size encodes the fraction of cells "
        "expressing the gene."
    )
    rank_by = str(p.get("rank_by") or "wilcoxon").strip().lower()
    if rank_by in ("cohens_d", "cohen", "cohens", "d", "auc"):
        effect = (
            "the area under the ROC curve (Mann-Whitney AUC)"
            if rank_by == "auc"
            else "Cohen's d (the standardized mean difference)"
        )
        text = (
            f"Marker genes were identified per {p['groupby']} group by a one-versus-rest effect "
            f"size, {effect}, rather than by a p-value (following the OSCA scoreMarkers rationale "
            "that p-values computed on data-derived clusters are circular). The top "
            f"{p['n_genes']} genes per group by effect size are reported. {dotplot}"
        )
        return text, [SCANPY, SCATER]
    text = (
        f"Marker genes were identified per {p['groupby']} group with the {p['method']} test "
        f"(Scanpy rank_genes_groups), reporting the top {p['n_genes']} genes per group. "
        f"{dotplot} P-values are corrected by the Benjamini-Hochberg procedure."
    )
    return text, [SCANPY, BH]


def _annotate(p: dict):
    text = (
        f"Cell types were assigned by marker-set scoring: for each cell type in the "
        f"'{p['marker_set']}' panel, its marker genes were scored per cell with Scanpy's "
        "score_genes (mean expression of the set minus a randomly sampled control set), "
        f"averaged per {p['groupby']} cluster, and each cluster was labelled with its "
        "top-scoring type. Cells are displayed on the embedding coloured by assigned type."
    )
    return text, [SCANPY, TIROSH]


def _trajectory(p: dict):
    root = str(p.get("root") or "").strip()
    root_txt = f"cluster {root}" if root else "the diffusion-component extreme"
    text = (
        "A diffusion map was computed and the cluster graph abstracted with partition-based "
        "graph abstraction (PAGA). Cells were ordered along diffusion pseudotime (DPT) from a "
        f"root placed at {root_txt}. The embedding is coloured by pseudotime with the PAGA "
        "graph overlaid (nodes = clusters sized by cell count; edges = connectivity above "
        f"{p['threshold']})."
    )
    return text, [SCANPY, PAGA, DPT]


def _pseudotime_genes(p: dict):
    root = str(p.get("root") or "").strip()
    root_txt = f"a root at cluster {root}" if root else "a root at the diffusion-component extreme"
    text = (
        "Genes varying along the inferred trajectory were identified by assigning each cell a "
        f"diffusion pseudotime (DPT) from {root_txt} and correlating every gene's expression with "
        "pseudotime by Spearman's rank correlation, with p-values corrected across genes by the "
        f"Benjamini-Hochberg procedure. The top {p['top_n']} trending genes are shown as mean "
        "log1p expression binned along pseudotime. Because pseudotime is derived from the same "
        "expression data, these associations characterize the trajectory rather than providing an "
        "independent statistical test."
    )
    return text, [SCANPY, DPT, SCIPY, BH]


def _pca(p: dict):
    scaled = "standardized features and " if p.get("scale", True) else ""
    text = (
        f"Samples were projected onto their first two principal components ({scaled}scikit-learn "
        "PCA) and coloured by group; the percentage of variance explained is shown on each axis."
    )
    return text, [SKLEARN]


def _composition(p: dict):
    mode = str(p.get("mode") or "grouped")
    text = f"Category proportions were displayed as {mode} bars across conditions."
    return text, []


def _diff_abundance(p: dict):
    reference, treatment = str(p.get("reference") or "").strip(), str(p.get("treatment") or "").strip()
    contrast = f" ({treatment} versus {reference})" if reference and treatment else ""
    tmm = str(p.get("normalization") or "tmm").lower() == "tmm"
    norm = (
        "TMM-normalized (the edgeR differential-abundance convention, which limits the "
        "compositional bias whereby one expanding cluster makes the others appear to shrink)"
        if tmm else "median-of-ratios normalized"
    )
    text = (
        f"Differential abundance of clusters between conditions{contrast} was tested by tallying "
        "the number of cells of each cluster in each sample and modelling that cells-per-"
        f"(cluster × sample) count table with PyDESeq2 (a Python reimplementation of DESeq2), "
        f"{norm}, with the Wald test. Each sample — not each cell — is the unit of replication, "
        "and p-values are corrected by the Benjamini-Hochberg procedure. The log2 fold change in "
        "abundance per cluster is shown (positive = expanding in the treatment). Because cluster "
        "proportions are compositional, the per-cluster changes should be read together."
    )
    return text, [SCANPY, PYDESEQ2, DESEQ2, BH]


def _corr_heatmap(p: dict):
    axis = "samples" if str(p.get("axis", "samples")).startswith("sample") else "features"
    method = str(p.get("method", "pearson")).title()
    clustered = bool(p.get("cluster", True))
    tail = (
        " Rows and columns were reordered by hierarchical clustering (1−r distance, "
        "average linkage; SciPy)." if clustered else ""
    )
    text = (
        f"Pairwise {method} correlation coefficients were computed between {axis} and displayed "
        f"as a heatmap on a diverging colour scale centred at zero.{tail}"
    )
    return text, ([SCIPY] if clustered else [])


def _upset(p: dict):
    mode = str(p.get("mode", "distinct")).lower()
    semantics = (
        "each element assigned to the intersection of exactly the sets it belongs to"
        if mode != "inclusive"
        else "each combination counting every element belonging to at least those sets"
    )
    text = (
        f"Set membership was summarized as an UpSet plot: intersection sizes ({semantics}) are "
        f"shown as bars above a dot-matrix of set membership, with the top {p.get('max_intersections', 20)} "
        f"intersections of size at least {p.get('min_size', 1)} displayed."
    )
    return text, [UPSET]


def _line(p: dict):
    err = str(p.get("error", "sem")).lower()
    err_txt = {"sem": "the standard error of the mean", "sd": "one standard deviation",
               "ci95": "a 95% confidence interval (t-quantile)",
               "minmax": "the observed minimum and maximum"}.get(err, "the standard error of the mean")
    spread = str(p.get("spread", "band")).lower()
    how = {"band": "a shaded band", "error_bars": "error bars",
           "individual": "the individual replicate curves",
           "both": "a shaded band and the individual replicate curves",
           "none": "no spread"}.get(spread, "a shaded band")
    series = str(p.get("series") or "").strip()
    grouping = f" separately for each {series}" if series else ""
    text = (
        f"Values were plotted against the x variable{grouping}, with observations sharing an x "
        f"treated as replicates at that point. Each point shows the mean, and {how} shows "
        f"{err_txt}"
    )
    text += "; the x-axis is logarithmic." if _truthy(p.get("log_x")) else "."
    text += (" The per-point mean, spread and replicate count are reported in the accompanying "
             "table.")
    return text, []


def _venn(p: dict):
    named = str(p.get("sets") or "").strip()
    which = (f"the sets {named}" if named
             else "the three largest sets in the membership matrix")
    text = (
        f"Set overlaps were drawn as a Venn diagram over {which}. Each element was assigned to "
        "the region of exactly the sets it belongs to, so the regions are disjoint and their "
        "counts sum to the union"
    )
    text += (", with each region's share of the union shown alongside its count."
             if _truthy(p.get("show_percent")) else ".")
    text += (" Region counts and per-set totals are reported in full in the accompanying table.")
    return text, [UPSET]


def _forest(p: dict):
    level = float(p.get("conf_level", 0.95) or 0.95)
    order = str(p.get("sort_by", "significance")).lower()
    ordering = {
        "significance": "ordered by significance",
        "effect": "ordered by absolute effect size",
        "label": "ordered alphabetically",
    }.get(order, "in table order")
    ref = float(p.get("ref_line", 0.0) or 0.0)
    text = (
        f"Effect sizes were displayed as a forest plot for the top {p.get('top_n', 15)} features, "
        f"{ordering}, with each point showing the estimated effect and horizontal bars spanning "
        f"its {level:.0%} confidence interval against a reference line at {ref:g}. Intervals were "
        "taken from the input table's own confidence bounds where present; otherwise they were "
        "derived as effect ± z·SE from the reported standard error, or from the "
        "t-statistic via SE = effect / t. Features whose interval excludes the reference value "
        "are distinguished by direction."
    )
    return text, [SMYTH]


def _qq(p: dict):
    text = (
        "Test calibration was assessed with a quantile-quantile plot of observed against expected "
        "−log10 p-values under the uniform null"
    )
    text += (", with a pointwise 95% confidence band derived from the Beta(i, n−i+1) "
             "distribution of the i-th order statistic"
             if _truthy(p.get("band", True)) else "")
    text += (". The genomic inflation factor λ was computed as the median observed "
             "chi-square statistic (1 df) divided by its null expectation; λ ≈ 1 "
             "indicates a calibrated test, while λ > 1 indicates inflation. λ was "
             "computed from raw, uncorrected p-values over all tested features, independently of "
             "any thinning applied for display.")
    return text, [SCIPY]


def _scorecard(p: dict):
    norm = (
        " Each metric was min–max normalized to [0,1] so differently-scaled scores are comparable."
        if p.get("normalize", True) else ""
    )
    inv = ""
    raw = str(p.get("invert_metrics") or "").strip()
    if raw:
        names = ", ".join(s.strip() for s in raw.split(",") if s.strip())
        inv = (
            f" Metrics where lower is better ({names}) were inverted so that higher values "
            "always indicate better performance."
        )
    if str(p.get("layout") or "radar").lower() == "heatmap":
        text = (
            "Conditions were compared across multiple metrics as a colour-coded scorecard heatmap "
            f"(metrics in rows, conditions in columns).{norm}{inv}"
        )
    else:
        text = (
            "Conditions were compared across multiple metrics on a radar (spider) chart, one filled "
            f"polygon per condition.{norm}{inv}"
        )
    return text, []


def _normalization_qc(p: dict):
    groupby = p.get("groupby", "sample")
    text = (
        "Per-cell quality-control metrics — total counts, genes detected per cell, and the "
        "percentage of mitochondrial reads — were computed with Scanpy and displayed as violin "
        f"distributions split by {groupby}."
    )
    citations = [SCANPY]
    if str(p.get("filter")).lower() in ("true", "1", "yes"):
        nmads = p.get("nmads", 3.0)
        text += (
            " Low-quality cells were then removed with an adaptive outlier procedure (scater/OSCA): "
            f"within each {groupby}, cells whose log-transformed library size or number of detected "
            f"genes fell more than {nmads} median absolute deviations (MADs) below the median, or "
            f"whose mitochondrial percentage exceeded {nmads} MADs above the median, were discarded. "
            "Adaptive thresholds adjust to per-batch sequencing depth and capture efficiency without "
            "manual cutoffs."
        )
        citations = [SCANPY, SCATER, SCIPY]
    if str(p.get("doublets")).lower() in ("true", "1", "yes"):
        thr = float(p.get("doublet_threshold", 0.25))
        text += (
            f" Doublets were identified per capture ({groupby}) with Scrublet, which simulates "
            "artificial doublets from random pairs of observed transcriptomes and scores each cell "
            f"by its similarity to the simulated doublets; cells with a doublet score above {thr:g} "
            "were flagged."
        )
        citations = [*citations, SCRUBLET]
    return text, citations


def _sankey(p: dict):
    text = (
        "Quantities flowing between categories were displayed as a Sankey (alluvial) diagram, in "
        "which node and link thickness are proportional to the flow value summed over the input "
        "edge list."
    )
    return text, []


def _string_network(p: dict):
    text = (
        "Protein-protein interactions among the input genes were retrieved from the STRING database "
        f"(species {p.get('species', 9606)}, minimum combined score {p.get('required_score', 400)}/1000) "
        "and displayed as an editable interaction network, with nodes coloured by mean log2 fold "
        "change where available (otherwise by node degree) and edges representing STRING interactions."
    )
    return text, [STRING]


# How the run filled its dropouts — the choice that MOVES a proteomics fold-change further than the
# choice of test does, and which the paragraph asserted as "mean-imputed" on every run.
_IMPUTE_PHRASE = {
    "mean": ("residual missing values imputed within each group at the protein's observed group "
             "mean, which biases genuinely missing-not-at-random dropouts toward no change"),
    "mindet": ("residual missing values imputed per sample from the 1st percentile of that "
               "sample's observed intensities, a deterministic detection-limit proxy for "
               "missing-not-at-random dropouts"),
    "minprob": ("residual missing values imputed per sample by a downshifted-normal draw (mean "
                "− 1.8 SD, width 0.3 SD; seeded, so the run is reproducible), the Perseus "
                "left-censored treatment for missing-not-at-random dropouts"),
}


def _proteomics_de(p: dict):
    moderated = str(p.get("stats") or "welch").lower() == "moderated"
    test = (
        "an empirical-Bayes moderated t-test (limma-style shrinkage of the per-protein variance "
        "toward a global prior estimated across all proteins), which improves power at small "
        "sample sizes"
        if moderated else "a Welch (unequal-variance) t-test"
    )
    # `log_input` means the intensities ARRIVED on a log scale and the runner does NOT transform
    # them — the paragraph opened by claiming a log2 transform that had not happened.
    prep = ("Protein intensities were taken as already log-scaled and median-normalized across "
            "samples" if to_bool(p.get("log_input", False)) else
            "Protein intensities were log2-transformed and median-normalized across samples")
    a, b = str(p.get("group_a") or "").strip(), str(p.get("group_b") or "").strip()
    # Which two groups: the contrast is the whole claim, and "the two groups" names neither.
    between = (f"between the sample groups matching '{a}' and '{b}'" if a and b
               else "between the two sample groups")
    impute = _IMPUTE_PHRASE.get(str(p.get("missing") or "mean").strip().lower(),
                                _IMPUTE_PHRASE["mean"])
    text = (
        f"{prep}; proteins "
        f"quantified in at least {float(p.get('min_valid', 0.5)):g} of the samples per group were "
        f"tested for differential abundance {between} with {test}, with {impute}. P-values were "
        f"corrected by the Benjamini-Hochberg procedure and the result drawn as a volcano "
        f"(|log2FC| ≥ {float(p.get('fc_threshold', 1.0)):g}, FDR ≤ "
        f"{float(p.get('fdr_threshold', 0.05)):g}), with the top "
        f"{int(p.get('top_n', 10) or 0)} by significance labelled."
    )
    return text, ([SMYTH, BH, SCIPY] if moderated else [BH, SCIPY])


def _pvca(p: dict):
    factors = ", ".join(s.strip() for s in str(p.get("factors") or "").split(",") if s.strip())
    factor_txt = f"the {factors} factors" if factors else "the annotated sample factors"
    # The runner ALWAYS mean-centres and scales to unit variance only when `normalize` is set
    # (skills/pvca/run_real.py:38-42). Saying "standardized" unconditionally described a step the
    # run may not have taken — harmless while the knob was API-only, a printed-vs-computed
    # mismatch now that it renders as the "Scale features" switch.
    scaling = ("standardized (mean-centred and scaled to unit variance)"
               if p.get("normalize", True) else
               "mean-centred, without scaling to unit variance,")
    text = (
        "The contribution of known sources of variation was quantified by Principal Variance "
        f"Component Analysis. Features were {scaling} and decomposed by principal-component "
        f"analysis; the leading components explaining {float(p.get('pct_threshold', 0.6)):g} of the "
        f"total variance were retained, and for each the variance attributable to {factor_txt} was "
        "estimated by one-way analysis of variance. The per-component fractions were weighted by "
        "each component's share of the total variance and summed, apportioning the overall variance "
        "across factors (the remainder being unexplained residual)."
    )
    return text, [PVCA, SKLEARN]


def _regression(p: dict):
    x = str(p.get("x") or "").strip() or "the predictor"
    y = str(p.get("y") or "").strip() or "the response"
    text = (
        f"The relationship between {y} and {x} was assessed by ordinary-least-squares linear "
        "regression (SciPy), with the fitted line shown over the scatter and the coefficient of "
        "determination (R²), slope, and regression p-value reported."
    )
    return text, [SCIPY]


def _boxplot(p: dict):
    """Both of this template's original claims were UNCONDITIONAL and both are conditional facts —
    the class of defect the two-directional prose↔param guard exists to surface.

    ``style="strip"`` hides the box entirely (zero width, no fill) and draws every individual value,
    so "box-and-whisker … whiskers extending to 1.5× the IQR" described furniture the reader could
    not see. And ``order`` puts the categories the user named FIRST, in the order given, with only
    the remainder following the descending-median sort — so "groups are ordered by descending
    median" is true exactly when the user named none.
    """
    cites: list[str] = []
    horizontal = str(p.get("orientation", "v")).lower().startswith("h")
    axis = "horizontally" if horizontal else "vertically"
    group = str(p.get("group") or "").strip()
    value = str(p.get("value") or "").strip()
    what = f"{value or 'the measured value'} across {group or 'each group'}"

    strip = str(p.get("style", "box")).strip().lower() == "strip"
    if strip:
        # No box is drawn, so no IQR/whisker claim may be made. Naming the trade is the point of
        # the mode: a box implies more data than a small n has.
        body = (f"The distribution of {what} was shown as {axis}-oriented strip plots, with every "
                "individual value plotted and no box summary drawn")
    else:
        notch = (", and notches marking a confidence interval around the median"
                 if to_bool(p.get("notched", False)) else "")
        drawn = {"all": ", with every individual value overlaid",
                 "suspectedoutliers": ", with suspected outliers marked",
                 "outliers": ", with outliers marked"}.get(
                     str(p.get("points", "outliers")).strip().lower(), "")
        body = (f"The distribution of {what} was summarized as {axis}-oriented box-and-whisker "
                f"plots, each box spanning the interquartile range with the median marked and "
                f"whiskers extending to 1.5× the IQR{notch}{drawn}")

    named = [s.strip() for s in str(p.get("order") or "").split(",") if s.strip()]
    ordering = (f"; {', '.join(named)} lead in that order, with the remaining groups by descending "
                "median" if named else "; groups are ordered by descending median")
    counts = "; each label carries its group's n" if to_bool(p.get("add_count", False)) else ""

    text = body + ordering + counts + "."

    # The pairwise sentence is emitted ONLY when a comparison was actually requested — the stars are
    # a published claim, so the test behind them and any multiplicity correction have to be named
    # rather than left to the Statistics table alone.
    # The citations follow the CLAIMS, not the skill. A paragraph that names a statistical test and
    # the Benjamini-Hochberg procedure and then cites nothing is the same printed-vs-computed gap in
    # the bibliography that the prose↔param guard closes in the prose: the reader is given a method
    # they cannot look up. `_pairwise_prose` returns ("", []) when no pair was named, because a box
    # plot that tested nothing owes no reference.
    sentence, sig_cites = _pairwise_prose(p.get("pairs"), p.get("sig_test"), p.get("correction"))
    return text + sentence, cites + sig_cites


# How each GSEA engine is named in prose, and what it owes the bibliography. `inhouse` cites no
# tool on purpose — it is Selom's own numpy implementation of the Subramanian method, which is
# already cited, and crediting a package that never ran is the defect this table exists to fix.
_GSEA_ENGINES = {
    "gseapy": ("pre-ranked Gene Set Enrichment Analysis (gseapy.prerank)", [GSEAPY]),
    "blitzgsea": (
        "pre-ranked Gene Set Enrichment Analysis (blitzGSEA, with gamma-distribution-approximated "
        "p-values)", [BLITZGSEA],
    ),
    "inhouse": (
        "pre-ranked Gene Set Enrichment Analysis (an in-house weighted Kolmogorov-Smirnov "
        "implementation)", [],
    ),
}


def _gsea_run(p: dict) -> dict:
    """What the run resolved — engine, permutation count, whether an FDR was corrected.

    Prefers the runner's recorded fact (`_gsea_run`, lifted from ``layout.meta``). Falling back to
    the params is only for replay from recorded config (litsynth), where no figure is at hand: an
    explicit ``engine`` is honoured, and ``auto`` is reported as gseapy because that is what it
    selects wherever gseapy is importable — the shipped configuration, and the previous
    unconditional claim.
    """
    fact = p.get("_gsea_run")
    if isinstance(fact, dict):
        return fact
    engine = str(p.get("engine") or "auto").strip().lower()
    if engine not in _GSEA_ENGINES:
        engine = "gseapy"
    return {
        "engine": engine,
        # Mirrors skills/gsea/run_real._perm_count: both library engines floor at 100 and read an
        # explicit 0 as the default, so the raw param is not the number the run used.
        "n_perm": int(p.get("n_perm", 1000)) if engine == "inhouse"
        else max(100, int(p.get("n_perm", 1000)) or 1000),
        "fdr_corrected": not str(p.get("gene_set") or "").strip() and engine != "inhouse",
    }


def _gsea(p: dict):
    pasted = str(p.get("gene_set") or "").strip()
    weight = p.get("weight", 1.0)
    run = _gsea_run(p)
    method, engine_cite = _GSEA_ENGINES.get(str(run.get("engine")), _GSEA_ENGINES["gseapy"])
    n_perm = int(run.get("n_perm", 1000))
    if pasted:
        target = f"a single gene set ('{p.get('set_name') or 'Gene set'}')"
        lib_cite: list[str] = []
    else:
        source = {"go": "the Gene Ontology", "wikipathways": "WikiPathways",
                  "curated": "a curated pathway collection", "reference": "a reference gene-set collection",
                  "all": "the combined gene-set library"}.get(str(p.get("gene_sets") or "go").lower(),
                                                              "the Gene Ontology")
        target = f"every gene set in {source}"
        lib_cite = [GO]
    # A permutation count of zero is not a small test, it is NO test: the in-house engine returns
    # the enrichment score unnormalized and leaves p at 1.0. Claiming "0 permutations ... to yield
    # a normalized enrichment score and empirical p-value" would describe a result that was never
    # computed, so the sentence changes rather than the number in it.
    if n_perm > 0:
        significance = (
            f"significance was assessed against {n_perm} gene-set permutations to yield a "
            "normalized enrichment score (NES) and empirical p-value"
        )
    else:
        significance = (
            "no permutation test was run, so the enrichment score is reported unnormalized and "
            "without an empirical p-value"
        )
    # Benjamini-Hochberg across sets exists only in library mode. A pasted single set has nothing
    # to correct across, and the in-house engine computes no q at all — the paragraph claimed the
    # correction (and cited it) on both.
    if run.get("fdr_corrected"):
        significance += (
            ", with false-discovery rates corrected across sets by the Benjamini-Hochberg procedure"
        )
        fdr_cite = [BH]
    else:
        fdr_cite = []
    text = (
        "Genes were ranked by their signed differential-expression metric (log2 fold change or a "
        f"signed test statistic) and tested for coordinated enrichment by {method} against "
        f"{target}. A running enrichment score was accumulated along the ranked list with the "
        f"Kolmogorov-Smirnov statistic weighted by the metric (exponent {float(weight):g}); "
        f"{significance}. The running enrichment curve, leading-edge hits, and ranked metric "
        "are shown."
    )
    return text, [GSEA, *engine_cite, *lib_cite, *fdr_cite]


def _ssgsea(p: dict):
    pasted = str(p.get("gene_set") or "").strip()
    if pasted:
        target = "a user-supplied gene set"
        lib_cite: list[str] = []
    else:
        source = {"go": "the Gene Ontology", "wikipathways": "WikiPathways",
                  "curated": "a curated pathway collection", "reference": "a reference gene-set collection",
                  "all": "the combined gene-set library"}.get(str(p.get("gene_sets") or "go").lower(),
                                                              "the Gene Ontology")
        target = f"every gene set in {source}"
        lib_cite = [GO]
    weight = p.get("weight", 0.25)
    min_size, max_size = p.get("min_size", 10), p.get("max_size", 500)
    fact = p.get("_ssgsea_run")
    fact = fact if isinstance(fact, dict) else {}
    # `top_n` is a CAP: `order[:top_n]` yields fewer rows whenever the library scored fewer sets
    # than the cap, and the paragraph quoted the cap as though it were the count. The runner
    # records what it actually drew (the figure title has always stated it); the param is the
    # fallback for replay from recorded config, where no figure is at hand.
    shown = int(fact.get("shown", p.get("top_n", 25)))
    # Prefer the runner's resolved boolean; `to_bool` is the fallback, matching the coercion the
    # runner applies to RAW params. Not a live defect on this path — `resolved_params` already
    # casts by the declared `bool` type, so the string "false" arrives here as False — but the two
    # sides now agree by construction rather than by both happening to be right.
    zscored = bool(fact["zscore"]) if "zscore" in fact else to_bool(p.get("zscore", True))
    norm = " Per-pathway scores were z-scored across samples for display." if zscored else ""
    text = (
        "Per-sample pathway activity was quantified by single-sample Gene Set Enrichment "
        "Analysis (ssGSEA; gseapy.ssgsea). Within each sample, genes were rank-normalized and a "
        f"normalized enrichment score was computed for {target} as a Kolmogorov-Smirnov-like "
        f"statistic over the ranked list, weighted by the rank (exponent {float(weight):g}); no "
        "differential-expression test or permutation was required. Gene sets with fewer than "
        f"{int(min_size)} or more than {int(max_size)} detected members were excluded. The "
        f"{shown} most variable gene sets across samples are shown as a sample x pathway "
        f"heatmap.{norm}"
    )
    return text, [SSGSEA, GSEAPY, *lib_cite]


def _go_graph(p: dict):
    ns = str(p.get("namespace") or "").strip()
    ns_txt = (
        f" restricted to the {ns} namespace" if ns
        else " across the biological-process, cellular-component and molecular-function namespaces"
    )
    text = (
        f"Differentially expressed genes (|log2FC| >= {p['fc_threshold']}, FDR <= {p['fdr_threshold']}) "
        "were tested for over-representation against Gene Ontology terms using the hypergeometric "
        "distribution, with p-values corrected across terms by the Benjamini-Hochberg procedure. The "
        f"top {p['top_n']} enriched terms{ns_txt} are drawn in their is_a/part_of hierarchy as an "
        "editable node-link graph, each node coloured by its -log10 adjusted p-value."
    )
    return text, [GO, BH]


def _cepo(p: dict):
    norm = (
        "Counts were normalized to 10,000 per cell and log1p-transformed, and "
        if p.get("normalize", True) else ""
    )
    text = (
        f"Cell-identity marker genes were identified per {p.get('group_key') or 'cell-type'} group with "
        "Cepo, which ranks genes by differential stability — combining how highly and how stably each "
        f"gene is expressed within a group relative to the rest — rather than by mean difference. {norm}"
        # `min_cells` filters CELL TYPES, not genes (skills/proprietary/cepo/run_real.py:69 —
        # `types = [t for t in unique(labels) if (labels == t).sum() >= min_cells]`). The prose
        # described a per-gene detection filter the runner never applies at that value.
        f"cell types with at least {p['min_cells']} cells were scored, using genes expressed in at least "
        f"{float(p['exprs_pct']):g} of cells, and the top {p['n_genes']} differential-stability "
        "genes per group are reported. This is a clean-room Python reimplementation of the Cepo method."
    )
    return text, [CEPO, SCANPY]


def _erg_adaptation(p: dict) -> str:
    """Resolve the recording adaptation for the methods wording.

    Two things this used to get wrong, both of which put the WRONG WORD in the first sentence of
    an ERG methods paragraph — the one that says whether the reader is looking at rod or cone
    physiology:

    * it read ``adaptation`` only, but every ERG runner resolves the flash mode through
      ``_erg.resolve_flash_mode``, where an explicit ``stimulus_type`` **wins** over the friendly
      hint. A figure run with ``stimulus_type="photopic_flash"`` and the default ``adaptation="auto"``
      is photopic, and the prose called it scotopic.
    * with ``adaptation="auto"`` the mode is a fact about the DATA (the first of scotopic→photopic
      actually present in the export), which no parameter can tell you. So the runner records what
      it resolved in ``layout.meta.adaptation`` and ``build_body`` lifts it — the ``_significance``
      pattern. Absent (litsynth replaying from recorded params alone) we fall back to the
      param-derived answer, which is exact whenever either knob was set explicitly.
    """
    recorded = str(p.get("_adaptation") or "").strip().lower()
    if recorded in ("scotopic", "photopic"):
        return recorded
    return _erg.adaptation_mode(p.get("adaptation", "auto"), p.get("stimulus_type", ""))


def _erg_manual_marks(p: dict, device_may_win: bool = False) -> str:
    """The sentence that discloses OPERATOR-SET landmark times (erg-manual-marks R6).

    A manual mark moves the time at which the a-/b- (or N1/P1) landmark is read, and the runner
    RE-MEASURES the amplitude there — so the numbers on the figure are not the ones the automatic
    window produced. That is a provenance fact of the same weight as ``ab_detector``, and the
    paragraph described the automatic construction as if it were the whole story.

    ``device_may_win`` is the honest qualifier for the two skills where a supplied device-metrics
    table outranks the marks (``erg_bwave_bar`` / ``erg_intensity_response`` apply them only on the
    measure-from-traces path); stating the rule keeps the sentence true under both inputs rather
    than inventing a second printed-vs-computed gap while closing one.
    """
    marks = _erg.parse_manual_marks(p.get("manual_marks", ""))
    if not marks:
        return ""
    n = len(marks)
    scope = (" where amplitudes were measured from the traces (device markers, when the input "
             "carries them, remain authoritative)" if device_may_win else "")
    return (f" Landmark times were set by the operator for {n} segment(s) rather than taken from "
            f"the automatic window, and the amplitudes re-measured at those times{scope}.")


# What an error bar MEANS. `_charts.ERR_LABEL` is the figure-side abbreviation ("SEM"); this is its
# prose half, and the two must agree or the paragraph and the axis label describe different numbers.
_SPREAD_PHRASE = {
    "sem": "the standard error of the mean",
    "sd": "the standard deviation",
    "ci95": "a 95% confidence interval",
    "minmax": "the range from minimum to maximum",
}


def _spread_phrase(error) -> str:
    """``error`` → the phrase naming what the bar/band spans. Defaults to SEM, matching every
    runner's own default, so a paragraph never silently promotes an SD bar to a standard error."""
    return _SPREAD_PHRASE.get(str(error or "sem").strip().lower(), _SPREAD_PHRASE["sem"])


# The statistical vocabulary shared by every skill that draws significance brackets. One home: the
# figure gets its stars from `_stats.test_pairs`, and this is the sentence describing that same
# call — `boxplot` and `erg_bwave_bar` name the identical tests and corrections.
_SIG_TEST_LABEL = {
    "welch": "Welch's t-test (unequal variances)",
    "student": "Student's t-test (equal variances)",
    "mannwhitney": "the Mann-Whitney U test",
    "mwu": "the Mann-Whitney U test",
    "u": "the Mann-Whitney U test",
}
_CORRECTION_CLAUSE = {
    "bonferroni": " p-values were adjusted for multiple comparisons using the Bonferroni correction",
    "bh": " p-values were adjusted for multiple comparisons using the Benjamini-Hochberg procedure",
}


def _pairwise_prose(raw_pairs, sig_test, correction, *, subject: str = "groups"):
    """``(sentence, citations)`` for a figure's significance brackets — ``("", [])`` when no
    comparison was asked for, because a figure that tested nothing owes no test and no reference.

    Two claims are made conditional here. The **test** and the **multiplicity correction** are named
    because the stars are a published claim and silence about multiplicity reads as "corrected". And
    a pair carrying an OVERRIDE (``"A~B:**"`` / ``"A~B:0.003"``) was **not** computed by that test —
    the operator supplied the star — so the sentence says which pairs Selom actually tested rather
    than crediting the named test with all of them.
    """
    pairs = _stats.parse_pairs(raw_pairs)
    if not pairs:
        return "", []
    label = _SIG_TEST_LABEL.get(str(sig_test or "welch").strip().lower(), _SIG_TEST_LABEL["welch"])
    corr = str(correction or "none").strip().lower()
    adjust = _CORRECTION_CLAUSE.get(corr, " p-values are uncorrected for multiple comparisons")
    n_over = sum(1 for _a, _b, override in pairs if override)
    if n_over == len(pairs):
        # Nothing was computed — naming a test here would credit it with every star on the figure,
        # and citing SciPy would point the reader at software that never ran for this claim.
        return (f" Significance brackets were drawn for {len(pairs)} named pair(s) of {subject} "
                f"from operator-supplied values; no test was computed for them."), []
    cites = [SCIPY] + ([BH] if corr == "bh" else [])
    if n_over:
        return (f" Significance brackets were drawn for {len(pairs)} named pair(s) of {subject}, of "
                f"which {n_over} show operator-supplied values rather than a computed test; the "
                f"remaining {len(pairs) - n_over} pair(s) were compared with "
                f"{label};{adjust}."), cites
    return (f" Named pairs of {subject} were compared with {label}, and significance brackets "
            f"drawn on the figure;{adjust}."), cites


def _erg_ab_detector(p: dict) -> str:
    """The sentence that makes a ``robust``-detector measurement reproducible (A18).

    ``ab_detector`` selects a materially DIFFERENT measurement: ``robust`` seeds the landmarks with
    Savitzky-Golay smoothing plus prominence-gated peak picking behind a noise gate at 2 × 1.96 × SD
    of the pre-stimulus baseline, falling back to the windowed extremum when nothing clears it — so
    the a-/b-wave amplitudes and implicit times it produces differ from the default windowed path. A
    reader given only the windowed construction cannot reproduce numbers made under ``robust``.

    Returns "" for the default detector: the existing prose already describes it exactly, so every
    windowed figure's methods paragraph stays byte-identical.
    """
    if str(p.get("ab_detector", "windowed")).strip().lower() != "robust":
        return ""
    txt = (
        " Landmarks were seeded by the robust detector: the trace was smoothed with a second-order "
        "Savitzky-Golay filter and the a-/b-wave were picked as prominence-gated extrema clearing a "
        "noise gate of 2 x 1.96 x SD of the pre-stimulus baseline, falling back to the windowed "
        "extremum when no deflection cleared that gate."
    )
    # Which measurements actually sat at the noise floor, when the runner recorded it
    # (``layout.meta.ab_detector``, lifted by ``build_body``). Absent — a litsynth replay from
    # recorded params only — the sentence stops at the construction rather than claiming an outcome.
    d = p.get("_ab_detector")
    if isinstance(d, dict) and d.get("n_segments"):
        n = int(d["n_segments"])
        fell = [(role, int(d.get(f"{role}_fallback") or 0)) for role in ("a", "b")]
        named = [f"the {role}-wave in {k} of {n}" for role, k in fell if k]
        if named:
            joined = " and ".join(named)
            txt += (f" {joined[0].upper()}{joined[1:]} measured segment(s) did not clear that gate and were "
                    f"measured by the windowed fallback, i.e. at the noise floor "
                    f"(gate {float(d.get('threshold_uv_max') or 0.0):g} uV).")
        else:
            txt += (f" All landmarks in all {n} measured segment(s) cleared that gate "
                    f"(gate {float(d.get('threshold_uv_max') or 0.0):g} uV).")
    return txt


def _erg_inner_retinal(p: dict) -> str:
    """The OP / PhNR sentences for the trace-grid methods (L1-09).

    Both metrics are opt-in, so the default paragraph is unchanged. Where the runner recorded a
    group summary (``layout.meta.oscillatory_potentials``), the prose states how many segments were
    EXCLUDED as not measurable — a mean that quietly absorbed them as zeros would be the A17 defect
    wearing a methods-paragraph disguise.
    """
    txt = ""
    if _truthy(p.get("oscillatory_potentials")):
        txt += (
            " Oscillatory potentials were extracted from the same baseline-corrected traces with a "
            "zero-phase 75-300 Hz Butterworth band-pass (the ISCEV OP band, upper edge clamped below "
            "Nyquist), each wavelet measured from its peak to the preceding trough; the summed "
            "amplitude and the integrated RMS of the band-passed signal are reported. Traces too "
            "short to filter, or with too few samples in the analysis window, are reported as not "
            "measurable rather than as zero, and are excluded from group means."
        )
        g = p.get("_op_group")
        if isinstance(g, dict) and g.get("n_not_measurable"):
            txt += (f" {int(g['n_not_measurable'])} of "
                    f"{int(g['n_not_measurable']) + int(g.get('n') or 0)} segment(s) were not "
                    f"measurable and were excluded.")
    if _truthy(p.get("phnr")):
        txt += (
            " The photopic negative response was measured on the same traces as the amplitude from "
            "the pre-stimulus baseline to the negative trough following the b-wave peak, with its "
            "implicit time reported; a trace with no post-b-wave segment is reported as not measured."
        )
    return txt


def _truthy(v) -> bool:
    return str(v).strip().lower() not in ("", "false", "0", "no", "none")


def _erg_central(p: dict) -> str:
    """What each panel's drawn trace IS — the claim ``central`` decides and the paragraph used to
    make unconditionally.

    The original text said "a single representative eye is shown … representatives are labelled as
    such **rather than shown as group means**". ``central="mean"`` averages the n recordings at each
    time point and titles the figure "Mean … ERG", so the methods paragraph contradicted the figure's
    own title; ``central="none"`` draws every replicate at equal weight and shows no exemplar at all.

    The spread overlay travels with the mean branch for the same reason: a shaded band is a
    quantitative claim, and which quantity it spans (``error``) is nowhere else in the figure.
    """
    central = str(p.get("central", "representative")).strip().lower()
    if central == "mean":
        spread = str(p.get("spread", "band")).strip().lower()
        drawn = {
            "band": f"a shaded band spanning {_spread_phrase(p.get('error'))}",
            "error_bars": f"error bars spanning {_spread_phrase(p.get('error'))}",
            "both": (f"a shaded band and error bars, each spanning "
                     f"{_spread_phrase(p.get('error'))}"),
            "individual": "the contributing recordings overlaid faintly behind it",
        }.get(spread, "")
        # band/error_bars need n>=2 or the runner degrades to the bare mean line, so the claim is
        # made as "where more than one recording contributed" rather than unconditionally.
        overlay = (f", with {drawn} where more than one recording contributed"
                   if drawn and spread != "individual" else (f", with {drawn}" if drawn else ""))
        return ("For each condition and flash step the recordings were averaged point-by-point into "
                f"a mean trace{overlay}; cataractous or failed-acquisition eyes were excluded.")
    if central == "none":
        return ("For each condition and flash step every contributing recording is drawn at equal "
                "weight, with no averaged trace; cataractous or failed-acquisition eyes were "
                "excluded. The a/b-wave table reports the cohort mean.")
    role = str(p.get("role", "representative")).strip()
    named = f" (the rows marked '{role}')" if role and role != "representative" else ""
    return ("For each condition a single representative eye is shown"
            f"{named}, selected as the eye whose full amplitude-versus-intensity series lay closest "
            "(minimum sum-of-squared deviations) to its group mean; cataractous or "
            "failed-acquisition eyes were excluded, and representatives are labelled as such rather "
            "than shown as group means.")


def _erg_traces(p: dict):
    filtered = str(p.get("filter", True)).lower() not in ("false", "0", "no")
    lp = float(p.get("lowpass_hz", 120.0) or 120.0)
    display = (
        f"For display, traces were notch-filtered to remove mains/instrument line noise and "
        f"low-pass filtered at {lp:g} Hz while preserving the oscillatory potentials; "
        if filtered else ""
    )
    representative = _erg_central(p) + _erg_manual_marks(p)
    if _erg_adaptation(p) == "photopic":
        text = (
            "Full-field photopic (cone-driven) electroretinograms were recorded after light "
            "adaptation against a rod-suppressing background. Responses were elicited by "
            "light-adapted flashes; sweeps were averaged within each step and baseline-corrected to "
            f"the pre-stimulus mean. {display}the b-wave was measured from the cornea-negative "
            "trough to the following cornea-positive peak (the cone a-wave is small or absent under "
            f"photopic conditions).{_erg_ab_detector(p)}{_erg_inner_retinal(p)} {representative}"
        )
        return text, [ISCEV]
    ladder = ", ".join(f"{v:g}" for v in _erg.INTENSITIES_LOG)
    text = (
        "Full-field scotopic (rod-driven) electroretinograms were recorded from overnight "
        "dark-adapted mice. Responses were elicited by a series of flashes of increasing energy "
        f"(e.g. {ladder} log cd·s/m²); sweeps were averaged within each intensity and "
        f"baseline-corrected to the pre-stimulus mean. {display}the a-wave was measured from "
        "baseline to the initial cornea-negative trough and the b-wave from that trough to the "
        f"following cornea-positive peak.{_erg_ab_detector(p)}{_erg_inner_retinal(p)} {representative}"
    )
    return text, [ISCEV]


def _wave_label(col: str) -> str:
    """Value column → the landmark it names. Takes the resolved COLUMN rather than the params dict
    because ``wave`` exists on the bar and not on the intensity-response curve, and each template
    must reference only its own skill's vocabulary (the first guard is exact in that direction)."""
    return {"a_wave_uv": "a-wave", "b_wave_uv": "b-wave"}.get(str(col).strip(), str(col).strip())


def _erg_bwave_bar(p: dict):
    mode = _erg_adaptation(p)
    # Which measurement is plotted: `wave` selects a/b and `value_col` overrides it outright (empty
    # = derive from `wave`), exactly as the runner resolves it. The paragraph said "b-wave"
    # unconditionally, so an a-wave figure — one the parameter panel offers — shipped with prose
    # naming the other landmark entirely.
    wave_sel = "a" if str(p.get("wave", "b")).strip().lower() == "a" else "b"
    wave = _wave_label(str(p.get("value_col") or "").strip() or f"{wave_sel}_wave_uv")
    # `wave`/`value_col` decide WHICH landmark; a-wave is measured from baseline to the initial
    # cornea-negative trough, b-wave trough-to-peak — two different constructions, so the sentence
    # describing the measurement follows the same switch as the label.
    how = ("from the pre-stimulus baseline to the initial cornea-negative trough"
           if wave == "a-wave" else
           "as the trough-to-peak b-wave" if wave == "b-wave" else f"as {wave}")
    step = str(p.get("intensity_group") or "").strip()
    at = f" at flash step {step}" if step else " at a single flash intensity"
    # `show_error` can remove the error bar entirely and `error` decides what it spans — the
    # paragraph claimed a standard error on every run, including the ones that draw no bar at all.
    spread = (f" with {_spread_phrase(p.get('error'))}"
              if to_bool(p.get("show_error", True)) else " and no error bar")
    points = (", and every eye is overlaid as an individual data point"
              if to_bool(p.get("points", True)) else ", without the individual eyes overlaid")
    sig, cites = _pairwise_prose(p.get("comparisons"), p.get("sig_test"), p.get("correction"),
                                 subject="conditions")
    text = (
        f"Peak {mode} {wave} amplitudes{at} were compared across conditions. "
        f"Each bar shows the group mean{spread}{points}. Amplitudes were measured {how} on "
        "baseline-corrected, intensity-averaged traces; cataractous or failed-acquisition eyes were "
        f"excluded.{_erg_ab_detector(p)}{_erg_manual_marks(p, True)}{sig}"
    )
    return text, [ISCEV] + cites


def _erg_intensity_response(p: dict):
    mode = _erg_adaptation(p)
    # `value_col` is this skill's whole measurement selector (there is no `wave` knob) — its default
    # is the b-wave, but a run against `a_wave_uv` was described as a b-wave curve.
    wave = _wave_label(str(p.get("value_col") or "b_wave_uv"))
    # `spread` decides whether any spread is DRAWN and `error` decides what it spans; the paragraph
    # promised "mean ± standard error" on every run, including `spread="none"` (a bare mean curve)
    # and `error="sd"` (a wider bar the reader would have read as a standard error).
    spread = str(p.get("spread", "error_bars")).strip().lower()
    shown = {"error_bars": "error bars", "band": "a shaded band",
             "both": "error bars and a shaded band"}.get(spread)
    spread_txt = (f" (mean per condition, with {shown} spanning {_spread_phrase(p.get('error'))})"
                  if shown else " (mean per condition, with no spread drawn)")
    text = (
        f"{mode.capitalize()} {wave} amplitude was plotted against flash intensity for each "
        f"condition{spread_txt}."
    )
    cites = [ISCEV]
    # `fit=False` runs the whole skill with NO curve fitting — every word of the Naka-Rushton
    # paragraph, and both of its citations, described a model that never ran.
    if to_bool(p.get("fit", True)):
        slope = float(p.get("nr_slope", 0.0) or 0.0)
        if slope > 0:
            slope_txt = (f"the slope n was fixed at {slope:g} and Vmax and K were estimated")
        else:
            slope_txt = (
                "Vmax, K and the slope n were estimated where the data constrained the slope; for a "
                "responder whose slope was under-constrained, n was fixed at a physiological value "
                "(1.0)"
            )
        # "did not support a saturating fit" IS the `min_r2` threshold — the one number a reader
        # needs to know which conditions were dropped from the fit and why.
        min_r2 = float(p.get("min_r2", 0.3) or 0.0)
        text += (
            " The intensity-response relationship was fit per condition with the Naka-Rushton "
            "function V = Vmax·Iⁿ/(Iⁿ + Kⁿ), where I is flash energy, Vmax the saturated amplitude, "
            f"K the semi-saturation intensity and n the slope; {slope_txt} by bounded non-linear "
            "least-squares regression (SciPy). Conditions whose best fit did not reach R² ≥ "
            f"{min_r2:g} were left unfit."
        )
        cites += [NAKA_RUSHTON, SCIPY]
    else:
        text += " No intensity-response model was fit; the measured points are shown as recorded."
    text += _erg_ab_detector(p) + _erg_manual_marks(p, True)
    return text, cites


def _erg_flicker_fourier(p: dict) -> str:
    """The Fourier-fundamental sentence for the flicker methods (L1-09) — opt-in, so the default
    paragraph is unchanged."""
    if not _truthy(p.get("fourier")):
        return ""
    return (
        " In addition to the time-domain N1-P1, the fundamental Fourier component at the flicker "
        "frequency was measured on the unfiltered averaged sweep by discrete Fourier transform "
        "(DC removed), and its amplitude (2|X|/N) and phase are reported at the transform bin "
        "nearest the stimulus frequency."
    )


def _erg_flicker(p: dict):
    filtered = str(p.get("filter", True)).lower() not in ("false", "0", "no")
    lp = float(p.get("lowpass_hz", 120.0) or 120.0)
    display = (
        f" For display, traces were notch-filtered for mains/instrument line noise and low-pass "
        f"filtered at {lp:g} Hz."
        if filtered else ""
    )
    # `view` picks ONE of two figures, and the sentence describing them claimed both at once: the
    # waveform grid draws no amplitude-versus-frequency plot (so the "also plotted against
    # frequency" half was false on the DEFAULT path), and the summary view returns only that plot
    # and no waveform grid (so the other half was false there).
    shown = (
        "N1–P1 amplitude is plotted against flicker frequency, one series per condition"
        if str(p.get("view", "waveform")).strip().lower() == "summary" else
        "The steady-state waveform is shown per condition and flicker frequency"
    )
    text = (
        "Light-adapted flicker electroretinograms were recorded under a rod-suppressing background. "
        "For each flicker frequency the steady-state response was phase-averaged into a single "
        "representative cycle, and the N1–P1 amplitude — the cornea-negative trough to the following "
        "cornea-positive peak — together with the P1 implicit time were measured from that averaged "
        f"cycle. {shown}; the N1–P1 amplitude and P1 implicit time are reported for every condition "
        "and frequency in the accompanying table. No a-/b-wave or saturating intensity-response "
        "model is applied, as the flicker "
        "response is a periodic steady-state measure rather than a flash transient."
        f"{_erg_flicker_fourier(p)}{_erg_manual_marks(p, True)}{display}"
    )
    return text, [ISCEV]


def _facs_transform_space(p: dict) -> str:
    """The clause that makes the gate space reproducible (A15).

    Gate bounds travel in transformed display space, so the transform's resolved top-of-scale
    ``t`` (and where it came from) is part of the recipe: without it a reader cannot recompute the
    population counts, and a gate drawn on one export is not portable. ``_transform`` is the
    runner's recorded OUTCOME (``layout.meta.transform``, lifted by ``build_body``); absent — a
    litsynth replay from recorded params only — the clause is omitted rather than guessed.
    """
    xf = p.get("_transform")
    if not isinstance(xf, dict):
        return ""
    if xf.get("t_source") == "not_applicable":
        return ""  # arcsinh is anchored to `cofactor`, already stated
    ts = sorted({float(v) for v in (xf.get("t_per_channel") or {}).values()})
    if not ts:
        return ""
    t_txt = f"{ts[0]:g}" if len(ts) == 1 else "per channel (" + ", ".join(f"{t:g}" for t in ts) + ")"
    src = {
        "param": "pinned by the operator",
        "fcs_pnr": "taken from each channel's $PnR range keyword in the FCS",
        "default": "the standard 18-bit top of scale (the FCS declared no usable $PnR range)",
        "fcs_pnr+default": ("taken from each channel's $PnR range keyword in the FCS, falling back "
                            "to the standard 18-bit top of scale for "
                            + ", ".join(str(c) for c in (xf.get("t_default_channels") or []))),
    }.get(str(xf.get("t_source")), str(xf.get("t_source")))
    shape = ""
    if xf.get("name") == "logicle":
        shape = f", m = {float(xf.get('m', 4.5)):g}, w = {float(xf.get('w', 0.5)):g}, a = {float(xf.get('a', 0.0)):g}"
    elif xf.get("name") == "log":
        shape = f", m = {float(xf.get('m', 4.5)):g}"
    return f" (top of scale T = {t_txt}, {src}{shape})"


def _facs_unresolved_gates(p: dict) -> str:
    """State the populations that were DEFINED but not counted (A16).

    A gate the operator supplied that could not be evaluated used to vanish from the table, so a
    missing row read as a complete result. The table now carries a verdict row per unresolved gate;
    the methods prose must say the same thing, or the printed recipe over-claims what was measured.
    """
    unresolved = p.get("_gates_unresolved")
    if not unresolved:
        return ""
    named = "; ".join(f"{g.get('population')} ({g.get('reason')})" for g in unresolved)
    return (f" {len(unresolved)} defined gate(s) could NOT be evaluated and are reported in the "
            f"population table with no count rather than omitted: {named}.")


def _facs_gating(p: dict):
    comp = str(p.get("compensate", "auto")).strip().lower()
    # `_compensation_applied` is the runner's recorded OUTCOME (run_real writes it into
    # layout.meta; build_body lifts it). Absent — e.g. litsynth replaying from recorded params
    # only — the requested mode is described without asserting it succeeded.
    applied = p.get("_compensation_applied")
    if comp == "none":
        comp_txt = "no fluorescence compensation was applied"
    elif applied is False:
        comp_txt = (
            "fluorescence compensation was requested but NOT applied — the file carried no usable "
            "spillover matrix, so uncompensated events are shown"
        )
    elif comp == "matrix":
        comp_txt = ("an operator-supplied spillover matrix was applied" if applied
                    else "an operator-supplied spillover matrix was requested")
    else:
        comp_txt = ("the acquisition spillover matrix embedded in the FCS ($SPILLOVER) was applied"
                    if applied else
                    "the acquisition spillover matrix embedded in the FCS ($SPILLOVER) was applied "
                    "where present")

    transform = str(p.get("transform", "logicle")).strip().lower()
    if transform == "arcsinh":
        xform_txt = f"an inverse-hyperbolic-sine (arcsinh) transform (cofactor {float(p.get('cofactor', 150.0)):g})"
        xform_cite = []
    elif transform == "log":
        xform_txt = "a decade log transform"
        xform_cite = []
    elif transform == "linear":
        xform_txt = "a linear display scale"
        xform_cite = []
    else:
        xform_txt = "the Logicle (bi-exponential) display transform"
        xform_cite = [LOGICLE]
    xform_txt += _facs_transform_space(p)

    views = {"density": "a two-dimensional density plot", "contour": "a two-dimensional density-contour plot",
             "histogram": "a single-parameter histogram",
             "scatter": "a density-coloured scatter plot"}
    view = views.get(str(p.get("plot", "density")).strip().lower(), "a two-dimensional density plot")

    gated = str(p.get("gates") or "").strip()
    gate_txt = (
        " A hierarchical gate tree (rectangle, polygon and quadrant gates defined in the "
        "transformed display space, following the Gating-ML 2.0 gate definitions) was evaluated by "
        "Selom's own geometry implementation, and each population's event count, frequency of "
        "parent, frequency of total, and median fluorescence intensity were tabulated."
        if gated else
        " Population statistics (event count, frequency of parent, frequency of total, and median "
        "fluorescence intensity) were tabulated for the ungated sample."
    )
    text = (
        "Flow-cytometry standard (FCS) event data were read with FlowIO and compensated and "
        f"transformed with FlowUtils; {comp_txt}, and fluorescence intensities were displayed on "
        f"{xform_txt}. Events are shown as {view}.{gate_txt}{_facs_unresolved_gates(p)}"
    )
    return text, [FLOWIO, FLOWUTILS, *xform_cite, GATINGML]


_TEMPLATES = {
    "umap_scrna": _umap,
    "facs_gating": _facs_gating,
    "erg_traces": _erg_traces,
    "erg_bwave_bar": _erg_bwave_bar,
    "erg_intensity_response": _erg_intensity_response,
    "erg_flicker": _erg_flicker,
    "integration": _integration,
    "boxplot": _boxplot,
    "pvca": _pvca,
    "regression": _regression,
    "gsea": _gsea,
    "ssgsea": _ssgsea,
    "go_graph": _go_graph,
    "cepo": _cepo,
    "proteomics_de": _proteomics_de,
    "cluster": _cluster,
    "violin": _violin,
    "deg": _deg,
    "volcano": _volcano,
    "heatmap": _heatmap,
    "enrichment": _enrichment,
    "pathway": _pathway,
    "markers": _markers,
    "annotate": _annotate,
    "trajectory": _trajectory,
    "pseudotime_genes": _pseudotime_genes,
    "pca": _pca,
    "composition": _composition,
    "diff_abundance": _diff_abundance,
    "corr_heatmap": _corr_heatmap,
    "upset": _upset,
    "line": _line,
    "venn": _venn,
    "forest": _forest,
    "qq": _qq,
    "scorecard": _scorecard,
    "normalization_qc": _normalization_qc,
    "sankey": _sankey,
    "string_network": _string_network,
}


def _generic(spec: SkillSpec, p: dict):
    listed = ", ".join(f"{k}={v}" for k, v in p.items()) or "default parameters"
    return f"Figure generated by the Selom '{spec.title}' skill with {listed}.", []


def attribution(spec: SkillSpec) -> str:
    """The standard Selom attribution sentence for one skill."""
    return f"Analysis was performed using Selom (skill '{spec.id}' v{spec.version})."


def build_body(spec: SkillSpec, params: dict, figure: dict | None = None) -> tuple[str, list[str]]:
    """Methods prose + citations for one skill, WITHOUT the trailing Selom attribution.

    This is the reusable unit the multi-skill synthesizer (``litsynth``) stitches together:
    one attribution sentence belongs at the end of a whole Methods section, not after every
    paragraph. ``build`` wraps this for the single-figure case, so its output is unchanged.

    ``figure`` is the spec the runner actually produced, when available. Params alone cannot say
    whether the significance values were corrected for multiple testing — that is resolved from the
    data's headers at run time — so a runner that fell back to a RAW p-value declares it in
    ``layout.meta.significance`` and the prose drops its Benjamini-Hochberg claim accordingly.
    Omitted (litsynth, replay from recorded params only) keeps the adjusted wording, as before.
    """
    resolved = resolved_params(spec, params)
    meta = ((figure or {}).get("layout") or {}).get("meta") or {}
    if meta.get("significance") == "raw":
        resolved["_significance_adjusted"] = False
    if "compensation_applied" in meta:
        resolved["_compensation_applied"] = bool(meta["compensation_applied"])
    if isinstance(meta.get("transform"), dict):
        resolved["_transform"] = meta["transform"]     # A15 — the resolved gate space
    if meta.get("gates_unresolved"):
        resolved["_gates_unresolved"] = list(meta["gates_unresolved"])  # A16 — populations not counted
    if isinstance(meta.get("ab_detector"), dict):
        resolved["_ab_detector"] = meta["ab_detector"]  # A18 — which ERG detector, and its gate
    if meta.get("adaptation") in ("scotopic", "photopic"):
        # The rod/cone mode the ERG runner RESOLVED. Written only when `adaptation="auto"` let the
        # data decide, which the parameters alone cannot express — the first sentence of an ERG
        # paragraph says whether the reader is looking at rod or cone physiology.
        resolved["_adaptation"] = meta["adaptation"]
    if isinstance(meta.get("oscillatory_potentials"), dict):
        resolved["_op_group"] = meta["oscillatory_potentials"]  # L1-09 — OP segments excluded
    if isinstance(meta.get("clustered"), dict):
        # The runner clustered the cells itself because the requested `groupby` column was absent —
        # a fact about the DATA, and the only record of the `resolution` that produced them.
        resolved["_clustered"] = meta["clustered"]
    if isinstance(meta.get("gsea"), dict):
        # Which GSEA engine ran, how many permutations it was actually given, and whether an FDR
        # was corrected across sets. `engine` DEFAULTS to "auto" and resolves from what is
        # importable, so the params cannot name the statistics that were computed.
        resolved["_gsea_run"] = meta["gsea"]
    if isinstance(meta.get("ssgsea"), dict):
        # `top_n` is a cap, not a count, and `zscore` is read through a string-aware truthiness
        # test the prose did not share. Both are answers only the runner has.
        resolved["_ssgsea_run"] = meta["ssgsea"]
    builder = _TEMPLATES.get(spec.id)
    return builder(resolved) if builder else _generic(spec, resolved)


def build(spec: SkillSpec, params: dict, figure: dict | None = None) -> dict:
    """Methods paragraph + citations for one figure, from its resolved parameters (+ the produced
    figure, when the prose must not out-claim what the runner actually computed — see ``build_body``).
    """
    text, citations = build_body(spec, params, figure=figure)
    text += f" {attribution(spec)}"
    return {"text": text, "citations": citations}

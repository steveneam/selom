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
CEPO = "Kim, H.J., Wang, K., Chen, C. et al. Uncovering cell identity through differential stability with Cepo. Nature Computational Science 1, 784-790 (2021)."
PVCA = "Boedigheimer, M.J. et al. Sources of variation in baseline gene expression levels from toxicogenomics study control animals across multiple laboratories. BMC Genomics 9, 285 (2008)."
HARMONY = "Korsunsky, I. et al. Fast, sensitive and accurate integration of single-cell data with Harmony. Nature Methods 16, 1289-1296 (2019)."
ENTREZ = "Sayers, E.W. et al. Database resources of the National Center for Biotechnology Information. Nucleic Acids Research 50, D20-D26 (2022)."


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


def _violin(p: dict):
    gene = p.get("gene") or "the selected marker gene"
    text = (
        f"Per-group expression of {gene} was visualized as log1p-normalized violin "
        f"distributions grouped by {p['groupby']} (Scanpy)."
    )
    citations = [SCANPY]
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
    text = (
        "Differential-expression results were displayed as a volcano plot of -log10 adjusted "
        f"p-value against log2 fold change. Genes with |log2FC| >= {p['fc_threshold']} and FDR <= "
        f"{p['fdr_threshold']} were highlighted, and the top {p['top_n']} by significance were labelled. "
        "Adjusted p-values reflect Benjamini-Hochberg correction."
    )
    return text, [BH]


def _heatmap(p: dict):
    tree = (
        " and the clustering dendrogram is drawn alongside the rows"
        if str(p.get("dendrogram") or "none").lower() == "row" else ""
    )
    text = (
        f"Expression of the top {p['n_genes']} genes was z-scored per gene and displayed as a heatmap "
        f"grouped by {p['groupby']}. Rows were ordered by hierarchical clustering (correlation distance, "
        f"average linkage; SciPy){tree}."
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
    dotplot = (
        "Expression is summarized as a dotplot in which colour encodes the mean log1p "
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


def _proteomics_de(p: dict):
    moderated = str(p.get("stats") or "welch").lower() == "moderated"
    test = (
        "an empirical-Bayes moderated t-test (limma-style shrinkage of the per-protein variance "
        "toward a global prior estimated across all proteins), which improves power at small "
        "sample sizes"
        if moderated else "a Welch (unequal-variance) t-test"
    )
    text = (
        "Protein intensities were log2-transformed and median-normalized across samples; proteins "
        f"quantified in at least {float(p.get('min_valid', 0.5)):g} of the samples per group were "
        f"tested for differential abundance between the two groups with {test}, with residual "
        "missing values mean-imputed within each group. P-values were corrected by the "
        f"Benjamini-Hochberg procedure and the result drawn as a volcano (|log2FC| ≥ "
        f"{float(p.get('fc_threshold', 1.0)):g}, FDR ≤ {float(p.get('fdr_threshold', 0.05)):g})."
    )
    return text, ([SMYTH, BH, SCIPY] if moderated else [BH, SCIPY])


def _pvca(p: dict):
    factors = ", ".join(s.strip() for s in str(p.get("factors") or "").split(",") if s.strip())
    factor_txt = f"the {factors} factors" if factors else "the annotated sample factors"
    text = (
        "The contribution of known sources of variation was quantified by Principal Variance "
        "Component Analysis. Features were standardized and decomposed by principal-component "
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
    horizontal = str(p.get("orientation", "v")).lower().startswith("h")
    axis = "horizontally" if horizontal else "vertically"
    group = str(p.get("group") or "").strip()
    value = str(p.get("value") or "").strip()
    what = (
        f"{value or 'the measured value'} across {group or 'each group'}"
    )
    text = (
        f"The distribution of {what} was summarized as {axis}-oriented box-and-whisker plots, each "
        "box spanning the interquartile range with the median marked and whiskers extending to 1.5× "
        "the IQR; groups are ordered by descending median."
    )
    return text, []


def _gsea(p: dict):
    pasted = str(p.get("gene_set") or "").strip()
    weight = p.get("weight", 1.0)
    n_perm = p.get("n_perm", 1000)
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
    text = (
        "Genes were ranked by their signed differential-expression metric (log2 fold change or a "
        "signed test statistic) and tested for coordinated enrichment by pre-ranked Gene Set "
        f"Enrichment Analysis (gseapy.prerank) against {target}. A running enrichment score was "
        f"accumulated along the ranked list with the Kolmogorov-Smirnov statistic weighted by the "
        f"metric (exponent {weight:g}); significance was assessed against {n_perm} gene-set "
        "permutations to yield a normalized enrichment score (NES) and empirical p-value, with "
        "false-discovery rates corrected across sets by the Benjamini-Hochberg procedure. The "
        "running enrichment curve, leading-edge hits, and ranked metric are shown."
    )
    return text, [GSEA, GSEAPY, *lib_cite, BH]


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
        f"genes detected in at least {p['min_cells']} cells and expressed in at least "
        f"{float(p['exprs_pct']):g} of cells were scored, and the top {p['n_genes']} differential-stability "
        "genes per group are reported. This is a clean-room Python reimplementation of the Cepo method."
    )
    return text, [CEPO, SCANPY]


_TEMPLATES = {
    "umap_scrna": _umap,
    "integration": _integration,
    "boxplot": _boxplot,
    "pvca": _pvca,
    "regression": _regression,
    "gsea": _gsea,
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
    "pca": _pca,
    "composition": _composition,
    "corr_heatmap": _corr_heatmap,
    "upset": _upset,
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


def build_body(spec: SkillSpec, params: dict) -> tuple[str, list[str]]:
    """Methods prose + citations for one skill, WITHOUT the trailing Selom attribution.

    This is the reusable unit the multi-skill synthesizer (``litsynth``) stitches together:
    one attribution sentence belongs at the end of a whole Methods section, not after every
    paragraph. ``build`` wraps this for the single-figure case, so its output is unchanged.
    """
    resolved = resolved_params(spec, params)
    builder = _TEMPLATES.get(spec.id)
    return builder(resolved) if builder else _generic(spec, resolved)


def build(spec: SkillSpec, params: dict) -> dict:
    """Methods paragraph + citations for one figure, from its resolved parameters."""
    text, citations = build_body(spec, params)
    text += f" {attribution(spec)}"
    return {"text": text, "citations": citations}

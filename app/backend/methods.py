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
    text = (
        "Single-cell RNA-seq data were processed with Scanpy. "
        f"{prep}principal-component "
        f"analysis was computed, and a nearest-neighbour graph was built on the top {p['n_pcs']} "
        f"principal components using {p['n_neighbors']} neighbours. The graph was embedded in two "
        f"dimensions with UMAP, and cells were coloured by {p['color_by']} cluster."
    )
    return text, [SCANPY, UMAP]


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
    return text, [SCANPY]


def _deg(p: dict):
    mode = str(p.get("mode") or "auto").lower()
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
    text = (
        f"Marker genes were identified per {p['groupby']} group with the {p['method']} test "
        f"(Scanpy rank_genes_groups), reporting the top {p['n_genes']} genes per group. "
        "Expression is summarized as a dotplot in which colour encodes the mean log1p "
        f"expression within each group{scaled} and dot size encodes the fraction of cells "
        "expressing the gene; p-values are corrected by the Benjamini-Hochberg procedure."
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
    text = (
        "Per-cell quality-control metrics — total counts, genes detected per cell, and the "
        "percentage of mitochondrial reads — were computed with Scanpy and displayed as violin "
        f"distributions split by {p.get('groupby', 'sample')}."
    )
    return text, [SCANPY]


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


_TEMPLATES = {
    "umap_scrna": _umap,
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

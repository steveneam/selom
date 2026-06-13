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
    text = (
        f"Expression of the top {p['n_genes']} genes was z-scored per gene and displayed as a heatmap "
        f"grouped by {p['groupby']}. Rows were ordered by hierarchical clustering (correlation distance, "
        "average linkage; SciPy)."
    )
    return text, [SCIPY]


def _enrichment(p: dict):
    text = (
        "Pathway enrichment was computed by over-representation analysis: the overlap between the input "
        "gene list and each GO and Reactome gene set was tested with the hypergeometric distribution, and "
        "p-values were corrected across gene sets by the Benjamini-Hochberg procedure. The top "
        f"{p['top_n']} enriched sets are shown."
    )
    return text, [GO, REACTOME, BH]


_TEMPLATES = {
    "umap_scrna": _umap,
    "cluster": _cluster,
    "violin": _violin,
    "deg": _deg,
    "volcano": _volcano,
    "heatmap": _heatmap,
    "enrichment": _enrichment,
}


def _generic(spec: SkillSpec, p: dict):
    listed = ", ".join(f"{k}={v}" for k, v in p.items()) or "default parameters"
    return f"Figure generated by the Selom '{spec.title}' skill with {listed}.", []


def build(spec: SkillSpec, params: dict) -> dict:
    """Methods paragraph + citations for one figure, from its resolved parameters."""
    resolved = resolved_params(spec, params)
    builder = _TEMPLATES.get(spec.id)
    text, citations = builder(resolved) if builder else _generic(spec, resolved)
    text += f" Analysis was performed using Selom (skill '{spec.id}' v{spec.version})."
    return {"text": text, "citations": citations}

"""Auto figure-legend text (P4c — the legend half of the Methods+legend layer).

The deterministic sibling of ``methods.build_body``: where ``methods`` says *how* a figure was
computed (a past-tense recipe + citations), ``legends`` says *what the reader is looking at* — a
paste-ready figure caption. Same seam (per-skill templates keyed by skill id, resolved params), a
different voice. Together they are the owner's "drop data -> run -> publication-ready methods +
legend" headline (``docs/workspace-library/spec.md`` Sec 11).

A run is ``{skill, params, result}``; so unlike methods (params only), a legend builder also gets
the *result* (the emitted ``figure`` + Statistics ``table``) and may enrich the caption with the
real quantities it shows — the DE up/down split, the number of rows — read through the canonical
``extract.readers`` tally so the count never drifts from the grading read-back. The caption is
always honest from params alone; the result merely sharpens it (and is optional, so an own-data run
and a reproduction panel share one builder). No "Figure N." number is baked in — the caller owns the
numbering (the reproduction ledger knows the figure label; an own-data run leaves it to the user).
"""

from __future__ import annotations

from skills.contract import SkillSpec, resolved_params


# --- result-derived facts (optional enrichment) -------------------------------


def _facts(figure: dict | None, table: dict | list | None) -> dict:
    """The few honest quantities a caption may cite, pulled from the run's result. Everything is
    optional — a builder cites a fact only when present, so a params-only call still reads cleanly.

    With N tables the caption reads the **first** (docs/stats-tables/spec.md D5): a caption is one
    sentence about one figure, and the runner's array order names the primary table. Named there
    because silently citing table 1 of 3 is the kind of thing that looks like a bug later."""
    from skills._table import as_tables

    facts: dict = {}
    table = next(iter(as_tables(table)), None)
    if isinstance(table, dict):
        rows = table.get("rows")
        if isinstance(rows, list):
            facts["n_rows"] = len(rows)
        try:  # the canonical DE up/down tally — same source of truth as the grading reader
            from extract.readers import de_counts

            counts = de_counts(table)
        except Exception:  # noqa: BLE001 — enrichment is best-effort; never break the caption
            counts = None
        if counts is not None:
            facts["up"], facts["down"] = counts
    return facts


def _de_split(facts: dict) -> str:
    """`` (N up, M down)`` when the DE direction split was read, else empty."""
    if "up" in facts and "down" in facts:
        return f" ({facts['up']} up, {facts['down']} down)"
    return ""


def _contrast(p: dict) -> str:
    ref, trt = str(p.get("reference") or "").strip(), str(p.get("treatment") or "").strip()
    return f" for {trt} versus {ref}" if ref and trt else ""


# --- per-skill caption templates ----------------------------------------------
# Each: (resolved_params, facts) -> one paste-ready caption sentence.


def _umap(p, f):
    emb = (p.get("embedding") or "").strip()
    lead = f"{emb} embedding" if emb else "Two-dimensional UMAP embedding"
    return f"{lead} of the single-cell transcriptomes, coloured by {p.get('color_by', 'cluster')}."


def _integration(p, f):
    batch = str(p.get("batch_key") or "").strip() or "the library/batch covariate"
    color = str(p.get("color_by") or "").strip() or batch
    return (
        "UMAP embedding of the batch-integrated single cells, coloured by "
        f"{color} after Harmony correction across {batch}."
    )


def _cluster(p, f):
    return (
        "Single cells embedded in two dimensions and coloured by Leiden cluster "
        f"(resolution {p['resolution']})."
    )


def _violin(p, f):
    gene = p.get("gene") or "the selected marker gene"
    text = f"Violin plot of {gene} expression across {p['groupby']} groups."
    if str(p.get("annotate") or "none").lower() == "pubmed":
        text += (
            f" Markers with at least {int(p.get('known_min', 5))} matching PubMed records "
            "are annotated as known and the rest as novel."
        )
    return text


def _deg(p, f):
    return f"Top {p['top_n']} differentially expressed genes{_contrast(p)}.{_de_split(f)}".rstrip()


def _volcano(p, f):
    return (
        "Volcano plot of differential expression (-log10 adjusted p-value versus log2 fold change); "
        f"genes with |log2FC| >= {p['fc_threshold']} and FDR <= {p['fdr_threshold']} are "
        f"highlighted{_de_split(f)}, the top {p['top_n']} by significance labelled."
    )


def _proteomics_de(p, f):
    return (
        "Volcano plot of differential protein abundance between the two groups "
        f"(|log2FC| >= {float(p.get('fc_threshold', 1.0)):g}, FDR <= "
        f"{float(p.get('fdr_threshold', 0.05)):g}){_de_split(f)}."
    )


def _heatmap(p, f):
    return (
        f"Heatmap of the top {p['n_genes']} genes, z-scored per gene and grouped by "
        f"{p['groupby']}; rows ordered by hierarchical clustering."
    )


def _enrichment(p, f):
    split = str(p.get("direction") or "combined").lower() == "split"
    per = " per direction (up- and down-regulated separately)" if split else ""
    return f"Top {p['top_n']} over-represented GO and Reactome gene sets{per}."


def _go_graph(p, f):
    return (
        f"Top {p['top_n']} enriched Gene Ontology terms drawn in their is_a/part_of hierarchy as a "
        "node-link graph, each node coloured by its -log10 adjusted p-value."
    )


def _pathway(p, f):
    return (
        f"Top {p['top_n']} enriched Reactome pathways drawn in the event hierarchy as a node-link "
        "graph, each coloured by the mean log2 fold change of its member genes."
    )


def _markers(p, f):
    return (
        f"Dot plot of the top {p['n_genes']} marker genes per {p['groupby']} group: colour encodes "
        "mean expression and dot size the fraction of cells expressing the gene."
    )


def _annotate(p, f):
    return f"Single cells coloured by the cell type assigned from the '{p['marker_set']}' marker panel."


def _trajectory(p, f):
    return (
        "Diffusion-map embedding coloured by diffusion pseudotime, with the PAGA cluster graph "
        "overlaid (nodes sized by cell count)."
    )


def _pseudotime_genes(p, f):
    return (
        f"Top {p['top_n']} genes varying along the inferred trajectory, shown as mean expression "
        "binned along diffusion pseudotime."
    )


def _pca(p, f):
    return (
        "Principal-component analysis of the samples, coloured by group; each axis is labelled "
        "with the percentage of variance it explains."
    )


def _composition(p, f):
    mode = str(p.get("mode") or "grouped")
    return f"Category proportions across conditions, shown as {mode} bars."


def _diff_abundance(p, f):
    return (
        f"Differential abundance of clusters between conditions{_contrast(p)}, as the log2 fold "
        "change per cluster (positive = expanding in the treatment)."
    )


def _gsea(p, f):
    return (
        "Gene Set Enrichment Analysis: the running enrichment score along the ranked gene list, "
        "with the leading-edge genes and the ranked metric shown."
    )


def _ssgsea(p, f):
    return (
        f"Per-sample pathway activity (single-sample GSEA) for the top {int(p.get('top_n', 25))} "
        "gene sets, as a sample x pathway heatmap."
    )


def _corr_heatmap(p, f):
    axis = "samples" if str(p.get("axis", "samples")).startswith("sample") else "features"
    method = str(p.get("method", "pearson")).title()
    return (
        f"{method} correlation heatmap across {axis}, on a diverging colour scale centred at zero."
    )


def _upset(p, f):
    return (
        "UpSet plot of set intersections: intersection sizes as bars above a dot-matrix of set "
        f"membership, showing the top {p.get('max_intersections', 20)} intersections of size at "
        f"least {p.get('min_size', 1)}."
    )


def _scorecard(p, f):
    form = (
        "a colour-coded scorecard heatmap (metrics in rows, conditions in columns)"
        if str(p.get("layout") or "radar").lower() == "heatmap"
        else "a radar chart, one filled polygon per condition"
    )
    return f"Multi-metric comparison of conditions as {form}."


def _normalization_qc(p, f):
    return (
        "Per-cell quality-control distributions - total counts, genes detected per cell, and the "
        f"percentage of mitochondrial reads - shown as violins split by {p.get('groupby', 'sample')}."
    )


def _sankey(p, f):
    return (
        "Sankey diagram of the quantities flowing between categories; node and link thickness are "
        "proportional to the flow value."
    )


def _string_network(p, f):
    return (
        "STRING protein-protein interaction network for the input genes (species "
        f"{p.get('species', 9606)}, combined score >= {p.get('required_score', 400)}/1000), nodes "
        "coloured by mean log2 fold change where available."
    )


def _cepo(p, f):
    return (
        f"Top {p['n_genes']} differential-stability marker genes per "
        f"{p.get('group_key') or 'cell-type'} group, identified with Cepo."
    )


def _boxplot(p, f):
    group = str(p.get("group") or "").strip() or "each group"
    value = str(p.get("value") or "").strip() or "the measured value"
    return (
        f"Box-and-whisker plots of {value} across {group}; each box spans the interquartile range "
        "with the median marked and whiskers at 1.5x the IQR (groups ordered by descending median)."
    )


def _pvca(p, f):
    factors = ", ".join(s.strip() for s in str(p.get("factors") or "").split(",") if s.strip())
    across = f"across {factors}" if factors else "across the annotated sample factors"
    return (
        f"Principal Variance Component Analysis apportioning the overall variance {across} (the "
        "remainder being unexplained residual)."
    )


def _regression(p, f):
    x = str(p.get("x") or "").strip() or "the predictor"
    y = str(p.get("y") or "").strip() or "the response"
    return (
        f"Scatter of {y} against {x} with the ordinary-least-squares fit overlaid; the coefficient "
        "of determination (R^2), slope, and regression p-value are reported."
    )


_TEMPLATES = {
    "umap_scrna": _umap,
    "integration": _integration,
    "cluster": _cluster,
    "violin": _violin,
    "deg": _deg,
    "volcano": _volcano,
    "proteomics_de": _proteomics_de,
    "heatmap": _heatmap,
    "enrichment": _enrichment,
    "go_graph": _go_graph,
    "pathway": _pathway,
    "markers": _markers,
    "annotate": _annotate,
    "trajectory": _trajectory,
    "pseudotime_genes": _pseudotime_genes,
    "pca": _pca,
    "composition": _composition,
    "diff_abundance": _diff_abundance,
    "gsea": _gsea,
    "ssgsea": _ssgsea,
    "corr_heatmap": _corr_heatmap,
    "upset": _upset,
    "scorecard": _scorecard,
    "normalization_qc": _normalization_qc,
    "sankey": _sankey,
    "string_network": _string_network,
    "cepo": _cepo,
    "boxplot": _boxplot,
    "pvca": _pvca,
    "regression": _regression,
}


def _generic(spec: SkillSpec, p: dict) -> str:
    """Honest fallback for a skill with no bespoke template: name the skill, no invented detail."""
    return f"{spec.title} of the input data."


def build_caption(spec: SkillSpec, params: dict, *, figure: dict | None = None,
                  table: dict | list | None = None) -> str:
    """The paste-ready figure caption for one run (no leading "Figure N." — the caller numbers it).

    Honest from the resolved params alone; enriched with the run's real quantities (DE split, etc.)
    when ``figure``/``table`` are supplied. This is the reusable unit the ledger composer stitches
    per panel."""
    resolved = resolved_params(spec, params)
    facts = _facts(figure, table)
    builder = _TEMPLATES.get(spec.id)
    return builder(resolved, facts) if builder else _generic(spec, resolved)


def build(spec: SkillSpec, params: dict, *, figure: dict | None = None,
          table: dict | list | None = None) -> dict:
    """Figure legend for one run, as the run response carries it (mirrors ``methods.build``)."""
    return {"text": build_caption(spec, params, figure=figure, table=table)}

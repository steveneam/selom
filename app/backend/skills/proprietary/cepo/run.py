"""Selom Cepo — differential-stability cell-type markers (proprietary).

Clean-room Python reimplementation of **Cepo** (Kim et al. 2021, *Nat Comput Sci*
"Cepo: a method for clustering-free identification of cell-type-specific genes") — there
is no Python port upstream (PYangLab/Cepo is R-only, MIT-licensed → a clean-room reimpl
is licensing-fine; cite Kim 2021). Cepo ranks markers by **differential stability (DS)**:
genes that are both highly *detected* AND stably expressed (low coefficient of variation)
within a cell type relative to the other types. This recovers identity genes that
mean-difference tests (scanpy ``rank_genes_groups``, the commodity ``markers`` skill) miss.

Algorithm (faithful to Cepo's ``R/Cepo.R``) — within each cell type, per gene g:
  detection   nz = mean(x > 0)
  variability cv = sd(x) / mean(x)          (CV; +inf where mean == 0)
  rank across genes →  x1 = rank(nz)/(G+1),  x2 = 1 - rank(cv)/(G+1)
  stability index      segIdx = w1*x1 + w2*x2
then the DS statistic ``DS[g, c] = segIdx[g, c] - mean_{d != c} segIdx[g, d]``. The top-DS
genes of a type are its stability markers. Validated against the Hani ``mmc2`` boolean Cepo
oracle (GSE201356 retinal-organoid paper). Real engine: ``run_real.py``; the stub here is a
deterministic, dependency-free spec of the same wire shape (what the golden test pins).
"""

from skills._engine import use_real_engine

# Diverging scale for the DS score (DS is signed: + = stable-and-detected here vs. others).
COLORSCALE = "RdBu"


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy", "scipy"):
        from skills.proprietary.cepo.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic DS dotplot: 3 cell types x 4 top markers each (block-diagonal DS).

    Each type's own markers carry a high positive DS and are widely detected (big dot);
    off-type they carry a negative DS and are barely detected (small dot) — the canonical
    stability-marker look, with zero heavy deps."""
    types = ["Rods", "Cones", "Bipolar"]
    block = [
        ["NRL", "GNAT1", "RHO", "PDE6B"],
        ["ARR3", "GNGT2", "OPN1SW", "PDE6H"],
        ["VSX2", "GRIK1", "TRPM1", "CABP5"],
    ]
    genes = [g for row in block for g in row]

    xs: list[str] = []
    ys: list[str] = []
    ds: list[float] = []
    sizes: list[float] = []
    detect: list[float] = []
    for ti, ctype in enumerate(types):
        for j, gene in enumerate(genes):
            own = (j // 4) == ti
            ds_val = round(0.34 + 0.02 * (3 - (j % 4)) if own else -0.12 + 0.01 * (j % 4), 4)
            det = round(0.86 - 0.04 * (j % 4) if own else 0.10 + 0.02 * (j % 4), 4)
            xs.append(gene)
            ys.append(ctype)
            ds.append(ds_val)
            detect.append(det)
            sizes.append(round(4.0 + det * 22.0, 4))

    rows = [[t, g, d, f] for t, g, d, f in zip(ys, xs, ds, detect) if d > 0]
    return _dotplot_spec(
        xs, ys, ds, sizes, detect, genes, types,
        title="Cepo stability markers — top 4 per cell type (stub)",
        table=_ds_table(rows),
    )


def _ds_table(rows) -> dict:
    """Top stability markers as a Statistics table (cell type · gene · DS · detection)."""
    from skills._table import table

    rows = sorted(rows, key=lambda r: (str(r[0]), -float(r[2])))
    out = [[str(t), str(g), round(float(d), 4), round(float(f), 4)] for t, g, d, f in rows]
    return table(["cell type", "gene", "DS", "detection"], out, title="Cepo differential stability")


def _dotplot_spec(xs, ys, ds, sizes, detect, gene_order, type_order, title, table=None) -> dict:
    """Assemble the editable DS-dotplot Plotly spec (shared by stub + real engine).
    colour = DS score (diverging, centred at 0) · dot size = detection fraction."""
    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": xs,
                "y": ys,
                "marker": {
                    "color": ds,
                    "colorscale": COLORSCALE,
                    "reversescale": True,
                    "cmid": 0,
                    "showscale": True,
                    "colorbar": {"title": {"text": "DS score"}},
                    "size": sizes,
                    "line": {"color": "#334155", "width": 0.5},
                },
                "customdata": detect,
                "hovertemplate": (
                    "%{x} · %{y}<br>DS %{marker.color:.3f}"
                    "<br>%{customdata:.0%} of cells expressing<extra></extra>"
                ),
                "name": "cepo",
            }
        ],
        "layout": {
            "title": {
                "text": title,
                "subtitle": {"text": "colour = differential stability · dot size = % of cells expressing"},
            },
            "xaxis": {
                "title": {"text": "gene"},
                "type": "category",
                "categoryorder": "array",
                "categoryarray": gene_order,
                "tickangle": -45,
            },
            "yaxis": {
                "title": {"text": "cell type"},
                "type": "category",
                "categoryorder": "array",
                "categoryarray": type_order,
            },
            "plot_bgcolor": "white",
        },
    }
    if table is not None:
        spec["table"] = table
    return spec

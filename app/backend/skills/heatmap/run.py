"""Expression heatmap of marker / top-variable genes (row z-scored).

scRNA path ranks markers per cluster and shows mean expression per cluster; bulk
CSV path shows the top-variance genes across samples. Both render a single Plotly
heatmap trace on a diverging RdBu scale centred at zero. The stub is a deterministic
z-matrix in the same shape.
"""

import math

from skills._engine import use_real_engine
from skills._genes import display_symbols


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.heatmap.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    n_genes, n_groups = 20, 6
    genes = [f"GENE{i + 1}" for i in range(n_genes)]
    groups = [f"c{j}" for j in range(n_groups)]
    z = [[round(math.sin(i * 0.5 + j * 1.1), 3) for j in range(n_groups)] for i in range(n_genes)]
    return heatmap_spec(z, groups, genes, "Marker heatmap (stub)", "cluster")


def _h_colorbar() -> dict:
    """Small horizontal colour key tucked at the bottom-left — used whenever a left-gutter row
    tree owns the left and the row labels move to the right, so the key never competes with them."""
    return {
        "title": {"text": "z-score", "side": "top", "font": {"size": 10}},
        "orientation": "h",
        "len": 0.3,
        "thickness": 10,
        "x": 0.0,
        "xanchor": "left",
        "y": -0.16,
        "yanchor": "top",
        "tickfont": {"size": 9},
    }


def _dendro_trace(dendro, axis_id, transpose):
    """Build a dendrogram polyline trace + return ``(trace, max_distance)``.

    A SciPy dendrogram gives paired ``icoord`` (leaf-axis positions) and ``dcoord`` (distances).
    For a LEFT (row) tree the distance runs along x and the leaf positions along y; for a TOP
    (column) tree it's the reverse. ``transpose`` selects: ``False`` → row tree (x=distance,
    y=leaf), ``True`` → column tree (x=leaf, y=distance). ``axis_id`` (e.g. ``"2"``/``"3"``)
    pins the trace to its own gutter axes (``x{id}``/``y{id}``).
    """
    xs, ys, max_d = [], [], 0.0
    for dc, ic in zip(dendro["dcoord"], dendro["icoord"]):
        dvals = [round(float(v), 4) for v in dc]
        ivals = [round(float(v), 4) for v in ic]
        if transpose:  # column tree: leaf positions on x, distance on y
            xs += ivals + [None]
            ys += dvals + [None]
        else:  # row tree: distance on x, leaf positions on y
            xs += dvals + [None]
            ys += ivals + [None]
        max_d = max(max_d, max(dc))
    trace = {
        "type": "scatter",
        "mode": "lines",
        "x": xs,
        "y": ys,
        "xaxis": f"x{axis_id}",
        "yaxis": f"y{axis_id}",
        "line": {"color": "#94a3b8", "width": 1},
        "hoverinfo": "skip",
        "showlegend": False,
    }
    return trace, max_d


def heatmap_spec(z, x_labels, y_labels, title, x_title, row_dendro=None, col_dendro=None) -> dict:
    """Shared heatmap spec — used by both the stub and the real engine.

    ``row_dendro`` / ``col_dendro`` (optional) are ``{"icoord", "dcoord"}`` SciPy dendrograms.
    A row tree draws in a LEFT gutter (and moves the row labels to the right so the tree owns
    the left); a column tree draws in a TOP gutter — the standard clustermap furniture. Either,
    both, or neither may be supplied. When neither is given the spec is exactly the single-trace
    heatmap as before (so the stub golden stays byte-identical).
    """
    # Preserve the CANONICAL row/col labels (pre-symbol-strip) as a render-inert provenance anchor:
    # the FE "rename" is a cosmetic axis-ticktext edit that never touches the data, so the canonical
    # IDs stay the source of truth and a rename can always show the original (heatmap-clustermap-spec
    # §6). Stamped under ``meta.selom.heatmapLabels`` (Plotly ignores ``layout.meta``).
    orig_meta = {"selom": {"heatmapLabels": {"x": list(x_labels), "y": list(y_labels)}}}
    # Show readable gene SYMBOLS on the axis (``ENSG…~STRIP2`` → ``STRIP2``); plain symbols / IDs and
    # the stub's ``GENE1…`` labels pass through unchanged.
    y_labels = display_symbols(y_labels)
    heat = {
        "type": "heatmap",
        "z": z,
        "x": x_labels,
        "y": y_labels,
        "colorscale": "RdBu",
        "reversescale": True,
        "zmid": 0,
        "colorbar": {"title": {"text": "z-score"}},
    }
    has_row = bool(row_dendro)
    has_col = bool(col_dendro)
    if not has_row and not has_col:
        return {
            "data": [heat],
            "layout": {
                "title": {"text": title},
                "xaxis": {"title": {"text": x_title}},
                "yaxis": {"title": {"text": "gene"}, "automargin": True},
                "meta": orig_meta,
            },
        }

    # Clustermap: heatmap on x/y, dendrogram lines on their own gutter axes (shared spans). The
    # left gutter (x2/y2) holds the row tree, the top gutter (x3/y3) the column tree. The heatmap
    # cedes 16% on the left for a row tree and 16% on the top for a column tree.
    n_rows = len(y_labels)
    n_cols = len(x_labels)
    x_lo = 0.16 if has_row else 0.0
    y_hi = 0.84 if has_col else 1.0

    data = [heat]
    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": x_title}, "domain": [x_lo, 1.0]},
        "yaxis": {"title": {"text": "gene"}, "automargin": True, "domain": [0.0, y_hi]},
    }

    if has_row:
        # tree owns the left → row labels on the right (theme must preserve yaxis.side); the
        # vertical colour key would clash with the right-hand labels, so go horizontal bottom-left.
        layout["yaxis"]["side"] = "right"
        heat["colorbar"] = _h_colorbar()
        row_trace, max_dr = _dendro_trace(row_dendro, "2", transpose=False)
        data.append(row_trace)
        # leaves (distance 0) abut the heatmap on the right, root at the left
        layout["xaxis2"] = {"domain": [0.0, 0.14], "range": [max_dr * 1.05, 0],
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}
        layout["yaxis2"] = {"domain": [0.0, y_hi], "range": [0, 10 * n_rows], "anchor": "x2",
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}

    if has_col:
        col_trace, max_dc = _dendro_trace(col_dendro, "3", transpose=True)
        data.append(col_trace)
        # leaves (distance 0) abut the heatmap at the bottom of the top gutter, root at the top
        layout["xaxis3"] = {"domain": [x_lo, 1.0], "range": [0, 10 * n_cols], "anchor": "y3",
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}
        layout["yaxis3"] = {"domain": [0.86, 1.0], "range": [0, max_dc * 1.05],
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}

    layout["meta"] = orig_meta
    return {"data": data, "layout": layout}

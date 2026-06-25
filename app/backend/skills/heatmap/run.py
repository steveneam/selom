"""Expression heatmap of marker / top-variable genes (row z-scored).

scRNA path ranks markers per cluster and shows mean expression per cluster; bulk
CSV path shows the top-variance genes across samples. Both render a single Plotly
heatmap trace on a diverging RdBu scale centred at zero. The stub is a deterministic
z-matrix in the same shape.
"""

import math

from skills._engine import use_real_engine
from skills._genes import display_symbols

# Categorical palette for annotation-track strips — reused from the shared chart palette so the
# track colours sit in the same family as the line/condition colours elsewhere.
from skills._charts import LINE_PALETTE

# Each column annotation track is a thin strip above the heatmap; this is its allocated height in
# paper fraction (the strip fills ~80 % of it, leaving a sliver between strips). The top tree (when
# present) keeps its 0.16 band; the track band sits between the heatmap and that tree.
_TRACK_H = 0.04

# Coloured dendrogram branches (heatmap-clustermap-spec §9 / refs 035648/035701): when the tree is
# cut into k clusters (the ``cut_k`` param), each below-cut cluster gets a distinct hue and the shared
# trunk above the cut stays grey. ``_TRUNK_COLOR`` is the existing single-tree dendrogram grey; the
# cluster palette is kept SEPARATE from the annotation-track palette so a "cluster" colour never reads
# as a "category" colour. SciPy bakes these exact hex strings into its ``color_list`` (run_real sets
# them via ``set_link_color_palette`` + ``above_threshold_color``); this module just groups by colour.
_TRUNK_COLOR = "#94a3b8"
_CLUSTER_PALETTE = [
    "#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#65a30d",
]


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


def _h_colorbar(y: float = -0.16) -> dict:
    """Small horizontal colour key tucked at the bottom-left — used whenever a left-gutter row
    tree owns the left and the row labels move to the right, so the key never competes with them.
    ``y`` drops lower when a categorical track legend takes the first bottom row."""
    return {
        "title": {"text": "z-score", "side": "top", "font": {"size": 10}},
        "orientation": "h",
        "len": 0.3,
        "thickness": 10,
        "x": 0.0,
        "xanchor": "left",
        "y": y,
        "yanchor": "top",
        "tickfont": {"size": 9},
    }


def _dendro_traces(dendro, axis_id, transpose):
    """Build the dendrogram polyline trace(s) + return ``(traces, max_distance)``.

    A SciPy dendrogram gives paired ``icoord`` (leaf-axis positions) and ``dcoord`` (distances),
    one link per entry. For a LEFT (row) tree the distance runs along x and the leaf positions
    along y; for a TOP (column) tree it's the reverse. ``transpose`` selects: ``False`` → row tree
    (x=distance, y=leaf), ``True`` → column tree (x=leaf, y=distance). ``axis_id`` (e.g.
    ``"2"``/``"3"``) pins the trace(s) to their own gutter axes (``x{id}``/``y{id}``).

    Without a cut this is ONE grey trace (every link concatenated, ``None``-separated). With a
    ``colors`` list (one colour per link, from a ``cut_k`` cut — heatmap-clustermap-spec §9) the
    links are grouped into one trace PER colour so each cluster's branches read in its own hue; the
    grey trunk draws first (underneath) so the coloured clusters sit on top. Splitting one tree into
    several traces is why the FE leaf-tip projection is multi-trace-aware (``lib/heatmap/dendrogram``).
    """
    colors = dendro.get("colors")
    links = list(zip(dendro["dcoord"], dendro["icoord"]))
    max_d = max((max(dc) for dc, _ in links), default=0.0)

    def _xy(dc, ic):
        dvals = [round(float(v), 4) for v in dc]
        ivals = [round(float(v), 4) for v in ic]
        if transpose:  # column tree: leaf positions on x, distance on y
            return ivals + [None], dvals + [None]
        return dvals + [None], ivals + [None]  # row tree: distance on x, leaf positions on y

    def _trace(xs, ys, color):
        return {
            "type": "scatter",
            "mode": "lines",
            "x": xs,
            "y": ys,
            "xaxis": f"x{axis_id}",
            "yaxis": f"y{axis_id}",
            "line": {"color": color, "width": 1},
            "hoverinfo": "skip",
            "showlegend": False,
        }

    if not colors:
        xs, ys = [], []
        for dc, ic in links:
            x, y = _xy(dc, ic)
            xs += x
            ys += y
        return [_trace(xs, ys, _TRUNK_COLOR)], max_d

    # Group links by their assigned colour, preserving first-appearance order, then draw the trunk
    # (grey, above-cut links) first so the coloured clusters layer cleanly over it.
    groups: dict[str, tuple[list, list]] = {}
    order: list[str] = []
    for (dc, ic), color in zip(links, colors):
        if color not in groups:
            groups[color] = ([], [])
            order.append(color)
        x, y = _xy(dc, ic)
        groups[color][0].extend(x)
        groups[color][1].extend(y)
    order.sort(key=lambda c: 0 if c == _TRUNK_COLOR else 1)
    return [_trace(groups[c][0], groups[c][1], c) for c in order], max_d


def _track_color(i: int) -> str:
    return LINE_PALETTE[i % len(LINE_PALETTE)]


def _discrete_colorscale(n: int) -> list:
    """A stepwise Plotly colorscale for ``n`` categories: code ``i`` (with zmin=-0.5, zmax=n-0.5)
    lands mid-band ``i`` → the i-th palette colour. One colour per category, hard edges."""
    stops = []
    for i in range(n):
        c = _track_color(i)
        stops.append([i / n, c])
        stops.append([(i + 1) / n, c])
    return stops


def _col_track_layer(tracks, x_labels, x_lo, y_hi):
    """Build the categorical annotation-track strips above the heatmap + their legend.

    ``tracks`` is a list of ``{"name", "codes", "categories"}`` (codes index into categories,
    -1 = missing). Each strip is a 1-row heatmap sharing the heatmap's column axis (``matches:x``)
    on its own thin y-band; ``legend`` proxy scatters give each category a swatch. Returns
    ``(traces, axes, legend_groups)`` — ``axes`` is the ``{axis_key: spec}`` to merge into layout,
    ``legend_groups`` the count (drives legend sizing). Strips stack upward from the heatmap, the
    first requested track adjacent to the map (the conventional clustermap col-colour order).
    """
    traces, axes, proxies = [], {}, []
    band_lo = round(y_hi + 0.01, 4)  # small gap between the heatmap top and the first strip
    for i, track in enumerate(tracks):
        aid = 4 + i
        cats = track["categories"]
        n = max(1, len(cats))
        codes = track["codes"]
        cells = [c if c >= 0 else None for c in codes]  # missing → blank cell
        hover = [cats[c] if c >= 0 else "—" for c in codes]
        lo = round(band_lo + i * _TRACK_H, 4)
        hi = round(lo + _TRACK_H * 0.8, 4)
        traces.append({
            "type": "heatmap",
            "z": [cells],
            "x": list(x_labels),
            "y": [track["name"]],
            "xaxis": f"x{aid}",
            "yaxis": f"y{aid}",
            "colorscale": _discrete_colorscale(n),
            "zmin": -0.5,
            "zmax": n - 0.5,
            "showscale": False,
            "xgap": 0,
            "ygap": 0,
            "customdata": [hover],
            "hovertemplate": f"{track['name']}: %{{customdata}}<extra></extra>",
        })
        axes[f"xaxis{aid}"] = {
            "domain": [x_lo, 1.0], "anchor": f"y{aid}", "matches": "x",
            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": "",
        }
        axes[f"yaxis{aid}"] = {
            "domain": [lo, hi], "anchor": f"x{aid}", "side": "left",
            "showgrid": False, "zeroline": False, "ticks": "", "tickfont": {"size": 9},
        }
        for j, cat in enumerate(cats):
            proxies.append({
                "type": "scatter", "x": [None], "y": [None], "mode": "markers",
                "marker": {"size": 9, "color": _track_color(j), "symbol": "square"},
                "name": str(cat), "legendgroup": track["name"],
                "legendgrouptitle": {"text": track["name"], "font": {"size": 10}},
                "showlegend": True, "hoverinfo": "skip",
            })
    return traces, axes, proxies


def _row_quant_layer(quant, y_labels, x0, x1, y_hi, aid):
    """A quantitative side track aligned to the rows (035636 "mean log₂FC") — a horizontal bar
    strip on its own thin x-band left of the heatmap, sharing the heatmap's row axis (``matches:y``).
    ``quant`` = ``{"name", "values", "diverging"}``; a diverging value (log₂FC) gets a 0-centred axis
    and sign colours, a non-negative stat (variance / mean) grows from 0 in one colour."""
    vals = quant["values"]
    diverging = bool(quant.get("diverging"))
    present = [abs(v) if diverging else v for v in vals if isinstance(v, (int, float))]
    m = max(present, default=1.0) or 1.0
    if diverging:
        rng = [-m * 1.05, m * 1.05]
        colors = ["#2563eb" if (v or 0) >= 0 else "#dc2626" for v in vals]
    else:
        rng = [0, m * 1.05]
        colors = "#64748b"
    trace = {
        "type": "bar",
        "orientation": "h",
        "x": list(vals),
        "y": list(y_labels),
        "xaxis": f"x{aid}",
        "yaxis": f"y{aid}",
        "marker": {"color": colors},
        "showlegend": False,
        "hovertemplate": f"{quant['name']}: %{{x:.2f}}<extra></extra>",
    }
    axes = {
        f"xaxis{aid}": {
            "domain": [x0, x1], "anchor": f"y{aid}", "range": rng,
            "title": {"text": quant["name"], "font": {"size": 9}},
            "tickfont": {"size": 8}, "nticks": 3, "zeroline": diverging, "showgrid": False,
        },
        f"yaxis{aid}": {
            "domain": [0.0, y_hi], "anchor": f"x{aid}", "matches": "y",
            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": "",
        },
    }
    return trace, axes


def heatmap_spec(
    z, x_labels, y_labels, title, x_title, row_dendro=None, col_dendro=None, col_tracks=None,
    row_quant=None, col_headers=None,
) -> dict:
    """Shared heatmap spec — used by both the stub and the real engine.

    ``row_dendro`` / ``col_dendro`` (optional) are ``{"icoord", "dcoord"}`` SciPy dendrograms.
    A row tree draws in a LEFT gutter (and moves the row labels to the right so the tree owns
    the left); a column tree draws in a TOP gutter — the standard clustermap furniture. Either,
    both, or neither may be supplied. ``col_tracks`` (optional) are categorical annotation strips
    (``{"name", "codes", "categories"}``) painted on the column axis between the heatmap and the
    top tree, with a per-track legend (heatmap-clustermap-spec §3 / ref 035134). ``row_quant``
    (optional, ``{"name", "values", "diverging"}``) is a quantitative side bar aligned to the rows,
    drawn in a thin band left of the heatmap (between the row tree and the map — ref 035636).
    ``col_headers`` (optional, ``[{"group", "center"}]``) are block-split group headers centred over
    each column block (ref 035617). When none of these is given the spec is exactly the single-trace
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
    tracks = col_tracks or []
    has_tracks = bool(tracks)
    has_quant = bool(row_quant)
    headers = col_headers or []
    has_headers = bool(headers)
    if not has_row and not has_col and not has_tracks and not has_quant and not has_headers:
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
    # left gutter (x2/y2) holds the row tree, a quant side bar (next free axis) the next left band,
    # the top gutter (x3/y3) the column tree; annotation strips (x4/y4, x5/y5, …) stack between the
    # heatmap and the top tree. The heatmap cedes 16% on the left for a row tree, 12% more for a
    # quant bar, 16% on the top for a column tree, and ``_TRACK_H`` per annotation track. A row tree
    # OR a quant bar owns the left, so the row labels move to the right (``labels_right``).
    n_rows = len(y_labels)
    n_cols = len(x_labels)
    row_tree_w = 0.16 if has_row else 0.0
    quant_w = 0.12 if has_quant else 0.0
    x_lo = round(row_tree_w + quant_w, 4)
    labels_right = has_row or has_quant
    # Top edge of the heatmap+track stack: under the column tree (0.84) if present, else near the
    # top (a sliver of headroom for the topmost strip's label when there's no tree). Block-split
    # headers (no col tree in split mode) reserve their own row above the stack.
    band_top = 0.84 if has_col else (0.95 if has_tracks else 1.0)
    if has_headers:
        band_top = min(band_top, 0.93)
    y_hi = round(band_top - len(tracks) * _TRACK_H - (0.01 if has_tracks else 0.0), 4)

    data = [heat]
    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": x_title}, "domain": [x_lo, 1.0]},
        "yaxis": {"title": {"text": "gene"}, "automargin": True, "domain": [0.0, y_hi]},
    }

    if has_quant:
        q_trace, q_axes = _row_quant_layer(
            row_quant, y_labels, row_tree_w, round(x_lo - 0.02, 4), y_hi, 4 + len(tracks)
        )
        data.append(q_trace)
        layout.update(q_axes)

    if has_tracks:
        track_traces, track_axes, proxies = _col_track_layer(tracks, x_labels, x_lo, y_hi)
        data += track_traces
        data += proxies
        layout.update(track_axes)
        # Per-track category legend at the bottom (the right side carries gene labels when a row tree
        # is present, so bottom is the always-clear home). The z-score key (which goes horizontal at
        # the bottom under a row tree) drops below it so the two never collide.
        layout["legend"] = {
            "orientation": "h", "x": 0.0, "xanchor": "left", "y": -0.14, "yanchor": "top",
            "font": {"size": 9}, "itemsizing": "constant", "tracegroupgap": 14,
        }
        layout["margin"] = {"b": 110}

    if has_headers:
        # one bold block header centred over each split block, just above the heatmap+track stack
        header_y = round(band_top + 0.03, 4)
        layout["annotations"] = [
            {
                "x": h["center"], "xref": "x", "y": header_y, "yref": "paper",
                "text": str(h["group"]), "showarrow": False, "xanchor": "center",
                "yanchor": "bottom", "font": {"size": 11, "color": "#33404d"},
            }
            for h in headers
        ]

    if labels_right:
        # a row tree or quant bar owns the left → row labels on the right (theme must preserve
        # yaxis.side); the vertical colour key would clash with the right-hand labels, so go
        # horizontal bottom-left (dropping below the track legend when one is present).
        layout["yaxis"]["side"] = "right"
        heat["colorbar"] = _h_colorbar(-0.30 if has_tracks else -0.16)

    if has_row:
        row_traces, max_dr = _dendro_traces(row_dendro, "2", transpose=False)
        data += row_traces
        # leaves (distance 0) abut the heatmap on the right, root at the left
        layout["xaxis2"] = {"domain": [0.0, 0.14], "range": [max_dr * 1.05, 0],
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}
        layout["yaxis2"] = {"domain": [0.0, y_hi], "range": [0, 10 * n_rows], "anchor": "x2",
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}

    if has_col:
        col_traces, max_dc = _dendro_traces(col_dendro, "3", transpose=True)
        data += col_traces
        # leaves (distance 0) abut the heatmap at the bottom of the top gutter, root at the top
        layout["xaxis3"] = {"domain": [x_lo, 1.0], "range": [0, 10 * n_cols], "anchor": "y3",
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}
        layout["yaxis3"] = {"domain": [0.86, 1.0], "range": [0, max_dc * 1.05],
                            "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""}

    layout["meta"] = orig_meta
    return {"data": data, "layout": layout}

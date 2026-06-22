"""Generic small-multiples *trace grid* — the reusable figure primitive behind the ERG
module (and any time-series shown as ``row × col`` small multiples: EEG/ECG/patch-clamp,
dose × condition, …). See docs/erg-module/spec.md.

The look: a grid of floating line panels with **no per-panel axes** (no ticks, lines,
labels, or grid) and a **single shared scale bar** that encodes amplitude (vertical) and
time (horizontal) for the whole grid. By default every panel shares one x- and y-range, so
trace heights are directly comparable — which is what makes one scale bar meaningful. Row
labels sit at the right, column labels across the top.

A skill computes the panels and calls :func:`grid_spec`; the return is a pure, fully-editable
Plotly ``{"data": [...], "layout": {...}}`` (plain floats, no numpy). This generalises the
shared-spec-builder pattern of ``skills/normalization_qc/run.py::qc_panel_spec`` to 2-D
placement with hidden axes + a scale bar. ``theme.apply`` adds fonts/colourway/title; the
``trace_grid`` theme kind keeps the per-panel axes hidden.
"""
from __future__ import annotations

# Scale bar defaults (vertical = amplitude, horizontal = time).
DEFAULT_SCALEBAR = {"x_len": 100.0, "x_unit": "ms", "y_len": 200.0, "y_unit": "µV"}

# Paper-fraction margins around the panel block (room for labels + the scale bar).
_M_LEFT, _M_RIGHT, _M_TOP, _M_BOTTOM = 0.07, 0.07, 0.055, 0.06


def _span(panels: list[dict], key: str) -> tuple[float, float]:
    lo = min(min(p[key]) for p in panels)
    hi = max(max(p[key]) for p in panels)
    if lo == hi:  # degenerate (flat / single point) — give the axis a unit of room
        hi = lo + 1.0
    return float(lo), float(hi)


def grid_spec(
    panels: list[dict],
    *,
    nrows: int,
    ncols: int,
    scalebar: dict | None = None,
    row_labels: list | None = None,
    col_labels: list | None = None,
    share_y: bool = True,
    share_x: bool = True,
    row_gap: float = 0.012,
    col_gap: float = 0.010,
    line_width: float = 1.2,
    title: str | None = None,
    baseline: bool = False,
) -> dict:
    """Build a no-axes small-multiples trace grid.

    ``panels``: list of ``{"row": int, "col": int, "x": [...], "y": [...],
    "color": str?, "name": str?}`` (row 0 = top, col 0 = left). One ``scatter``
    line trace per panel, each bound to its own ``xaxis{N}``/``yaxis{N}`` placed by
    ``domain`` + ``anchor`` and hidden (``visible: False``). Exactly one L-shaped scale
    bar (two paper-referenced line shapes + two unit annotations) sits bottom-left, sized
    to the shared data→paper mapping so it reads true against every panel.
    """
    if not panels:
        raise ValueError("grid_spec: no panels")
    if nrows < 1 or ncols < 1:
        raise ValueError(f"grid_spec: nrows/ncols must be >=1 (got {nrows}x{ncols})")
    for p in panels:
        if not (0 <= p["row"] < nrows and 0 <= p["col"] < ncols):
            raise ValueError(f"panel (row={p['row']},col={p['col']}) outside {nrows}x{ncols} grid")

    sb = {**DEFAULT_SCALEBAR, **(scalebar or {})}
    xlo, xhi = _span(panels, "x")
    ylo, yhi = _span(panels, "y")
    xspan, yspan = xhi - xlo, yhi - ylo

    gx0, gx1 = _M_LEFT, 1.0 - _M_RIGHT
    gy0, gy1 = _M_BOTTOM, 1.0 - _M_TOP
    col_w = (gx1 - gx0 - col_gap * (ncols - 1)) / ncols
    row_h = (gy1 - gy0 - row_gap * (nrows - 1)) / nrows

    def x_domain(col: int) -> list[float]:
        x0 = gx0 + col * (col_w + col_gap)
        return [round(x0, 5), round(x0 + col_w, 5)]

    def y_domain(row: int) -> list[float]:  # row 0 == top of the figure
        y_top = gy1 - row * (row_h + row_gap)
        return [round(y_top - row_h, 5), round(y_top, 5)]

    data: list[dict] = []
    layout: dict = {"showlegend": False, "margin": {"t": 10, "r": 10, "b": 10, "l": 10}}
    if title:
        layout["title"] = {"text": title}

    for p in panels:
        k = p["row"] * ncols + p["col"] + 1
        sfx = "" if k == 1 else str(k)
        xref, yref = f"x{sfx}", f"y{sfx}"
        line = {"width": line_width}
        if p.get("color"):
            line["color"] = p["color"]
        trace = {
            "type": "scatter",
            "mode": "lines",
            "x": [round(float(v), 4) for v in p["x"]],
            "y": [round(float(v), 4) for v in p["y"]],
            "line": line,
            "xaxis": xref,
            "yaxis": yref,
            "name": str(p.get("name", f"r{p['row']}c{p['col']}")),
            "hoverinfo": "x+y",
        }
        # Optional grouping hint: traces sharing a `group` (e.g. an ERG condition spanning
        # the 7 intensity panels) carry a `legendgroup` so the editor edits them as one
        # series. No legend is shown (showlegend=False), so this only tags identity.
        if p.get("group") is not None:
            trace["legendgroup"] = str(p["group"])
        data.append(trace)
        ax = {"domain": x_domain(p["col"]), "anchor": yref, "visible": False}
        ay = {"domain": y_domain(p["row"]), "anchor": xref, "visible": False}
        if share_x:
            ax["range"] = [xlo, xhi]
        if share_y:
            ay["range"] = [ylo, yhi]
        layout[f"xaxis{sfx}"] = ax
        layout[f"yaxis{sfx}"] = ay

    shapes: list[dict] = []
    annotations: list[dict] = []

    # Optional faint zero baseline per panel (off by default).
    if baseline and ylo <= 0 <= yhi:
        for p in panels:
            k = p["row"] * ncols + p["col"] + 1
            sfx = "" if k == 1 else str(k)
            shapes.append({
                "type": "line", "xref": f"x{sfx}", "yref": f"y{sfx}",
                "x0": xlo, "x1": xhi, "y0": 0, "y1": 0,
                "line": {"color": "#d0d0d0", "width": 0.6},
            })

    # Shared scale bar (paper coords), sized to the data→paper mapping of one panel.
    # Record the shape + annotation indices so the editor can find this primitive
    # deterministically (show/hide/restyle) instead of guessing among layout.shapes.
    sb_shape_idx = [len(shapes), len(shapes) + 1]
    sb_anno_idx = [len(annotations), len(annotations) + 1]
    hlen = (sb["x_len"] / xspan) * col_w
    vlen = (sb["y_len"] / yspan) * row_h
    bx, by = gx0 * 0.5, 0.02
    shapes.append({  # vertical (amplitude)
        "type": "line", "xref": "paper", "yref": "paper",
        "x0": bx, "x1": bx, "y0": by, "y1": round(by + vlen, 5),
        "line": {"color": "#000", "width": 1.5},
    })
    shapes.append({  # horizontal (time)
        "type": "line", "xref": "paper", "yref": "paper",
        "x0": bx, "x1": round(bx + hlen, 5), "y0": by, "y1": by,
        "line": {"color": "#000", "width": 1.5},
    })
    annotations.append({
        "xref": "paper", "yref": "paper", "x": round(bx - 0.006, 5), "y": round(by + vlen / 2, 5),
        "text": f"{_num(sb['y_len'])} {sb['y_unit']}", "showarrow": False,
        "textangle": -90, "xanchor": "right", "yanchor": "middle", "font": {"size": 11},
    })
    annotations.append({
        "xref": "paper", "yref": "paper", "x": round(bx + hlen / 2, 5), "y": round(by - 0.014, 5),
        "text": f"{_num(sb['x_len'])} {sb['x_unit']}", "showarrow": False,
        "xanchor": "center", "yanchor": "top", "font": {"size": 11},
    })

    if row_labels:
        for r, lab in enumerate(row_labels):
            d = y_domain(r)
            annotations.append({
                "xref": "paper", "yref": "paper", "x": round(gx1 + 0.008, 5),
                "y": round((d[0] + d[1]) / 2, 5), "text": str(lab), "showarrow": False,
                "xanchor": "left", "yanchor": "middle", "font": {"size": 11},
            })
    if col_labels:
        for c, lab in enumerate(col_labels):
            d = x_domain(c)
            annotations.append({
                "xref": "paper", "yref": "paper", "x": round((d[0] + d[1]) / 2, 5),
                "y": round(gy1 + 0.012, 5), "text": str(lab), "showarrow": False,
                "xanchor": "center", "yanchor": "bottom", "font": {"size": 12, "color": "#111"},
            })

    layout["shapes"] = shapes
    layout["annotations"] = annotations

    # Render-inert editor hint (Plotly ignores layout.meta): deterministic series grouping +
    # the scale-bar primitive's shape/annotation indices, so the agnostic editor edits the 6
    # ERG conditions (not 42 traces) and manages the scale bar without guessing. See
    # docs/figure-editor-contract/spec.md §3.1.
    selom: dict = {"figureKind": "trace_grid"}
    grouped: dict[str, list[int]] = {}
    order: list[str] = []
    for i, p in enumerate(panels):
        g = p.get("group")
        if g is None:
            continue
        g = str(g)
        if g not in grouped:
            grouped[g] = []
            order.append(g)
        grouped[g].append(i)
    if order:
        selom["series"] = [
            {"label": g, "traceIndices": grouped[g], "colorPath": f"/data/{grouped[g][0]}/line/color"}
            for g in order
        ]
    selom["primitives"] = [{
        "kind": "scalebar", "shapeIdx": sb_shape_idx, "annoIdx": sb_anno_idx,
        "xLen": sb["x_len"], "xUnit": sb["x_unit"], "yLen": sb["y_len"], "yUnit": sb["y_unit"],
    }]
    layout.setdefault("meta", {})["selom"] = selom

    return {"data": data, "layout": layout}


def _num(v) -> str:
    """Render a scale-bar length without a trailing ``.0`` (200 not 200.0)."""
    f = float(v)
    return str(int(f)) if f.is_integer() else str(f)

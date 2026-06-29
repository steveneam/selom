"""Generic small-multiples *trace grid* — the reusable figure primitive behind the ERG
module (and any time-series shown as ``row × col`` small multiples: EEG/ECG/patch-clamp,
dose × condition, …). See docs/records/erg-module/spec.md.

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


def _bounds(vals) -> tuple[float, float]:
    nums = [float(v) for v in vals if v is not None]
    lo, hi = min(nums), max(nums)
    if lo == hi:  # degenerate (flat / single point) — give the axis a unit of room
        hi = lo + 1.0
    return float(lo), float(hi)


def _extent(panels: list[dict]) -> tuple[list, list]:
    """All x and all y across the panels INCLUDING optional overlays (``band``/``error``/``markers``/
    ``extra_lines``), so the shared axis range never clips an overlay. A panel with no overlay keys
    contributes only its line ``x``/``y`` — identical to the pre-overlay behaviour."""
    xs: list = []
    ys: list = []
    for p in panels:
        xs.extend(p["x"])
        ys.extend(p["y"])
        b = p.get("band")
        if b:
            xs.extend(b["x"])
            ys.extend(b.get("lower", []))
            ys.extend(b.get("upper", []))
        e = p.get("error")
        if e:
            xs.extend(e["x"])
            for yy, ee in zip(e["y"], e.get("err", [])):
                ys.append(yy)
                if ee is not None:
                    ys.extend([yy - ee, yy + ee])
        for m in p.get("markers", []):
            xs.append(m["x"])
            ys.append(m["y"])
        for ln in p.get("extra_lines", []):
            xs.extend(ln["x"])
            ys.extend(ln["y"])
    return xs, ys


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
    all_x, all_y = _extent(panels)
    xlo, xhi = _bounds(all_x)
    ylo, yhi = _bounds(all_y)
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
    panel_main_idx: list[int] = []  # data index of each panel's primary line (overlays shift indices)
    panel_marker_idx: list[int | None] = []  # data index of each panel's marker-dot overlay (or None)
    # A titled grid needs top headroom or the title clips the figure edge (above the column labels).
    layout: dict = {"showlegend": False,
                    "margin": {"t": 48 if title else 10, "r": 10, "b": 10, "l": 10}}
    if title:
        layout["title"] = {"text": title, "y": 0.985, "yanchor": "top"}

    for p in panels:
        k = p["row"] * ncols + p["col"] + 1
        sfx = "" if k == 1 else str(k)
        xref, yref = f"x{sfx}", f"y{sfx}"
        # Overlays drawn BEHIND the mean line (shaded band, faint replicate lines) go first so the
        # line sits on top; a panel with no overlay keys contributes nothing here (byte-identical).
        data.extend(_overlay_behind(p, xref, yref))
        line = {"width": line_width}
        if p.get("color"):
            line["color"] = p["color"]
        trace = {
            "type": "scatter",
            "mode": "lines",
            "x": [round(float(v), 4) for v in p["x"]],
            # 6 dp (was 4): a non-µV display unit rescales the amplitude (mV → ×0.001), and
            # 4 dp would crush small mV/V features to zero. Golden-safe: the stub's y-values
            # are already coarser than 6 dp, so the µV default is byte-identical.
            "y": [round(float(v), 6) for v in p["y"]],
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
        if p.get("opacity") is not None:  # e.g. central=none draws every replicate at equal weight
            trace["opacity"] = float(p["opacity"])
        panel_main_idx.append(len(data))
        data.append(trace)
        # Overlays drawn ON TOP of the mean line (per-point error bars, marker dots) go last.
        # The marker-dot trace (when present) is appended LAST by _overlay_front, so its data
        # index is len(data)-1 — recorded so the editor can bind a dragged dot to its segment.
        data.extend(_overlay_front(p, xref, yref))
        panel_marker_idx.append(len(data) - 1 if p.get("markers") else None)
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
        grouped[g].append(panel_main_idx[i])  # the line's real data index (overlays shift it)
    if order:
        selom["series"] = [
            {"label": g, "traceIndices": grouped[g], "colorPath": f"/data/{grouped[g][0]}/line/color"}
            for g in order
        ]
    selom["primitives"] = [{
        "kind": "scalebar", "shapeIdx": sb_shape_idx, "annoIdx": sb_anno_idx,
        "xLen": sb["x_len"], "xUnit": sb["x_unit"], "yLen": sb["y_len"], "yUnit": sb["y_unit"],
    }]

    # Editable landmark marks (docs/records/erg-manual-marks/spec.md R4): each panel may carry a
    # `mark_meta` list [{segment, role, t_ms, source, label}, …] describing its a/b (or N1/P1)
    # landmark points (seeded from the auto-detection / supplied manual marks). We surface them as
    # `meta.selom.marks` so the Marks panel can list/edit them and the canvas can bind a drag back
    # to the right `manual_marks` entry. `trace`/`point` (the marker-dot's data index + point index)
    # are attached only when the visual dot is actually drawn (so a dragged dot is resolvable).
    marks_meta: list[dict] = []
    for i, p in enumerate(panels):
        mm = p.get("mark_meta")
        if not mm:
            continue
        tr = panel_marker_idx[i]
        n_dots = len(p.get("markers", []))
        for j, m in enumerate(mm):
            entry = dict(m)
            if tr is not None and j < n_dots:
                entry["trace"] = tr
                entry["point"] = j
            marks_meta.append(entry)
    if marks_meta:
        selom["marks"] = marks_meta

    # Capability contract (docs/figure-data-capabilities/spec.md §1) — a trace grid is an ERG
    # waveform figure: a stray drag must NOT box-zoom (default gesture "none") and wheel-zoom is OFF
    # (a stray scroll zooms one panel and is fiddly to undo on a small-multiples grid); zoom/pan are
    # DELIBERATE modebar buttons. It carries editable landmark dots iff it has marks, and owns the
    # scale-bar primitive. Render-inert: drives the editor's tools + gestures, not pixels.
    selom["capabilities"] = {
        "gesture": {"default": "none", "zoomTools": True, "scrollZoom": False},
        "tools": {"landmarkMarks": bool(marks_meta), "scaleBar": True},
    }

    layout.setdefault("meta", {})["selom"] = selom

    return {"data": data, "layout": layout}


def _num(v) -> str:
    """Render a scale-bar length without a trailing ``.0`` (200 not 200.0)."""
    f = float(v)
    return str(int(f)) if f.is_integer() else str(f)


# --- per-panel overlays -----------------------------------------------------------------
# A panel dict may carry optional overlays drawn against its own hidden axis (the SAME
# xaxis{N}/yaxis{N} as the line). One shared hook serves two features (docs/records/erg-module/
# mean-spread-styling-spec.md §3, D6): the N1/P1 marker dots on the flicker grid (M3), and
# the mean ± spread band / per-point error bars / faint replicate lines for the styling
# feature. A panel with none of these keys emits no extra traces (byte-identical output).
#
#   band:        {x, lower, upper, color?, alpha?=0.25, boundary?=none|solid|dashed, group?}
#   error:       {x, y, err[], every?=1, color?, width?=1.0, cap?=3.0, size?=4}
#   markers:     [{x, y, label?, color?, size?=7}, …]
#   extra_lines: [{x, y, color?, width?=0.6, alpha?=0.18}, …]

def _rgba(hexcolor, alpha) -> str:
    """``'#rrggbb'`` (or 3-digit shorthand) → ``'rgba(r,g,b,a)'``. Plotly won't derive a
    translucent fill from a hex line colour, so band fills are emitted as rgba server-side."""
    h = str(hexcolor or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        r = g = b = 136
    return f"rgba({r},{g},{b},{round(float(alpha), 3)})"


def _overlay_behind(p: dict, xref: str, yref: str) -> list[dict]:
    """Overlay traces drawn behind the panel's mean line: the shaded ± band (2-trace ``tonexty``
    fill) and faint replicate lines. Returns ``[]`` for a panel with neither key."""
    out: list[dict] = []
    b = p.get("band")
    if b:
        x = [round(float(v), 4) for v in b["x"]]
        lo = [round(float(v), 6) for v in b["lower"]]
        hi = [round(float(v), 6) for v in b["upper"]]
        color = b.get("color") or "#888888"
        boundary = str(b.get("boundary", "none")).lower()
        bline = ({"width": 0.8, "color": color, "dash": "dash"} if boundary == "dashed"
                 else {"width": 0.8, "color": color} if boundary == "solid"
                 else {"width": 0})
        base = {"type": "scatter", "mode": "lines", "xaxis": xref, "yaxis": yref,
                "hoverinfo": "skip", "showlegend": False}
        t_lo = {**base, "x": x, "y": lo, "line": dict(bline)}
        t_hi = {**base, "x": x, "y": hi, "line": dict(bline), "fill": "tonexty",
                "fillcolor": _rgba(color, b.get("alpha", 0.25))}
        if b.get("group") is not None:
            t_lo["legendgroup"] = t_hi["legendgroup"] = str(b["group"])
        out += [t_lo, t_hi]
    for ln in p.get("extra_lines", []):
        out.append({
            "type": "scatter", "mode": "lines",
            "x": [round(float(v), 4) for v in ln["x"]],
            "y": [round(float(v), 6) for v in ln["y"]],
            "line": {"width": float(ln.get("width", 0.6)), "color": ln.get("color") or "#999999"},
            "opacity": float(ln.get("alpha", 0.18)),
            "xaxis": xref, "yaxis": yref, "hoverinfo": "skip", "showlegend": False,
        })
    return out


def _overlay_front(p: dict, xref: str, yref: str) -> list[dict]:
    """Overlay traces drawn on top of the panel's mean line: per-point error bars and marker
    dots. Returns ``[]`` for a panel with neither key."""
    out: list[dict] = []
    e = p.get("error")
    if e:
        every = max(1, int(e.get("every", 1) or 1))  # draw-every-Nth (de-clutter dense series)
        arr = [float(ev) if (i % every == 0 and ev is not None) else None
               for i, ev in enumerate(e.get("err", []))]
        color = e.get("color") or "#444444"
        out.append({
            "type": "scatter", "mode": "markers",
            "x": [round(float(v), 4) for v in e["x"]],
            "y": [round(float(v), 6) for v in e["y"]],
            "marker": {"color": color, "size": float(e.get("size", 4))},
            "error_y": {"type": "data", "array": arr, "visible": True,
                        "thickness": float(e.get("width", 1.0)), "width": float(e.get("cap", 3.0)),
                        "color": color},
            "xaxis": xref, "yaxis": yref, "hoverinfo": "x+y", "showlegend": False,
        })
    markers = p.get("markers")
    if markers:
        colors = [m.get("color") or "#333333" for m in markers]
        tr = {
            "type": "scatter",
            "x": [round(float(m["x"]), 4) for m in markers],
            "y": [round(float(m["y"]), 6) for m in markers],
            "marker": {"color": colors,
                       "size": float(markers[0].get("size", 7)),
                       "line": {"color": "#ffffff", "width": 0.8}, "symbol": "circle"},
            "xaxis": xref, "yaxis": yref, "showlegend": False,
        }
        labels = [str(m.get("label", "")) for m in markers]
        if any(labels):
            # Pinned role labels (figure-data-capabilities §6): coloured to match each dot and placed
            # per-role (trough labels below the dot, peak labels above) so they clear the trace.
            tr["mode"] = "markers+text"
            tr["text"] = labels
            tr["textposition"] = [m.get("textpos", "top center") for m in markers]
            tr["textfont"] = {"size": 10, "color": colors}
            tr["hoverinfo"] = "x+y+text"
        else:
            tr["mode"] = "markers"
            tr["hoverinfo"] = "x+y"
        out.append(tr)
    return out

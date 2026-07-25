"""Shared, dependency-free helpers for the FACS / flow-cytometry skill.

Pure-stdlib builders so the ``facs_gating`` STUB runs with ZERO heavy deps: Plotly
trace assembly (density / contour / histogram / scatter), gate-shape geometry
(rectangle / polygon / quadrant) in **transformed display space**, the population
StatsTable, plus a tolerant gate-JSON parser and a channel resolver.

The heavy numeric work — loading the FCS (FlowIO), compensation ($SPILLOVER / operator
matrix, via FlowUtils), the logicle/arcsinh/log/linear transform (FlowUtils), the
gaussian-KDE scatter colouring, and the clean-room numpy gate-tree population stats —
lives in ``skills/facs_gating/run_real.py``. This module never imports numpy or the
flow engines, so both the stub and the light skeleton stay dependency-free.
"""
from __future__ import annotations

import json

from skills._table import table

# Gate outline / crosshair colour — a neutral publication ink, kept off the theme's
# volcano path so base theming leaves layout shapes untouched.
GATE_LINE = "#1f2a37"
# ColorBrewer *Blues*: starts at white so zero-density bins blend into the white plot
# background, then ramps to a deep navy — a clean, print-safe density ramp.
DENSITY_COLORSCALE = [
    [0.0, "#ffffff"], [0.125, "#deebf7"], [0.25, "#c6dbef"], [0.375, "#9ecae1"],
    [0.5, "#6baed6"], [0.625, "#4292c6"], [0.75, "#2171b5"], [0.875, "#08519c"],
    [1.0, "#08306b"],
]

_RECT = {"rect", "rectangle"}
_POLY = {"polygon", "poly"}
_QUAD = {"quadrant", "quad"}


# ---- channel resolve --------------------------------------------------------
def resolve_channel(labels, requested, aliases=None):
    """Resolve ``requested`` to one of ``labels`` (case-insensitive, alias-aware).

    ``labels`` are the detector (PnN) names; ``aliases`` is an optional parallel list of
    stain (PnS) names, so a request for ``"CD3"`` matches the detector whose stain is
    ``"CD3"``. Returns the matched PnN label, or ``None`` when nothing matches.
    """
    want = str(requested or "").strip().lower()
    if not want:
        return None
    for lab in labels:
        if str(lab).strip().lower() == want:
            return lab
    for i, alias in enumerate(aliases or []):
        if alias and str(alias).strip().lower() == want and i < len(labels):
            return labels[i]
    # loose containment (e.g. "FITC" -> "FITC-A") as a last resort
    for lab in labels:
        if want in str(lab).strip().lower():
            return lab
    return None


def default_channels(labels):
    """Pick a sensible default (x, y) pair — the first two channels present."""
    labs = list(labels)
    if len(labs) >= 2:
        return labs[0], labs[1]
    if len(labs) == 1:
        return labs[0], labs[0]
    return None, None


# ---- gate JSON parse --------------------------------------------------------
def _num(v):
    """Coerce to a finite float, else ``None`` (a ``null`` bound = open on that side)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    import math

    return f if math.isfinite(f) else None


# A16 — why a gate the operator DEFINED did not produce a population. The operator supplied the
# gate explicitly, so its disappearance from the table is a wrong result presented as a complete
# one: nothing distinguished "this population was 0 events" from "this gate never ran". Every drop
# now carries one of these reasons all the way into the population table's `status` column.
GATE_STATUS_OK = "ok"
DROP_NOT_AN_OBJECT = "not_a_gate_object"
DROP_NO_GEOMETRY = "no_geometry"
DROP_TOO_FEW_VERTICES = "fewer_than_3_vertices"
DROP_NON_FINITE_SPLIT = "non_finite_split"
DROP_UNKNOWN_TYPE = "unknown_type"
DROP_CHANNEL_NOT_IN_FCS = "channel_not_in_fcs"
DROP_PARENT_UNRESOLVED = "parent_unresolved"

_DROP_FIX = {
    DROP_NOT_AN_OBJECT: "each entry in `gates` must be a JSON object.",
    DROP_NO_GEOMETRY: "a rectangle gate needs at least one of x_min / x_max / y_min / y_max.",
    DROP_TOO_FEW_VERTICES: "a polygon gate needs at least 3 finite [x, y] vertices.",
    DROP_NON_FINITE_SPLIT: "a quadrant gate needs finite x_split and y_split values.",
    DROP_UNKNOWN_TYPE: "`type` must be one of rect / polygon / quadrant.",
    DROP_CHANNEL_NOT_IN_FCS: "name a channel the FCS actually carries (check the PnN detector names).",
    DROP_PARENT_UNRESOLVED: "resolve the parent gate first — a child of an unresolved gate cannot "
                            "be counted, and counting it against ALL events would be a wrong number.",
}


def drop_reason_fix(reason):
    """The one-line, actionable fix for a gate-drop reason (see :data:`GATE_STATUS_OK` siblings)."""
    return _DROP_FIX.get(reason, "check the gate definition.")


def parse_gates(raw, default_x=None, default_y=None):
    """Parse the ``gates`` JSON-string param → ``(gates, dropped)``.

    Travels like ERG's ``manual_marks`` — a JSON string (or an already-parsed
    ``dict``/``list``). Accepts either a bare list of gate objects or ``{"gates": [...]}``.
    Bounds are in **transformed display space** (the same coordinates the plot is drawn
    in). Each output gate is ``{"id", "type", "parent", "x", "y", "label", ...geometry}`` where
    ``type`` is one of ``rect`` / ``polygon`` / ``quadrant`` and channels default to the
    plotted ``(default_x, default_y)`` when omitted.

    Still tolerant — a malformed or geometry-less entry never raises — but no longer SILENT
    (A16): every dropped entry is returned in ``dropped`` as
    ``{"id", "label", "reason", "fix"}`` so the caller can put a verdict row in the population
    table instead of letting the population vanish.
    """
    dropped: list[dict] = []

    def _drop(gid, label, reason):
        dropped.append({"id": gid, "label": label or gid, "reason": reason,
                        "fix": drop_reason_fix(reason)})

    if not raw:
        return [], dropped
    obj = raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except (TypeError, ValueError):
            return [], dropped
    if isinstance(obj, dict):
        obj = obj.get("gates", [])
    if not isinstance(obj, list):
        return [], dropped

    out: list[dict] = []
    for i, item in enumerate(obj):
        gid = str((item.get("id") if isinstance(item, dict) else None) or f"P{i + 1}")
        if not isinstance(item, dict):
            _drop(gid, gid, DROP_NOT_AN_OBJECT)
            continue
        kind = str(item.get("type", "rect")).strip().lower()
        label = str(item.get("label") or gid)
        base = {
            "id": gid,
            "parent": (str(item["parent"]) if item.get("parent") not in (None, "") else None),
            "x": item.get("x") or default_x,
            "y": item.get("y") or default_y,
            "label": label,
        }
        if kind in _RECT:
            g = {**base, "type": "rect", "x_min": _num(item.get("x_min")),
                 "x_max": _num(item.get("x_max")), "y_min": _num(item.get("y_min")),
                 "y_max": _num(item.get("y_max"))}
            if g["x_min"] is None and g["x_max"] is None and g["y_min"] is None and g["y_max"] is None:
                _drop(gid, label, DROP_NO_GEOMETRY)
                continue
            out.append(g)
        elif kind in _POLY:
            verts = []
            for v in item.get("vertices") or []:
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    vx, vy = _num(v[0]), _num(v[1])
                    if vx is not None and vy is not None:
                        verts.append((vx, vy))
            if len(verts) < 3:
                _drop(gid, label, DROP_TOO_FEW_VERTICES)
                continue
            out.append({**base, "type": "polygon", "vertices": verts})
        elif kind in _QUAD:
            xs, ys = _num(item.get("x_split")), _num(item.get("y_split"))
            if xs is None or ys is None:
                _drop(gid, label, DROP_NON_FINITE_SPLIT)
                continue
            out.append({**base, "type": "quadrant", "x_split": xs, "y_split": ys})
        else:
            _drop(gid, label, DROP_UNKNOWN_TYPE)
    return out, dropped


# ---- plotly trace builders --------------------------------------------------
def density_trace(x, y, bins, colorscale=None):
    """A 2-D density heatmap (``go.Histogram2d``) — the default population view."""
    return {
        "type": "histogram2d", "x": list(x), "y": list(y),
        "nbinsx": int(bins), "nbinsy": int(bins),
        "colorscale": colorscale or DENSITY_COLORSCALE,
        "colorbar": {"title": {"text": "events"}, "thickness": 12, "len": 0.7, "outlinewidth": 0},
        "hoverinfo": "x+y+z",
    }


def contour_trace(x, y, bins, colorscale=None):
    """A 2-D density contour (``go.Histogram2dContour``)."""
    return {
        "type": "histogram2dcontour", "x": list(x), "y": list(y),
        "nbinsx": int(bins), "nbinsy": int(bins),
        "colorscale": colorscale or DENSITY_COLORSCALE,
        "colorbar": {"title": {"text": "events"}, "thickness": 12, "len": 0.7, "outlinewidth": 0},
        "contours": {"coloring": "fill"}, "line": {"width": 0.5},
    }


def histogram_trace(x, bins):
    """A single-parameter 1-D histogram (``go.Histogram``)."""
    return {
        "type": "histogram", "x": list(x), "nbinsx": int(bins),
        "marker": {"color": "#4292c6", "line": {"color": "#08519c", "width": 0.5}},
        "opacity": 0.9,
    }


def scatter_trace(x, y, color, colorscale=None):
    """A WebGL scatter (``go.Scattergl``) coloured by per-event density (``color``)."""
    return {
        "type": "scattergl", "mode": "markers", "x": list(x), "y": list(y),
        "marker": {
            "color": list(color), "colorscale": colorscale or DENSITY_COLORSCALE,
            "size": 3, "opacity": 0.7, "showscale": True,
            "colorbar": {"title": {"text": "density"}, "thickness": 12, "len": 0.7, "outlinewidth": 0},
        },
        "hoverinfo": "x+y",
    }


# ---- layout -----------------------------------------------------------------
def figure_layout(plot, x_label, y_label, title, transform):
    """Editable layout for the chosen ``plot`` — axis titles carry the transform note.

    ``histogram`` is 1-D (x = the parameter, y = event count); the 2-D views label both
    axes with their channel and the display transform.
    """
    scale = f" ({transform})" if transform and transform != "linear" else ""
    lay = {
        "title": {"text": title},
        "xaxis": {"title": {"text": f"{x_label}{scale}"}, "zeroline": False},
        "showlegend": False,
        "plot_bgcolor": "white",
        "bargap": 0.02,
    }
    if plot == "histogram":
        lay["yaxis"] = {"title": {"text": "event count"}, "zeroline": False}
    else:
        lay["yaxis"] = {"title": {"text": f"{y_label}{scale}"}, "zeroline": False}
    return lay


# ---- gate shapes ------------------------------------------------------------
def _same(a, b):
    return a is not None and b is not None and str(a).strip().lower() == str(b).strip().lower()


def gate_shapes(gates, plot_x, plot_y):
    """Build ``(shapes, annotations)`` for the gates drawn on the ``(plot_x, plot_y)`` axes.

    A gate is drawn only when its channels match the plotted axes (gates on other
    channels still drive the population stats — they're just not overlaid here). Bounds
    are consumed as-is (transformed display space). Quadrants render as a full crosshair
    at ``(x_split, y_split)`` via paper-referenced lines.
    """
    shapes: list[dict] = []
    annos: list[dict] = []
    line = {"color": GATE_LINE, "width": 1.5}
    for g in gates:
        if not (_same(g.get("x"), plot_x) and _same(g.get("y"), plot_y)):
            continue
        if g["type"] == "rect":
            x0, x1 = g.get("x_min"), g.get("x_max")
            y0, y1 = g.get("y_min"), g.get("y_max")
            if None in (x0, x1, y0, y1):
                continue
            shapes.append({"type": "rect", "xref": "x", "yref": "y",
                           "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                           "line": line, "fillcolor": "rgba(0,0,0,0)"})
            annos.append(_label_anno(g["label"], min(x0, x1), max(y0, y1)))
        elif g["type"] == "polygon":
            verts = g["vertices"]
            path = "M" + " L".join(f"{vx},{vy}" for vx, vy in verts) + " Z"
            shapes.append({"type": "path", "xref": "x", "yref": "y", "path": path,
                           "line": line, "fillcolor": "rgba(0,0,0,0)"})
            annos.append(_label_anno(g["label"], min(v[0] for v in verts),
                                     max(v[1] for v in verts)))
        elif g["type"] == "quadrant":
            xs, ys = g["x_split"], g["y_split"]
            shapes.append({"type": "line", "xref": "x", "yref": "paper",
                           "x0": xs, "x1": xs, "y0": 0, "y1": 1, "line": line})
            shapes.append({"type": "line", "xref": "paper", "yref": "y",
                           "x0": 0, "x1": 1, "y0": ys, "y1": ys, "line": line})
    return shapes, annos


def _label_anno(text, x, y):
    return {"x": x, "y": y, "xref": "x", "yref": "y", "text": str(text),
            "showarrow": False, "xanchor": "left", "yanchor": "bottom",
            "font": {"size": 11, "color": GATE_LINE},
            "bgcolor": "rgba(255,255,255,0.7)"}


# ---- population table -------------------------------------------------------
def _r(v):
    """Round a float to 2 dp for the table; pass ``None`` / non-numbers through."""
    if v is None or isinstance(v, bool):
        return v
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return v


def population_table(rows, x_label, y_label, title="Population statistics"):
    """A StatsTable of the gate tree: count, % parent, % total, median MFI (x, y), and status.

    ``rows`` is an ordered list of dicts with keys ``population``, ``parent``, ``count``,
    ``pct_parent``, ``pct_total``, ``mfi_x``, ``mfi_y`` (MFI values may be ``None``), plus an
    optional ``status``.

    ``status`` is the A16 verdict column and it is the reason a row may carry ``count=None``: an
    unresolved gate gets a ROW saying why it could not be counted, instead of vanishing from a
    table whose counts ARE the result. It is appended last so a reader (and the FE's column
    handling) sees the same leading columns as before.
    """
    columns = ["population", "parent", "count", "% parent", "% total",
               f"median {x_label}", f"median {y_label}", "status"]
    out = []
    for r in rows:
        out.append([
            r.get("population"), r.get("parent") or "—", r.get("count"),
            _r(r.get("pct_parent")), _r(r.get("pct_total")),
            _r(r.get("mfi_x")), _r(r.get("mfi_y")), r.get("status") or GATE_STATUS_OK,
        ])
    return table(columns, out, title=title)

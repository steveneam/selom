"""UpSet plot of set intersections (paper Fig 4F).

A scalable alternative to a Venn diagram: an intersection-size bar chart sits above a
dot-matrix that reads off *which* sets each intersection covers, with a set-size bar
panel on the left. Built entirely from editable Plotly traces over a shared category
axis — no upsetplot/AGPL dependency. Input is a boolean membership matrix
(elements × sets); the real engine derives the intersections, the stub is a fixed
3-set example of the same wire shape.
"""

from skills._engine import use_real_engine

# Palette (kept local so the stub golden is dependency-free; mirrors theme tokens).
_BAR = "#3f4c5a"     # intersection-size bars / membership
_SETBAR = "#aeb7c2"  # set-size bars
_DOT_OFF = "#dde3ea"  # absent-membership dots
_DOT_ON = "#33404d"   # present-membership dots + connectors


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.upset.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic 3-set UpSet — sets A/B/C with fixed intersection sizes."""
    intersections = [
        {"members": ["A"], "size": 30},
        {"members": ["B"], "size": 24},
        {"members": ["A", "B"], "size": 18},
        {"members": ["C"], "size": 15},
        {"members": ["A", "C"], "size": 9},
        {"members": ["A", "B", "C"], "size": 6},
    ]
    sets = ["A", "B", "C"]          # display order, largest first (top of matrix)
    set_sizes = [63, 48, 30]
    return upset_spec(intersections, sets, set_sizes, "Set intersections (stub)")


def upset_spec(intersections, sets, set_sizes, title) -> dict:
    """Editable UpSet spec — shared by the stub and the real engine.

    ``intersections`` is an ordered list of ``{"members": [set names], "size": int}``
    (already filtered + sorted, largest first). ``sets`` lists the set names in
    display order (largest first → top row); ``set_sizes`` is aligned to it.
    """
    sets = list(sets)
    ids = [f"c{i}" for i in range(len(intersections))]

    # 1) intersection-size bars (top panel, axes x/y) — added first so the shared
    #    x category order follows the (sorted) intersection order.
    sizes = [int(it["size"]) for it in intersections]
    bars = {
        "type": "bar", "x": ids, "y": sizes,
        "marker": {"color": _BAR}, "width": 0.6,
        "text": [str(s) for s in sizes], "textposition": "outside",
        "cliponaxis": False, "showlegend": False, "hoverinfo": "y",
    }

    # 2) set-size bars (left panel, axes x2/y2)
    setbars = {
        "type": "bar", "orientation": "h",
        "x": [int(s) for s in set_sizes], "y": list(sets),
        "xaxis": "x2", "yaxis": "y2",
        "marker": {"color": _SETBAR}, "showlegend": False, "hoverinfo": "x",
    }

    # 3) background dot grid (every set × every intersection), axes x/y2
    bg_x, bg_y = [], []
    for cid in ids:
        for s in sets:
            bg_x.append(cid)
            bg_y.append(s)
    background = {
        "type": "scatter", "mode": "markers", "x": bg_x, "y": bg_y,
        "xaxis": "x", "yaxis": "y2",
        "marker": {"color": _DOT_OFF, "size": 11},
        "showlegend": False, "hoverinfo": "skip",
    }

    # 4) connectors — a vertical line through the member rows of each intersection
    pos = {s: i for i, s in enumerate(sets)}
    line_x, line_y = [], []
    for cid, it in zip(ids, intersections):
        members = [m for m in it["members"] if m in pos]
        if len(members) >= 2:
            lo = min(members, key=lambda m: pos[m])
            hi = max(members, key=lambda m: pos[m])
            line_x += [cid, cid, None]
            line_y += [lo, hi, None]
    connectors = {
        "type": "scatter", "mode": "lines", "x": line_x, "y": line_y,
        "xaxis": "x", "yaxis": "y2",
        "line": {"color": _DOT_ON, "width": 2},
        "showlegend": False, "hoverinfo": "skip",
    }

    # 5) present-membership dots (drawn last → on top), axes x/y2
    on_x, on_y = [], []
    for cid, it in zip(ids, intersections):
        for m in it["members"]:
            if m in pos:
                on_x.append(cid)
                on_y.append(m)
    present = {
        "type": "scatter", "mode": "markers", "x": on_x, "y": on_y,
        "xaxis": "x", "yaxis": "y2",
        "marker": {"color": _DOT_ON, "size": 11},
        "showlegend": False, "hoverinfo": "skip",
    }

    return {
        "data": [bars, setbars, background, connectors, present],
        "layout": {
            "title": {"text": title},
            "bargap": 0.4,
            "xaxis":  {"domain": [0.24, 1.0], "anchor": "y2", "showgrid": False,
                       "showticklabels": False, "ticks": "", "zeroline": False},
            "yaxis":  {"domain": [0.55, 1.0], "title": {"text": "Intersection size"},
                       "zeroline": False},
            "xaxis2": {"domain": [0.0, 0.18], "anchor": "y2", "autorange": "reversed",
                       "title": {"text": "Set size"}, "showgrid": False, "zeroline": False},
            "yaxis2": {"domain": [0.0, 0.46], "anchor": "x2",
                       "categoryorder": "array", "categoryarray": list(reversed(sets)),
                       "showgrid": False, "zeroline": False},
        },
    }

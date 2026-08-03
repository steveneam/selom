"""Venn diagram of 2–3 set overlaps.

The overlap figure reviewers expect for "which genes are shared between these
contrasts". Consumes the SAME boolean membership matrix as ``upset`` (elements ×
sets), so a table that drives one drives the other — the two are the small-n and
large-n views of one question, and ``upset`` is the honest answer above three sets.

Two deliberate choices worth knowing before editing:

* **The circles are real traces, not ``layout.shapes``.** Each set is a filled
  ``scatter`` polygon, so it is legend-toggleable, individually restylable in the
  editor, and — the part that matters — the figure's ``data`` is non-empty, which is
  what ``smoke.check_figure`` requires of a genuine editable figure. A shapes-only
  diagram would render identically and fail that gate, correctly: it would be a
  picture, not an editable figure.
* **Region counts are a separate text trace**, positioned at hand-checked points that
  are provably inside their own region and outside every other (verified per region
  against the circle equations). Plotly has no Venn primitive and no region centroid
  solver; a computed centroid is not worth a dependency for the only two layouts that
  exist.

Above three sets the engine refuses and names ``upset`` rather than drawing a
four-ellipse diagram nobody can read.
"""

import math

from skills._engine import to_bool, use_real_engine
from skills._table import table

# Set fills. Deliberately local (the stub golden must stay dependency-free) and
# translucent so overlaps read as a blend rather than a stack.
_FILLS = ["#3f6fb5", "#c4622d", "#4f9068"]
_OPACITY = 0.42

# --- geometry ---------------------------------------------------------------------------
# r = 1 for every circle. Centres and per-region label anchors are fixed for the only two
# layouts a Venn supports. Each label point was checked against all three circle equations:
# inside its own sets, outside the others (see the module docstring).
_TWO = {
    "centers": [(-0.42, 0.0), (0.42, 0.0)],
    "labels": {("0",): (-0.72, 0.0), ("1",): (0.72, 0.0), ("0", "1"): (0.0, 0.0)},
    "names": [(-0.42, 1.14), (0.42, 1.14)],
    "xrange": [-1.75, 1.75], "yrange": [-1.30, 1.45],
}
_THREE = {
    "centers": [(0.0, 0.55), (-0.4763, -0.275), (0.4763, -0.275)],
    "labels": {
        ("0",): (0.0, 0.85), ("1",): (-0.75, -0.50), ("2",): (0.75, -0.50),
        ("0", "1"): (-0.47, 0.16), ("0", "2"): (0.47, 0.16), ("1", "2"): (0.0, -0.62),
        ("0", "1", "2"): (0.0, -0.10),
    },
    # The two lower set names sit just clear of their circles (checked: |p − centre| > r), far
    # enough out not to touch the stroke — at 1.32/0.98 the text kissed the edge when rendered.
    "names": [(0.0, 1.72), (-1.42, -1.06), (1.42, -1.06)],
    "xrange": [-2.15, 2.15], "yrange": [-1.85, 2.05],
}


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.venn.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic 3-set DE overlap — the shape a contrast comparison produces."""
    counts = {
        ("A",): 412, ("B",): 268, ("C",): 190,
        ("A", "B"): 143, ("A", "C"): 96, ("B", "C"): 61,
        ("A", "B", "C"): 55,
    }
    return venn_spec(counts, ["A", "B", "C"], params, "Set overlap (stub)")


def _circle(cx, cy, r=1.0, n=180):
    """Closed polygon approximating a circle — 180 points is smooth at figure scale."""
    xs, ys = [], []
    for i in range(n + 1):
        a = 2.0 * math.pi * i / n
        xs.append(round(cx + r * math.cos(a), 5))
        ys.append(round(cy + r * math.sin(a), 5))
    return xs, ys


def venn_spec(counts: dict, sets: list, params: dict, title: str) -> dict:
    """Editable Venn spec — shared by the stub and the real engine.

    ``counts`` maps a tuple of set NAMES (a region, e.g. ``("A","B")`` = in A and B and
    nothing else) to its element count; ``sets`` is the display order. Regions absent
    from ``counts`` are drawn as 0 — an empty overlap is a finding, not a gap, and
    silently omitting it would let a reader assume the region was never computed.
    """
    sets = list(sets)
    if len(sets) not in (2, 3):
        raise ValueError(
            f"venn draws 2 or 3 sets, got {len(sets)} — use the `upset` skill for more "
            "(it is the same membership matrix, and stays readable at any set count)"
        )
    geo = _TWO if len(sets) == 2 else _THREE
    show_pct = to_bool(params.get("show_percent", False))
    total = sum(int(v) for v in counts.values()) or 1

    data = []
    for i, name in enumerate(sets):
        cx, cy = geo["centers"][i]
        xs, ys = _circle(cx, cy)
        data.append({
            "type": "scatter", "x": xs, "y": ys, "name": str(name),
            "mode": "lines", "fill": "toself",
            "fillcolor": _FILLS[i % len(_FILLS)], "opacity": _OPACITY,
            "line": {"color": _FILLS[i % len(_FILLS)], "width": 1.5},
            "hoverinfo": "name", "showlegend": True,
        })

    # Region counts, one text trace so every label moves/restyles as a unit.
    lx, ly, ltext, lhover = [], [], [], []
    for key, (px, py) in geo["labels"].items():
        members = tuple(sets[int(i)] for i in key)
        n = int(counts.get(members, 0))
        lx.append(px)
        ly.append(py)
        ltext.append(f"{n}<br>{100.0 * n / total:.1f}%" if show_pct else str(n))
        lhover.append(" ∩ ".join(members) + f": {n}")
    data.append({
        "type": "scatter", "x": lx, "y": ly, "mode": "text", "text": ltext,
        "textfont": {"size": 15}, "hovertext": lhover, "hoverinfo": "text",
        "showlegend": False, "name": "counts",
    })

    # Set names, outside their circles (the legend repeats them, but a printed figure
    # is read without one).
    nx, ny = zip(*geo["names"][: len(sets)])
    data.append({
        "type": "scatter", "x": list(nx), "y": list(ny), "mode": "text",
        "text": [str(s) for s in sets], "textfont": {"size": 14},
        "hoverinfo": "skip", "showlegend": False, "name": "set labels",
    })

    axis = {"showgrid": False, "zeroline": False, "showticklabels": False,
            "ticks": "", "visible": False}
    spec = {
        "data": data,
        "layout": {
            "title": {"text": title},
            "xaxis": {**axis, "range": list(geo["xrange"])},
            # scaleanchor keeps the circles CIRCULAR at any container aspect ratio — without
            # it a wide editor pane draws ellipses and the overlap areas stop being honest.
            "yaxis": {**axis, "range": list(geo["yrange"]),
                      "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True,
            "plot_bgcolor": "white",
        },
    }
    spec["table"] = _region_table(counts, sets, total)
    return spec


def _region_table(counts: dict, sets: list, total: int) -> dict:
    """Region · sets · elements · % — the numbers behind the drawn circles.

    Rows are every region of the diagram (largest first), then each set's TOTAL, which is
    the number a reader actually quotes ("2 118 DE genes in contrast A") and which no
    single region carries.
    """
    rows = []
    # One pass accumulates the per-set totals while emitting the region rows — a set's total is
    # just the sum of every region it appears in, so it needs no second scan of `counts`.
    totals = dict.fromkeys(sets, 0)
    for members, n in sorted(counts.items(), key=lambda kv: (-int(kv[1]), kv[0])):
        rows.append([" ∩ ".join(members), len(members), int(n),
                     round(100.0 * int(n) / total, 2)])
        for s in members:
            totals[s] = totals.get(s, 0) + int(n)
    for s in sets:
        tot = totals.get(s, 0)
        rows.append([f"{s} (total)", "—", tot, round(100.0 * tot / total, 2)])
    return table(["region", "sets", "elements", "% of union"], rows,
                 f"Set overlap — {total} elements in the union")

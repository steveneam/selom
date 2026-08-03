"""Forest plot — effect size with a confidence interval, one row per feature.

The figure a DE table is already shaped for and that Selom could not draw: an effect
(log2 fold-change, a coefficient, a hazard/odds ratio) as a point, its confidence
interval as a horizontal bar, and a reference line at the null. It answers the question
a volcano deliberately does not — *how big, and how certain* — for a shortlist of
features rather than the whole transcriptome.

The interval is the entire point of the plot, so where it comes from is never guessed
silently: the real engine takes explicit CI bounds if the table has them, else derives
them from a standard error, else from the t-statistic (``se = effect / t``, exactly the
limma/edgeR relationship), and **records which of the three it used** in the Statistics
table title. A forest plot whose bars came from an unstated derivation is a chart, not
evidence.
"""

from skills._engine import use_real_engine
from skills._table import table

# Buckets: an interval clear of the null on either side, or crossing it.
_UP = "#b2432b"
_DOWN = "#2f6ea8"
_NULL = "#8a939d"

# 95% normal quantile — the default. Any other level needs the real engine (scipy).
_Z95 = 1.959963984540054


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.forest.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic six-feature effect shortlist, two of them crossing the null."""
    rows = [
        {"label": "TSTD1", "effect": 6.39, "lo": 5.61, "hi": 7.17, "p": 4.2e-9},
        {"label": "CFH", "effect": 3.11, "lo": 2.42, "hi": 3.80, "p": 1.1e-6},
        {"label": "RPE65", "effect": 1.86, "lo": 1.02, "hi": 2.70, "p": 3.4e-4},
        {"label": "MERTK", "effect": -2.44, "lo": -3.30, "hi": -1.58, "p": 8.7e-5},
        {"label": "BEST1", "effect": 0.42, "lo": -0.31, "hi": 1.15, "p": 0.26},
        {"label": "TYR", "effect": -0.28, "lo": -1.04, "hi": 0.48, "p": 0.47},
    ]
    return forest_spec(rows, params, "log2 fold-change", "Effect sizes (stub)",
                       ci_source="stub (fixed intervals)")


def forest_spec(rows: list, params: dict, x_label: str, title: str,
                ci_source: str = "") -> dict:
    """Editable forest spec — shared by the stub and the real engine.

    ``rows`` is an ordered list of ``{"label", "effect", "lo", "hi", "p"?}`` already
    sorted and truncated by the caller; row 0 is drawn at the TOP, which is how a forest
    plot is read.
    """
    ref = float(params.get("ref_line", 0.0))
    rows = list(rows)
    if not rows:
        raise ValueError("forest: no rows to plot after filtering")

    # Plotly lays a category axis out bottom-up, so the display order is reversed to put
    # row 0 at the top. categoryarray pins it — without an explicit order, a repeat run
    # with a different sort would silently redraw the rows in trace order.
    labels = [str(r["label"]) for r in rows]
    buckets = {
        "excludes null (higher)": ([], [], [], [], _UP),
        "excludes null (lower)": ([], [], [], [], _DOWN),
        "crosses null": ([], [], [], [], _NULL),
    }
    for r in rows:
        eff, lo, hi = float(r["effect"]), float(r["lo"]), float(r["hi"])
        key = ("excludes null (higher)" if lo > ref else
               "excludes null (lower)" if hi < ref else "crosses null")
        xs, ys, plus, minus, _ = buckets[key]
        xs.append(round(eff, 4))
        ys.append(str(r["label"]))
        plus.append(round(hi - eff, 4))
        minus.append(round(eff - lo, 4))

    data = []
    for name, (xs, ys, plus, minus, color) in buckets.items():
        if not xs:
            continue  # an absent bucket emits no trace — an empty legend entry is noise
        data.append({
            "type": "scatter", "mode": "markers", "name": name,
            "x": xs, "y": ys, "orientation": "h",
            "marker": {"color": color, "size": 9, "symbol": "square"},
            "error_x": {"type": "data", "array": plus, "arrayminus": minus,
                        "visible": True, "color": color, "thickness": 1.6, "width": 5},
            "hovertemplate": "%{y}: %{x} [%{customdata[0]}, %{customdata[1]}]<extra></extra>",
            "customdata": [[round(x - m, 4), round(x + p, 4)]
                           for x, p, m in zip(xs, plus, minus)],
        })

    spec = {
        "data": data,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": x_label}, "zeroline": False},
            # type:category is explicit, not incidental: feature labels are often
            # numeric-looking (probe ids, ENSEMBL-stripped numbers) and Plotly would infer a
            # LINEAR axis and lay them out at their numeric values (parity-audit D2).
            "yaxis": {"type": "category", "categoryorder": "array",
                      "categoryarray": list(reversed(labels)),
                      "automargin": True, "zeroline": False},
            "shapes": [{"type": "line", "x0": ref, "x1": ref, "yref": "paper",
                        "y0": 0, "y1": 1,
                        "line": {"color": _NULL, "width": 1, "dash": "dash"}}],
            "showlegend": True,
            "plot_bgcolor": "white",
        },
    }
    spec["table"] = _forest_table(rows, params, ref, ci_source)
    return spec


def _forest_table(rows: list, params: dict, ref: float, ci_source: str) -> dict:
    """feature · effect · CI · p · whether the interval clears the null."""
    level = float(params.get("conf_level", 0.95))
    show_p = any(r.get("p") is not None for r in rows)
    columns = ["feature", "effect", f"CI {level:.0%} low", f"CI {level:.0%} high"]
    if show_p:
        columns.append("p")
    columns.append("excludes null")

    out = []
    for r in rows:
        eff, lo, hi = float(r["effect"]), float(r["lo"]), float(r["hi"])
        row = [str(r["label"]), round(eff, 4), round(lo, 4), round(hi, 4)]
        if show_p:
            p = r.get("p")
            row.append(_p(p) if p is not None else "—")
        row.append("yes" if (lo > ref or hi < ref) else "no")
        out.append(row)
    title = f"Effect sizes ({level:.0%} CI"
    title += f", from {ci_source})" if ci_source else ")"
    return table(columns, out, title)


def _p(x) -> float:
    """A p-value at 3 significant figures, JSON-friendly."""
    try:
        return float(f"{float(x):.3g}")
    except (TypeError, ValueError, OverflowError):
        return x


def z_for(conf_level: float) -> float:
    """Two-sided normal quantile for ``conf_level``; 0.95 without needing scipy."""
    if abs(conf_level - 0.95) < 1e-9:
        return _Z95
    from scipy.stats import norm

    return float(norm.isf((1.0 - conf_level) / 2.0))

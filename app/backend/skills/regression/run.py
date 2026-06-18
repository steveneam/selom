"""Regression scatter — two continuous variables with an OLS fit.

A scatter of y against x with an ordinary-least-squares fit line and an R²/slope/p
annotation — the canonical "does A track B?" panel (e.g. a maturation / cell-identity
score against developmental age, Kim et al. 2023 Fig 4C). Real engine in ``run_real.py``
(scipy linregress over a CSV); the stub here is a deterministic positive trend of the
same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scipy", "pandas"):
        from skills.regression.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic positive trend: identity score rises with developmental age."""
    xs = [8, 11, 13, 17, 20, 23, 27, 31, 38, 44]
    ys = [0.22, 0.31, 0.30, 0.44, 0.52, 0.55, 0.63, 0.68, 0.79, 0.86]
    # OLS over the fixed points (kept inline so the stub stays dependency-free).
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy**2 / (sxx * syy)) if sxx and syy else 0.0
    return regression_spec(xs, ys, slope, intercept, r2, 1.3e-4, None, None,
                           "developmental age (weeks)", "identity score",
                           "Maturation vs developmental age (stub)")


def regression_spec(xs, ys, slope, intercept, r2, pval, groups, labels,
                    x_label, y_label, title) -> dict:
    """Editable scatter + fit-line spec (shared by stub + real engine).

    ``groups`` (optional) colors the points by category; ``labels`` (optional) annotates
    each point. The fit line + R²/slope/p annotation describe the OLS over all points."""
    xr = [round(float(x), 4) for x in xs]
    yr = [round(float(y), 4) for y in ys]
    point = {
        "type": "scatter", "mode": "markers" if not labels else "markers+text",
        "name": "samples", "x": xr, "y": yr,
        "marker": {"size": 9, "line": {"color": "#ffffff", "width": 1}},
    }
    if labels is not None:
        point["text"] = [str(t) for t in labels]
        point["textposition"] = "top center"
        point["textfont"] = {"size": 9}
    if groups is not None:
        point["transforms"] = [{"type": "groupby", "groups": [str(g) for g in groups]}]
        point["marker"]["color"] = "#3a6ea5"
    data = [point]

    lo, hi = min(xr), max(xr)
    data.append({
        "type": "scatter", "mode": "lines", "name": "OLS fit",
        "x": [lo, hi], "y": [round(slope * lo + intercept, 4), round(slope * hi + intercept, 4)],
        "line": {"color": "#b0413e", "width": 2, "dash": "solid"}, "hoverinfo": "skip",
    })
    annot = f"R² = {r2:.2f}   slope = {slope:.3g}   p = {_fmt_p(pval)}"
    return {
        "data": data,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": x_label}, "zeroline": False},
            "yaxis": {"title": {"text": y_label}, "zeroline": False},
            "showlegend": False,
            "plot_bgcolor": "white",
            "annotations": [{
                "xref": "paper", "yref": "paper", "x": 0.02, "y": 0.98,
                "xanchor": "left", "yanchor": "top", "showarrow": False,
                "text": annot, "font": {"size": 12},
                "bgcolor": "rgba(255,255,255,0.7)",
            }],
        },
    }


def _fmt_p(p):
    return "n/a" if p is None else f"{float(p):.3g}"

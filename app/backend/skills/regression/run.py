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
                    x_label, y_label, title, *, fit=True) -> dict:
    """Editable scatter (+ optional fit-line) spec, shared by stub + real engine.

    ``groups`` colors the points by category as ONE TRACE PER GROUP; ``labels`` annotates
    each point. With ``fit`` the OLS line and its R²/slope/p annotation are drawn — turn it
    off and this is a plain x/y/hue scatter, which is the generic shape the plot review
    listed as missing (source-review §3.2 row 5). It was not missing: everything except
    the flag was already here.

    ``groups`` used to emit ``transforms: [{type: groupby}]``, which is **dead**. Plotly
    removed transforms in plotly.js 3 / plotly.py 6, and this repo runs plotly.js 3.6.0 and
    plotly.py 6.8 — the latter REFUSES the key outright. Nothing validated the spec on the
    way out (the skill returns a raw dict), so the figure shipped with a key the renderer
    ignores and every point drawn in one flat colour: an advertised knob that silently did
    nothing. One trace per group is how every other skill does it, and it earns a real
    legend for free.
    """
    xr = [round(float(x), 4) for x in xs]
    yr = [round(float(y), 4) for y in ys]
    text = [str(t) for t in labels] if labels is not None else None

    def _points(name, px, py, ptext, showlegend):
        tr = {
            "type": "scatter", "mode": "markers" if not labels else "markers+text",
            "name": name, "x": px, "y": py,
            # No explicit colour: the trace picks up the style's colourway, so grouped
            # traces are themed centrally rather than by a hardcoded hex here.
            "marker": {"size": 9, "line": {"color": "#ffffff", "width": 1}},
        }
        if ptext is not None:
            tr["text"] = ptext
            tr["textposition"] = "top center"
            tr["textfont"] = {"size": 9}
        if showlegend:
            tr["showlegend"] = True
        return tr

    if groups is None:
        data = [_points("samples", xr, yr, text, False)]
    else:
        gs = [str(g) for g in groups]
        data = []
        for name in dict.fromkeys(gs):          # first-appearance order, stable
            idx = [j for j, g in enumerate(gs) if g == name]
            data.append(_points(name, [xr[j] for j in idx], [yr[j] for j in idx],
                                [text[j] for j in idx] if text else None, True))

    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": x_label}, "zeroline": False},
        "yaxis": {"title": {"text": y_label}, "zeroline": False},
        "showlegend": groups is not None,
        "plot_bgcolor": "white",
    }
    if fit:
        lo, hi = min(xr), max(xr)
        data.append({
            "type": "scatter", "mode": "lines", "name": "OLS fit",
            "x": [lo, hi],
            "y": [round(slope * lo + intercept, 4), round(slope * hi + intercept, 4)],
            "line": {"color": "#b0413e", "width": 2, "dash": "solid"}, "hoverinfo": "skip",
        })
        annot = f"R² = {r2:.2f}   slope = {slope:.3g}   p = {_fmt_p(pval)}"
        layout["annotations"] = [{
            "xref": "paper", "yref": "paper", "x": 0.02, "y": 0.98,
            "xanchor": "left", "yanchor": "top", "showarrow": False,
            "text": annot, "font": {"size": 12},
            "bgcolor": "rgba(255,255,255,0.7)",
        }]
    return {"data": data, "layout": layout}


def _fmt_p(p):
    return "n/a" if p is None else f"{float(p):.3g}"

"""Q-Q plot of p-values — is this test calibrated?

Under a true null, p-values are uniform, so ranking them and plotting observed against
expected ``-log10(p)`` should follow the diagonal. Systematic lift off the diagonal is
inflation (unmodelled structure, batch, pseudo-replication, a mis-specified test);
sagging below it is a conservative test. It is a diagnostic for analyses Selom already
runs, and it makes a failure mode visible that a volcano actively hides — a volcano of
an inflated test looks *better*, not worse.

The figure carries **λ**, the inflation factor: the median observed chi-square statistic
over its null expectation. λ ≈ 1 is calibrated, λ > 1 inflated, λ < 1 conservative. It is
reported for any p-value column, but the interpretation is only as good as the assumption
that most features are null — stated in the table title rather than left implied, because
for a DE table with a strong global effect a λ above 1 can be real biology rather than a
defect.

The 95% band is the pointwise Beta order-statistic interval: the i-th of n uniform draws
is Beta(i, n−i+1), so the band is exact for the null model rather than a normal
approximation to it.
"""

import math

from skills._engine import to_bool, use_real_engine
from skills._table import table

_POINT = "#2f4858"
_DIAG = "#b2432b"
_BAND = "rgba(140,150,160,0.22)"


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.qq.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic mildly-inflated ladder — the shape a real inflated test makes."""
    n = 40
    # Fixed, reproducible: expected quantiles pushed up by a constant factor so the
    # stub demonstrates the diagnostic rather than a perfect null nobody would plot.
    expected = [-math.log10((i - 0.5) / n) for i in range(1, n + 1)]
    observed = [round(e * 1.18 + (0.05 if i % 3 == 0 else 0.0), 4)
                for i, e in enumerate(expected, start=1)]
    labels = [f"F{i:03d}" for i in range(1, n + 1)]
    return qq_spec(observed, expected, labels, params, n_total=n, lam=1.18,
                   band=None, title="P-value Q-Q (stub)")


def qq_spec(observed, expected, labels, params: dict, n_total: int, lam: float,
            band=None, title: str = "P-value Q-Q") -> dict:
    """Editable Q-Q spec — shared by the stub and the real engine.

    ``observed``/``expected`` are ``-log10(p)``, most significant FIRST (both descending),
    aligned with ``labels``. ``band`` is an optional ``(lo, hi)`` pair of arrays on the
    same ``-log10`` scale, aligned to ``expected``.
    """
    observed, expected, labels = list(observed), list(expected), list(labels)
    if not observed:
        raise ValueError("qq: no finite p-values to plot")
    # The reference line spans the EXPECTED range — the x-extent of the data — not the observed
    # maximum. Using max(observed) is the obvious-looking choice and it is wrong: on an inflated
    # test the top observed value is far above any expected quantile (λ=2.1 real data: observed
    # 12.6 vs expected 4.5), so the line trails into an empty right-hand half and the x-axis
    # stretches to hold it. Caught by rendering it, not by any assertion on the spec.
    hi_end = max(expected)

    data = []
    # Band first so the points and the diagonal draw over it.
    if band is not None and to_bool(params.get("band", True)):
        lo, hi = band
        data.append({
            "type": "scatter", "x": list(expected) + list(reversed(expected)),
            "y": list(hi) + list(reversed(list(lo))),
            "fill": "toself", "fillcolor": _BAND, "line": {"width": 0},
            "mode": "lines", "name": "95% null band",
            "hoverinfo": "skip", "showlegend": True,
        })
    data.append({
        "type": "scatter", "mode": "lines", "x": [0.0, round(hi_end, 4)],
        "y": [0.0, round(hi_end, 4)], "name": "null (y = x)",
        "line": {"color": _DIAG, "width": 1.5, "dash": "dash"},
        "hoverinfo": "skip",
    })
    data.append({
        "type": "scattergl" if len(observed) > 3000 else "scatter",
        "mode": "markers", "x": expected, "y": observed, "name": "observed",
        "marker": {"color": _POINT, "size": 5, "opacity": 0.8},
        "customdata": labels,
        "hovertemplate": "%{customdata}<br>expected %{x:.2f} · observed %{y:.2f}"
                         "<extra></extra>",
    })

    spec = {
        "data": data,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "expected −log10(p)"}, "zeroline": False,
                      "rangemode": "tozero"},
            "yaxis": {"title": {"text": "observed −log10(p)"}, "zeroline": False,
                      "rangemode": "tozero"},
            "showlegend": True,
            "plot_bgcolor": "white",
            # Render-inert: λ is a computed property of the run, and the editor / methods
            # text should read it rather than parse it back out of a title string.
            "meta": {"lambda_gc": round(float(lam), 4), "n_tests": int(n_total)},
        },
    }
    spec["table"] = _qq_table(observed, expected, labels, params, n_total, lam)
    return spec


def _qq_table(observed, expected, labels, params: dict, n_total: int, lam: float) -> dict:
    """λ + the most extreme points — the tail is what a reader inspects after seeing lift."""
    top_n = max(1, int(params.get("top_n", 15)))
    rows = []
    for lab, obs, exp in list(zip(labels, observed, expected))[:top_n]:
        p = 10.0 ** (-float(obs))
        rows.append([str(lab), float(f"{p:.3g}"), round(float(exp), 4),
                     round(float(obs), 4), round(float(obs) - float(exp), 4)])
    verdict = ("calibrated" if 0.95 <= lam <= 1.05 else
               "inflated" if lam > 1.05 else "conservative")
    return table(
        ["feature", "p", "expected −log10(p)", "observed −log10(p)", "excess"],
        rows,
        f"λ = {lam:.3f} ({verdict}) over {n_total} tests — λ assumes most features are "
        f"null; top {len(rows)} shown",
    )

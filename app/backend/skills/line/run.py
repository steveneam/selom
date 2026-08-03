"""Line plot — one or more series over a continuous x, with spread.

The generic time-course / dose-response / any-x panel: mean per x with SEM (or SD,
CI95, min-max) drawn as a shaded band, error bars, the individual replicate curves, or
nothing. The plot review listed this as missing and noted "the ERG skills each hand-roll
one" — they do not. ``skills/_charts.line_figure`` has been the general engine all
along (its own docstring calls it "the line analogue of ``bar_figure``", and it is not
ERG-specific); what was missing was a **skill** in front of it that reads a CSV.

So this file is deliberately thin. It owns the input contract — long-form
``x`` / ``y`` / optional ``series`` — and nothing else: the spread vocabulary
(``central`` · ``spread`` · ``error`` · ``points``) is the SAME vocabulary the bar
chart and the ERG grid speak, because it is literally the same code. A user who learns
these knobs on an ERG intensity-response reads them unchanged here.
"""

from skills._charts import line_figure, spread_stats
from skills._engine import to_bool, use_real_engine
from skills._table import table


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.line.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic two-arm time course with replicate spread."""
    x = [0, 6, 12, 24, 48]
    series = {
        "Treated": [[0.9, 1.8, 3.4, 5.9, 7.1], [1.1, 2.1, 3.0, 6.4, 7.6],
                    [1.0, 1.6, 3.7, 5.5, 6.8]],
        "Control": [[1.0, 1.1, 1.3, 1.2, 1.4], [0.9, 1.3, 1.1, 1.4, 1.2],
                    [1.2, 1.0, 1.4, 1.1, 1.5]],
    }
    # {label: {x: [replicate values]}} — the shape the real engine also builds.
    grouped = {
        label: {xi: [rep[i] for rep in reps] for i, xi in enumerate(x)}
        for label, reps in series.items()
    }
    return line_spec(grouped, params, "time (h)", "fold change",
                     "Response over time (stub)")


def line_spec(grouped: dict, params: dict, x_title: str, y_title: str,
              title: str) -> dict:
    """Editable line spec — shared by the stub and the real engine.

    ``grouped`` = ``{series label: {x value: [y values at that x]}}``. Aggregation happens
    HERE rather than in the caller so the stub and the real engine cannot drift on what
    "mean ± SEM" means — they call one ``spread_stats``.
    """
    error = str(params.get("error", "sem")).strip().lower()
    if not grouped:
        raise ValueError("line: no series to plot")

    series = []
    for label, by_x in grouped.items():
        xs = sorted(by_x)
        mean, lower, upper, errs = [], [], [], []
        for xi in xs:
            st = spread_stats(by_x[xi], error)
            mean.append(st["mean"])
            lower.append(st["mean"] - st["lo"])
            upper.append(st["mean"] + st["hi"])
            errs.append(st["err"])
        series.append({"label": str(label), "x": xs, "mean": mean,
                       "lower": lower, "upper": upper, "errs": errs})

    spec, rows = line_figure(
        series,
        x_title=x_title, y_title=y_title, title=title,
        error=error,
        spread=str(params.get("spread", "band")).strip().lower(),
        central=str(params.get("central", "mean")).strip().lower(),
        markers=to_bool(params.get("markers", False)),
        points=to_bool(params.get("points", False)),
        log_x=to_bool(params.get("log_x", False)),
        legend=len(series) > 1,
    )
    err_label = {"sem": "SEM", "sd": "SD", "ci95": "95% CI",
                 "minmax": "min-max"}.get(error, "SEM")
    # n per point is the number a reader needs to judge the band and cannot read off it.
    n_by = {(s["label"], xi): spread_stats(grouped[s["label"]][xi], error)["n"]
            for s in series for xi in s["x"]}
    spec["table"] = table(
        ["series", "x", "mean", err_label, "n"],
        [[r[0], r[1], r[2], r[3], n_by.get((r[0], r[1]))] for r in rows],
        f"Values per point (mean ± {err_label})",
    )
    return spec

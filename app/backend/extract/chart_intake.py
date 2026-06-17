"""Chart-extractor intake (X4 wired into the ingest layer) — "drop a paper figure → editable data".

Turns a recovered chart series (``chart_to_data`` X4) into Selom's two editable artifacts: the
Statistics **table** (``{columns, rows, title}``, the S2.1 shape the FE already renders) and an
editable Plotly **figure** (``{data, layout}``, theme applied downstream). So a panel recovered from
a published raster lands in the editor exactly like a skill's output — the clean-room ClawBio
``data-extractor`` capability, end-to-end.

Honest ceiling carries through from ``chart_to_data``: recovery is **calibration-first** (the caller
supplies two reference points per axis) and **vision-grade** (``confidence 0.7``, ``source: extracted``,
subject to the human-confirm gate E4) — never text-layer-exact. The recovered table/figure surface
that confidence in their titles so the value is never mistaken for an exact reading.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .chart_to_data import (
    Axis,
    Calibration,
    RecoveredSeries,
    recover_bars,
    recover_line,
    recover_scatter,
)

FORMS = ("bar", "line", "scatter")


def _bar_labels(series: RecoveredSeries, labels: Sequence[str] | None) -> list[str]:
    if labels:
        return [labels[i] if i < len(labels) else f"Bar {i + 1}" for i in range(len(series.values))]
    return [f"Bar {i + 1}" for i in range(len(series.values))]


def recovered_to_table(
    series: RecoveredSeries,
    *,
    labels: Sequence[str] | None = None,
    series_name: str = "value",
    x_name: str = "x",
    y_name: str = "y",
) -> dict:
    """A RecoveredSeries → the editable Statistics table (S2.1)."""
    grade = f"vision-grade (confidence {series.confidence})"
    if series.form == "bar":
        cats = _bar_labels(series, labels)
        return {
            "columns": ["category", series_name],
            "rows": [[c, v] for c, v in zip(cats, series.values)],
            "title": f"Recovered bars ({len(series.values)}) — {grade}",
        }
    return {
        "columns": [x_name, y_name],
        "rows": [[x, y] for x, y in series.points],
        "title": f"Recovered {series.form} ({len(series.points)} points) — {grade}",
    }


def recovered_to_figure(
    series: RecoveredSeries,
    *,
    labels: Sequence[str] | None = None,
    series_name: str = "value",
    x_name: str = "x",
    y_name: str = "y",
) -> dict:
    """A RecoveredSeries → an editable Plotly ``{data, layout}`` (pure spec; theme applied later)."""
    grade = f"Recovered from figure — vision-grade (confidence {series.confidence})"
    if series.form == "bar":
        cats = _bar_labels(series, labels)
        data = [{"type": "bar", "x": cats, "y": list(series.values), "name": series_name}]
        layout = {"title": {"text": grade}, "yaxis": {"title": {"text": series_name}}}
    else:
        xs = [p[0] for p in series.points]
        ys = [p[1] for p in series.points]
        mode = "lines" if series.form == "line" else "markers"
        data = [{"type": "scatter", "mode": mode, "x": xs, "y": ys, "name": series_name}]
        layout = {
            "title": {"text": grade},
            "xaxis": {"title": {"text": x_name}},
            "yaxis": {"title": {"text": y_name}},
        }
    return {"data": data, "layout": layout}


def extract_chart(
    image,
    calib: Calibration,
    form: str,
    *,
    labels: Sequence[str] | None = None,
    color: tuple[int, int, int] | None = None,
    tol: int = 40,
    thresh: int = 200,
    step: int = 1,
    min_size: int = 3,
    series_name: str = "value",
    x_name: str = "x",
    y_name: str = "y",
) -> dict:
    """Recover a panel's series and emit ``{series, table, figure}`` — the editable bundle."""
    f = form.lower()
    if f == "bar":
        series = recover_bars(image, calib, color=color, tol=tol, thresh=thresh)
    elif f == "line":
        series = recover_line(image, calib, color=color, tol=tol, thresh=thresh, step=step)
    elif f == "scatter":
        series = recover_scatter(image, calib, color=color, tol=tol, thresh=thresh, min_size=min_size)
    else:
        raise ValueError(f"unsupported chart form '{form}' (expected one of {', '.join(FORMS)})")
    kw = {"labels": labels, "series_name": series_name, "x_name": x_name, "y_name": y_name}
    return {
        "series": series,
        "table": recovered_to_table(series, **kw),
        "figure": recovered_to_figure(series, **kw),
    }


# --- request-param parsing (kept here so main.py stays thin + this stays testable) -------------


def calibration_from_params(q: Mapping[str, str]) -> Calibration:
    """Build a Calibration from flat query params: ``{x,y}_{px0,val0,px1,val1}`` (+ ``{x,y}_log``).
    A missing reference raises ValueError (the endpoint maps it to a 400)."""

    def num(key: str) -> float:
        v = q.get(key)
        if v is None or v == "":
            raise ValueError(f"missing calibration param '{key}'")
        try:
            return float(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"calibration param '{key}' must be a number") from e

    def flag(key: str) -> bool:
        return str(q.get(key, "")).lower() in ("1", "true", "yes")

    return Calibration(
        x=Axis(px0=num("x_px0"), val0=num("x_val0"), px1=num("x_px1"), val1=num("x_val1"), log=flag("x_log")),
        y=Axis(px0=num("y_px0"), val0=num("y_val0"), px1=num("y_px1"), val1=num("y_val1"), log=flag("y_log")),
    )


def color_from_param(value: str | None) -> tuple[int, int, int] | None:
    """Parse a series color from ``#rrggbb`` or ``r,g,b``; None means mask by darkness."""
    if not value:
        return None
    v = value.strip()
    if v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    parts = [p for p in v.replace(" ", "").split(",") if p != ""]
    if len(parts) == 3:
        try:
            r, g, b = (int(p) for p in parts)
        except ValueError as e:
            raise ValueError(f"invalid color '{value}' (expected #rrggbb or r,g,b)") from e
        return (r, g, b)
    raise ValueError(f"invalid color '{value}' (expected #rrggbb or r,g,b)")

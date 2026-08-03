"""Real line engine — a long-form table to one line per series.

Reads ``x`` / ``y`` / optional ``series`` columns and collects every y value sharing a
(series, x) pair as the replicates at that point. That is what makes a plain long table
— the shape every instrument export and every tidy dataframe already has — work with no
reshaping: repeated rows ARE the replicates.

Column choice is explicit-param-first, then a conservative auto-detect: the first two
numeric columns for x/y, and NO automatic series column. Guessing a series column is the
one auto-detection that can silently change the figure's meaning — split a single curve
into twenty, or merge twenty into one — so it is opt-in.
"""

from skills._plotly import jsonable
from skills.line.run import line_spec


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")

    x_col, y_col = _xy(df, params, pd)
    series_col = _named(df, params.get("series"))

    cols = [x_col, y_col] + ([series_col] if series_col else [])
    sub = df[cols].copy()
    sub[x_col] = pd.to_numeric(sub[x_col], errors="coerce")
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")
    sub = sub.dropna(subset=[x_col, y_col])
    if sub.empty:
        raise ValueError(f"line: no rows with numeric {x_col!r} and {y_col!r}")

    grouped: dict = {}
    if series_col:
        labels = sub[series_col].astype(str)
        for label in dict.fromkeys(labels):      # first-appearance order, stable
            part = sub[labels == label]
            grouped[label] = _by_x(part, x_col, y_col)
    else:
        grouped[y_col] = _by_x(sub, x_col, y_col)

    title = f"{y_col} over {x_col}" + (f" by {series_col}" if series_col else "")
    return jsonable(line_spec(grouped, params, str(x_col), str(y_col), title))


def _by_x(frame, x_col, y_col) -> dict:
    """{x value: [every y observed at that x]} — repeated rows are the replicates."""
    out: dict = {}
    for xi, yi in zip(frame[x_col].tolist(), frame[y_col].tolist()):
        out.setdefault(float(xi), []).append(float(yi))
    return out


def _xy(df, params, pd):
    cols = {str(c).strip().lower(): c for c in df.columns}
    x = cols.get(str(params.get("x") or "").strip().lower())
    y = cols.get(str(params.get("y") or "").strip().lower())
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if x is None:
        x = numeric[0] if numeric else None
    if y is None:
        y = next((c for c in numeric if c != x), None)
    if x is None or y is None:
        raise ValueError("line needs two numeric columns (x and y)")
    return x, y


def _named(df, raw):
    name = str(raw or "").strip()
    if not name:
        return None
    cols = {str(c).strip().lower(): c for c in df.columns}
    col = cols.get(name.lower())
    if col is None:
        raise ValueError(
            f"line: no such series column {name!r} "
            f"(available: {', '.join(map(str, df.columns))})"
        )
    return col

"""Real regression engine — OLS over two numeric columns of a CSV.

Reads x / y numeric columns (named via the ``x`` / ``y`` params, else the first two
numeric columns), fits an ordinary-least-squares line with scipy.stats.linregress, and
draws the scatter + fit + R²/slope/p. Optional ``group`` colors points; optional
``label`` annotates them. pandas + scipy only.
"""

from skills._engine import to_bool
from skills.regression.run import regression_spec

_MAX_POINTS = 2000   # keep the editable spec light


def run(data_path: str, params: dict) -> dict:
    import pandas as pd
    from scipy import stats

    df = pd.read_csv(data_path)
    x_col, y_col = _xy(df, params)
    group_col = _named(df, params.get("group"))
    label_col = _named(df, params.get("label"))

    cols = [x_col, y_col] + [c for c in (group_col, label_col) if c]
    sub = df[cols].copy()
    sub[x_col] = pd.to_numeric(sub[x_col], errors="coerce")
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")
    sub = sub.dropna(subset=[x_col, y_col]).head(_MAX_POINTS)
    if len(sub) < 3:
        raise ValueError("regression needs at least 3 paired numeric points")

    xs = sub[x_col].tolist()
    ys = sub[y_col].tolist()
    groups = sub[group_col].astype(str).tolist() if group_col else None
    labels = sub[label_col].astype(str).tolist() if label_col else None

    # `fit` off = a plain x/y/hue scatter. The OLS is not computed at all in that case:
    # running a fit whose numbers are never shown would still put them in provenance and
    # in the L3-synthesized table, implying a model the figure does not claim.
    want_fit = to_bool(params.get("fit", True))
    slope = intercept = r2 = pval = None
    if want_fit:
        f = stats.linregress(xs, ys)
        slope, intercept, r2, pval = f.slope, f.intercept, f.rvalue**2, f.pvalue

    title = f"{y_col} vs {x_col}"
    return regression_spec(
        xs, ys, slope, intercept, r2, pval, groups, labels,
        x_col, y_col, title, fit=want_fit,
    )


def _xy(df, params):
    import pandas as pd

    cols = {c.lower(): c for c in df.columns}
    x = cols.get(str(params.get("x") or "").strip().lower())
    y = cols.get(str(params.get("y") or "").strip().lower())
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if x is None:
        x = numeric[0] if numeric else None
    if y is None:
        y = next((c for c in numeric if c != x), None)
    if x is None or y is None:
        raise ValueError("regression needs two numeric columns (x and y)")
    return x, y


def _named(df, raw):
    name = str(raw or "").strip()
    if not name:
        return None
    cols = {c.lower(): c for c in df.columns}
    return cols.get(name.lower())

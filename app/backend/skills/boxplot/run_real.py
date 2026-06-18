"""Real box-plot engine — a long-form CSV → one box per group.

Reads a table with a categorical group column and a numeric value column (named via
``group`` / ``value`` params, else auto-detected: first non-numeric column = group,
first numeric column = value) and renders grouped box-and-whisker distributions.
Groups are ordered by descending median so the most concordant / highest group leads —
matching the Kim et al. 2023 Fig 2C reading (Cepo first). pandas only.
"""

from skills.boxplot.run import boxplot_spec

_MAX_GROUPS = 40   # keep the editable spec light


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    group_col, value_col = _columns(df, params)

    vals = pd.to_numeric(df[value_col], errors="coerce")
    sub = pd.DataFrame({"g": df[group_col].astype(str), "v": vals}).dropna(subset=["v"])
    if sub.empty:
        raise ValueError("boxplot: no numeric values found to plot")

    # Order groups by descending median (highest-concordance group first).
    order = sub.groupby("g")["v"].median().sort_values(ascending=False).index[:_MAX_GROUPS]
    groups = {str(g): sub.loc[sub["g"] == g, "v"].tolist() for g in order}

    title = f"{value_col} by {group_col}"
    return boxplot_spec(groups, params, value_col, group_col, title)


def _columns(df, params: dict) -> tuple[str, str]:
    """Resolve (group, value) columns: explicit params win, else auto-detect."""
    import pandas as pd

    cols = {c.lower(): c for c in df.columns}
    group = str(params.get("group") or "").strip()
    value = str(params.get("value") or "").strip()
    group_col = cols.get(group.lower()) if group else None
    value_col = cols.get(value.lower()) if value else None

    if value_col is None:
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        value_col = numeric[0] if numeric else None
    if value_col is None:
        raise ValueError("boxplot needs a numeric value column")
    if group_col is None:
        cat = [c for c in df.columns if c != value_col and not pd.api.types.is_numeric_dtype(df[c])]
        group_col = cat[0] if cat else next(c for c in df.columns if c != value_col)
    return group_col, value_col

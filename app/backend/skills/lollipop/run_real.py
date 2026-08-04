"""Real lollipop engine — a table → one ranked stem-and-dot per category.

Takes the SAME long-form shape every other categorical skill here takes (a category column + a
numeric value column, repeated rows are replicates) and also the shape a ranked list actually
arrives in — ONE row per category, already aggregated. Both work with no reshaping, and the
difference is visible in the output rather than papered over: a pre-aggregated table has n=1
everywhere, so it gets no confidence interval and no significance brackets (see ``run._ci`` and
the ``pairs`` guard), instead of an interval computed from a single number.

Column choice is explicit-param-first, then the same conservative auto-detect ``boxplot`` uses:
first non-numeric column = category, first numeric column = value. pandas only.
"""

from skills.lollipop.run import lollipop_spec


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")

    group_col, value_col = _columns(df, params)
    vals = pd.to_numeric(df[value_col], errors="coerce")
    sub = pd.DataFrame({"g": df[group_col].astype(str), "v": vals}).dropna(subset=["v"])
    if sub.empty:
        raise ValueError(
            f"lollipop: no rows with a numeric {value_col!r} to rank"
        )

    # Keep first-appearance order here; `lollipop_spec` owns the ranking, so the sort lives in one
    # place and `sort=none` genuinely means "the order in the file".
    groups: dict = {}
    for key, value in zip(sub["g"].tolist(), sub["v"].tolist()):
        groups.setdefault(str(key), []).append(float(value))

    title = f"{value_col} by {group_col}"
    return lollipop_spec(groups, params, str(value_col), str(group_col), title)


def _columns(df, params: dict) -> tuple[str, str]:
    """Resolve (category, value) columns: explicit params win, else auto-detect."""
    import pandas as pd

    cols = {str(c).strip().lower(): c for c in df.columns}
    group = str(params.get("group") or "").strip()
    value = str(params.get("value") or "").strip()
    group_col = cols.get(group.lower()) if group else None
    value_col = cols.get(value.lower()) if value else None
    if group and group_col is None:
        raise ValueError(
            f"lollipop: no such category column {group!r} "
            f"(available: {', '.join(map(str, df.columns))})"
        )
    if value and value_col is None:
        raise ValueError(
            f"lollipop: no such value column {value!r} "
            f"(available: {', '.join(map(str, df.columns))})"
        )

    if value_col is None:
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        value_col = numeric[0] if numeric else None
    if value_col is None:
        raise ValueError("lollipop needs a numeric value column")
    if group_col is None:
        cat = [c for c in df.columns
               if c != value_col and not pd.api.types.is_numeric_dtype(df[c])]
        group_col = cat[0] if cat else next(c for c in df.columns if c != value_col)
    return group_col, value_col

"""Real ridge engine — a long-form table (or an h5ad's ``.obs``) → one density curve per group.

Same shape every categorical skill here takes: a group column + a numeric value column, repeated
rows are the observations. The h5ad path reads ``.obs`` only and opens the file ``backed="r"`` — a
per-cell QC metric or a stored score is an obs column, and none of the expression matrix is needed
to draw its distribution.

Group ordering is by descending median, matching ``boxplot``: the ridge with the highest values
leads, which is the reading order for a comparison. ``order`` overrides it.
"""

from skills.ridge.run import ridge_spec

_MAX_GROUPS = 25


def run(data_path: str, params: dict) -> dict:
    low = str(data_path).lower()
    if low.endswith((".h5ad", ".h5")):
        frame = _obs_frame(data_path)
    else:
        frame = _table_frame(data_path)
    return _ridge(frame, params)


def _obs_frame(data_path: str):
    import anndata as ad

    return ad.read_h5ad(data_path, backed="r").obs


def _table_frame(data_path: str):
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        return pd.read_excel(data_path)
    return pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")


def _ridge(frame, params: dict) -> dict:
    import pandas as pd

    group_col, value_col = _columns(frame, params)
    vals = pd.to_numeric(frame[value_col], errors="coerce")
    sub = pd.DataFrame({"g": frame[group_col].astype(str), "v": vals}).dropna(subset=["v"])
    if sub.empty:
        raise ValueError(f"ridge: no rows with a numeric {value_col!r}")

    ordered = sub.groupby("g")["v"].median().sort_values(ascending=False).index[:_MAX_GROUPS]
    groups = {str(g): sub.loc[sub["g"] == g, "v"].tolist() for g in ordered}

    title = f"{value_col} by {group_col}"
    return ridge_spec(groups, params, str(value_col), str(group_col), title)


def _columns(frame, params: dict) -> tuple:
    """Resolve (group, value): explicit params win, else the first non-numeric column = group and
    the first numeric column = value — the same auto-detect ``boxplot`` uses."""
    import pandas as pd

    cols = {str(c).strip().lower(): c for c in frame.columns}
    group = str(params.get("group") or "").strip()
    value = str(params.get("value") or "").strip()
    group_col = cols.get(group.lower()) if group else None
    value_col = cols.get(value.lower()) if value else None
    if group and group_col is None:
        raise ValueError(
            f"ridge: no such group column {group!r} "
            f"(available: {', '.join(map(str, frame.columns))})"
        )
    if value and value_col is None:
        raise ValueError(
            f"ridge: no such value column {value!r} "
            f"(available: {', '.join(map(str, frame.columns))})"
        )

    if value_col is None:
        numeric = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
        value_col = numeric[0] if numeric else None
    if value_col is None:
        raise ValueError("ridge needs a numeric value column")
    if group_col is None:
        cat = [c for c in frame.columns
               if c != value_col and not pd.api.types.is_numeric_dtype(frame[c])]
        group_col = cat[0] if cat else next(c for c in frame.columns if c != value_col)
    return group_col, value_col

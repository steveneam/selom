"""Real UpSet engine (pandas).

Reads a boolean membership matrix (CSV/TSV/XLSX, first column = element id, e.g. a
gene; remaining columns = sets), derives the set intersections, and feeds the shared
``upset_spec``. Values are coerced to membership flexibly: native booleans, numeric
columns (>0 = member), or text spellings (``TRUE``/``1``/``yes``). This is exactly the
shape of a "top markers per cell type" or "DE hits per contrast" table, so a published
membership table drops straight in.

``mode``:
  * ``distinct``  — each element counted once, in the intersection of *exactly* the
    sets it belongs to (standard UpSet semantics).
  * ``inclusive`` — each observed combination counts every element that belongs to
    *at least* those sets.
"""

from skills._plotly import jsonable
from skills.upset.run import upset_spec


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path, index_col=0)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",", index_col=0)

    if df.shape[1] < 2:
        raise ValueError("upset needs a membership matrix with at least two set columns")

    membership = pd.DataFrame({col: _as_member(df[col], pd) for col in df.columns})
    columns = list(membership.columns)

    # set sizes + display order (largest set on top of the matrix)
    set_total = {c: int(membership[c].sum()) for c in columns}
    sets_display = sorted(columns, key=lambda c: (-set_total[c], columns.index(c)))
    set_sizes = [set_total[c] for c in sets_display]

    mode = str(params.get("mode") or "distinct").strip().lower()
    counts = _intersection_counts(membership, columns, mode, pd)

    min_size = int(params.get("min_size", 1))
    intersections = [
        {"members": [c for c in sets_display if c in combo], "size": size}
        for combo, size in counts.items()
        if combo and size >= min_size
    ]

    sort_by = str(params.get("sort_by") or "size").strip().lower()
    if sort_by == "degree":
        intersections.sort(key=lambda it: (-len(it["members"]), -it["size"]))
    else:
        intersections.sort(key=lambda it: -it["size"])
    intersections = intersections[: int(params.get("max_intersections", 20))]

    title = "Set intersections" + ("" if intersections else " (none above min_size)")
    return jsonable(upset_spec(intersections, sets_display, set_sizes, title))


def _as_member(series, pd):
    """Coerce one column to a boolean membership mask, accepting bool / numeric / text."""
    if series.dtype == bool:
        return series
    num = pd.to_numeric(series, errors="coerce")
    if num.notna().any():
        return num.fillna(0) > 0
    text = series.astype(str).str.strip().str.lower()
    return text.isin(["true", "1", "yes", "on", "t", "y"])


def _intersection_counts(membership, columns, mode, pd):
    """Map each observed non-empty set-combination → element count, per ``mode``."""
    signatures = membership.apply(
        lambda row: frozenset(c for c in columns if row[c]), axis=1
    )
    distinct = signatures[signatures.map(len) > 0].value_counts()  # combo -> exact count
    if mode != "inclusive":
        return {combo: int(n) for combo, n in distinct.items()}

    # inclusive: every element whose membership is a superset of the combination
    out = {}
    for combo in distinct.index:
        cols = list(combo)
        out[combo] = int(membership[cols].all(axis=1).sum())
    return out

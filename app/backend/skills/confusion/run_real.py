"""Real confusion engine — two label columns → a cross-tabulation.

Reads an h5ad's ``.obs`` or a table, and needs NOTHING else: a contingency table is built from two
label columns, so the expression matrix is never touched. That is why the h5ad path opens the file
``backed="r"`` — an 83k-cell matrix costs nothing here because none of it is read.

Both label columns must describe the SAME rows. That is the one thing this skill cannot verify for
the user and the one thing that makes the output meaningless if it is false, so the columns come
from a single frame and are never joined across files.
"""

from skills.confusion.run import confusion_spec, resolve_labels


def run(data_path: str, params: dict) -> dict:
    low = str(data_path).lower()
    if low.endswith((".h5ad", ".h5")):
        frame, source = _obs_frame(data_path), "cells"
    else:
        frame, source = _table_frame(data_path), "rows"
    return _confusion(frame, params, source)


def _obs_frame(data_path: str):
    import anndata as ad

    adata = ad.read_h5ad(data_path, backed="r")
    return adata.obs


def _table_frame(data_path: str):
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        return pd.read_excel(data_path)
    return pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")


def _confusion(frame, params: dict, source: str) -> dict:
    import pandas as pd

    # `true`/`predicted` are the ONLY names for these two columns. An undeclared `y`/`x` alias sat
    # here until 2026-08-06 — no caller passed it, no control offered it and no paragraph described
    # it, but a value arriving under it would have chosen the axis columns and been written into the
    # reproducibility bundle as config no param_spec could interpret (test_skill_param_declaration_guard).
    true_col = _column(frame, params.get("true"), "true")
    pred_col = _column(frame, params.get("predicted"), "predicted", avoid=true_col)

    sub = pd.DataFrame({
        "t": frame[true_col].astype(str),
        "p": frame[pred_col].astype(str),
    }).dropna()
    if sub.empty:
        raise ValueError(f"confusion: no rows carrying both {true_col!r} and {pred_col!r}")

    row_labels = resolve_labels(pd.unique(sub["t"]), params.get("true_order"))
    col_labels = resolve_labels(pd.unique(sub["p"]), params.get("predicted_order"))
    index = {c: j for j, c in enumerate(col_labels)}
    counts = [[0.0] * len(col_labels) for _ in row_labels]
    row_index = {r: i for i, r in enumerate(row_labels)}
    counted = 0
    for t, p in zip(sub["t"].tolist(), sub["p"].tolist()):
        i, j = row_index.get(t), index.get(p)
        if i is None or j is None:      # only possible past the label cap
            continue
        counts[i][j] += 1.0
        counted += 1

    # cnsplots asserts this same identity, and it is worth keeping: a confusion matrix whose cells
    # do not sum to the input row count has dropped observations somewhere, and every downstream
    # number — the marginals, the agreement, kappa — is then computed on a silently smaller
    # dataset. The only legitimate shortfall is the label cap, so that is what the message says.
    if counted != len(sub):
        dropped = len(sub) - counted
        if len(row_labels) < sub["t"].nunique() or len(col_labels) < sub["p"].nunique():
            raise ValueError(
                f"confusion: {true_col!r} x {pred_col!r} has more than 60 distinct labels on an "
                f"axis, so {dropped} of {len(sub)} {source} fall outside the drawn matrix. "
                "Narrow the labels first — a matrix that large is unreadable in any case."
            )
        raise RuntimeError(
            f"confusion: counted {counted} {source} but the input had {len(sub)} — "
            "the matrix would under-report every marginal"
        )

    title = f"{pred_col} vs {true_col}"
    return confusion_spec(counts, row_labels, col_labels, params,
                          str(true_col), str(pred_col), title)


def _column(frame, requested, role: str, avoid=None):
    """Resolve one label column: an explicit param wins, else the first categorical column that is
    not already taken. Numeric columns are never auto-picked — a continuous measure cross-tabulated
    against anything produces one row per distinct value, which is not a confusion matrix."""
    columns = list(frame.columns)
    lookup = {str(c).strip().lower(): c for c in columns}
    name = str(requested or "").strip()
    if name:
        col = lookup.get(name.lower())
        if col is None:
            raise ValueError(
                f"confusion: no such {role} label column {name!r} "
                f"(available: {', '.join(map(str, columns))})"
            )
        return col

    import pandas as pd

    for col in columns:
        if col == avoid:
            continue
        series = frame[col]
        if pd.api.types.is_numeric_dtype(series) and not isinstance(
            series.dtype, pd.CategoricalDtype
        ):
            continue
        if series.astype(str).nunique() > 1:
            return col
    raise ValueError(
        f"confusion needs two categorical label columns; none found for the {role} axis "
        f"(available: {', '.join(map(str, columns))})"
    )

"""Real composition-bar engine (pandas).

Reads a CSV/TSV/XLSX whose first column is the category (e.g. cell type) and whose numeric
columns are the conditions/series (e.g. ``DR (%)``, ``PD (%)``). Builds grouped (default)
or stacked bars, optionally sorted by one of the value columns. Emits the shared
``_composition_spec`` wire shape.
"""


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    from skills._plotly import jsonable
    from skills.composition.run import _composition_spec

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path, index_col=0)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",", index_col=0)

    num = df.select_dtypes("number")
    if num.shape[1] < 1:
        raise ValueError("composition needs at least one numeric value column (a condition/series)")

    sort_by = str(params.get("sort_by") or "").strip()
    if sort_by and sort_by in num.columns:
        num = num.sort_values(sort_by)
    elif sort_by:
        raise ValueError(f"sort_by '{sort_by}' not among value columns {list(num.columns)}")

    categories = [str(c) for c in num.index]
    series = {str(col): num[col].tolist() for col in num.columns}
    spec = _composition_spec(
        categories, series, params.get("mode", "grouped"), params.get("orientation", "h"),
        "Composition",
    )
    return jsonable(spec)

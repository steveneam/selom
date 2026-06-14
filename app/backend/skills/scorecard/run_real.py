"""Real scorecard engine (pandas) — conditions × metrics radar.

Reads a CSV/TSV/XLSX whose first column is the condition/model name and whose numeric
columns are the metrics. With ``normalize`` (default), each metric column is min–max
scaled to [0, 1] so differently-scaled scores are comparable on one radius. Feeds the
shared ``scorecard_spec``.
"""

from skills._engine import to_bool
from skills._plotly import jsonable
from skills.scorecard.run import scorecard_spec


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path, index_col=0)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",", index_col=0)

    num = df.select_dtypes("number")
    if num.shape[1] < 3:
        raise ValueError("scorecard needs at least three numeric metric columns")

    max_rows = int(params.get("max_rows", 8))
    if num.shape[0] > max_rows:
        num = num.iloc[:max_rows]

    radial_range = None
    if to_bool(params.get("normalize", True)):
        lo, hi = num.min(), num.max()
        span = (hi - lo).replace(0, 1.0)  # constant metric -> avoid divide-by-zero
        num = (num - lo) / span
        radial_range = [0, 1]

    metrics = [str(c) for c in num.columns]
    series = {str(idx): num.loc[idx].tolist() for idx in num.index}
    fill = to_bool(params.get("fill", True))
    spec = scorecard_spec(metrics, series, fill, "Benchmark scorecard", radial_range)
    return jsonable(spec)

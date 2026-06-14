"""Real scorecard engine (pandas) — conditions × metrics radar.

Reads a CSV/TSV/XLSX whose first column is the condition/model name and whose numeric
columns are the metrics. With ``normalize`` (default), each metric column is min–max
scaled to [0, 1] so differently-scaled scores are comparable on one radius. Feeds the
shared ``scorecard_spec``.
"""

from skills._engine import to_bool
from skills._plotly import jsonable
from skills.scorecard.run import scorecard_heatmap_spec, scorecard_spec


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
        num = num.iloc[:max_rows].copy()

    # Metrics where *lower* is better (off-target, error rate, ...) are inverted so the
    # colour/radius reads consistently — higher always means "better" across the whole
    # scorecard. Without this a high off-target value would look as good as high accuracy,
    # which silently misleads the reader (a publish-confidence trap).
    invert = _invert_cols(params.get("invert_metrics"), num.columns)

    radial_range = None
    if to_bool(params.get("normalize", True)):
        lo, hi = num.min(), num.max()
        span = (hi - lo).replace(0, 1.0)  # constant metric -> avoid divide-by-zero
        num = (num - lo) / span
        for c in invert:
            num[c] = 1.0 - num[c]
        radial_range = [0, 1]
    else:
        for c in invert:  # flip around the column's own range so the scale is preserved
            num[c] = (num[c].min() + num[c].max()) - num[c]

    metrics = [str(c) for c in num.columns]
    series = {str(idx): num.loc[idx].tolist() for idx in num.index}
    if str(params.get("layout") or "radar").lower() == "heatmap":
        # radial_range doubles as the colour-scale range: [0,1] when normalized, else None
        spec = scorecard_heatmap_spec(metrics, series, "Benchmark scorecard", radial_range)
    else:
        fill = to_bool(params.get("fill", True))
        spec = scorecard_spec(metrics, series, fill, "Benchmark scorecard", radial_range)
    return jsonable(spec)


def _invert_cols(invert_param, columns) -> list:
    """Resolve ``invert_metrics`` (comma-separated metric names, case-insensitive) to the
    matching column labels — the lower-is-better metrics to flip so higher always reads
    as better. Unknown names are ignored."""
    if not invert_param:
        return []
    wanted = {s.strip().lower() for s in str(invert_param).split(",") if s.strip()}
    return [c for c in columns if str(c).lower() in wanted]

"""Real correlation-heatmap engine (pandas + scipy).

Reads a numeric feature × sample matrix (CSV/TSV/XLSX, first column = feature id),
computes the Pearson or Spearman correlation across the requested axis
(``samples`` → column×column, ``features`` → row×row), and reorders the symmetric
matrix by hierarchical clustering (1−r distance, average linkage) so correlated
items sit together. Feeds the shared ``corr_spec`` wire shape.
"""

from skills._engine import to_bool
from skills._plotly import jsonable
from skills.corr_heatmap.run import corr_spec


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path, index_col=0)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",", index_col=0)

    num = df.select_dtypes("number")
    if num.shape[1] < 2:
        raise ValueError("corr_heatmap needs a numeric matrix with at least two columns")

    axis = str(params.get("axis") or "samples").strip().lower()
    method = str(params.get("method") or "pearson").strip().lower()
    if method not in ("pearson", "spearman"):
        method = "pearson"

    # correlate samples (columns) by default, or features (rows) when asked
    mat = num if axis.startswith("sample") else num.T
    corr = mat.corr(method=method)  # n × n, symmetric, unit diagonal

    labels = [str(c) for c in corr.columns]
    z = corr.to_numpy(dtype=float)
    if to_bool(params.get("cluster", True)):
        z, labels = _cluster_order(z, labels, np)

    scope = "Sample" if axis.startswith("sample") else "Feature"
    title = f"{scope} correlation ({method.title()})"
    return jsonable(corr_spec(np.round(z, 4).tolist(), labels, title))


def _cluster_order(z, labels, np):
    """Symmetric leaf-order reordering by hierarchical clustering on 1−r distance."""
    if z.shape[0] < 3:
        return z, labels

    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform

    dist = 1.0 - z
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2.0  # enforce exact symmetry for squareform
    dist[dist < 0] = 0.0
    order = leaves_list(linkage(squareform(dist, checks=False), method="average"))
    return z[np.ix_(order, order)], [labels[i] for i in order]

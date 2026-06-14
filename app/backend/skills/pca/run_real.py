"""Real PCA engine (scikit-learn) for a feature × sample table.

Reads a CSV/TSV/XLSX with features in rows (first column = id) and samples in columns,
transposes to samples × features, drops non-finite / zero-variance features, optionally
standardizes, and computes the first two principal components. Points are coloured by
group inferred from the sample name (trailing replicate index stripped). Emits the shared
``_pca_spec`` wire shape.
"""

import re

DEFAULT_GROUP_REGEX = r"\d+$"  # DR1 -> DR, PD3 -> PD


def run(data_path: str, params: dict) -> dict:
    import pandas as pd
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    from skills._engine import to_bool
    from skills._plotly import jsonable
    from skills.pca.run import _pca_spec

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path, index_col=0)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",", index_col=0)

    # samples x features; keep only numeric, finite, non-constant features.
    X = df.select_dtypes("number").T
    X = X.loc[:, X.notna().all(axis=0)]
    X = X.loc[:, X.var(axis=0) > 0]
    if X.shape[0] < 3 or X.shape[1] < 2:
        raise ValueError(
            f"PCA needs >=3 samples and >=2 informative features (got {X.shape[0]} samples, "
            f"{X.shape[1]} features after filtering)"
        )

    values = X.to_numpy(dtype=float)
    if to_bool(params.get("scale", True)):
        values = StandardScaler().fit_transform(values)

    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(values)
    var = pca.explained_variance_ratio_ * 100.0

    samples = [str(s) for s in X.index]
    regex = params.get("group_regex") or DEFAULT_GROUP_REGEX
    groups = [re.sub(regex, "", s) or s for s in samples]
    label = to_bool(params.get("label_points", True))

    traces = []
    for g in sorted(dict.fromkeys(groups)):  # stable, de-duplicated group order
        idx = [i for i, gg in enumerate(groups) if gg == g]
        traces.append(
            {
                "type": "scatter",
                "mode": "markers+text" if label else "markers",
                "name": g,
                "x": [round(float(coords[i, 0]), 4) for i in idx],
                "y": [round(float(coords[i, 1]), 4) for i in idx],
                "text": [samples[i] for i in idx],
                "textposition": "top center",
                "marker": {"size": 11},
            }
        )

    spec = _pca_spec(traces, float(var[0]), float(var[1]), f"PCA — {X.shape[0]} samples, {X.shape[1]} features")
    return jsonable(spec)

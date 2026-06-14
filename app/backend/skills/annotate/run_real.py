"""Real cell-type annotation engine (scanpy, Mode A — marker-set scoring).

For each cell type in the chosen panel: score its marker genes per cell
(``sc.tl.score_genes``), average the scores per cluster, and assign every cluster the
top-scoring type. The figure recolours the (stored or computed) embedding by the assigned
type, one trace per type. Emits the shared ``_umap_by_type_spec`` wire shape.
"""

import json
import pathlib

_PANELS = pathlib.Path(__file__).parent / "panels.json"


def _load_panel(marker_set: str) -> dict:
    panels = json.loads(_PANELS.read_text(encoding="utf-8"))
    if marker_set not in panels:
        raise ValueError(f"unknown marker_set '{marker_set}'; available: {sorted(panels)}")
    return panels[marker_set]


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd
    import scanpy as sc

    from skills._engine import to_bool
    from skills._plotly import jsonable
    from skills.annotate.run import _umap_by_type_spec

    panel = _load_panel(params.get("marker_set") or "retinal")
    markers = panel["markers"]

    from skills._genes import read_anndata

    adata = read_anndata(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    groupby = params.get("groupby") or "leiden"
    need_graph = groupby not in adata.obs.columns
    emb_key = params.get("embedding") or "X_umap"
    need_emb = emb_key not in adata.obsm

    if need_graph or need_emb:
        n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
        sc.pp.pca(adata, n_comps=n_pcs)
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
    if need_graph:
        sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
        groupby = "leiden"
    if need_emb:
        sc.tl.umap(adata)
        emb_key = "X_umap"

    # Score each cell type's markers per cell (only genes present in the data).
    scored: list[str] = []
    for cell_type, genes in markers.items():
        present = [g for g in genes if g in adata.var_names]
        if len(present) < 2:
            continue  # too few markers in this dataset to score the type reliably
        sc.tl.score_genes(adata, present, score_name=f"__score::{cell_type}", random_state=0)
        scored.append(cell_type)
    if not scored:
        raise ValueError(
            f"none of the '{params.get('marker_set')}' panel markers were found in the data "
            "(check the organism / gene symbols)"
        )

    # Per-cluster mean score -> argmax type -> per-cell label.
    scores = pd.DataFrame(
        {ct: adata.obs[f"__score::{ct}"].to_numpy() for ct in scored},
        index=adata.obs_names,
    )
    scores["__g"] = adata.obs[groupby].astype(str).to_numpy()
    per_cluster = scores.groupby("__g")[scored].mean()
    cluster_label = per_cluster.idxmax(axis=1).to_dict()
    cell_type = adata.obs[groupby].astype(str).map(cluster_label)

    coords = np.asarray(adata.obsm[emb_key])[:, :2]
    traces = []
    for ct in scored:  # stable order = panel order; skip types no cluster won
        mask = (cell_type == ct).to_numpy()
        if not mask.any():
            continue
        traces.append(
            {
                "type": "scattergl",
                "mode": "markers",
                "name": ct,
                "x": [round(float(v), 4) for v in coords[mask, 0]],
                "y": [round(float(v), 4) for v in coords[mask, 1]],
                "marker": {"size": 4},
            }
        )

    n_types = len({v for v in cluster_label.values()})
    n_clusters = per_cluster.shape[0]
    emb_name = emb_key.replace("X_", "").upper()
    spec = _umap_by_type_spec(
        traces,
        f"Cell-type annotation — {panel.get('name', params.get('marker_set'))}",
        f"{n_types} types assigned across {n_clusters} clusters · scored {len(scored)} marker sets",
    )
    spec["layout"]["xaxis"]["title"]["text"] = f"{emb_name} 1"
    spec["layout"]["yaxis"]["title"]["text"] = f"{emb_name} 2"
    return jsonable(spec)

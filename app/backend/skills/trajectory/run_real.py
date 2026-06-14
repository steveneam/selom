"""Real trajectory engine (scanpy: diffusion map -> PAGA -> diffusion pseudotime).

Computes a neighbour graph + diffusion map, abstracts the cluster graph with PAGA, picks a
root (a chosen cluster, else the diffusion-component extreme), and assigns diffusion
pseudotime. Draws the embedding coloured by pseudotime with the PAGA graph overlaid
(node = cluster centroid, size = cell count; edge width = connectivity, pruned at
``threshold``). Emits the shared ``_trajectory_spec`` wire shape.
"""


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import scanpy as sc

    from skills._engine import to_bool
    from skills._plotly import jsonable
    from skills.trajectory.run import _trajectory_spec

    adata = sc.read_h5ad(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    groupby = params.get("groupby") or "leiden"
    emb_key = params.get("embedding") or "X_umap"
    need_graph = groupby not in adata.obs.columns
    need_emb = emb_key not in adata.obsm
    have_neighbors = "neighbors" in adata.uns

    if need_graph or need_emb or not have_neighbors:
        n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
        sc.pp.pca(adata, n_comps=n_pcs)
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
    if need_graph:
        sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
        groupby = "leiden"
    if need_emb:
        sc.tl.umap(adata)
        emb_key = "X_umap"
    # PAGA needs a categorical grouping (a user-supplied label column may be object).
    adata.obs[groupby] = adata.obs[groupby].astype("category")

    # Diffusion map -> PAGA (cluster connectivity) -> diffusion pseudotime from a root.
    sc.tl.diffmap(adata)
    sc.tl.paga(adata, groups=groupby)

    groups = list(adata.obs[groupby].cat.categories) if hasattr(adata.obs[groupby], "cat") \
        else sorted(adata.obs[groupby].astype(str).unique())
    groups = [str(g) for g in groups]

    root = str(params.get("root") or "").strip()
    obs_groups = adata.obs[groupby].astype(str).to_numpy()
    if root and root in groups:
        # Root the trajectory at the cluster's cell most extreme along DC1.
        idx = np.where(obs_groups == root)[0]
        dc1 = np.asarray(adata.obsm["X_diffmap"])[idx, 1]
        adata.uns["iroot"] = int(idx[int(np.argmin(dc1))])
        root_note = f"root cluster {root}"
    else:
        adata.uns["iroot"] = int(np.argmin(np.asarray(adata.obsm["X_diffmap"])[:, 1]))
        root_note = f"auto root (cluster {obs_groups[adata.uns['iroot']]})"

    sc.tl.dpt(adata)
    pseudotime = np.asarray(adata.obs["dpt_pseudotime"], dtype=float)
    finite = pseudotime[np.isfinite(pseudotime)]
    if finite.size:  # DPT can emit inf for cells unreachable from the root
        pseudotime = np.where(np.isfinite(pseudotime), pseudotime, float(finite.max()))
    coords = np.asarray(adata.obsm[emb_key])[:, :2]

    # Cluster centroids in the embedding + cell counts (node size).
    centroids, counts = {}, {}
    for g in groups:
        mask = obs_groups == g
        counts[g] = int(mask.sum())
        centroids[g] = (float(coords[mask, 0].mean()), float(coords[mask, 1].mean()))
    max_count = max(counts.values()) or 1

    # PAGA edges: upper triangle of the connectivity matrix, pruned at `threshold`.
    conn = adata.uns["paga"]["connectivities"]
    dense = conn.toarray() if hasattr(conn, "toarray") else np.asarray(conn)
    threshold = float(params.get("threshold", 0.05))
    edges = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            w = float(dense[i, j])
            if w >= threshold:
                x0, y0 = centroids[groups[i]]
                x1, y1 = centroids[groups[j]]
                edges.append((round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4), round(1.0 + 7.0 * w, 3)))

    nodes = [
        (round(centroids[g][0], 4), round(centroids[g][1], 4), str(g), round(8.0 + 30.0 * counts[g] / max_count, 2))
        for g in groups
    ]

    # Smooth principal-curve lineages (the "flowy" Slingshot-style backbone) over the
    # embedding — optional, degrades to PAGA-only if simpleppt is unavailable.
    lineages = _lineage_curves(coords, pseudotime, np)

    emb_name = emb_key.replace("X_", "").upper()
    lin_note = f" · {len(lineages)} lineage{'s' if len(lineages) != 1 else ''}" if lineages else ""
    spec = _trajectory_spec(
        [round(float(v), 4) for v in coords[:, 0]],
        [round(float(v), 4) for v in coords[:, 1]],
        [round(float(v), 4) for v in pseudotime],
        edges,
        nodes,
        "Trajectory & pseudotime (PAGA + DPT)",
        f"{root_note} · {len(groups)} clusters · {len(edges)} edges (≥{threshold}){lin_note}",
        lineages,
    )
    spec["layout"]["xaxis"]["title"]["text"] = f"{emb_name} 1"
    spec["layout"]["yaxis"]["title"]["text"] = f"{emb_name} 2"
    return jsonable(spec)


def _lineage_curves(coords, pseudotime, np, n_nodes=50):
    """Smooth principal-curve lineages: a simpleppt principal tree over the embedding,
    one scipy spline per root->tip path. Root = tree node nearest the lowest-pseudotime
    cell. Returns ``[(xs, ys, name)]``; empty (PAGA-only) if simpleppt is missing or the
    fit fails, so the figure always renders."""
    import contextlib
    import io

    try:
        import networkx as nx
        import simpleppt
        from scipy.interpolate import splev, splprep
    except Exception:
        return []

    X = np.asarray(coords, dtype=float)[:, :2]
    n = X.shape[0]
    if n < 30:
        return []
    nodes = int(min(n_nodes, max(10, n // 30)))
    try:
        with contextlib.redirect_stderr(io.StringIO()):  # mute simpleppt's tqdm
            ppt = simpleppt.ppt(X, Nodes=nodes, seed=0)
    except Exception:
        return []

    F = np.asarray(ppt.F).T                       # (Nodes, 2) principal-tree node coords
    graph = nx.from_numpy_array(np.asarray(ppt.B))
    root_cell = int(np.argmin(pseudotime))
    root = int(np.argmin(((F - X[root_cell]) ** 2).sum(axis=1)))
    tips = [v for v in graph.nodes if graph.degree(v) == 1 and v != root]

    curves = []
    for i, tip in enumerate(tips[:5]):
        try:
            path = nx.shortest_path(graph, root, tip)
        except Exception:
            continue
        pts = F[path]
        if len(pts) < 3:
            continue
        try:
            tck, _ = splprep([pts[:, 0], pts[:, 1]], s=len(pts) * 0.5, k=min(3, len(pts) - 1))
            u = np.linspace(0.0, 1.0, 200)
            cx, cy = splev(u, tck)
        except Exception:
            cx, cy = pts[:, 0], pts[:, 1]
        curves.append(([round(float(v), 4) for v in cx],
                       [round(float(v), 4) for v in cy], f"Lineage {i + 1}"))
    return curves

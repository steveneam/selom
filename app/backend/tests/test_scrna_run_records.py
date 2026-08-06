"""What the `trajectory` and `annotate` FIGURES record about themselves — and that it reaches the
prose.

The 2026-08-06 ``PROSE_SILENT`` triage found both runners resolving the things the figure MEANS and
telling nobody (NEXT#10(c)). The consuming half is pinned in ``test_methods.py`` against synthetic
``layout.meta`` records; this is the producing half, through the real runners on a tiny matrix, so
a runner that stops writing the record cannot leave those pins green:

* a ``groupby`` column that is absent makes both runners cluster the cells THEMSELVES — the PAGA
  nodes and the assigned cell-type labels are then Leiden clusters, not the user's column;
* an ``embedding`` key that is not stored is silently replaced by a UMAP computed on the spot, and
  ``trajectory``'s caption called the result "the diffusion-map embedding" either way;
* a ``root`` naming a cluster that is not in the grouping falls through to the automatic root, while
  the paragraph printed the requested one — and pseudotime is measured FROM the root.
"""

import numpy as np
import pytest

from companions import legends, methods
from skills.contract import load_skill

sc = pytest.importorskip("scanpy")
ad = pytest.importorskip("anndata")

# The heavy lane by the marker's own definition ("real-engine validations"): each case drives
# scanpy's PCA/neighbours/Leiden/diffmap/PAGA/DPT or score_genes end to end (~40 s for the file).
# It needs no corpus, so `be-slow` — which runs with SELOM_DATASETS_DIR unset — covers it, and
# `be-slow` is gated in both `verify.sh` and CI.
pytestmark = pytest.mark.slow

# Two retinal types with enough panel markers to be scorable (>= 2 present); every other type in
# the panel has none, which is the case the old "for each cell type in the panel" claim ignored.
RODS = ["RHO", "NRL", "NR2E3", "GNAT1"]
MULLER = ["RLBP1", "RGR", "GLUL", "SLC1A3"]


def _h5ad(path, *, with_group: bool, with_emb: bool, n: int = 180, n_bg: int = 200):
    """Three populations, each lifting its own four-gene block, optionally carrying the
    ``cell_type`` column and the ``X_umap`` embedding the runs ask for — without them the runner
    must make its own, which is the whole point.

    Sized by what the real engines need, not by what reads small: ``score_genes`` draws its control
    set from expression-matched bins and raises on a thin gene pool, and PAGA needs a connected
    enough kNN graph to abstract at all (two perfectly separated groups yield zero edges and
    scanpy's igraph adjacency then raises)."""
    rng = np.random.default_rng(0)
    genes = RODS + MULLER + [f"G{i}" for i in range(n_bg)]
    per = n // 3
    X = rng.gamma(2.0, 1.5, (n, len(genes))).astype("float32")
    labels: list[str] = []
    for k in range(3):
        X[k * per:(k + 1) * per, k * 4:(k + 1) * 4] += 2.5
        labels += [chr(65 + k)] * per
    X = np.clip(X, 0.0, None)
    a = ad.AnnData(X=X, obs={"cell_type": labels} if with_group else {})
    a.var_names = genes
    if with_emb:  # a stored embedding the runner must USE rather than recompute
        a.obsm["X_umap"] = np.column_stack([X[:, 0], X[:, len(RODS)]]).astype("float32")
    a.write_h5ad(path)
    return path


def _meta(spec):
    return (spec.get("layout") or {}).get("meta") or {}


def _run(skill_id, path, params):
    if skill_id == "trajectory":
        from skills.trajectory.run_real import run
    else:
        from skills.annotate.run_real import run
    return run(str(path), params)


# ── annotate ───────────────────────────────────────────────────────────────────────────────────

def test_annotate_records_the_panel_it_used_and_the_types_it_could_not_score(tmp_path):
    """The panel IS the content of this figure: its literature source was cited nowhere, and "for
    each cell type in the panel" was false for every type whose markers this dataset lacks."""
    p = _h5ad(tmp_path / "a.h5ad", with_group=True, with_emb=True)
    spec = _run("annotate", p, {"groupby": "cell_type", "embedding": "X_umap"})

    rec = _meta(spec)["annotate"]
    assert rec["panel"] == "retinal" and rec["panel_name"] == "Retinal cell types"
    assert "699906" in rec["citation"]                      # Lu 2021 — the markers' own source
    assert set(rec["scored"]) == {"Rod photoreceptors", "Müller glia"}
    assert "RPE" in rec["skipped"] and rec["n_panel_types"] == 10
    assert rec["embedding"] == "X_umap" and rec["embedding_computed"] is False
    assert "clustered" not in _meta(spec)                   # the requested column was there

    out = methods.build(load_skill("annotate"), {"groupby": "cell_type"}, figure=spec)
    assert any("699906" in c for c in out["citations"])
    assert "had fewer than two of their marker genes present in this dataset" in out["text"]
    assert "grouped by cell_type" in out["text"]
    assert "on the stored UMAP embedding" in out["text"]


def test_annotate_records_a_substituted_grouping_and_a_computed_embedding(tmp_path):
    """Neither substitution was disclosed anywhere: the labels are assigned to clusters the runner
    invented, drawn in a space it invented, and the prose named the user's column and "the
    embedding"."""
    p = _h5ad(tmp_path / "b.h5ad", with_group=False, with_emb=False)
    spec = _run("annotate", p, {"groupby": "cell_type", "embedding": "X_umap"})

    assert _meta(spec)["clustered"] == {"requested": "cell_type", "groupby": "leiden"}
    assert _meta(spec)["annotate"]["embedding_computed"] is True

    text = methods.build(load_skill("annotate"), {"groupby": "cell_type"}, figure=spec)["text"]
    assert "grouped by Leiden clusters computed on the data" in text
    assert "grouped by cell_type" not in text
    assert "a UMAP embedding computed for this figure" in text

    caption = legends.build_caption(load_skill("annotate"), {"groupby": "cell_type"}, figure=spec)
    assert "to their Leiden cluster computed by Selom" in caption


# ── trajectory ─────────────────────────────────────────────────────────────────────────────────

def test_trajectory_records_the_embedding_it_drew_not_the_one_it_ordered_in(tmp_path):
    """The diffusion map orders the cells; the stored embedding places them. The caption called the
    result "Diffusion-map embedding" while the figure's own axes said UMAP."""
    p = _h5ad(tmp_path / "c.h5ad", with_group=True, with_emb=True)
    spec = _run("trajectory", p, {"groupby": "cell_type", "embedding": "X_umap"})

    rec = _meta(spec)["trajectory"]
    assert rec["embedding"] == "X_umap" and rec["embedding_computed"] is False
    assert spec["layout"]["xaxis"]["title"]["text"] == "UMAP 1"
    assert isinstance(rec["lineages"], int)
    assert "clustered" not in _meta(spec)

    caption = legends.build_caption(load_skill("trajectory"), {"groupby": "cell_type"}, figure=spec)
    assert caption.startswith("The UMAP embedding coloured by diffusion pseudotime")
    assert "Diffusion-map embedding" not in caption


def test_trajectory_records_whether_the_requested_root_was_honoured(tmp_path):
    """A root that is not one of the groups falls through to the automatic root without a word."""
    p = _h5ad(tmp_path / "d.h5ad", with_group=True, with_emb=True)

    honoured = _run("trajectory", p, {"groupby": "cell_type", "root": "B"})
    assert _meta(honoured)["trajectory"]["root"] == {
        "mode": "requested", "cluster": "B", "requested": "B"}
    assert "from a root at cluster B" in methods.build(
        load_skill("trajectory"), {"groupby": "cell_type", "root": "B"}, figure=honoured)["text"]

    absent = _run("trajectory", p, {"groupby": "cell_type", "root": "ZZZ"})
    root = _meta(absent)["trajectory"]["root"]
    assert root["mode"] == "auto" and root["requested"] == "ZZZ"
    assert root["cluster"] in {"A", "B", "C"}
    text = methods.build(load_skill("trajectory"),
                         {"groupby": "cell_type", "root": "ZZZ"}, figure=absent)["text"]
    assert "the requested cluster 'ZZZ' was not among the groups" in text
    assert "a root at cluster ZZZ" not in text


def test_trajectory_records_a_substituted_grouping(tmp_path):
    """The PAGA nodes the paragraph describes as clusters are the runner's own Leiden clusters."""
    p = _h5ad(tmp_path / "e.h5ad", with_group=False, with_emb=True)
    spec = _run("trajectory", p, {"groupby": "cell_type", "embedding": "X_umap"})

    assert _meta(spec)["clustered"] == {"requested": "cell_type", "groupby": "leiden"}
    text = methods.build(load_skill("trajectory"), {"groupby": "cell_type"}, figure=spec)["text"]
    assert "grouped by Leiden clusters computed on the data" in text
    assert "grouped by cell_type" not in text

"""What the violin FIGURE says about itself — the two claims its own knobs could falsify.

Both were found by the 2026-08-05 ``PROSE_SILENT`` triage, and both were baked into the figure, not
only the prose:

* the value axis was hard-coded ``"expression (log1p)"``, while ``normalize=False`` skips both
  ``normalize_total`` and ``log1p`` and plots the supplied values;
* when the requested ``groupby`` column is absent the runner CLUSTERS the cells itself and groups by
  Leiden. The title and axis disclose the substitution, but nothing recorded that it happened — so
  the methods paragraph and the caption both went on naming the column the user asked for, and the
  ``resolution`` that produced those clusters appeared nowhere at all.
"""

import numpy as np
import pytest

from companions import legends, methods
from skills.contract import load_skill

sc = pytest.importorskip("scanpy")
ad = pytest.importorskip("anndata")


def _h5ad(path, *, with_group: bool):
    """A tiny two-population matrix, optionally carrying the ``cell_type`` column the run asks for.
    Without it the runner must cluster the cells itself."""
    rng = np.random.default_rng(0)
    n, g = 40, 12
    X = np.vstack([rng.normal(6.0, 0.4, (n // 2, g)), rng.normal(1.0, 0.4, (n // 2, g))])
    X = np.clip(X, 0.0, None).astype("float32")
    obs = {"cell_type": ["A"] * (n // 2) + ["B"] * (n // 2)} if with_group else {}
    a = ad.AnnData(X=X, obs=obs)
    a.var_names = [f"G{i}" for i in range(g)]
    a.write_h5ad(path)
    return path


def _run(path, params):
    from skills.violin.run_real import run

    return run(str(path), params)


def _meta(spec):
    return (spec.get("layout") or {}).get("meta") or {}


def test_value_axis_names_the_scale_actually_plotted(tmp_path):
    p = _h5ad(tmp_path / "with.h5ad", with_group=True)

    assert _run(p, {"groupby": "cell_type"})["layout"]["yaxis"]["title"]["text"] == \
        "expression (log1p)"
    # `normalize=False` skips normalize_total AND log1p — the axis claimed the transform anyway.
    assert _run(p, {"groupby": "cell_type", "normalize": False})["layout"]["yaxis"]["title"]["text"] \
        == "expression (as supplied)"


def test_a_substituted_grouping_is_recorded_and_reaches_the_prose(tmp_path):
    """The whole point: the figure already said "leiden" while the paragraph said "cell_type"."""
    missing = _h5ad(tmp_path / "nogroup.h5ad", with_group=False)
    spec = _run(missing, {"groupby": "cell_type", "resolution": 0.8})

    rec = _meta(spec).get("clustered")
    assert rec == {"requested": "cell_type", "groupby": "leiden", "resolution": 0.8}
    assert "leiden" in spec["layout"]["xaxis"]["title"]["text"]

    text = methods.build(load_skill("violin"), {"groupby": "cell_type"}, figure=spec)["text"]
    assert "Leiden clusters computed on the data at resolution 0.8" in text
    assert "the requested 'cell_type' was not present in the data" in text
    assert "grouped by cell_type" not in text

    caption = legends.build_caption(load_skill("violin"), {"groupby": "cell_type"}, figure=spec)
    assert "Leiden cluster (resolution 0.8)" in caption
    assert "cell_type groups" not in caption


def test_nothing_is_recorded_when_the_requested_grouping_was_there(tmp_path):
    """No substitution, no record — the default run is byte-identical to before, and the prose
    falls back to naming the requested column."""
    present = _h5ad(tmp_path / "with.h5ad", with_group=True)
    spec = _run(present, {"groupby": "cell_type"})

    assert "clustered" not in _meta(spec)
    assert "grouped by cell_type" in \
        methods.build(load_skill("violin"), {"groupby": "cell_type"}, figure=spec)["text"]

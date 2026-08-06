"""What the `normalization_qc` companion may and may not CLAIM.

The peer of `test_deg_prose_honesty.py` / `test_violin_grouping.py`: one file per
printed-vs-computed family, pinning the claim rather than the wording. Two claims were false from
the params alone, and neither could be fixed by quoting a param harder:

* **the grouping** — a requested `groupby` column that is absent falls back through
  `_GROUP_FALLBACKS` (`sample`/`batch`/`orig.ident`/…), or to no split at all, while the paragraph
  named the column the user ASKED for. The same substitute-and-say-nothing shape as `violin` and
  `deg`, third family.
* **the population** — `max_cells` randomly subsamples the cells the VIOLINS show (seeded), while
  the filter/doublet counts and the summary table are computed on every cell. The figure and its own
  table describe different populations and nothing disclosed it. Whether the cap bites depends on
  the file's cell count, which a param cannot know: the declared smoke case draws 3,000 of 10,000.

The runner records both in `layout.meta.qc`; `methods.build_body` lifts them as `_qc_run`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from companions import methods
from skills.contract import load_skill

anndata = pytest.importorskip("anndata")
pytest.importorskip("scanpy")


def _h5ad(tmp_path, n_cells=400, group_col="sample"):
    """A tiny raw-count AnnData with one MT- gene, enough for `calculate_qc_metrics`."""
    rng = np.random.default_rng(0)
    counts = rng.poisson(3.0, size=(n_cells, 30)).astype("float32")
    var = pd.DataFrame(index=[f"GENE{i}" for i in range(29)] + ["MT-CO1"])
    obs = pd.DataFrame({group_col: [f"S{i % 3}" for i in range(n_cells)]},
                       index=[f"c{i}" for i in range(n_cells)])
    path = tmp_path / "qc.h5ad"
    anndata.AnnData(X=counts, obs=obs, var=var).write_h5ad(path)
    return str(path)


def _prose(path, params):
    from skills.normalization_qc.run_real import run

    figure = run(data_path=path, params=params)
    return methods.build_body(load_skill("normalization_qc"), params, figure)[0], figure


def test_prose_names_the_grouping_that_was_SUBSTITUTED(tmp_path):
    """The requested column is absent, so the runner falls back to `sample`. Naming the requested
    one describes a figure split by a column that is not in the file."""
    text, figure = _prose(_h5ad(tmp_path), {"groupby": "cell_type", "max_cells": 10_000})
    assert figure["layout"]["meta"]["qc"]["groupby"] == "sample"
    assert "split by sample" in text
    assert "The requested grouping column cell_type was not present, so sample was used" in text


def test_prose_names_the_requested_column_when_no_substitution_happened(tmp_path):
    """The mirror — an honest run must not carry a substitution disclaimer."""
    text, _ = _prose(_h5ad(tmp_path), {"groupby": "sample", "max_cells": 10_000})
    assert "split by sample" in text
    assert "was not present" not in text


def test_prose_says_there_is_no_grouping_when_nothing_could_be_substituted(tmp_path):
    """No requested column and no fallback in the file → every cell is pooled into one violin. The
    paragraph said "split by sample" over a figure with no split at all."""
    path = _h5ad(tmp_path, group_col="tissue")          # not in _GROUP_FALLBACKS
    text, figure = _prose(path, {"groupby": "cell_type", "max_cells": 10_000})
    assert figure["layout"]["meta"]["qc"]["groupby"] is None
    assert "pooled across all cells" in text
    assert "no sample/batch column could be substituted" in text


def test_prose_discloses_the_display_subsample_and_its_size(tmp_path):
    """The violins show a seeded random subsample; the counts beneath them do not."""
    text, figure = _prose(_h5ad(tmp_path, n_cells=400), {"groupby": "sample", "max_cells": 100})
    assert figure["layout"]["meta"]["qc"] == {
        "groupby": "sample", "requested_groupby": "sample", "shown": 100, "total": 400,
    }
    assert "random subsample of 100 of the 400 cells" in text
    assert "all reported counts below are over the full set" in text


def test_prose_stays_silent_when_the_cap_did_not_bite(tmp_path):
    """A disclosure that fires when nothing was dropped is its own kind of wrong."""
    text, _ = _prose(_h5ad(tmp_path, n_cells=400), {"groupby": "sample", "max_cells": 6000})
    assert "subsample" not in text

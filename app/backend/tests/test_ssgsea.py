"""ssGSEA skill — stub shape, the pure pivot/z-score/table transform, and a gated real run.

Per the new-skill discipline, the dep-free assertions call the stub and the pure
``_assemble`` helper DIRECTLY (a synthetic res2d-shaped frame, no gseapy), and the
real-engine smoke test runs gseapy.ssgsea on a tiny in-memory matrix (skipped when the
dep is absent). Real numeric fidelity is validated by a live dogfood, not here.
"""

from importlib.util import find_spec

import pytest


def test_stub_shape():
    from skills.ssgsea.run import _stub_figure

    fig = _stub_figure({})
    heat = fig["data"][0]
    assert heat["type"] == "heatmap"
    assert heat["zmid"] == 0
    assert len(heat["z"]) == len(heat["y"])                          # rows == pathways
    assert all(len(row) == len(heat["x"]) for row in heat["z"])      # cols == samples
    assert "table" not in fig                                        # the stub attaches no table


def test_assemble_pivots_zscores_and_keeps_raw_in_table():
    import pandas as pd

    from skills.ssgsea.run_real import _assemble

    # res2d-shaped long frame (NES as object strings, exactly like gseapy returns it).
    res = pd.DataFrame({
        "Name": ["S1", "S2", "S1", "S2", "S1", "S2"],
        "Term": ["A", "A", "B", "B", "C", "C"],
        "ES":   [1, 2, 3, 4, 5, 6],
        "NES":  ["0.1", "0.9", "0.5", "0.5", "0.2", "0.8"],
    })
    fig = _assemble(res, ["S1", "S2"], {"top_n": 25, "zscore": True})
    heat = fig["data"][0]
    assert heat["x"] == ["S1", "S2"]                # original sample order preserved
    assert set(heat["y"]) == {"A", "B", "C"}
    # constant pathway B (0.5/0.5) z-scores to (0, 0)
    assert heat["z"][heat["y"].index("B")] == [0.0, 0.0]
    # the table carries the RAW NES, not the z-scores
    tbl = fig["table"]
    assert tbl["columns"] == ["gene set", "S1", "S2"]
    rowmap = {r[0]: r[1:] for r in tbl["rows"]}
    assert rowmap["A"] == [0.1, 0.9]


def test_top_n_keeps_the_most_variable_pathways():
    import pandas as pd

    from skills.ssgsea.run_real import _assemble

    rows = []
    for term, (a, b) in {"flat": (0.5, 0.5), "mid": (0.2, 0.8), "big": (0.0, 1.0)}.items():
        rows += [{"Name": "S1", "Term": term, "ES": 1, "NES": str(a)},
                 {"Name": "S2", "Term": term, "ES": 1, "NES": str(b)}]
    fig = _assemble(pd.DataFrame(rows), ["S1", "S2"], {"top_n": 2, "zscore": False})
    assert set(fig["data"][0]["y"]) == {"big", "mid"}           # "flat" dropped (least variable)
    assert "3 gene sets x 2 samples (top 2 by variance)" in fig["layout"]["title"]["text"]


@pytest.mark.skipif(find_spec("gseapy") is None, reason="gseapy not installed")
def test_real_engine_on_synthetic_matrix(tmp_path):
    import numpy as np
    import pandas as pd

    from skills.ssgsea.run_real import run

    rng = np.random.default_rng(0)
    genes = [f"G{i}" for i in range(120)]
    expr = pd.DataFrame(rng.lognormal(size=(120, 4)), index=genes,
                        columns=["S1", "S2", "S3", "S4"])
    members = genes[:25]
    expr.loc[members, ["S1", "S2"]] += 6.0     # enrich the pasted set in S1/S2 only
    path = tmp_path / "expr.csv"
    expr.to_csv(path)

    fig = run(str(path), {"gene_set": " ".join(members), "top_n": 25, "min_size": 5,
                          "max_size": 200, "weight": 0.25, "zscore": False})
    heat = fig["data"][0]
    assert heat["type"] == "heatmap"
    assert heat["x"] == ["S1", "S2", "S3", "S4"]
    assert len(heat["y"]) == 1                  # the single pasted set
    nes = fig["table"]["rows"][0][1:]           # raw NES per sample
    assert nes[0] > nes[2] and nes[1] > nes[3]  # enriched samples score higher

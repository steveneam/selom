"""scorecard ``layout`` param — radar (default) vs metrics × conditions heatmap.

Fig 6F shows the organoid-fidelity benchmark in two forms; ``layout=heatmap`` adds the
grid form to the existing radar. Pinned to the stub so it runs without pandas.
"""

import pytest

from skills.contract import run_skill


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_scorecard_default_is_radar():
    fig = run_skill("scorecard", "unused", {})
    assert {t["type"] for t in fig["data"]} == {"scatterpolar"}


def test_scorecard_heatmap_layout():
    fig = run_skill("scorecard", "unused", {"layout": "heatmap"})
    assert len(fig["data"]) == 1
    tr = fig["data"][0]
    assert tr["type"] == "heatmap"
    # rows = metrics (5), columns = conditions (3) for the fixed stub
    assert len(tr["y"]) == 5 and len(tr["x"]) == 3
    assert len(tr["z"]) == 5 and all(len(row) == 3 for row in tr["z"])
    # normalized stub -> colour scale pinned to [0, 1]
    assert tr["zmin"] == 0 and tr["zmax"] == 1
    # plain JSON, no numpy / base64 leakage
    import json

    assert json.loads(json.dumps(fig)) == fig

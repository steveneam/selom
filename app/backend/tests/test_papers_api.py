"""Read-only Reproduction-view API (spec §Endpoints; R5 data layer).

The three captured ledgers feed the FE Reproduction view: the index spectrum (/papers) and
the per-paper detail (/papers/{slug} = full driven ledger, including the derived scorecard).
Data is the real engine output, so these assert the headline numbers the view renders.
"""

from fastapi.testclient import TestClient

import papers_api
from main import app

client = TestClient(app)

# The headline reproducibility spectrum (the whole point of the index view).
EXPECTED = {"rpgrip1": 63, "jev": 86, "hani": 96}


def test_list_papers_is_the_ascending_spectrum():
    papers = client.get("/papers").json()["papers"]
    assert [p["slug"] for p in papers] == ["rpgrip1", "jev", "hani"]
    # ascending reproducibility so the row reads red -> green
    repros = [p["score"]["reproducibility"] for p in papers]
    assert repros == sorted(repros) == [63, 86, 96]
    for p in papers:
        assert p["title"] and p["score"]["color"].startswith("#")
        # every index card carries its mini heatmap strip
        assert p["cells"] and all("color" in c for c in p["cells"])


def test_each_paper_scorecard_matches_the_headline():
    for slug, repro in EXPECTED.items():
        sc = client.get(f"/papers/{slug}/scorecard").json()
        assert sc["score"]["reproducibility"] == repro
        assert sc["panel_scores"], "scorecard must carry per-panel cells for the heatmap"


def test_full_ledger_feeds_the_detail_table():
    # The detail view joins panels (+golden) to validations (golden-vs-computed verdict/blame).
    led = client.get("/papers/rpgrip1").json()
    assert led["paper"]["slug"] == "rpgrip1"
    assert led["panels"] and led["validations"] and led["scorecard"]
    keys = {v["panel_key"] for v in led["validations"]}
    assert keys, "validations must be joinable to panels by panel_key"
    # every validation result carries the table's columns
    a_result = led["validations"][0]["results"][0]
    assert {"metric", "golden", "computed", "verdict"} <= set(a_result)


def test_jev_surfaces_a_provenance_divergence():
    # D14: JEV 4e reproduces its deposit (ST6) but diverges from the figure — surfaced, not blamed.
    sc = client.get("/papers/jev/scorecard").json()
    assert sc["provenance_divergences"] == ["4e: ST6+ Fig4e−"]


def test_unknown_paper_is_404():
    assert client.get("/papers/nope").status_code == 404
    assert client.get("/papers/nope/scorecard").status_code == 404


def test_slugs_match_the_registry():
    assert set(papers_api.SLUGS) == set(papers_api._LEDGER_MODULES)

"""lit-synthesizer Phase D — a reproduction Ledger -> one paper-level Methods section."""

import pytest

import papers_api
import reproduction as R
from litsynth import from_ledger


def _panel(fig, panel, skill_id, *, params=None, scope=R.TRANSCRIPTOMIC):
    return R.Panel(
        paper_id="demo", figure=fig, panel=panel, skill_id=skill_id,
        params=params or {}, scope=scope,
    )


def _demo_ledger() -> R.Ledger:
    # Figure order: umap, cluster, umap(dup), deg, a form panel (no skill), an out-of-scope
    # demo (markers), and a wet-lab panel (volcano) — only the first four distinct runs survive.
    paper = R.Paper(id="demo", slug="demo", title="Demo paper", modality="scrna", geo=["GSE1", "GSE2"])
    panels = [
        _panel("1", "A", "umap_scrna"),
        _panel("1", "B", "cluster"),
        _panel("2", "A", "umap_scrna"),  # identical (skill, params) -> deduped
        _panel("2", "B", "deg", params={"top_n": "25"}),
        _panel("3", "A", None),  # form/claim panel, no skill -> skipped
        _panel("3", "B", "markers", scope=R.DATA_NOT_DEPOSITED),  # out of scope -> skipped
        _panel("3", "C", "volcano", scope=R.WET_LAB),  # out of scope -> skipped
    ]
    return R.Ledger(paper=paper, panels=panels)


def test_ledger_skill_runs_filters_orders_and_dedups():
    runs = from_ledger.ledger_skill_runs(_demo_ledger())
    assert [r.skill_id for r in runs] == ["umap_scrna", "cluster", "deg"]  # dup + form + 2 oos dropped
    assert runs[2].params == {"top_n": "25"}  # resolved params carried through


def test_dataset_descriptor_prefers_geo_then_title():
    assert from_ledger.dataset_descriptor(R.Paper(id="p", slug="p", geo=["GSE1", "GSE2"])) == (
        "Data deposited under GSE1, GSE2 were analyzed"
    )
    assert from_ledger.dataset_descriptor(R.Paper(id="p", slug="p", title="My Paper")) == "My Paper"
    assert from_ledger.dataset_descriptor(R.Paper(id="p", slug="p")) is None


def test_compose_ledger_methods_frames_intro_and_dedups_citations():
    section = from_ledger.compose_ledger_methods(_demo_ledger())
    assert section.skill_ids == ["umap_scrna", "cluster", "deg"]
    assert len(section.paragraphs) == 3
    # Declared scrna modality + GEO descriptor both frame the intro.
    assert section.intro.startswith("Data deposited under GSE1, GSE2 were analyzed. Single-cell RNA-seq")
    assert section.modality == "scrna"
    # 25 is the resolved deg threshold, proving panel params flow through.
    assert "top 25 genes" in section.text
    # Citations deduped (SCANPY shared by all three skills appears once).
    assert len(section.citations) == len(set(section.citations))
    assert "All analyses were performed using Selom" in section.text


def test_explicit_modality_overrides_paper_modality():
    section = from_ledger.compose_ledger_methods(_demo_ledger(), modality="bulk")
    assert "Bulk RNA-seq" in section.intro and "Single-cell" not in section.intro


def test_no_in_scope_panels_raises():
    paper = R.Paper(id="empty", slug="empty")
    ledger = R.Ledger(
        paper=paper,
        panels=[_panel("1", "A", None), _panel("1", "B", "deg", scope=R.WET_LAB)],
    )
    with pytest.raises(ValueError, match="no in-scope analysis panels"):
        from_ledger.compose_ledger_methods(ledger)


# --- against the REAL driven ledgers (the three-paper spectrum) -----------------------------


@pytest.mark.parametrize("slug", papers_api.SLUGS)
def test_real_ledgers_compose_a_methods_section(slug):
    section = from_ledger.compose_ledger_methods(papers_api.driven_ledger(slug))
    assert section.text and section.skill_ids and section.paragraphs
    assert len(section.skill_ids) == len(section.paragraphs)
    assert len(section.citations) == len(set(section.citations))  # deduped across the whole paper
    assert "All analyses were performed using Selom" in section.text


def test_hani_is_framed_as_scrna():
    section = from_ledger.compose_ledger_methods(papers_api.driven_ledger("hani"))
    assert section.modality == "scrna"
    assert "Single-cell RNA-seq" in section.intro
    assert "GSE201356" in section.intro


def test_endpoint_serves_methods_and_validates_slug():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    r = c.get("/papers/hani/methods")
    assert r.status_code == 200
    body = r.json()
    assert body["skill_ids"] and "Single-cell RNA-seq" in body["intro"]
    # modality override flows through the query param.
    assert "Bulk RNA-seq" in c.get("/papers/hani/methods", params={"modality": "bulk"}).json()["intro"]
    # Unknown paper is a clean 404.
    assert c.get("/papers/nope/methods").status_code == 404

"""paper_metadata enrichment — DOI extraction, OpenAlex/CrossRef parse, the fail-soft chain,
the degrade-safe glue, the API endpoint, and a gated pikepdf XMP round-trip.

The network is behind one Fetcher seam, so the orchestration is exercised offline with
fixture-returning fetchers (no real HTTP). Live numeric/real-API fidelity is dogfooded
separately, not here.
"""

import json
from importlib.util import find_spec
from urllib.error import HTTPError

import pytest


# --- fixture fetchers -----------------------------------------------------------------


def _bytes(obj):
    return json.dumps(obj).encode("utf-8")


def _fetch_map(mapping, *, miss_404=True):
    """A Fetcher: first (substring -> payload-bytes) whose substring is in the URL wins.
    No match -> HTTPError 404 (a clean 'not in this index') or OSError when miss_404=False."""
    def fetch(url):
        for sub, payload in mapping:
            if sub in url:
                return payload
        if miss_404:
            raise HTTPError(url, 404, "not found", {}, None)
        raise OSError("network down")
    return fetch


def _raises(exc):
    def fetch(url):
        raise exc
    return fetch


_OPENALEX_FULL = {
    "id": "https://openalex.org/W99", "doi": "https://doi.org/10.1038/s41586-021-1",
    "display_name": "A complete paper", "publication_year": 2021, "type": "article",
    "authorships": [{"author": {"display_name": "Jane Roe"}}],
    "primary_location": {"source": {"display_name": "Nature", "type": "journal"}},
    "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345/"},
}
_OPENALEX_NO_VENUE = {**_OPENALEX_FULL, "primary_location": {"source": {}}}
_CROSSREF_VENUE = {"message": {
    "DOI": "10.1038/s41586-021-1", "title": ["A complete paper"], "container-title": ["Nature"],
    "author": [{"given": "Jane", "family": "Roe"}], "issued": {"date-parts": [[2021]]},
    "type": "journal-article",
}}


# --- DOI extraction / parse (pure) ----------------------------------------------------


def test_clean_and_find_doi():
    import paper_metadata as pm

    assert pm._clean_doi("https://doi.org/10.1038/s41586-020-2649-2") == "10.1038/s41586-020-2649-2"
    assert pm._clean_doi("doi:10.1101/2023.01.02.522345v1).") == "10.1101/2023.01.02.522345v1"
    assert pm._clean_doi("not a doi") is None
    assert pm._doi_in("text with DOI 10.1016/j.cell.2023.05.001, end") == "10.1016/j.cell.2023.05.001"


def test_openalex_and_crossref_parse_and_preprint_flag():
    import paper_metadata as pm

    r = pm._openalex_work(_OPENALEX_FULL)
    assert (r.title, r.year, r.venue, r.pmid, r.openalex_id) == ("A complete paper", 2021, "Nature", "12345", "W99")
    assert r.authors == ["Jane Roe"] and r.is_preprint is False
    # CrossRef posted-content => preprint; bioRxiv DOI prefix also flags preprint.
    # (_crossref_work takes the unwrapped `message` dict; crossref_by_doi does the unwrapping.)
    c = pm._crossref_work({"DOI": "10.1101/2023.1", "title": ["P"], "type": "posted-content"})
    assert c.is_preprint is True
    assert pm._openalex_work({}) is None and pm._crossref_work(None) is None


def test_extract_candidate_ids_prefers_xmp_then_text(monkeypatch, tmp_path):
    import paper_metadata as pm
    import papers

    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(pm, "read_xmp", lambda p: {})
    monkeypatch.setattr(papers, "extract_pages", lambda p, pages: ["Title\nDOI: 10.1234/abc.def here"])
    monkeypatch.setattr(papers, "pdf_info", lambda p: {"metadata": {"Title": "Some Real Article Title"}})
    ids = pm.extract_candidate_ids(pdf)
    assert ids.doi == "10.1234/abc.def" and "text" in ids.sources
    assert ids.title == "Some Real Article Title"

    # XMP wins over text when present.
    monkeypatch.setattr(pm, "read_xmp", lambda p: {"doi": "10.5555/xmp.win", "title": None})
    ids2 = pm.extract_candidate_ids(pdf)
    assert ids2.doi == "10.5555/xmp.win" and "xmp" in ids2.sources


# --- orchestration (fail-soft chain) --------------------------------------------------


def _enrich(ids, *, oa, cr, pm_fetch):
    import paper_metadata as pm

    return pm.enrich_from_ids(ids, openalex_fetch=oa, crossref_fetch=cr, pubmed_fetch=pm_fetch)


def test_doi_path_resolves_via_openalex():
    import paper_metadata as pm

    oa = _fetch_map([("api.openalex.org/works/doi:", _bytes(_OPENALEX_FULL))])
    rec, prov = _enrich(pm.CandidateIds(doi="10.1038/s41586-021-1"),
                        oa=oa, cr=_raises(AssertionError("crossref not needed")),
                        pm_fetch=_raises(AssertionError("pubmed not needed")))
    assert rec.matched_by == "doi" and rec.source == "openalex" and rec.confidence == 0.97
    assert rec.venue == "Nature" and prov["degraded"] is False and prov["tried"] == ["openalex"]


def test_doi_cross_check_fills_gaps_from_crossref():
    import paper_metadata as pm

    oa = _fetch_map([("api.openalex.org/works/doi:", _bytes(_OPENALEX_NO_VENUE))])
    cr = _fetch_map([("api.crossref.org/works/", _bytes(_CROSSREF_VENUE))])
    rec, prov = _enrich(pm.CandidateIds(doi="10.1038/s41586-021-1"),
                        oa=oa, cr=cr, pm_fetch=_raises(AssertionError("pubmed not needed")))
    assert rec.source == "openalex"          # primary kept
    assert rec.venue == "Nature"             # gap filled from crossref
    assert prov["tried"] == ["openalex", "crossref"]


def test_title_fallback_ranks_by_similarity():
    import paper_metadata as pm

    results = {"results": [
        {"id": "https://openalex.org/W1", "display_name": "An unrelated study", "publication_year": 2019,
         "authorships": [], "primary_location": {"source": {"display_name": "J1"}}},
        {"id": "https://openalex.org/W2", "display_name": "The exact paper title", "publication_year": 2020,
         "authorships": [{"author": {"display_name": "A B"}}], "primary_location": {"source": {"display_name": "J2"}}},
    ]}
    oa = _fetch_map([("api.openalex.org/works?", _bytes(results))])
    rec, prov = _enrich(pm.CandidateIds(title="The exact paper title"),
                        oa=oa, cr=_raises(AssertionError()), pm_fetch=_raises(AssertionError()))
    assert rec.matched_by == "title" and rec.title == "The exact paper title"
    assert rec.confidence >= 0.95 and prov["source"] == "openalex"


def test_degrades_on_network_error_but_not_on_404():
    import paper_metadata as pm

    rec, prov = _enrich(pm.CandidateIds(doi="10.1/x"),
                        oa=_raises(OSError("down")), cr=_raises(OSError("down")),
                        pm_fetch=_raises(OSError("down")))
    assert rec is None and prov["degraded"] is True and prov["tried"] == ["openalex", "crossref", "pubmed"]

    # All clean 404s -> a clean "not found", NOT a degradation.
    miss = _fetch_map([], miss_404=True)
    rec2, prov2 = _enrich(pm.CandidateIds(doi="10.1/x"), oa=miss, cr=miss, pm_fetch=miss)
    assert rec2 is None and prov2["degraded"] is False


# --- glue (cache + degrade) -----------------------------------------------------------


def test_metadata_by_doi_caches_and_is_degrade_safe(tmp_path):
    import paper_metadata as pm
    from litsynth.cache import JsonCache

    cache = JsonCache(tmp_path / "c.json")
    oa = _fetch_map([("api.openalex.org/works/doi:", _bytes(_OPENALEX_FULL))])
    out = pm.metadata_by_doi("10.1038/s41586-021-1", openalex_fetch=oa,
                             crossref_fetch=_raises(AssertionError()), pubmed_fetch=_raises(AssertionError()),
                             cache=cache)
    assert out["record"]["venue"] == "Nature" and out["degraded"] is False
    # Second call is served from cache (the now-asserting fetchers are never consulted).
    again = pm.metadata_by_doi("10.1038/s41586-021-1", openalex_fetch=_raises(AssertionError()),
                               crossref_fetch=_raises(AssertionError()), pubmed_fetch=_raises(AssertionError()),
                               cache=cache)
    assert again["record"]["venue"] == "Nature"
    # A blank DOI is a clean empty (no fetch).
    assert pm.metadata_by_doi("", cache=cache)["record"] is None


def test_api_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    import paper_metadata as pm

    monkeypatch.setattr(pm, "metadata_by_doi", lambda doi: {"record": {"doi": doi, "title": "X"},
                                                            "provenance": {"matched_by": "doi"}, "degraded": False})
    client = TestClient(main.app)
    r = client.get("/papers/metadata/by-doi", params={"doi": "10.1/x"})
    assert r.status_code == 200 and r.json()["record"]["doi"] == "10.1/x"
    assert client.get("/papers/metadata/by-doi", params={"doi": ""}).status_code == 400


def test_suggest_filename_variants():
    import paper_metadata as pm

    rec = pm.PaperMetadata(title="A Great Paper", authors=["Jane Roe", "John Doe"], year=2021, venue="Nature")
    assert pm.suggest_filename(rec) == "Roe_2021_Nature.pdf"
    # PubMed 'Surname Initials' format -> surname is the FIRST token.
    pub = pm.PaperMetadata(title="T", authors=["Roe JA", "Doe K"], year=2020, venue="Cell")
    assert pm.suggest_filename(pub) == "Roe_2020_Cell.pdf"
    # Venue missing -> fall back to a short title; illegal chars stripped.
    notitle = pm.PaperMetadata(title="Cones/Rods: a study", authors=["Bee A"], year=2019, venue=None)
    fn = pm.suggest_filename(notitle, template="{author}_{year}_{title}")
    assert fn.startswith("Bee_2019_ConesRods") and "/" not in fn and ":" not in fn
    # Fully empty record still yields a safe name.
    assert pm.suggest_filename(pm.PaperMetadata()).endswith(".pdf")


def test_apply_rename_copies_and_suffixes_collisions(tmp_path):
    import paper_metadata as pm

    src = tmp_path / "download.pdf"
    src.write_bytes(b"%PDF-1.4 hello")
    rec = pm.PaperMetadata(authors=["Jane Roe"], year=2021, venue="Nature")
    out = pm.apply_rename(src, rec)
    assert out.name == "Roe_2021_Nature.pdf" and out.read_bytes() == b"%PDF-1.4 hello"
    assert src.exists()  # non-destructive copy by default
    # A second rename of a different source collides -> suffixed.
    src2 = tmp_path / "other.pdf"
    src2.write_bytes(b"%PDF-1.4 two")
    out2 = pm.apply_rename(src2, rec)
    assert out2.name == "Roe_2021_Nature (2).pdf"


@pytest.mark.skipif(find_spec("pikepdf") is None, reason="pikepdf not installed")
def test_xmp_write_then_read_round_trip(tmp_path):
    import pikepdf

    import paper_metadata as pm

    src = tmp_path / "blank.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    pdf.save(str(src))
    pdf.close()

    out = tmp_path / "tagged.pdf"
    rec = pm.PaperMetadata(title="My Paper", authors=["Jane Roe"], doi="10.1234/round.trip",
                           venue="Nature", year=2021)
    pm.write_xmp(src, rec, out)
    got = pm.read_xmp(out)
    assert got.get("doi") == "10.1234/round.trip"
    assert got.get("title") == "My Paper"

"""lit-synthesizer Phase B/C — PubMed + bioRxiv citation lookup, fully offline (injected fetcher)."""

from litsynth import biorxiv, lookup, pubmed
from litsynth.cache import JsonCache
from litsynth.pubmed import NcbiConfig, ThrottledFetcher

ESEARCH_XML = b"""<?xml version="1.0"?>
<eSearchResult><Count>1</Count><RetMax>1</RetMax><IdList><Id>29409532</Id></IdList></eSearchResult>"""

ESUMMARY_XML = b"""<?xml version="1.0"?>
<eSummaryResult>
<DocSum>
<Id>29409532</Id>
<Item Name="PubDate" Type="Date">2018 Feb 06</Item>
<Item Name="Source" Type="String">Genome Biol</Item>
<Item Name="AuthorList" Type="List">
<Item Name="Author" Type="String">Wolf FA</Item>
<Item Name="Author" Type="String">Angerer P</Item>
<Item Name="Author" Type="String">Theis FJ</Item>
</Item>
<Item Name="Title" Type="String">SCANPY: large-scale single-cell gene expression data analysis.</Item>
<Item Name="FullJournalName" Type="String">Genome biology</Item>
<Item Name="DOI" Type="String">10.1186/s13059-017-1382-0</Item>
</DocSum>
</eSummaryResult>"""


def fixture_fetch(url: str) -> bytes:
    if "esearch" in url:
        return ESEARCH_XML
    if "esummary" in url:
        return ESUMMARY_XML
    raise AssertionError(f"unexpected url {url}")


def test_search_parses_esearch_then_esummary():
    cites = pubmed.search("scanpy", fetch=fixture_fetch)
    assert len(cites) == 1
    c = cites[0]
    assert c.pmid == "29409532"
    assert c.title.startswith("SCANPY")
    assert c.year == 2018
    assert c.authors == ["Wolf FA", "Angerer P", "Theis FJ"]
    assert c.doi == "10.1186/s13059-017-1382-0"
    assert c.venue == "Genome biology"
    assert c.url == "https://pubmed.ncbi.nlm.nih.gov/29409532/"
    assert c.source == "pubmed"
    assert c.metadata_license is None  # PubMed metadata is US-gov, not a per-record license


def test_search_empty_when_no_ids():
    empty = b'<?xml version="1.0"?><eSearchResult><IdList></IdList></eSearchResult>'
    assert pubmed.search("nothing", fetch=lambda u: empty) == []


def test_search_blank_term_skips_fetch():
    def boom(url):
        raise AssertionError("should not fetch on a blank term")

    assert pubmed.search("   ", fetch=boom) == []


def test_by_doi_resolves_one():
    c = pubmed.by_doi("10.1186/s13059-017-1382-0", fetch=fixture_fetch)
    assert c is not None and c.pmid == "29409532"


def test_doi_from_elocation():
    assert pubmed._doi_from_elocation("doi: 10.1/x") == "10.1/x"
    assert pubmed._doi_from_elocation("10.2/y") == "10.2/y"
    assert pubmed._doi_from_elocation("pii: abc") is None
    assert pubmed._doi_from_elocation(None) is None


def test_year_extraction():
    assert pubmed._year("2018 Feb 06") == 2018
    assert pubmed._year(None) is None
    assert pubmed._year("n/a") is None


def test_config_min_interval_and_identity():
    keyless = NcbiConfig(email="a@b.c")
    assert keyless.min_interval == 0.34
    assert keyless.identity_params() == {"tool": "selom", "email": "a@b.c"}
    keyed = NcbiConfig(api_key="K")
    assert keyed.min_interval == 0.11
    assert keyed.identity_params()["api_key"] == "K"


def test_esearch_url_carries_identity_and_min_year():
    url = pubmed.esearch_url("scanpy", NcbiConfig(email="a@b.c"), retmax=5, min_year=2015)
    assert "tool=selom" in url and "email=a%40b.c" in url
    assert "mindate=2015" in url and "datetype=pdat" in url


def test_throttled_fetcher_spaces_requests():
    clock = {"now": 0.0}
    slept: list[float] = []

    class FakeResp:
        def __init__(self, data):
            self._d = data

        def read(self):
            return self._d

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout=None):
        return FakeResp(b"ok")

    def sleep(s):
        slept.append(s)
        clock["now"] += s

    f = ThrottledFetcher(min_interval=0.34, opener=opener, sleep=sleep, clock=lambda: clock["now"])
    assert f("http://x/1") == b"ok"  # first call: no wait
    assert slept == []
    f("http://x/2")  # immediate second call: must sleep one interval
    assert len(slept) == 1 and abs(slept[0] - 0.34) < 1e-9


def test_jsoncache_roundtrip_and_none(tmp_path):
    c = JsonCache(tmp_path / "c.json")
    assert c.has("k") is False
    c.set("k", [1, 2])
    assert c.get("k") == [1, 2]
    c.set("none", None)
    assert c.has("none") is True  # 'cached as None' (a negative result) != 'never cached'
    assert c.get("none") is None


def test_lookup_search_caches_and_degrades(tmp_path):
    cache = JsonCache(tmp_path / "c.json")
    cfg = NcbiConfig()
    calls = {"n": 0}

    def fetch(url):
        calls["n"] += 1
        return fixture_fetch(url)

    r1 = lookup.search_citations("scanpy", fetch=fetch, cache=cache, cfg=cfg)
    assert r1["degraded"] is False and len(r1["results"]) == 1
    after_first = calls["n"]
    r2 = lookup.search_citations("scanpy", fetch=fetch, cache=cache, cfg=cfg)
    assert r2["results"] == r1["results"]
    assert calls["n"] == after_first  # cache hit: no extra fetch

    def boom(url):
        raise OSError("network down")

    r3 = lookup.search_citations("novel query", fetch=boom, cache=cache, cfg=cfg)
    assert r3 == {"results": [], "degraded": True}


def test_lookup_by_doi_degrades(tmp_path):
    cache = JsonCache(tmp_path / "c.json")

    def boom(url):
        raise OSError("down")

    # source=both now consults PubMed AND bioRxiv; both down -> degraded, nothing cached.
    out = lookup.citation_by_doi(
        "10.x/y", fetch=boom, biorxiv_fetch=boom, cache=cache, cfg=NcbiConfig()
    )
    assert out == {"citation": None, "degraded": True}
    assert cache.has("doi:both:10.x/y") is False  # a transient failure is not pinned


def test_endpoints_validate_without_network():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    # Empty query returns early — no lookup, no network.
    assert c.get("/citations/search").json() == {"results": [], "degraded": False}
    # bioRxiv has no free-text search API -> honest empty, still no network.
    assert c.get("/citations/search", params={"q": "scanpy", "source": "biorxiv"}).json() == {
        "results": [],
        "degraded": False,
    }
    # Missing DOI is a clean 400.
    assert c.get("/citations/by-doi").status_code == 400
    # Unknown source is a clean 400 on both endpoints (no network).
    assert c.get("/citations/search", params={"q": "x", "source": "bogus"}).status_code == 400
    assert c.get("/citations/by-doi", params={"doi": "10.x/y", "source": "bogus"}).status_code == 400


# --- bioRxiv / medRxiv (Phase C) — real-format fixtures from the live API (verified 2026-06-18) ---

BIORXIV_OK = b"""{"messages":[{"status":"ok","category":"all"}],"collection":[
{"doi":"10.1101/2020.07.21.214197","title":"Bioactivity descriptors for uncharacterized compounds",
"authors":"Bertoni, M.; Duran-Frigola, M.; Badia-i-Mompel, P.","date":"2020-07-21","version":"1",
"license":"cc_by_nc_nd","category":"bioinformatics","server":"bioRxiv","published":"NA"}]}"""

# medRxiv: two posted versions -> by_doi must pick the highest version.
MEDRXIV_OK = b"""{"messages":[{"status":"ok","category":"all"}],"collection":[
{"doi":"10.1101/2020.09.09.20191205","title":"Evolution of immunity to SARS-CoV-2","authors":"Doe, J.; Roe, R.",
"date":"2020-09-10","version":"1","license":"cc_no","server":"medRxiv","published":"NA"},
{"doi":"10.1101/2020.09.09.20191205","title":"Evolution of immunity to SARS-CoV-2","authors":"Doe, J.; Roe, R.",
"date":"2020-09-11","version":"2","license":"cc_no","server":"medRxiv","published":"NA"}]}"""

NOT_FOUND = b'{"messages":[{"status":"no posts found"}],"collection":[]}'


def biorxiv_fetch(url: str) -> bytes:
    if "/biorxiv/10.1101/2020.07.21.214197/" in url:
        return BIORXIV_OK
    if "/medrxiv/10.1101/2020.09.09.20191205/" in url:
        return MEDRXIV_OK
    return NOT_FOUND  # includes biorxiv/<medrxiv-only doi> -> exercises the server fallback


def test_biorxiv_by_doi_parses_and_captures_license():
    c = biorxiv.by_doi("10.1101/2020.07.21.214197", fetch=biorxiv_fetch)
    assert c is not None
    assert c.title.startswith("Bioactivity descriptors")
    assert c.authors == ["Bertoni, M.", "Duran-Frigola, M.", "Badia-i-Mompel, P."]
    assert c.year == 2020
    assert c.venue == "bioRxiv"
    assert c.doi == "10.1101/2020.07.21.214197"
    assert c.pmid is None
    assert c.url == "https://doi.org/10.1101/2020.07.21.214197"
    assert c.source == "biorxiv"
    assert c.metadata_license == "cc_by_nc_nd"  # the headline: never assume CC, surface the tag


def test_biorxiv_falls_back_to_medrxiv():
    # The bioRxiv server has no record for this DOI -> by_doi tries medRxiv next.
    c = biorxiv.by_doi("10.1101/2020.09.09.20191205", fetch=biorxiv_fetch)
    assert c is not None and c.source == "medrxiv"
    assert c.metadata_license == "cc_no"  # all-rights-reserved, surfaced honestly


def test_biorxiv_not_found_is_clean_none():
    assert biorxiv.by_doi("10.1101/0000.00.00.000000", fetch=biorxiv_fetch) is None


def test_biorxiv_blank_doi_skips_fetch():
    def boom(url):
        raise AssertionError("should not fetch on a blank DOI")

    assert biorxiv.by_doi("   ", fetch=boom) is None


def test_biorxiv_helpers():
    assert biorxiv._authors("A, B.; C, D.") == ["A, B.", "C, D."]
    assert biorxiv._authors("") == [] and biorxiv._authors(None) == []
    assert biorxiv._year("2020-09-11") == 2020
    assert biorxiv._year(None) is None and biorxiv._year("n/a") is None
    assert biorxiv._latest([]) is None
    latest = biorxiv._latest(
        [{"version": "1", "title": "v1"}, {"version": "3", "title": "v3"}, {"version": "2", "title": "v2"}]
    )
    assert latest["title"] == "v3"  # highest version wins, regardless of list order
    # The DOI's internal slash stays literal in the path (the API 404s if it is encoded).
    assert biorxiv.details_url("biorxiv", "10.1101/x") == (
        "https://api.biorxiv.org/details/biorxiv/10.1101/x/na/json"
    )


def test_lookup_by_doi_both_falls_back_to_biorxiv(tmp_path):
    cache = JsonCache(tmp_path / "c.json")
    empty_esearch = b'<?xml version="1.0"?><eSearchResult><IdList></IdList></eSearchResult>'
    bx_calls = {"n": 0}

    def pubmed_miss(url):  # PubMed cleanly finds nothing (no error)
        return empty_esearch

    def bx(url):
        bx_calls["n"] += 1
        return biorxiv_fetch(url)

    out = lookup.citation_by_doi(
        "10.1101/2020.07.21.214197",
        fetch=pubmed_miss,
        biorxiv_fetch=bx,
        cache=cache,
        cfg=NcbiConfig(),
    )
    assert out["degraded"] is False
    assert out["citation"]["source"] == "biorxiv"
    assert out["citation"]["metadata_license"] == "cc_by_nc_nd"
    after = bx_calls["n"]
    again = lookup.citation_by_doi(
        "10.1101/2020.07.21.214197", fetch=pubmed_miss, biorxiv_fetch=bx, cache=cache, cfg=NcbiConfig()
    )
    assert again["citation"] == out["citation"]
    assert bx_calls["n"] == after  # cache hit: no extra bioRxiv fetch


def test_lookup_by_doi_source_biorxiv_skips_pubmed(tmp_path):
    cache = JsonCache(tmp_path / "c.json")

    def pubmed_boom(url):
        raise AssertionError("source=biorxiv must not touch PubMed")

    out = lookup.citation_by_doi(
        "10.1101/2020.07.21.214197",
        source="biorxiv",
        fetch=pubmed_boom,
        biorxiv_fetch=biorxiv_fetch,
        cache=cache,
        cfg=NcbiConfig(),
    )
    assert out["degraded"] is False and out["citation"]["source"] == "biorxiv"


def test_lookup_search_biorxiv_source_short_circuits(tmp_path):
    cache = JsonCache(tmp_path / "c.json")

    def boom(url):
        raise AssertionError("source=biorxiv search must not fetch (no free-text API)")

    out = lookup.search_citations("anything", source="biorxiv", fetch=boom, cache=cache, cfg=NcbiConfig())
    assert out == {"results": [], "degraded": False}

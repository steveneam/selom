"""lit-synthesizer Phase B — PubMed citation lookup, fully offline (injected fetcher)."""

from litsynth import lookup, pubmed
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

    out = lookup.citation_by_doi("10.x/y", fetch=boom, cache=cache, cfg=NcbiConfig())
    assert out == {"citation": None, "degraded": True}


def test_endpoints_validate_without_network():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    # Empty query returns early — no lookup, no network.
    assert c.get("/citations/search").json() == {"results": [], "degraded": False}
    # Missing DOI is a clean 400.
    assert c.get("/citations/by-doi").status_code == 400

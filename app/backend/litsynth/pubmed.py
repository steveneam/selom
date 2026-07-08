"""NCBI E-utilities client — PubMed citation lookup (lit-synthesizer Phase B).

Stdlib only (``urllib`` + ``xml.etree``). The HTTP layer is a single ``Fetcher`` callable so
the parse logic is offline-testable (inject a fixture-returning fetcher); the real
``ThrottledFetcher`` self-throttles to NCBI's published limits — 3 req/s keyless, 10 with an
API key (NBK25497) — and sends the required tool/email identification. License-clean: PubMed
bibliographic metadata is US-government, not copyrightable; we store fields, not corpora.
"""

from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from litsynth.models import Citation

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "selom/0.1 (https://github.com/steveneam/selom; lit-synthesizer)"

# A Fetcher takes a fully-formed URL and returns the raw response bytes. The real one
# self-throttles + identifies; tests inject a fixture map. Keeping the network behind this
# single seam is what makes the whole module offline-testable (mirrors the gated oracle).
Fetcher = Callable[[str], bytes]


@dataclass
class NcbiConfig:
    tool: str = "selom"
    email: str | None = None
    api_key: str | None = None

    @classmethod
    def from_env(cls) -> NcbiConfig:
        from config import settings  # lazy: keep the pure client free of an import-time config dep

        return cls(
            tool=settings.ncbi_tool,
            email=settings.ncbi_email or None,
            api_key=settings.ncbi_api_key or None,
        )

    @property
    def min_interval(self) -> float:
        # NBK25497: 3 req/s keyless, 10 req/s with a key. Self-throttle just under each.
        return 0.11 if self.api_key else 0.34

    def identity_params(self) -> dict[str, str]:
        p = {"tool": self.tool}
        if self.email:
            p["email"] = self.email
        if self.api_key:
            p["api_key"] = self.api_key
        return p


class ThrottledFetcher:
    """The real Fetcher: spaces requests to NCBI's rate limit + sends a descriptive UA.

    The clock, sleep, and opener are injectable so the throttle is testable WITHOUT a real
    network call or a real sleep.
    """

    def __init__(
        self,
        *,
        min_interval: float = 0.34,
        opener: Callable = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = 20.0,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.min_interval = min_interval
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._timeout = timeout
        self._ua = user_agent
        self._last = float("-inf")  # the first request never throttles, whatever the clock origin

    def __call__(self, url: str) -> bytes:
        wait = self.min_interval - (self._clock() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = self._clock()
        req = urllib.request.Request(url, headers={"User-Agent": self._ua})
        with self._opener(req, timeout=self._timeout) as resp:
            return resp.read()


def default_fetcher(cfg: NcbiConfig) -> ThrottledFetcher:
    return ThrottledFetcher(min_interval=cfg.min_interval)


# --- URL builders ---------------------------------------------------------------------


def _url(path: str, params: dict[str, str]) -> str:
    return f"{EUTILS}/{path}?{urllib.parse.urlencode(params)}"


def esearch_url(term: str, cfg: NcbiConfig, *, retmax: int, min_year: int | None) -> str:
    params = {"db": "pubmed", "term": term, "retmax": str(retmax), "retmode": "xml", **cfg.identity_params()}
    if min_year is not None:
        params.update({"mindate": str(min_year), "maxdate": "3000", "datetype": "pdat"})
    return _url("esearch.fcgi", params)


def esummary_url(pmids: Sequence[str], cfg: NcbiConfig) -> str:
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", **cfg.identity_params()}
    return _url("esummary.fcgi", params)


# --- XML parsing ----------------------------------------------------------------------


def _parse_ids(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    return [el.text for el in root.findall("IdList/Id") if el.text]


def _parse_count(xml_bytes: bytes) -> int:
    """The total number of matches an esearch reports, from the top-level <Count> (which
    is the full hit count regardless of retmax). Missing/blank <Count> ⇒ 0."""
    root = ET.fromstring(xml_bytes)
    txt = (root.findtext("Count") or "").strip()
    return int(txt) if txt.isdigit() else 0


def _text(item: ET.Element | None) -> str | None:
    if item is None:
        return None
    t = (item.text or "").strip()
    return t or None


def _year(pubdate: str | None) -> int | None:
    if not pubdate:
        return None
    m = re.search(r"\d{4}", pubdate)
    return int(m.group()) if m else None


def _doi_from_elocation(eloc: str | None) -> str | None:
    if not eloc:
        return None
    low = eloc.lower()
    if "doi:" in low:
        return eloc[low.index("doi:") + 4 :].strip() or None
    if eloc.startswith("10."):
        return eloc.strip()
    return None


def _docsum_to_citation(ds: ET.Element) -> Citation:
    items = {it.get("Name"): it for it in ds.findall("Item")}
    pmid = _text(ds.find("Id"))
    author_list = items.get("AuthorList")
    authors = (
        [a.text.strip() for a in author_list.findall("Item") if a.text]
        if author_list is not None
        else []
    )
    doi = _text(items.get("DOI")) or _doi_from_elocation(_text(items.get("ELocationID")))
    return Citation(
        title=_text(items.get("Title")) or "",
        authors=authors,
        year=_year(_text(items.get("PubDate"))),
        venue=_text(items.get("FullJournalName")) or _text(items.get("Source")),
        doi=doi,
        pmid=pmid,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        source="pubmed",
    )


def _parse_summaries(xml_bytes: bytes) -> list[Citation]:
    root = ET.fromstring(xml_bytes)
    return [_docsum_to_citation(ds) for ds in root.findall("DocSum")]


# --- public API (fetcher-injected) ----------------------------------------------------


def search(
    term: str,
    *,
    fetch: Fetcher,
    cfg: NcbiConfig | None = None,
    max_results: int = 20,
    min_year: int | None = None,
) -> list[Citation]:
    cfg = cfg or NcbiConfig()
    if not term.strip():
        return []
    ids = _parse_ids(fetch(esearch_url(term, cfg, retmax=max_results, min_year=min_year)))
    if not ids:
        return []
    return _parse_summaries(fetch(esummary_url(ids, cfg)))


def count(term: str, *, fetch: Fetcher, cfg: NcbiConfig | None = None) -> int:
    """Total number of PubMed records matching ``term`` — one esearch (retmax=0), no esummary.

    This is the literature-support primitive behind the violin "known vs novel marker"
    annotation: query a gene (optionally ANDed with a domain context) and read the hit count.
    A blank term is 0 hits without a fetch."""
    cfg = cfg or NcbiConfig()
    if not term.strip():
        return 0
    return _parse_count(fetch(esearch_url(term, cfg, retmax=0, min_year=None)))


def by_doi(doi: str, *, fetch: Fetcher, cfg: NcbiConfig | None = None) -> Citation | None:
    cfg = cfg or NcbiConfig()
    doi = doi.strip()
    if not doi:
        return None
    ids = _parse_ids(fetch(esearch_url(f"{doi}[DOI]", cfg, retmax=1, min_year=None)))
    if not ids:
        return None
    summaries = _parse_summaries(fetch(esummary_url(ids[:1], cfg)))
    return summaries[0] if summaries else None

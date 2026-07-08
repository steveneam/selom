"""Live wiring for the citation-lookup endpoints (Phase B): env config + a throttled
fetcher + an on-disk cache, with graceful degradation. The pure clients live in
``pubmed.py`` (fetcher-injected); this supplies the real fetcher/cache so ``main.py`` stays
thin. Network or parse failure degrades to empty/None + ``degraded=True`` — a lookup must
never break the caller. ``fetch``/``cache``/``cfg`` are injectable so the glue
(cache + degrade) is offline-testable too.
"""

from __future__ import annotations

import pathlib
import tempfile
import xml.etree.ElementTree as ET

from config import settings
from litsynth import biorxiv, pubmed
from litsynth.cache import JsonCache

_CONFIG = pubmed.NcbiConfig.from_env()
_FETCHER = pubmed.default_fetcher(_CONFIG)
_BIORXIV_FETCHER = biorxiv.default_fetcher()
_CACHE = JsonCache(
    settings.citation_cache
    or (pathlib.Path(tempfile.gettempdir()) / "selom-citation-cache.json")
)

# Realistic lookup failures: network (OSError covers URLError/HTTPError/timeout) + JSON/XML
# parse (json.JSONDecodeError subclasses ValueError, so bioRxiv parse errors are covered too).
_LOOKUP_ERRORS = (OSError, ValueError, ET.ParseError)


def search_citations(
    q, *, source="both", max_results=20, min_year=None, fetch=None, cache=None, cfg=None
) -> dict:
    # bioRxiv/medRxiv have no free-text search API (Phase C, verified) — topical search is
    # PubMed-only. 'biorxiv' source is therefore an honest empty result, not a fabricated one;
    # 'both'/'pubmed' both resolve via PubMed (which already indexes many preprints).
    if source == "biorxiv":
        return {"results": [], "degraded": False}
    fetch = fetch or _FETCHER
    cache = cache or _CACHE
    cfg = cfg or _CONFIG
    key = f"search:{(q or '').strip().lower()}:{max_results}:{min_year or ''}"
    if cache.has(key):
        return {"results": cache.get(key) or [], "degraded": False}
    try:
        results = pubmed.search(q, fetch=fetch, cfg=cfg, max_results=max_results, min_year=min_year)
    except _LOOKUP_ERRORS:
        return {"results": [], "degraded": True}
    dumped = [c.model_dump() for c in results]
    cache.set(key, dumped)
    return {"results": dumped, "degraded": False}


def pubmed_count(term, *, fetch=None, cache=None, cfg=None) -> dict:
    """How many PubMed records match ``term`` — the literature-support count, cached + degrade-safe.

    The primitive behind the violin "known vs novel marker" annotation. A blank term is a clean
    0 (no fetch); a network/parse failure degrades to ``{"count": None, "degraded": True}`` so the
    annotation simply drops rather than breaking the figure (the lit-synth honest-empty rule)."""
    if not (term or "").strip():
        return {"count": 0, "degraded": False}
    fetch = fetch or _FETCHER
    cache = cache or _CACHE
    cfg = cfg or _CONFIG
    key = f"count:{term.strip().lower()}"
    if cache.has(key):
        return {"count": cache.get(key), "degraded": False}
    try:
        n = pubmed.count(term, fetch=fetch, cfg=cfg)
    except _LOOKUP_ERRORS:
        return {"count": None, "degraded": True}
    cache.set(key, n)
    return {"count": n, "degraded": False}


def citation_by_doi(
    doi, *, source="both", fetch=None, biorxiv_fetch=None, cache=None, cfg=None
) -> dict:
    """Resolve a DOI to one bibliographic Citation, cached, degrade-safe.

    ``source`` selects the index trust order: ``pubmed`` first (richer, peer-reviewed venue),
    then bioRxiv/medRxiv as a fallback that *also* captures the preprint's per-record license
    (``both``). ``biorxiv`` consults only the preprint servers. ``degraded`` is True only when a
    consulted source raised (network/parse) and we got no hit; a clean "not found" is a cached
    ``None`` with ``degraded=False``.
    """
    fetch = fetch or _FETCHER
    biorxiv_fetch = biorxiv_fetch or _BIORXIV_FETCHER
    cache = cache or _CACHE
    cfg = cfg or _CONFIG
    key = f"doi:{source}:{(doi or '').strip().lower()}"
    if cache.has(key):
        return {"citation": cache.get(key), "degraded": False}

    citation = None
    degraded = False
    if source in ("pubmed", "both"):
        try:
            c = pubmed.by_doi(doi, fetch=fetch, cfg=cfg)
        except _LOOKUP_ERRORS:
            degraded = True
        else:
            citation = c
    if citation is None and source in ("biorxiv", "both"):
        try:
            c = biorxiv.by_doi(doi, fetch=biorxiv_fetch)
        except _LOOKUP_ERRORS:
            degraded = True
        else:
            citation = c

    if degraded and citation is None:
        return {"citation": None, "degraded": True}  # transient failure — don't pin it in cache
    dumped = citation.model_dump() if citation else None
    cache.set(key, dumped)
    return {"citation": dumped, "degraded": False}

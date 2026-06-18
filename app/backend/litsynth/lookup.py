"""Live wiring for the citation-lookup endpoints (Phase B): env config + a throttled
fetcher + an on-disk cache, with graceful degradation. The pure clients live in
``pubmed.py`` (fetcher-injected); this supplies the real fetcher/cache so ``main.py`` stays
thin. Network or parse failure degrades to empty/None + ``degraded=True`` — a lookup must
never break the caller. ``fetch``/``cache``/``cfg`` are injectable so the glue
(cache + degrade) is offline-testable too.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import xml.etree.ElementTree as ET

from litsynth import pubmed
from litsynth.cache import JsonCache

_CONFIG = pubmed.NcbiConfig.from_env()
_FETCHER = pubmed.default_fetcher(_CONFIG)
_CACHE = JsonCache(
    os.environ.get("SELOM_CITATION_CACHE")
    or (pathlib.Path(tempfile.gettempdir()) / "selom-citation-cache.json")
)

# Realistic lookup failures: network (OSError covers URLError/HTTPError/timeout) + XML parse.
_LOOKUP_ERRORS = (OSError, ValueError, ET.ParseError)


def search_citations(q, *, max_results=20, min_year=None, fetch=None, cache=None, cfg=None) -> dict:
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


def citation_by_doi(doi, *, fetch=None, cache=None, cfg=None) -> dict:
    fetch = fetch or _FETCHER
    cache = cache or _CACHE
    cfg = cfg or _CONFIG
    key = f"doi:{(doi or '').strip().lower()}"
    if cache.has(key):
        return {"citation": cache.get(key), "degraded": False}
    try:
        c = pubmed.by_doi(doi, fetch=fetch, cfg=cfg)
    except _LOOKUP_ERRORS:
        return {"citation": None, "degraded": True}
    dumped = c.model_dump() if c else None
    cache.set(key, dumped)
    return {"citation": dumped, "degraded": False}

"""bioRxiv / medRxiv API client — preprint citation lookup with per-record license (Phase C).

Stdlib only (``urllib`` + ``json``). Mirrors ``pubmed.py`` and reuses the SAME injectable
``Fetcher`` seam (``ThrottledFetcher``) so the parse logic is offline-testable (inject a
fixture-returning fetcher) and the real fetcher self-throttles + sends a descriptive UA.

bioRxiv's public ``details`` endpoint is **DOI-addressed — there is no free-text search API**
(verified live 2026-06-18), so this module resolves a DOI to a ``Citation`` and, crucially,
captures the record's own ``license`` (``cc_by`` / ``cc_by_nc_nd`` / ``cc_no`` = all-rights-
reserved) on ``Citation.metadata_license`` — never assume CC. A bioRxiv/medRxiv DOI shares the
``10.1101`` prefix across both servers, so ``by_doi`` tries ``biorxiv`` then ``medrxiv``; a miss
returns ``{"status": "no posts found"}`` with an empty ``collection`` (a clean ``None``, not an
error). Bibliographic fields + the license tag only — no abstract-corpus redistribution
(see ``docs/records/lit-synthesizer-scope.md`` + the pre-launch gate).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from litsynth.models import Citation
from litsynth.pubmed import USER_AGENT, Fetcher, ThrottledFetcher

API = "https://api.biorxiv.org/details"
SERVERS: tuple[str, ...] = ("biorxiv", "medrxiv")
# bioRxiv publishes no rate limit; be a polite citizen anyway (and ThrottledFetcher's UA
# avoids the bare-agent 403s some CDNs return).
MIN_INTERVAL = 0.5


def default_fetcher() -> ThrottledFetcher:
    return ThrottledFetcher(min_interval=MIN_INTERVAL, user_agent=USER_AGENT)


def details_url(server: str, doi: str) -> str:
    # The DOI's internal '/' is a literal path segment the API expects un-encoded
    # (verified: encoding it 404s; the raw slash resolves). Hence no urlencode here.
    return f"{API}/{server}/{doi.strip()}/na/json"


# --- parsing (pure) -------------------------------------------------------------------


def _year(date: str | None) -> int | None:
    # bioRxiv dates are reliably ISO 'YYYY-MM-DD'.
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def _authors(raw: str | None) -> list[str]:
    # bioRxiv ships authors as one '; '-joined string ("Last, F.; Last2, F2."), unlike
    # PubMed's list. Split + preserve each name verbatim (don't re-format a valid citation).
    if not raw:
        return []
    return [a.strip() for a in raw.split(";") if a.strip()]


def _latest(collection: list[dict]) -> dict | None:
    # One record per posted version; take the highest version number.
    if not collection:
        return None

    def ver(rec: dict) -> int:
        try:
            return int(rec.get("version") or 0)
        except (TypeError, ValueError):
            return 0

    return max(collection, key=ver)


def _record_to_citation(rec: dict) -> Citation:
    server = (rec.get("server") or "").strip()
    doi = (rec.get("doi") or "").strip() or None
    return Citation(
        title=(rec.get("title") or "").strip(),
        authors=_authors(rec.get("authors")),
        year=_year(rec.get("date")),
        venue=server or None,  # 'bioRxiv' / 'medRxiv' — the preprint server is the venue
        doi=doi,
        pmid=None,  # a preprint has no PMID
        url=f"https://doi.org/{doi}" if doi else None,
        source=server.lower() or "biorxiv",  # 'biorxiv' | 'medrxiv'
        metadata_license=(rec.get("license") or None),  # the headline of Phase C
    )


# --- public API (fetcher-injected) ----------------------------------------------------


def by_doi(doi: str, *, fetch: Fetcher, servers: Sequence[str] = SERVERS) -> Citation | None:
    """Resolve a preprint DOI to a Citation, trying each server until one has the record.

    Network/parse failures propagate (``OSError``/``json`` ``ValueError``) — the caller
    (``lookup.py``) catches them and degrades. A genuine miss ("no posts found") is a clean
    ``None``, never an exception.
    """
    doi = (doi or "").strip()
    if not doi:
        return None
    for server in servers:
        payload = json.loads(fetch(details_url(server, doi)))
        rec = _latest(payload.get("collection") or [])
        if rec:
            return _record_to_citation(rec)
    return None

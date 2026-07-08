"""Paper metadata enrichment — turn a PDF (or a bare DOI) into a resolved bibliographic record.

The "Article Matcher" the Papers/EndNote-style spinoff needs (external-tools study §4 BUILD #2),
built as an ordered, fail-soft chain — the same shape as the lit-synth injected-Fetcher seam:

    PDF -> candidate IDs (DOI regex on page-1 text + XMP via pikepdf + /Info + filename)
        -> DOI?  -> OpenAlex (CC0) primary, CrossRef cross-check, PubMed fill   [deterministic]
        -> else title -> OpenAlex search / PubMed search (ranked, preprint-flagged)
        -> record (+ OPTIONAL XMP write-back via pikepdf)

LICENSE POSTURE (all verified, external-tools study §2): OpenAlex (CC0, commercial-OK),
CrossRef REST (no-ownership, cacheable, commercial-OK), PubMed E-utilities (US-gov), pikepdf
(MPL-2.0 / qpdf Apache-2.0). Deliberately does NOT depend on ``pdf2doi`` (its code is MIT but it
transitively pulls PyMuPDF/AGPL) — we borrow only its DOI-first algorithm. CrossRef is queried
over raw REST (stdlib urllib), so no ``habanero`` dependency is added; pikepdf is the one new
optional dep, in the ``pdf`` extra, and the chain degrades cleanly without it.

Every network call goes through a single ``Fetcher`` seam (URL -> bytes), reusing the litsynth
ThrottledFetcher/NcbiConfig, so the whole chain is offline-testable (inject fixture fetchers).
"""

from __future__ import annotations

import difflib
import json
import pathlib
import re
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from urllib.error import HTTPError

from pydantic import BaseModel, Field

from config import settings
from litsynth import pubmed
from litsynth.cache import JsonCache

OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"

# DOIs minted by the common preprint servers — used to flag preprints when the index doesn't.
_PREPRINT_DOI_PREFIXES = ("10.1101", "10.21203", "10.20944", "10.26434", "10.31234",
                          "10.31219", "10.31223", "10.22541")
# Crossref's recommended DOI pattern; case-insensitive, trailing punctuation trimmed by caller.
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)
_ARXIV_RE = re.compile(r"arxiv:\s*(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE)


# --- models ---------------------------------------------------------------------------


class CandidateIds(BaseModel):
    """Identifiers harvested from a PDF before any network lookup (with provenance)."""

    doi: str | None = None
    arxiv_id: str | None = None
    title: str | None = None            # best-effort title guess (XMP dc:title / clean /Info Title)
    sources: list[str] = Field(default_factory=list)  # e.g. ["text", "xmp", "info", "filename"]


class PaperMetadata(BaseModel):
    """A resolved bibliographic record. Bibliographic fields only (not copyrightable)."""

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None            # journal / source
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None            # "1289-1296" or a single page
    doi: str | None = None
    pmid: str | None = None
    openalex_id: str | None = None
    url: str | None = None
    is_preprint: bool = False
    source: str | None = None           # index that resolved it: openalex | crossref | pubmed
    matched_by: str | None = None       # how we matched: doi | title
    confidence: float = 0.0             # 0..1


# --- candidate-ID extraction (local, no network) --------------------------------------


def _clean_doi(raw: str | None) -> str | None:
    if not raw:
        return None
    doi = str(raw).strip()
    doi = re.sub(r"^(?:doi:|https?://(?:dx\.)?doi\.org/)", "", doi, flags=re.IGNORECASE).strip()
    m = _DOI_RE.search(doi)
    if not m:
        return None
    return m.group(0).rstrip(").,;]>'\"").strip() or None


def _doi_in(text: str | None) -> str | None:
    if not text:
        return None
    m = _DOI_RE.search(text)
    return m.group(0).rstrip(").,;]>'\"") if m else None


def _looks_like_title(s: str | None) -> bool:
    """A heuristic title sniff for /Info Title — reject filenames / boilerplate."""
    if not s:
        return False
    s = s.strip()
    if len(s) < 12 or " " not in s:
        return False
    low = s.lower()
    if low.endswith((".pdf", ".dvi", ".tex", ".doc", ".docx")):
        return False
    return "untitled" not in low and "microsoft word" not in low


def read_xmp(pdf_path: str | pathlib.Path) -> dict:
    """DOI / title from the PDF's XMP packet via pikepdf — degrade-safe ({} if absent/unavailable).

    pikepdf (MPL-2.0) is optional; a missing dep or a PDF with no XMP both return {} so the
    extraction chain simply falls back to text/Info rather than raising.
    """
    try:
        import pikepdf
    except ImportError:
        return {}
    try:
        with pikepdf.open(str(pdf_path)) as pdf:
            with pdf.open_metadata() as meta:
                ident = meta.get("dc:identifier")
                doi = _clean_doi(meta.get("prism:doi")) or _clean_doi(ident)
                title = meta.get("dc:title")
                if isinstance(title, (list, tuple)):
                    title = title[0] if title else None
                return {"doi": doi, "title": title}
    except Exception:  # noqa: BLE001 - any pikepdf/parse failure degrades to no-XMP
        return {}


def extract_candidate_ids(pdf_path: str | pathlib.Path, *, max_pages: int = 2) -> CandidateIds:
    """Harvest a DOI / arXiv id / title guess from a PDF, page-1 first.

    Order of trust for the DOI: embedded XMP (pikepdf) > the document text (first ``max_pages``)
    > the ``/Info`` dict > the filename. The first that yields a DOI wins; ``sources`` records
    where each datum came from. Best-effort and never raises on a malformed PDF.
    """
    import papers

    sources: list[str] = []
    doi = arxiv_id = title = None

    xmp = read_xmp(pdf_path)
    if xmp.get("doi"):
        doi, _ = xmp["doi"], sources.append("xmp")
    if xmp.get("title") and _looks_like_title(xmp["title"]):
        title = str(xmp["title"]).strip()

    text = ""
    try:
        text = "\n".join(papers.extract_pages(pdf_path, list(range(max_pages))))
    except Exception:  # noqa: BLE001 - text layer may be empty/garbled; fall through to Info
        text = ""
    if doi is None and (hit := _doi_in(text)):
        doi, _ = hit, sources.append("text")
    if (m := _ARXIV_RE.search(text)):
        arxiv_id = m.group(1)

    try:
        info = papers.pdf_info(pdf_path).get("metadata", {})
    except Exception:  # noqa: BLE001
        info = {}
    if doi is None:
        for val in info.values():
            if (hit := _doi_in(str(val))):
                doi, _ = hit, sources.append("info")
                break
    if title is None and _looks_like_title(info.get("Title")):
        title = info["Title"].strip()

    if doi is None and (hit := _doi_in(str(pathlib.Path(pdf_path).name).replace("_", "/"))):
        doi, _ = hit, sources.append("filename")

    return CandidateIds(doi=_clean_doi(doi), arxiv_id=arxiv_id, title=title, sources=sources)


# --- OpenAlex (CC0) -------------------------------------------------------------------


def _with_mailto(url: str, email: str | None) -> str:
    if not email:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}mailto={urllib.parse.quote(email)}"


def openalex_by_doi(doi: str, *, fetch: pubmed.Fetcher, email: str | None = None) -> PaperMetadata | None:
    url = _with_mailto(f"{OPENALEX}/doi:{urllib.parse.quote(doi, safe='/')}", email)
    return _openalex_work(json.loads(fetch(url)))


def openalex_search(title: str, *, fetch: pubmed.Fetcher, email: str | None = None,
                    per_page: int = 5) -> list[PaperMetadata]:
    if not title.strip():
        return []
    params = urllib.parse.urlencode({"search": title, "per_page": str(per_page)})
    url = _with_mailto(f"{OPENALEX}?{params}", email)
    data = json.loads(fetch(url))
    return [w for w in (_openalex_work(r) for r in data.get("results", [])) if w]


def _pages(first, last) -> str | None:
    """Join a first/last page into a range ("1289-1296"), or a single page, or None."""
    first = str(first).strip() if first not in (None, "") else ""
    last = str(last).strip() if last not in (None, "") else ""
    if first and last and first != last:
        return f"{first}-{last}"
    return first or last or None


def _openalex_work(w: dict | None) -> PaperMetadata | None:
    if not w or not isinstance(w, dict) or not (w.get("id") or w.get("doi")):
        return None
    doi = _clean_doi(w.get("doi"))
    ids = w.get("ids") or {}
    pmid = ids.get("pmid")
    if pmid:
        pmid = str(pmid).rstrip("/").rsplit("/", 1)[-1] or None
    loc = (w.get("primary_location") or {})
    src = (loc.get("source") or {})
    biblio = w.get("biblio") or {}
    authors = [a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])]
    is_preprint = (
        str(w.get("type") or "").lower() == "preprint"
        or str(src.get("type") or "").lower() == "repository"
        or _is_preprint_doi(doi)
    )
    return PaperMetadata(
        title=w.get("display_name") or w.get("title"),
        authors=[a for a in authors if a],
        year=w.get("publication_year"),
        venue=src.get("display_name"),
        volume=biblio.get("volume") or None,
        issue=biblio.get("issue") or None,
        pages=_pages(biblio.get("first_page"), biblio.get("last_page")),
        doi=doi,
        pmid=pmid,
        openalex_id=(w.get("id") or "").rsplit("/", 1)[-1] or None,
        url=(f"https://doi.org/{doi}" if doi else w.get("id")),
        is_preprint=is_preprint,
        source="openalex",
    )


# --- CrossRef (raw REST, no habanero) -------------------------------------------------


def crossref_by_doi(doi: str, *, fetch: pubmed.Fetcher, email: str | None = None) -> PaperMetadata | None:
    url = _with_mailto(f"{CROSSREF}/{urllib.parse.quote(doi, safe='/')}", email)
    msg = json.loads(fetch(url)).get("message")
    return _crossref_work(msg)


def _crossref_work(m: dict | None) -> PaperMetadata | None:
    if not m or not isinstance(m, dict):
        return None
    doi = _clean_doi(m.get("DOI"))
    title = m.get("title") or []
    venue = m.get("container-title") or []
    authors = [" ".join(p for p in (a.get("given"), a.get("family")) if p) for a in (m.get("author") or [])]
    dp = ((m.get("issued") or {}).get("date-parts") or [[None]])
    year = dp[0][0] if dp and dp[0] else None
    typ, subtyp = str(m.get("type") or "").lower(), str(m.get("subtype") or "").lower()
    is_preprint = typ == "posted-content" or subtyp == "preprint" or _is_preprint_doi(doi)
    return PaperMetadata(
        title=(title[0] if title else None),
        authors=[a for a in authors if a.strip()],
        year=int(year) if year else None,
        venue=(venue[0] if venue else None),
        volume=str(m["volume"]) if m.get("volume") else None,
        issue=str(m["issue"]) if m.get("issue") else None,
        pages=str(m["page"]) if m.get("page") else None,
        doi=doi,
        url=(f"https://doi.org/{doi}" if doi else None),
        is_preprint=is_preprint,
        source="crossref",
    )


# --- PubMed (reuse litsynth.pubmed) ---------------------------------------------------


def _from_citation(c) -> PaperMetadata:
    return PaperMetadata(
        title=c.title or None,
        authors=list(c.authors),
        year=c.year,
        venue=c.venue,
        doi=_clean_doi(c.doi),
        pmid=c.pmid,
        url=c.url,
        is_preprint=c.source in ("biorxiv", "medrxiv"),
        source="pubmed",
    )


def pubmed_by_doi(doi: str, *, fetch: pubmed.Fetcher, cfg: pubmed.NcbiConfig | None = None) -> PaperMetadata | None:
    c = pubmed.by_doi(doi, fetch=fetch, cfg=cfg)
    return _from_citation(c) if c else None


def pubmed_search(title: str, *, fetch: pubmed.Fetcher, cfg: pubmed.NcbiConfig | None = None,
                  max_results: int = 5) -> list[PaperMetadata]:
    return [_from_citation(c) for c in pubmed.search(title, fetch=fetch, cfg=cfg, max_results=max_results)]


# --- merge / scoring helpers ----------------------------------------------------------


def _is_preprint_doi(doi: str | None) -> bool:
    return bool(doi) and any(str(doi).lower().startswith(p) for p in _PREPRINT_DOI_PREFIXES)


def _norm_title(t: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower()).strip()


def _title_sim(a: str | None, b: str | None) -> float:
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _complete(rec: PaperMetadata) -> bool:
    return bool(rec.title and rec.authors and rec.year and rec.venue)


def _merge(primary: PaperMetadata, other: PaperMetadata) -> PaperMetadata:
    """Fill the primary record's empty bibliographic fields from a cross-check source.
    Keeps the primary's source/matched_by/confidence; only bib gaps are filled."""
    d = primary.model_dump()
    o = other.model_dump()
    for f in ("title", "year", "venue", "volume", "issue", "pages", "doi", "pmid", "openalex_id", "url"):
        if not d.get(f) and o.get(f):
            d[f] = o[f]
    if not d.get("authors") and o.get("authors"):
        d["authors"] = o["authors"]
    if not d.get("is_preprint") and o.get("is_preprint"):
        d["is_preprint"] = True
    return PaperMetadata(**d)


# --- orchestration (pure; fetcher-injected) -------------------------------------------


def enrich_from_ids(
    ids: CandidateIds,
    *,
    openalex_fetch: pubmed.Fetcher,
    crossref_fetch: pubmed.Fetcher,
    pubmed_fetch: pubmed.Fetcher,
    cfg: pubmed.NcbiConfig | None = None,
    email: str | None = None,
    title_min_sim: float = 0.6,
) -> tuple[PaperMetadata | None, dict]:
    """Resolve candidate IDs to a record via the ordered, fail-soft chain.

    DOI path: OpenAlex primary, then CrossRef and PubMed used to *fill gaps* (cross-check),
    stopping once the record is complete. Title path (no DOI): OpenAlex then PubMed search,
    ranked by title similarity. ``degraded`` is True only when a consulted source raised a
    real failure (not a clean 404 / no-match). Never raises — a lookup must not break intake.
    """
    tried: list[str] = []
    degraded = False

    def _call(fn):
        nonlocal degraded
        try:
            return fn()
        except HTTPError as e:
            if e.code == 404:  # clean "not in this index" — not a degradation
                return None
            degraded = True
            return None
        except (OSError, ValueError, ET.ParseError):  # network / JSON / XML failure
            degraded = True
            return None

    # --- DOI path (deterministic) ---
    if ids.doi:
        primary: PaperMetadata | None = None
        doi_sources = [
            ("openalex", lambda: openalex_by_doi(ids.doi, fetch=openalex_fetch, email=email)),
            ("crossref", lambda: crossref_by_doi(ids.doi, fetch=crossref_fetch, email=email)),
            ("pubmed", lambda: pubmed_by_doi(ids.doi, fetch=pubmed_fetch, cfg=cfg)),
        ]
        for name, fn in doi_sources:
            tried.append(name)
            rec = _call(fn)
            if rec is None:
                continue
            primary = rec if primary is None else _merge(primary, rec)
            if _complete(primary):
                break
        # PMID back-fill: OpenAlex often satisfies _complete() without carrying a PMID, so the loop
        # stops before PubMed. PMID is a distinct identifier users expect — fetch it directly from
        # PubMed-by-DOI when missing (fail-soft; only if PubMed wasn't already consulted).
        if primary is not None and not primary.pmid and "pubmed" not in tried:
            tried.append("pubmed")
            pm_rec = _call(lambda: pubmed_by_doi(ids.doi, fetch=pubmed_fetch, cfg=cfg))
            if pm_rec is not None:
                primary = _merge(primary, pm_rec)
        if primary is not None:
            primary.matched_by = "doi"
            primary.confidence = 0.97
            return primary, {"matched_by": "doi", "source": primary.source, "tried": tried,
                             "degraded": degraded, "doi": ids.doi}

    # --- title path (ranked fallback) ---
    if ids.title:
        title_sources = [
            ("openalex", lambda: openalex_search(ids.title, fetch=openalex_fetch, email=email)),
            ("pubmed", lambda: pubmed_search(ids.title, fetch=pubmed_fetch, cfg=cfg)),
        ]
        best: PaperMetadata | None = None
        best_sim = 0.0
        for name, fn in title_sources:
            tried.append(name)
            for cand in (_call(fn) or []):
                sim = _title_sim(ids.title, cand.title)
                if sim > best_sim:
                    best, best_sim = cand, sim
            if best is not None and best_sim >= title_min_sim:
                break
        if best is not None and best_sim >= title_min_sim:
            best.matched_by = "title"
            best.confidence = round(best_sim, 2)
            return best, {"matched_by": "title", "source": best.source, "tried": tried,
                          "degraded": degraded, "title_similarity": round(best_sim, 3)}

    return None, {"matched_by": None, "source": None, "tried": tried, "degraded": degraded}


def enrich_pdf(
    pdf_path: str | pathlib.Path,
    *,
    openalex_fetch: pubmed.Fetcher,
    crossref_fetch: pubmed.Fetcher,
    pubmed_fetch: pubmed.Fetcher,
    cfg: pubmed.NcbiConfig | None = None,
    email: str | None = None,
) -> tuple[PaperMetadata | None, dict]:
    """Extract candidate IDs from a PDF, then resolve them (the full local chain)."""
    ids = extract_candidate_ids(pdf_path)
    rec, prov = enrich_from_ids(
        ids, openalex_fetch=openalex_fetch, crossref_fetch=crossref_fetch,
        pubmed_fetch=pubmed_fetch, cfg=cfg, email=email,
    )
    prov["candidates"] = ids.model_dump()
    return rec, prov


# --- XMP write-back (pikepdf, optional) -----------------------------------------------


def write_xmp(pdf_path: str | pathlib.Path, record: PaperMetadata,
              out_path: str | pathlib.Path) -> None:
    """Embed the resolved record into a copy of the PDF as XMP (Dublin Core + PRISM).

    The "better than Papers" differentiator (Papers matched but did not write metadata back).
    Requires pikepdf (the optional ``pdf`` extra); raises one actionable error if absent.
    """
    try:
        import pikepdf
    except ImportError as exc:
        raise RuntimeError(
            "XMP write-back needs 'pikepdf', in the optional 'pdf' extra. Install: uv sync --extra pdf"
        ) from exc
    with pikepdf.open(str(pdf_path)) as pdf:
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            if record.title:
                meta["dc:title"] = record.title
            if record.authors:
                meta["dc:creator"] = list(record.authors)
            if record.doi:
                meta["prism:doi"] = record.doi
                meta["dc:identifier"] = f"doi:{record.doi}"
            if record.venue:
                meta["prism:publicationName"] = record.venue
            if record.year:
                meta["prism:coverDisplayDate"] = str(record.year)
        pdf.save(str(out_path))


# --- filename suggestion / auto-rename (the reference-manager "auto-file" step) --------

_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _clean_token(s: str | None) -> str:
    """Strip filesystem-illegal characters and collapse whitespace."""
    return re.sub(r"\s+", " ", _ILLEGAL.sub("", s or "")).strip()


def _surname(authors: list[str]) -> str:
    """The first author's surname, handling both 'Given Family' (OpenAlex/CrossRef) and
    'Family Initials' (PubMed, e.g. 'Roe JA')."""
    if not authors:
        return "Unknown"
    parts = (authors[0] or "").split()
    if not parts:
        return "Unknown"
    last = parts[-1]
    # PubMed 'Surname Initials' — the trailing token is short all-caps initials.
    if len(parts) >= 2 and len(last) <= 3 and last.isupper():
        return _clean_token(parts[0]) or "Unknown"
    return _clean_token(parts[-1]) or "Unknown"


def _short_title(title: str | None, words: int = 8) -> str:
    return _clean_token(" ".join((title or "").split()[:words]))


def suggest_filename(record: PaperMetadata, *, template: str = "{author}_{year}_{venue}",
                     ext: str = ".pdf", max_len: int = 180) -> str:
    """A reference-manager-style filename from a resolved record (e.g. ``Roe_2021_Nature.pdf``).

    Tokens: ``{author}`` (first-author surname), ``{year}``, ``{venue}`` (journal, falling back
    to a short title — the owner's "Journal/Title"), ``{journal}``, ``{title}`` (short),
    ``{doi}``. The result is sanitized for every OS, length-capped, and always non-empty.
    """
    venue = _clean_token(record.venue) or _short_title(record.title) or "Untitled"
    fields = {
        "author": _surname(record.authors),
        "year": str(record.year) if record.year else "n.d.",
        "venue": venue,
        "journal": _clean_token(record.venue) or "Untitled",
        "title": _short_title(record.title) or "Untitled",
        "doi": _clean_token(record.doi),
    }
    name = template
    for key, value in fields.items():
        name = name.replace("{" + key + "}", value)
    name = _ILLEGAL.sub("", name)
    name = re.sub(r"\s+", " ", name).strip().strip("._ ")[:max_len].rstrip("._ ")
    return (name or "paper") + ext


def apply_rename(pdf_path: str | pathlib.Path, record: PaperMetadata, *,
                 dest_dir: str | pathlib.Path | None = None, template: str = "{author}_{year}_{venue}",
                 move: bool = False) -> pathlib.Path:
    """Copy (default) or move ``pdf_path`` to a metadata-derived filename; returns the new path.

    Non-destructive by default (copy) so a wrong match never loses the original — pass
    ``move=True`` to rename in place. Filename collisions get a ``(2)``, ``(3)``... suffix.
    """
    import shutil

    src = pathlib.Path(pdf_path)
    ext = src.suffix or ".pdf"
    target_dir = pathlib.Path(dest_dir) if dest_dir else src.parent
    base = suggest_filename(record, template=template, ext="")
    dest = target_dir / f"{base}{ext}"
    n = 2
    while dest.exists() and dest.resolve() != src.resolve():
        dest = target_dir / f"{base} ({n}){ext}"
        n += 1
    target_dir.mkdir(parents=True, exist_ok=True)
    (shutil.move if move else shutil.copy2)(str(src), str(dest))
    return dest


# --- env-wired glue (cache + degrade) — what the endpoint calls -----------------------

_CFG = pubmed.NcbiConfig.from_env()
_PUBMED_FETCH = pubmed.default_fetcher(_CFG)
# OpenAlex permits 10 req/s with a mailto; CrossRef's polite pool is generous. One shared
# throttled JSON fetcher just under that, with the descriptive UA the seam already sends.
_JSON_FETCH = pubmed.ThrottledFetcher(min_interval=0.12)
_EMAIL = settings.openalex_email or settings.ncbi_email or None
_CACHE = JsonCache(
    settings.paper_metadata_cache
    or (pathlib.Path(tempfile.gettempdir()) / "selom-paper-metadata-cache.json")
)


def metadata_by_doi(doi, *, openalex_fetch=None, crossref_fetch=None, pubmed_fetch=None,
                    cache=None, cfg=None, email=None) -> dict:
    """Resolve a DOI to an enriched record, cached + degrade-safe (what GET /papers/metadata/by-doi calls)."""
    clean = _clean_doi(doi)
    if not clean:
        return {"record": None, "provenance": {"matched_by": None, "source": None, "tried": [],
                                               "degraded": False}, "degraded": False}
    cache = cache or _CACHE
    key = f"doi:{clean.lower()}"
    if cache.has(key):
        cached = cache.get(key) or {}
        return {**cached, "degraded": False}
    rec, prov = enrich_from_ids(
        CandidateIds(doi=clean),
        openalex_fetch=openalex_fetch or _JSON_FETCH,
        crossref_fetch=crossref_fetch or _JSON_FETCH,
        pubmed_fetch=pubmed_fetch or _PUBMED_FETCH,
        cfg=cfg or _CFG,
        email=email if email is not None else _EMAIL,
    )
    payload = {"record": rec.model_dump() if rec else None, "provenance": prov}
    if not prov.get("degraded"):  # don't pin a transient failure in the cache
        cache.set(key, payload)
    return {**payload, "degraded": bool(prov.get("degraded"))}


def metadata_for_pdf(pdf_path, *, openalex_fetch=None, crossref_fetch=None, pubmed_fetch=None,
                     cfg=None, email=None) -> dict:
    """Resolve a dropped PDF to an enriched record — the upload counterpart of
    :func:`metadata_by_doi` (what ``POST /papers/extract`` calls). Extracts candidate IDs from the
    PDF (XMP / DOI regex / filename) then resolves them via the fail-soft OpenAlex→CrossRef→PubMed
    chain. Degrade-safe: a missing record / network failure returns ``record: None`` with the
    provenance flagging it, never raising."""
    rec, prov = enrich_pdf(
        pdf_path,
        openalex_fetch=openalex_fetch or _JSON_FETCH,
        crossref_fetch=crossref_fetch or _JSON_FETCH,
        pubmed_fetch=pubmed_fetch or _PUBMED_FETCH,
        cfg=cfg or _CFG,
        email=email if email is not None else _EMAIL,
    )
    return {"record": rec.model_dump() if rec else None, "provenance": prov,
            "degraded": bool(prov.get("degraded"))}

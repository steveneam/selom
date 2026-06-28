from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import paper_metadata
from litsynth import SkillRunRef, compose_methods
from litsynth import lookup as citations_lookup

router = APIRouter()

_CITATION_SOURCES = ("both", "pubmed", "biorxiv")


class ComposeMethodsRequest(BaseModel):
    runs: list[SkillRunRef]            # the analysis story, in run order (or with explicit `order`)
    modality: str = ""                 # frames the lead sentence (scrna|bulk|proteomics|…)
    dataset: str | None = None         # optional dataset descriptor; leads the intro when given


@router.post("/methods/compose")
def compose_methods_endpoint(req: ComposeMethodsRequest):
    # lit-synthesizer Phase A: stitch an ordered sequence of skill runs into ONE publication
    # Methods section + deduped citations (deterministic, offline, no LLM). Promotes the
    # per-figure methods engine (used at /skills/{id}/run) to the project/story level without
    # touching that response shape. See docs/lit-synthesizer-scope.md.
    if not req.runs:
        raise HTTPException(status_code=400, detail="runs is required")
    try:
        section = compose_methods(req.runs, req.modality, req.dataset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return section.model_dump()


@router.get("/citations/search")
def citations_search(q: str = "", source: str = "both", max_results: int = 20, min_year: int | None = None):
    # lit-synthesizer Phase B/C: topical PubMed lookup (NCBI E-utilities, cached, self-throttled).
    # Advisory tier-3 (off by default in the synthesizer); degrades to [] + degraded=True on any
    # network/parse failure — a lookup must never break the caller. bioRxiv has no free-text search
    # API (Phase C), so source=biorxiv returns []. See docs/lit-synthesizer-scope.md.
    if source not in _CITATION_SOURCES:
        raise HTTPException(status_code=400, detail=f"source must be one of {_CITATION_SOURCES}")
    if not q.strip():
        return {"results": [], "degraded": False}
    return citations_lookup.search_citations(q, source=source, max_results=max_results, min_year=min_year)


@router.get("/citations/by-doi")
def citations_by_doi(doi: str = "", source: str = "both"):
    # Deterministic DOI -> bibliographic Citation, cached. source=both tries PubMed then
    # bioRxiv/medRxiv (the latter also captures the preprint's per-record license). Phase C.
    if source not in _CITATION_SOURCES:
        raise HTTPException(status_code=400, detail=f"source must be one of {_CITATION_SOURCES}")
    if not doi.strip():
        raise HTTPException(status_code=400, detail="doi is required")
    return citations_lookup.citation_by_doi(doi, source=source)


@router.get("/papers/metadata/by-doi")
def paper_metadata_by_doi(doi: str = ""):
    # Article-Matcher enrichment (external-tools study §4 BUILD #2): a DOI -> resolved
    # bibliographic record via the fail-soft chain OpenAlex(CC0) primary -> CrossRef cross-check
    # -> PubMed fill, cached + degrade-safe (a lookup never breaks the caller). The full
    # PDF -> candidate-IDs -> record path lives in paper_metadata.enrich_pdf (local/dogfood).
    if not doi.strip():
        raise HTTPException(status_code=400, detail="doi is required")
    return paper_metadata.metadata_by_doi(doi)

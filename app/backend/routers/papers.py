from fastapi import APIRouter, HTTPException

import papers_api
from litsynth import from_ledger as ledger_methods
from litsynth import legends_from_ledger as ledger_legends

router = APIRouter()


@router.get("/papers")
def list_papers():
    # Read-only Reproduction view (spec §Endpoints; R5 data layer). The 3-paper
    # reproducibility spectrum (RPGRIP1 63 / JEV 86 / Hani 96) the FE index renders.
    return {"papers": papers_api.list_papers()}


@router.get("/papers/{slug}")
def get_paper(slug: str):
    # The full driven ledger: paper + panels (+golden) + validations (golden-vs-computed
    # verdict/blame) + the derived scorecard (Reproducibility Score). One fetch feeds the
    # whole detail view (heatmap + dual-axis score + golden-vs-computed table).
    if slug not in papers_api.SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown paper '{slug}'")
    return papers_api.driven_ledger(slug).model_dump()


@router.get("/papers/{slug}/scorecard")
def get_scorecard(slug: str):
    # Just the derived scorecard (panel_scores + the weighted paper rollup + findings).
    if slug not in papers_api.SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown paper '{slug}'")
    return papers_api.driven_ledger(slug).scorecard.model_dump()


@router.get("/papers/{slug}/methods")
def get_paper_methods(slug: str, modality: str = ""):
    # lit-synthesizer Phase D: turn this paper's driven ledger into ONE publication Methods
    # section + deduped citations (deterministic, offline). Walks the in-scope analysis panels
    # in figure order, reusing each skill's existing methods prose. `modality` overrides the
    # ledger's declared paper.modality for the intro framing. See docs/lit-synthesizer-scope.md.
    if slug not in papers_api.SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown paper '{slug}'")
    ledger = papers_api.driven_ledger(slug)
    try:
        section = ledger_methods.compose_ledger_methods(ledger, modality=(modality or None))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return section.model_dump()


@router.get("/papers/{slug}/legends")
def get_paper_legends(slug: str):
    # The legend twin of /methods: this paper's driven ledger -> one paste-ready figure caption
    # per in-scope analysis panel (deterministic, offline), enriched with each panel's reproduced
    # figure/table when present. See docs/workspace-library/spec.md Sec 11.
    if slug not in papers_api.SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown paper '{slug}'")
    ledger = papers_api.driven_ledger(slug)
    try:
        items = ledger_legends.compose_ledger_legends(ledger)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"slug": slug, "legends": [fl.model_dump() for fl in items]}

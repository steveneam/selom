from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gene_sets import library as gene_sets

router = APIRouter()


class CompileRequest(BaseModel):
    set_ids: list[str]
    op: str = "union"            # union | intersect
    name: str | None = None


@router.get("/gene-sets")
def gene_sets_list(q: str = "", source: str | None = None, limit: int = 50):
    # Gene-set builder Phase A (DECISIONS #11): a searchable, license-clean catalog over
    # the corpus Selom owns or that is open (GO · WikiPathways · curated). The FE "Gene
    # Sets" surface reads this; cards omit the full member list (fetched per set below).
    return {"sources": gene_sets.list_sources(), "results": gene_sets.search(q, source, limit)}


@router.post("/gene-sets/compile")
def gene_sets_compile(req: CompileRequest):
    # Gene-set builder Phase B: union/intersect several catalog sets, HGNC-normalize +
    # dedup, return the compiled gene list + provenance (sources, licenses, op, stats).
    if not req.set_ids:
        raise HTTPException(status_code=400, detail="set_ids is required")
    result = gene_sets.compile_sets(req.set_ids, req.op)
    if req.name:
        result["name"] = req.name
    return result


@router.get("/gene-sets/{set_id}")
def gene_set_detail(set_id: str):
    s = gene_sets.get_set(set_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"unknown gene set '{set_id}'")
    return s                                            # card + member symbols + provenance

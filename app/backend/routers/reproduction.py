import asyncio
import json
import pathlib
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import paper_metadata
from extract import routing
from config import settings
from jobs.store import TERMINAL

from routers._run import _resolve_data_map, _save_capped, _save_upload

router = APIRouter()


@router.post("/papers/{paper_id}/reproduce")
async def reproduce_paper(
    paper_id: str,
    main: UploadFile,
    supplements: list[UploadFile] = File(default=[]),
    design: UploadFile | None = File(None),
    data_map: str = Form(""),
):
    # Live-reproduction drive (docs/reproduction-engine/live-reproduction-spec.md §5): the user's
    # paper PDF + its supplements -> a graded two-axis ledger. Bytes are saved to a per-run temp dir
    # (cleaned after the inline drive), submitted as a reproduce run (reproduction_runs.start_run),
    # which orchestrates the matched skills over the supplements. Inline -> already terminal on
    # return; the FE then GETs /reproduction-runs/{run_id} to fill the Score stage.
    # `data_map` (JSON {panel_key: filename}) is the per-panel data picker (Slice 2 R4): the FE points
    # a `data_unmatched` panel at a chosen supplement by filename; we resolve it to that file's saved
    # path so the matcher's override (which wins over the auto-heuristic) feeds the picked file.
    import reproduction_runs

    max_bytes = settings.max_upload_mb * 1024 * 1024
    run_dir = tempfile.mkdtemp(prefix="selom-repro-")
    try:
        main_path = await _save_capped(run_dir, main, max_bytes)
        supp_paths: list[str] = []
        path_by_name: dict[str, str] = {}
        for s in supplements:
            p = await _save_capped(run_dir, s, max_bytes)
            supp_paths.append(p)
            path_by_name[pathlib.Path(s.filename or "").name] = p
        params = None
        if design is not None:  # a design sheet (sample->condition) threads to the DE skills
            params = {"_design_path": await _save_capped(run_dir, design, max_bytes)}
        resolved_map = _resolve_data_map(data_map, path_by_name)
        rec = reproduction_runs.start_run(main_path, supp_paths, paper_id=paper_id, params=params,
                                          data_map=resolved_map)
        return reproduction_runs.public(rec, light=True)
    except ValueError as exc:  # the size cap
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


@router.post("/papers/{paper_id}/assess-data")
async def assess_paper_data(
    paper_id: str,
    main: UploadFile | None = File(None),
    supplements: list[UploadFile] = File(default=[]),
    skills: str = Form(""),
):
    # Pre-run data-fit check (Slice 2): classify + score each dropped supplement against the
    # analyses this paper routes to — so the user sees a confidence band (Confident / Not a fit /
    # …) BEFORE clicking Run and can swap a wrong/dirty file. NO skills execute (cheap: ingest +
    # route + score). The same FileFitReport shape the Score stage shows after a run, so the FE
    # renders one panel for both. ``skills`` (csv of skill ids) lets the FE skip re-routing.
    from engine.compat import report_files
    from engine.match import merge_ledger, tabular_paths
    from extract.ingest import ingest_paper

    max_bytes = settings.max_upload_mb * 1024 * 1024
    run_dir = tempfile.mkdtemp(prefix="selom-assess-")
    try:
        supp_paths = [await _save_capped(run_dir, s, max_bytes) for s in supplements]
        if not supp_paths:
            return {"paper_id": paper_id, "n_files": 0, "data_fits": []}
        skill_ids = [s for s in (skills.split(",") if skills else []) if s.strip()]
        tabular = supp_paths
        if main is not None:  # route the paper → the in-scope panel skills to score against
            main_path = await _save_capped(run_dir, main, max_bytes)
            bundle = ingest_paper(main_path, supp_paths, paper_id=paper_id)
            tabular = tabular_paths(bundle)
            if not skill_ids:
                ledger = merge_ledger(bundle, paper_id)
                import reproduction as R

                skill_ids = [p.skill_id for p in ledger.panels
                             if p.skill_id and p.scope not in R.OUT_OF_SCOPE_SCOPES]
        fits = report_files(tabular, skill_ids)
        return {"paper_id": paper_id, "n_files": len(fits),
                "data_fits": [f.model_dump() for f in fits]}
    except ValueError as exc:  # the size cap
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


@router.get("/reproduction-runs/{run_id}")
def get_reproduction_run(run_id: str):
    # The run's state; on `succeeded` the driven Ledger + scorecard (same shape as GET /papers/{slug})
    # so the Score stage reuses the showcase heatmap / dual-axis score / golden-vs-computed.
    import reproduction_runs

    rec = reproduction_runs.get_run(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown reproduction run")
    return reproduction_runs.public(rec)


@router.get("/reproduction-runs/{run_id}/events")
async def reproduction_run_events(run_id: str):
    # SSE progress for the drive. Inline runs are already terminal, so this resolves in one event;
    # the arq path (deferred) would stream the per-panel transitions.
    import reproduction_runs

    async def stream():
        for _ in range(600):  # ~5 min ceiling at 0.5s/tick
            rec = reproduction_runs.get_run(run_id)
            if rec is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'unknown run'})}\n\n"
                return
            yield f"data: {json.dumps(reproduction_runs.public(rec, light=True))}\n\n"
            if rec.status in TERMINAL:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


class RouteRequest(BaseModel):
    text: str
    paper_id: str = ""


@router.post("/papers/route")
def route_paper(req: RouteRequest):
    # Skill Keyword Index (docs/skill-keyword-index/spec.md): route a dropped paper's text to a
    # per-figure feasibility map — each figure → a Selom skill or an out-of-scope modality (+reason)
    # — deterministically, no LLM on the path. Internal dogfood surface (engine D12 posture).
    return routing.route_text(req.text, paper_id=req.paper_id).model_dump()


@router.post("/papers/extract")
async def extract_paper(file: UploadFile):
    # Skill-Match intake step: drop a paper PDF -> its text layer (for the deterministic router) +
    # an enriched bibliographic record (paper_metadata, degrade-safe OpenAlex->CrossRef->PubMed).
    # The FE shows the metadata immediately, then routes the returned text via POST /papers/route on
    # "Run". Library-only; no LLM. The temp PDF is removed after extraction.
    import papers

    path = _save_upload(file)
    try:
        text = papers.extract_text(path)
        meta = paper_metadata.metadata_for_pdf(path)
        return {"text": text, "filename": file.filename or "",
                "metadata": meta["record"], "provenance": meta["provenance"]}
    finally:
        pathlib.Path(path).unlink(missing_ok=True)

import asyncio
import json
import pathlib
import shutil
import tempfile

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import export
import guardrails
import methods
import papers_api
import provenance
from extract import chart_intake
from gene_sets import library as gene_sets
from litsynth import SkillRunRef, compose_methods
from litsynth import from_ledger as ledger_methods
from litsynth import lookup as citations_lookup
from jobs.queue import get_job, result_store, submit
from jobs.store import TERMINAL
from skills import styles, theme
from skills.contract import load_skill, run_skill_with_table
from skills.registry import list_catalog, list_skill_ids

app = FastAPI(title="Selom API")

# ★D bridge: serve the staged X3 panel thumbnails (repro_assets) as read-only static files at
# /repro-assets/{slug}/{panel_key}.png. Presentational only — never a score input. Mounted only
# when the tree exists so a fresh clone without staged assets still boots.
_REPRO_ASSETS = pathlib.Path(__file__).resolve().parent / "repro-assets"
if _REPRO_ASSETS.is_dir():
    app.mount("/repro-assets", StaticFiles(directory=str(_REPRO_ASSETS)), name="repro-assets")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/skills")
def list_skills():
    # Live Skill-Store registry: every on-disk skill as a SkillCatalogEntry. The FE
    # Store reads this and drops its hard-coded Verified seed (B3 — registry-driven).
    return list_catalog()


@app.get("/skills/{skill_id}")
def describe(skill_id: str):
    return load_skill(skill_id).model_dump()        # registry-driven UI reads this


@app.get("/gene-sets")
def gene_sets_list(q: str = "", source: str | None = None, limit: int = 50):
    # Gene-set builder Phase A (DECISIONS #11): a searchable, license-clean catalog over
    # the corpus Selom owns or that is open (GO · WikiPathways · curated). The FE "Gene
    # Sets" surface reads this; cards omit the full member list (fetched per set below).
    return {"sources": gene_sets.list_sources(), "results": gene_sets.search(q, source, limit)}


class CompileRequest(BaseModel):
    set_ids: list[str]
    op: str = "union"            # union | intersect
    name: str | None = None


@app.post("/gene-sets/compile")
def gene_sets_compile(req: CompileRequest):
    # Gene-set builder Phase B: union/intersect several catalog sets, HGNC-normalize +
    # dedup, return the compiled gene list + provenance (sources, licenses, op, stats).
    if not req.set_ids:
        raise HTTPException(status_code=400, detail="set_ids is required")
    result = gene_sets.compile_sets(req.set_ids, req.op)
    if req.name:
        result["name"] = req.name
    return result


@app.get("/gene-sets/{set_id}")
def gene_set_detail(set_id: str):
    s = gene_sets.get_set(set_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"unknown gene set '{set_id}'")
    return s                                            # card + member symbols + provenance


@app.get("/papers")
def list_papers():
    # Read-only Reproduction view (spec §Endpoints; R5 data layer). The 3-paper
    # reproducibility spectrum (RPGRIP1 63 / JEV 86 / Hani 96) the FE index renders.
    return {"papers": papers_api.list_papers()}


@app.get("/papers/{slug}")
def get_paper(slug: str):
    # The full driven ledger: paper + panels (+golden) + validations (golden-vs-computed
    # verdict/blame) + the derived scorecard (Reproducibility Score). One fetch feeds the
    # whole detail view (heatmap + dual-axis score + golden-vs-computed table).
    if slug not in papers_api.SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown paper '{slug}'")
    return papers_api.driven_ledger(slug).model_dump()


@app.get("/papers/{slug}/scorecard")
def get_scorecard(slug: str):
    # Just the derived scorecard (panel_scores + the weighted paper rollup + findings).
    if slug not in papers_api.SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown paper '{slug}'")
    return papers_api.driven_ledger(slug).scorecard.model_dump()


@app.get("/papers/{slug}/methods")
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


def _save_upload(matrix: UploadFile) -> str:
    # Preserve the upload's extension so skills can tell .h5ad (scRNA) from .csv (bulk).
    suffix = pathlib.Path(matrix.filename or "").suffix or ".h5ad"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        shutil.copyfileobj(matrix.file, f)
        return f.name


@app.post("/skills/{skill_id}/run")
async def run(skill_id: str, request: Request, matrix: UploadFile, design: UploadFile | None = File(None)):
    # Synchronous one-shot — the proven fast path for light skills (B1). Heavy skills
    # should use POST /skills/{id}/jobs (below). Tuning params arrive as the query
    # string; the contract fills skill defaults and each runner coerces types.
    # An optional `design` sheet (sample->condition/time) feeds bulk + time-course DE;
    # it is threaded as a reserved param and kept out of the provenance record.
    path = _save_upload(matrix)
    params = dict(request.query_params)
    design_path = _save_upload(design) if design is not None else None
    if design_path:
        params["_design_path"] = design_path
    spec = load_skill(skill_id)
    try:
        figure, table = run_skill_with_table(skill_id, path, params)
        # B4 publish-confidence: every figure ships with its reproducibility bundle +
        # auto methods-text. Pillar 1 adds the Statistics `table` (None for purely-visual
        # skills). Additive — the FE still reads `.figure`.
        return {
            "figure": figure,                            # Plotly JSON -> frontend
            "provenance": provenance.build(spec, path, matrix.filename, params),
            "methods": methods.build(spec, params),
            "guardrails": guardrails.build(spec, path, params),
            "table": table,                              # Statistics node (Pillar 1) | None
        }
    finally:
        if design_path:
            pathlib.Path(design_path).unlink(missing_ok=True)


@app.post("/extract/chart")
async def extract_chart(figure: UploadFile, request: Request):
    # ClawBio data-extractor (X4), end-to-end: drop a bar/line/scatter panel image + an axis
    # calibration -> the recovered series as an editable Statistics table + an editable Plotly
    # figure (same artifacts a skill emits, so it lands in the editor). Calibration-first +
    # vision-grade (confidence 0.7, source: extracted) — never text-exact (sub-spec E4/E6).
    raw = await figure.read()
    q = request.query_params
    try:
        calib = chart_intake.calibration_from_params(q)
        labels = [s for s in q.get("labels", "").split(",") if s] or None
        result = chart_intake.extract_chart(
            raw,
            calib,
            q.get("form", ""),
            labels=labels,
            color=chart_intake.color_from_param(q.get("color")),
            tol=int(q.get("tol", 40)),
            thresh=int(q.get("thresh", 200)),
            step=int(q.get("step", 1)),
            min_size=int(q.get("min_size", 3)),
            series_name=q.get("series_name", "value"),
            x_name=q.get("x_name", "x"),
            y_name=q.get("y_name", "y"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    series = result["series"]
    return {
        "series": series.model_dump(),       # form + values/points + confidence + note
        "table": result["table"],            # editable Statistics table (S2.1)
        "figure": result["figure"],          # editable Plotly {data, layout}
        "confidence": series.confidence,     # vision-grade; gate before trusting as golden (E4)
        "note": series.note,
    }


class ComposeMethodsRequest(BaseModel):
    runs: list[SkillRunRef]            # the analysis story, in run order (or with explicit `order`)
    modality: str = ""                 # frames the lead sentence (scrna|bulk|proteomics|…)
    dataset: str | None = None         # optional dataset descriptor; leads the intro when given


@app.post("/methods/compose")
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


_CITATION_SOURCES = ("both", "pubmed", "biorxiv")


@app.get("/citations/search")
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


@app.get("/citations/by-doi")
def citations_by_doi(doi: str = "", source: str = "both"):
    # Deterministic DOI -> bibliographic Citation, cached. source=both tries PubMed then
    # bioRxiv/medRxiv (the latter also captures the preprint's per-record license). Phase C.
    if source not in _CITATION_SOURCES:
        raise HTTPException(status_code=400, detail=f"source must be one of {_CITATION_SOURCES}")
    if not doi.strip():
        raise HTTPException(status_code=400, detail="doi is required")
    return citations_lookup.citation_by_doi(doi, source=source)


@app.post("/skills/{skill_id}/jobs")
async def submit_job(skill_id: str, request: Request, matrix: UploadFile):
    # Async job path (B3): enqueue a run, return a job handle the FE polls. In inline
    # mode the job completes before this returns; arq mode runs it off-request.
    if skill_id not in set(list_skill_ids()):
        raise HTTPException(status_code=404, detail=f"unknown skill '{skill_id}'")
    path = _save_upload(matrix)
    params = dict(request.query_params)
    job = submit(skill_id, path, params, matrix.filename)
    return job.public()


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.public()


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    # Server-Sent Events: emit current state, then poll until terminal. Inline jobs are
    # already terminal, so this resolves in one event; arq jobs stream the transitions.
    async def stream():
        for _ in range(600):  # ~5 min ceiling at 0.5s/tick
            job = get_job(job_id)
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'unknown job'})}\n\n"
                return
            yield f"data: {json.dumps(job.public())}\n\n"
            if job.status in TERMINAL:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    bundle = result_store.get(job_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="result not available")
    return bundle                                     # {figure, provenance, methods} — same shape as /run


@app.get("/figures/export/presets")
def export_presets():
    # Journal-preset catalog (B4 journal export): the FE export menu renders from
    # this so sizes live in one place (export.PRESETS).
    return {"presets": export.list_presets()}


class ExportRequest(BaseModel):
    figure: dict                       # Plotly {data, layout} spec — the edited figure
    format: str = "png"                # png | svg | pdf
    preset: str | None = None          # journal size preset id (export.PRESETS)
    width: int | None = None           # explicit px overrides (preset wins if both unset)
    height: int | None = None
    filename: str | None = None        # download name (extension is forced to match format)
    # Optional headless style skin. The WYSIWYG FE path omits these (the on-screen
    # spec is already styled); they let a caller export a figure in a journal style
    # without going through the editor. theme.apply needs the skill_id for figure-type polish.
    style: str | None = None
    skill_id: str | None = None


_EXPORT_MEDIA = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf"}


@app.post("/figures/export")
async def export_figure(req: ExportRequest):
    # Render the edited figure to a publication-ready file via Kaleido + system
    # Chrome (no container at runtime). Off-thread so the sync render doesn't block
    # the event loop; a kaleido-less / Chrome-less install degrades to a clean 503.
    fmt = req.format.lower()
    if fmt not in export.FORMATS:
        raise HTTPException(status_code=400, detail=f"unsupported format '{req.format}'")
    if not isinstance(req.figure, dict) or "data" not in req.figure:
        raise HTTPException(status_code=400, detail="figure must be a Plotly spec with a data array")
    figure = theme.apply(req.figure, req.skill_id or "", req.style) if req.style else req.figure
    try:
        data = await asyncio.to_thread(
            export.render, figure, fmt, preset=req.preset, width=req.width, height=req.height
        )
    except export.ExportUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    name = (req.filename or "selom-figure").rsplit(".", 1)[0] or "selom-figure"
    headers = {"Content-Disposition": f'attachment; filename="{name}.{fmt}"'}
    return Response(content=data, media_type=_EXPORT_MEDIA[fmt], headers=headers)


@app.get("/figures/styles")
def figure_styles():
    # Journal style catalog (journal-styles v1): the FE style picker renders from this.
    return {"styles": styles.list_styles()}


class StyleApplyRequest(BaseModel):
    figure: dict                       # Plotly {data, layout} spec to restyle
    skill_id: str | None = None        # drives figure-type polish (volcano/embedding/…)
    style: str = styles.DEFAULT_STYLE  # target style id (export.styles.STYLES)


@app.post("/figures/style/apply")
def apply_figure_style(req: StyleApplyRequest):
    # Live editor preview: re-skin a figure in a journal style and return the styled
    # spec (one Python source of the transform — the FE commits it as an undoable edit).
    if not isinstance(req.figure, dict) or "data" not in req.figure:
        raise HTTPException(status_code=400, detail="figure must be a Plotly spec with a data array")
    return {"figure": theme.apply(req.figure, req.skill_id or "", req.style)}

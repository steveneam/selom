import asyncio
import hashlib
import json
import pathlib
import shutil
import tempfile
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import export
import guardrails
import legends
import methods
import paper_metadata
import papers_api
import provenance
from config import settings
from extract import chart_intake
from extract import routing
from gene_sets import library as gene_sets
from litsynth import SkillRunRef, compose_methods
from litsynth import from_ledger as ledger_methods
from litsynth import legends_from_ledger as ledger_legends
from litsynth import lookup as citations_lookup
from auth import AuthContext, require_user
from jobs.queue import get_job, result_store, submit
from jobs.store import TERMINAL
from storage.object_store import get_object_store
from uploads import QuotaExceeded, get_upload_repo, materialize_dataset
from skills import styles, theme
from skills._engine import to_bool
from skills.contract import (
    load_skill,
    run_bundle_with_table,
    run_skill_with_table,
    validate_param_ranges,
)
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


@app.get("/papers/{slug}/legends")
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


async def _save_capped(run_dir: str, upload: UploadFile, max_bytes: int) -> str:
    # Save one multipart upload into the per-run temp dir, rejecting oversized files (413 upstream).
    # Each file lands in its OWN unique subdir so its ORIGINAL name (and extension) is preserved
    # verbatim: the suffix-based kind inference in extract.ingest still works, AND the name the engine
    # reports back (the data-fit filenames + the per-panel picker round-trip) matches what the user
    # dropped — no uuid prefix to strip, so a picked filename resolves cleanly to its saved path.
    data = await upload.read()
    if len(data) > max_bytes:
        raise ValueError(
            f"'{upload.filename}' exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
    name = pathlib.Path(upload.filename or "file").name or "file"
    sub = pathlib.Path(run_dir) / uuid.uuid4().hex[:8]
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / name
    path.write_bytes(data)
    return str(path)


@app.post("/papers/{paper_id}/reproduce")
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


def _resolve_data_map(data_map: str, path_by_name: dict[str, str]) -> dict[str, str] | None:
    # Turn the picker's {panel_key: filename} (JSON) into {panel_key: saved_path}, keeping only
    # filenames that were actually uploaded this run. Malformed JSON / unknown filenames are dropped
    # silently (an honest no-op — the panel just stays auto-matched), never a 4xx.
    if not data_map:
        return None
    try:
        requested = json.loads(data_map)
    except (ValueError, TypeError):
        return None
    if not isinstance(requested, dict):
        return None
    resolved = {
        str(pk): path_by_name[pathlib.Path(str(fn)).name]
        for pk, fn in requested.items()
        if isinstance(fn, str) and pathlib.Path(fn).name in path_by_name
    }
    return resolved or None


@app.post("/papers/{paper_id}/assess-data")
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


@app.get("/reproduction-runs/{run_id}")
def get_reproduction_run(run_id: str):
    # The run's state; on `succeeded` the driven Ledger + scorecard (same shape as GET /papers/{slug})
    # so the Score stage reuses the showcase heatmap / dual-axis score / golden-vs-computed.
    import reproduction_runs

    rec = reproduction_runs.get_run(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown reproduction run")
    return reproduction_runs.public(rec)


@app.get("/reproduction-runs/{run_id}/events")
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


@app.post("/papers/route")
def route_paper(req: RouteRequest):
    # Skill Keyword Index (docs/skill-keyword-index/spec.md): route a dropped paper's text to a
    # per-figure feasibility map — each figure → a Selom skill or an out-of-scope modality (+reason)
    # — deterministically, no LLM on the path. Internal dogfood surface (engine D12 posture).
    return routing.route_text(req.text, paper_id=req.paper_id).model_dump()


@app.post("/papers/extract")
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


def _save_upload(matrix: UploadFile) -> str:
    # Save into a unique temp subdir under the upload's ORIGINAL name (mirrors _save_capped): the
    # extension is preserved so skills can tell .h5ad (scRNA) from .csv (bulk), AND the name the
    # engine derives back from the path matches what the user dropped — so an ERG figure's condition
    # label / sample id reads as the file stem, not a "tmpXXXX" temp name.
    name = pathlib.Path(matrix.filename or "").name or "data"
    if not pathlib.Path(name).suffix:
        name += ".h5ad"  # default extension so suffix-based kind inference still works
    path = pathlib.Path(tempfile.mkdtemp()) / name
    with open(path, "wb") as f:
        shutil.copyfileobj(matrix.file, f)
    return str(path)


def _inspect_for_run(path: str, filename: str | None):
    # The engine front door for an own-data run (P1c/P3a): ingest -> classify -> "is-my-data-clean?"
    # QC -> routing. Returns the classified `DataBundle`, its `QCReport`, and the `DataRouting`.
    # FAIL-SOFT by design (E4): any load/classify/QC error returns (None, None, None) so the proven
    # run path is NEVER broken by the guardrail — a file we can't inspect (e.g. a placeholder upload)
    # just runs as before, and a genuinely-bad payload still errors honestly inside the skill. We only
    # ever BLOCK when ingest + QC succeed AND surface a real block-severity flag.
    try:
        from engine import ingest_cached, route_data, run_qc

        bundle = ingest_cached(path)  # C3: reuse the parse if /data/inspect already saw these bytes
        bundle.qc = run_qc(bundle)
        bundle.source.filename = pathlib.Path(filename or "").name or bundle.source.filename
        return bundle, bundle.qc, route_data(bundle)
    except Exception:  # noqa: BLE001 — the guardrail is best-effort; never let it break a valid run
        return None, None, None


@app.post("/data/inspect")
async def inspect_data(matrix: UploadFile, sheet: str | None = None, hint: str | None = None,
                       profile: str | None = None):
    # Engine spine front door (P1, docs/engine-spine/spec.md): drop a data file -> its layered
    # data-type (format -> keywords -> modality), an "is-my-data-clean?" QC report, AND the dynamic
    # cleaning plan for that type. Product A's entry point; library-only, runs no analysis. The cheap
    # routing inventory in extract.ingest is the paper-side complement. `sheet` selects an xlsx sheet;
    # `hint` forces the modality (Kind); `profile` is the user's L3 data-type override (e.g. "erg").
    from engine import ALL_KINDS, ingest_cached, plan_cleaning, profile_data, route_profile, run_qc
    from engine import compat

    if hint is not None and hint not in ALL_KINDS:
        raise HTTPException(status_code=400, detail=f"hint must be one of {ALL_KINDS}")
    path = _save_upload(matrix)
    try:
        bundle = ingest_cached(path, hint=hint, sheet=sheet)  # C3 parsed-input cache
        bundle.source.filename = pathlib.Path(matrix.filename or "").name  # honest name (drives L1)
        bundle.qc = run_qc(bundle)
        # The user's data-type override arrives as `profile` (the "erg" profile) OR `hint` (an engine
        # Kind — "erg" isn't a Kind, so it can't ride `hint`). Either is the scientist's explicit
        # choice, so both must win in the profile, not just force the modality — otherwise a Kind
        # override (e.g. sc_counts) leaves a positively-detected content signal (ERG columns) still
        # out-ranking it in the label.
        prof = profile_data(bundle, override=profile or hint)   # the friendly, layered data-type label
        plan = plan_cleaning(bundle, profile=prof)      # the dynamic cleaning pane (kind-aware)
        routing = route_profile(bundle, prof.code)      # which analyses fit this data (P3 guidance)
        # Data-fit (Slice 2, product-agnostic): score THIS file against the analyses it routes to —
        # the same confidence band ("Confident / Not a fit / …") Product B shows, now for own data.
        fa = compat.assess_bundle(bundle)
        fits = sorted((compat.fit(s.skill_id, fa) for s in routing.steps),
                      key=lambda f: (f.compatible is False, -f.score))
        data_fit = {
            "quality": fa.quality,
            "confidence": fits[0].confidence if fits else ("uncertain" if fa.loadable else "unreadable"),
            "fits": [f.model_dump() for f in fits],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        pathlib.Path(path).unlink(missing_ok=True)
    return {
        "filename": matrix.filename or "",
        "kind": bundle.kind,
        "profile": prof.model_dump(),              # layered data-type label (format/keywords/modality)
        "cleaning_plan": plan.model_dump(),        # the dynamic "before & after cleaning" pane
        "source": bundle.source.model_dump(),
        "qc": bundle.qc.model_dump(),
        "routing": routing.model_dump(),           # suggested skill pipeline + honest note
        "data_fit": data_fit,                      # is-this-good-data verdict for own data (Slice 2)
    }


@app.post("/data/combine")
async def combine_data(files: list[UploadFile] = File(...), labels: str | None = Form(None)):
    # C6 multi-file combine: merge several single-condition ERG files (one .iwxdata/Diagnosys =
    # one eye/animal = one condition) into ONE multi-condition canonical table, so the trace-mean +
    # Fig-1E-with-reps run on a real cohort n. Returns the merged CSV (the FE turns it into a normal
    # dataset → the usual /data/inspect + run path takes over) plus a small JSON summary header.
    # `labels` is an optional comma-separated list aligned to `files` (blank entries auto-fall-through
    # to the file's own condition column, then its stem). pandas in-memory is the right tool at ERG
    # scale (kB–MB); see memory selom-data-substrate-decision (Parquet/DuckDB held for live launch).
    from engine import ingest_many

    if not files:
        raise HTTPException(status_code=400, detail="combine: no files")
    label_list = labels.split(",") if labels else None
    paths = [_save_upload(f) for f in files]
    bundle = None
    try:
        from engine import lineage

        bundle = ingest_many(paths, labels=label_list)
        csv_bytes = pathlib.Path(bundle.path).read_bytes()
        # D3 — capture each input file's content SHA NOW, while the uploads still exist (the finally
        # below deletes them), so the merged artifact's lineage can name "merged from {A, B, C}".
        parent_refs = [lineage.source_parent(p, f.filename or "") for p, f in zip(paths, files)]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in paths:
            pathlib.Path(p).unlink(missing_ok=True)
        if bundle is not None and bundle.path:
            pathlib.Path(bundle.path).unlink(missing_ok=True)
    df = bundle.payload
    conds = bundle.meta.get("conditions", [])
    summary = {
        "filename": bundle.source.filename,
        "n_files": bundle.meta.get("n_files"),
        "conditions": conds,
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "per_condition_n": (
            {c: int(df[df["condition"].astype(str) == c]["sample_id"].nunique()) for c in conds}
            if "sample_id" in df.columns else {}),
    }
    # D3 — materialize the merged cohort table as a content-addressed artifact: parents = the input
    # files (each by content SHA, captured above), so its lineage renders "merged from {A, B, C}".
    art = lineage.materialize(
        df, kind=lineage.KIND_COMBINED, filename=bundle.source.filename, parents=parent_refs,
        recipe_note=f"merged {bundle.meta.get('n_files')} file(s) into {len(conds)} condition(s)")
    if art is not None:
        summary["artifact_id"] = art.artifact_id
        summary["receipt"] = art.receipt
    return Response(
        content=csv_bytes, media_type="text/csv",
        headers={"X-Combine-Summary": json.dumps(summary),
                 "Access-Control-Expose-Headers": "X-Combine-Summary",
                 "Content-Disposition": f'attachment; filename="{bundle.source.filename}"'})


@app.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    # D3 — the lineage record for a materialized intermediate table: its metadata (shape, recipe,
    # parents, the "merged from {…}" receipt) + the ancestor chain. "Inspect the matrix the skill saw".
    from engine import lineage

    meta = lineage.get_meta(artifact_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"meta": meta.model_dump(),
            "lineage": [m.model_dump() for m in lineage.lineage(artifact_id)]}


@app.get("/artifacts/{artifact_id}/table")
def get_artifact_table(artifact_id: str):
    # D3 — the materialized table bytes themselves (CSV): the exact matrix a skill consumed, for
    # download/inspection. A meta-only matrix artifact has no table bytes (404 with a clear note).
    from engine import lineage

    data = lineage.get_table(artifact_id)
    if data is None:
        meta = lineage.get_meta(artifact_id)
        note = (meta.note if meta is not None else "artifact table not found")
        raise HTTPException(status_code=404, detail=note)
    meta = lineage.get_meta(artifact_id)
    fname = (meta.filename if meta is not None else "") or f"{artifact_id}.csv"
    return Response(
        content=data, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.post("/skills/{skill_id}/run")
async def run(skill_id: str, request: Request, matrix: UploadFile, design: UploadFile | None = File(None)):
    # Synchronous one-shot — the proven fast path for light skills (B1). Heavy skills
    # should use POST /skills/{id}/jobs (below). Tuning params arrive as the query
    # string; the contract fills skill defaults and each runner coerces types.
    # An optional `design` sheet (sample->condition/time) feeds bulk + time-course DE;
    # it is threaded as a reserved param and kept out of the provenance record.
    path = _save_upload(matrix)
    params = dict(request.query_params)
    # P1c "is-my-data-clean?" guardrail (engine-spine spec §5, E3/D-e5): a block-severity QC
    # problem warns + REQUIRES an explicit override rather than silently producing a misleading
    # figure — the native moat for non-bioinformaticians. `override=true` runs anyway. The flag is
    # popped here so it never reaches the skill, methods text, or the recorded provenance config.
    override = to_bool(params.pop("override", False))
    design_path = _save_upload(design) if design is not None else None
    if design_path:
        params["_design_path"] = design_path
    spec = load_skill(skill_id)
    # C3: enforce the param_spec ranges/options at the API — an out-of-range knob (e.g.
    # fc_threshold=100 on a max:5 param) is a 400 the user can fix, not a crash inside the skill.
    range_errors = validate_param_ranges(spec, params)
    if range_errors:
        raise HTTPException(status_code=400, detail={
            "error": "param_out_of_range",
            "message": "One or more parameters are outside their allowed range.",
            "errors": range_errors,
        })
    try:
        # Both products load through one ingest front door (engine-spine §6/§9): classify + QC, then
        # run from the same DataBundle. Fail-soft — an uninspectable upload yields no bundle and runs
        # the path-based way (byte-identical), so the guardrail never breaks a previously-valid run.
        bundle, qc, routing = _inspect_for_run(path, matrix.filename)
        # The layered data-type label + dynamic cleaning plan ride the run too (cheap — the bundle
        # is already in memory), and upgrade the modality routing to be profile-aware (e.g. an ERG
        # table suggests the electrophysiology skills, not the generic table options).
        prof = plan = None
        if bundle is not None:
            from engine import plan_cleaning, profile_data, route_profile

            prof = profile_data(bundle)
            plan = plan_cleaning(bundle, profile=prof)
            routing = route_profile(bundle, prof.code)
        if qc is not None and qc.blocked and not override:
            raise HTTPException(status_code=422, detail={
                "error": "data_check_failed",
                "message": "This data has a blocking problem for analysis. Review the flags, then "
                           "re-run with override=true to analyze it anyway.",
                "kind": bundle.kind,
                "qc": qc.model_dump(),
                "routing": routing.model_dump() if routing is not None else None,
                "profile": prof.model_dump() if prof is not None else None,
                "cleaning_plan": plan.model_dump() if plan is not None else None,
            })
        # D1 — declared data-contract gate (docs/architecture-consistency-gate/skill-input-contract.md):
        # before entering the runner, check the dropped data carries what THIS skill needs — the
        # column groups / modality the skill declares in engine.compat. A CERTAIN mismatch (missing
        # required columns, or the wrong payload class) is a clear pre-run 422 the user can act on,
        # NOT a runtime stack trace inside the skill. The fit is computed once here and reused for the
        # response's data_fit (single source). Honest: only a positively-determined incompatibility
        # gates (compatible is False); an unreadable / modality-unclear file stays optimistic and runs.
        # Overridable (override=true) — the same escape hatch as the QC gate — for a rare classifier or
        # column-synonym miss; the runner's own ValueError→400 then covers any skill without a contract.
        data_fit_obj = None
        if bundle is not None:
            from engine import compat

            data_fit_obj = compat.fit(skill_id, compat.assess_bundle(bundle))
            if data_fit_obj.gated and not override:
                raise HTTPException(status_code=422, detail={
                    "error": "data_contract_failed",
                    "message": compat.contract_message(data_fit_obj),
                    "skill_id": skill_id,
                    "kind": bundle.kind,
                    "data_fit": data_fit_obj.model_dump(),
                    "routing": routing.model_dump() if routing is not None else None,
                })
        # D2 — frame-validation at the skill seam (docs/architecture-consistency-gate/
        # frame-validation.md): once D1 confirms the required columns are PRESENT, check they carry
        # USABLE data — a present-but-empty / all-text fold-change column passes D1 yet becomes a
        # silently-degenerate figure (or a downstream crash) inside the runner. A certain structural
        # defect is a clear 400 at the seam (lazy — every defect listed at once), not a stack trace.
        # Honest: only inspects columns D1 already confirmed present; overridable (same escape hatch).
        if bundle is not None and not override:
            from engine import frame_schema

            frame_errs = frame_schema.check_skill_input(skill_id, bundle.payload)
            if frame_errs:
                raise HTTPException(status_code=400, detail={
                    "error": "frame_validation_failed",
                    "message": frame_schema.frame_validation_message(frame_errs, skill_id),
                    "skill_id": skill_id,
                    "stage": frame_schema.STAGE_SKILL_INPUT,
                    "violations": [v.model_dump() for v in frame_errs],
                })
        def _do_run():
            return (run_bundle_with_table(skill_id, bundle, params) if bundle is not None
                    else run_skill_with_table(skill_id, path, params))

        try:
            # C3 exec timeout: run the skill in a worker thread under a ceiling so a hung skill
            # returns 504 promptly and the event loop stays live, instead of pinning the server.
            timeout = settings.skill_timeout_s
            if timeout and timeout > 0:
                figure, table = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(None, _do_run), timeout
                )
            else:
                figure, table = _do_run()
        except ValueError as e:
            # A runner raises ValueError for a DATA problem (missing columns, no groups, an empty
            # result) — a 4xx the user can fix, NOT a 5xx outage. Surface the real cause so the FE
            # shows "missing required columns […]" instead of "the service is unavailable".
            raise HTTPException(status_code=400, detail=str(e))
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail={
                "error": "skill_timeout",
                "message": f"'{skill_id}' exceeded the {timeout}s execution limit and was abandoned.",
            })
        # L3 table synthesis (docs/table-synthesis/spec.md §4 / §8 step 4): a tableless skill that
        # has a deterministic synthesizer gets a canonical Statistics table re-shaped from its OWN
        # figure (S1 read-not-recompute -> tagged synthesized:True, S3), so the FE Statistics node
        # renders for purely-visual skills too. None when no synthesizer exists (-> L4 Pro-AI, S4) or
        # the skill already has a native table; never a fabricated table. Symmetric with the
        # reproduction reader, which attaches the same synthesis when a native table is absent.
        if table is None:
            from extract.synthesize import synthesize_table

            table = synthesize_table(skill_id, figure)
        # Data-fit for THIS skill on the user's own data (Slice 2, product-agnostic): the same
        # confidence band Product B shows — "is the data I'm running good/compatible for this
        # analysis?" Computed once above for the D1 contract gate; reused here (no second load/score).
        data_fit = data_fit_obj.model_dump() if data_fit_obj is not None else None
        # D3 — materialize the intermediate table the skill actually consumed as a content-addressed
        # artifact (parent = the source file, recipe = the cleaning plan), so the FE can "inspect the
        # matrix the skill saw" via GET /artifacts/{id}. Fail-soft + bounded (a single-cell matrix is
        # recorded meta-only) — a lineage write never breaks a run. See engine/lineage.py.
        artifact = None
        if bundle is not None:
            from engine import lineage

            meta = lineage.materialize_bundle(
                bundle, recipe=(plan.steps if plan is not None else None),
                recipe_note=(plan.note if plan is not None else ""))
            artifact = meta.model_dump() if meta is not None else None
        # B4 publish-confidence: every figure ships with its reproducibility bundle +
        # auto methods-text. Pillar 1 adds the Statistics `table` (None for purely-visual
        # skills). Additive — the FE still reads `.figure`.
        return {
            "figure": figure,                            # Plotly JSON -> frontend
            "provenance": provenance.build(spec, path, matrix.filename, params),
            "methods": methods.build(spec, params),
            "figure_legend": legends.build(spec, params, figure=figure, table=table),
            "guardrails": guardrails.build(spec, path, params),
            "table": table,                              # Statistics node (Pillar 1) | None
            "artifact": artifact,                        # D3 lineage record of the matrix the skill saw
            # The surfaced is-my-data-clean verdict + suggested next steps for THIS run (P1c/P3a),
            # plus the layered data-type label + dynamic cleaning plan. `kind`=unknown / nulls when
            # the upload couldn't be inspected (fail-soft).
            "data_check": ({"kind": bundle.kind, "qc": qc.model_dump(),
                            "routing": routing.model_dump() if routing is not None else None,
                            "profile": prof.model_dump() if prof is not None else None,
                            "cleaning_plan": plan.model_dump() if plan is not None else None}
                           if bundle is not None
                           else {"kind": "unknown", "qc": None, "routing": None,
                                 "profile": None, "cleaning_plan": None}),
            "data_fit": data_fit,                        # is-my-data-good-for-this-skill (Slice 2)
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


@app.get("/papers/metadata/by-doi")
def paper_metadata_by_doi(doi: str = ""):
    # Article-Matcher enrichment (external-tools study §4 BUILD #2): a DOI -> resolved
    # bibliographic record via the fail-soft chain OpenAlex(CC0) primary -> CrossRef cross-check
    # -> PubMed fill, cached + degrade-safe (a lookup never breaks the caller). The full
    # PDF -> candidate-IDs -> record path lives in paper_metadata.enrich_pdf (local/dogfood).
    if not doi.strip():
        raise HTTPException(status_code=400, detail="doi is required")
    return paper_metadata.metadata_by_doi(doi)


@app.post("/skills/{skill_id}/jobs")
async def submit_job(
    skill_id: str, request: Request, matrix: UploadFile, ctx: AuthContext = Depends(require_user)
):
    # Async job path (B3): enqueue a run, return a job handle the FE polls. In inline
    # mode the job completes before this returns; arq mode runs it off-request. The job is owned
    # by the verified tenant (ctx.user_id) — never a request param (spec §6.2).
    if skill_id not in set(list_skill_ids()):
        raise HTTPException(status_code=404, detail=f"unknown skill '{skill_id}'")
    path = _save_upload(matrix)
    params = dict(request.query_params)
    # C3: the same param-range gate as /run — reject an out-of-range knob before enqueuing.
    range_errors = validate_param_ranges(load_skill(skill_id), params)
    if range_errors:
        raise HTTPException(status_code=400, detail={
            "error": "param_out_of_range",
            "message": "One or more parameters are outside their allowed range.",
            "errors": range_errors,
        })
    job = submit(skill_id, path, params, matrix.filename, user_id=ctx.user_id, email=ctx.email)
    return job.public()


@app.get("/jobs/{job_id}")
def job_status(job_id: str, ctx: AuthContext = Depends(require_user)):
    job = get_job(job_id, ctx.user_id)  # scoped: another tenant's job id → 404
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.public()


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, ctx: AuthContext = Depends(require_user)):
    # Server-Sent Events: emit current state, then poll until terminal. Inline jobs are
    # already terminal, so this resolves in one event; arq jobs stream the transitions.
    async def stream():
        for _ in range(600):  # ~5 min ceiling at 0.5s/tick
            job = get_job(job_id, ctx.user_id)
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'unknown job'})}\n\n"
                return
            yield f"data: {json.dumps(job.public())}\n\n"
            if job.status in TERMINAL:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


def _content_etag(payload) -> str:
    """A strong ETag — the content hash of a JSON-able payload (Task C2)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return '"' + hashlib.sha256(blob.encode("utf-8")).hexdigest() + '"'


@app.get("/jobs/{job_id}/result")
def job_result(job_id: str, request: Request, ctx: AuthContext = Depends(require_user)):
    # Scope the result to the owner: confirm the job belongs to this tenant before serving its
    # bundle (the result store is keyed by job_id, so the ownership check is the gate).
    if get_job(job_id, ctx.user_id) is None:
        raise HTTPException(status_code=404, detail="result not available")
    bundle = result_store.get(job_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="result not available")
    # C2: a stored result is immutable, so its content hash is a stable ETag. An FE that already
    # holds this figure sends If-None-Match and gets a 304 (no figure re-download).
    etag = _content_etag(bundle)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(bundle, headers={"ETag": etag})  # {figure, provenance, methods} — /run shape


# --- Projects + presigned uploads + datasets (materialization step 6, spec §4.2/§6/§7) --------
# The genuine flow rewrite: a client uploads bytes straight to S3 via a presigned PUT (bypassing the
# API Gateway body cap); the server only ever holds pointers + tenant rows. Every handler derives the
# tenant from the verified claim (ctx.user_id) — NEVER a request param (spec §6.2); no request model
# below carries a user_id. Uploads require a DB (the datasets/users tables): a missing
# SELOM_DATABASE_URL surfaces as a clean 503, not a silent default.


def _uploads_repo():
    """FastAPI dependency → the UploadRepo, or a 503 when no database is configured."""
    try:
        return get_upload_repo()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class ProjectCreate(BaseModel):
    name: str
    color: str = "blue"


class IntakeRequest(BaseModel):
    project_id: str
    filename: str
    size_bytes: int                       # the client declares the size (browser file.size); caps the PUT
    content_sha256: str | None = None     # optional client-declared hash (the parse recomputes the truth)


class ConfirmRequest(BaseModel):
    sha256: str | None = None             # optional; size comes from the object head, not the client


@app.post("/projects")
def create_project(body: ProjectCreate, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="project name is required")
    try:
        return repo.create_project(ctx.user_id, ctx.email, name, body.color)
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.to_dict()) from exc


@app.get("/projects")
def list_projects(repo=Depends(_uploads_repo), ctx: AuthContext = Depends(require_user)):
    return {"projects": repo.list_projects(ctx.user_id)}


@app.post("/uploads/intake")
def upload_intake(body: IntakeRequest, repo=Depends(_uploads_repo),
                  ctx: AuthContext = Depends(require_user)):
    # Row-first (spec §7): the pending_upload datasets row is created BEFORE the presigned URL, so an
    # object can never exist without a row to reconcile against. The key is server-derived from the
    # JWT user_id (T1) — the presign signs exactly it, so the client can't write outside its prefix.
    if body.size_bytes <= 0:
        raise HTTPException(status_code=400, detail="size_bytes must be > 0 (the declared file size)")
    try:
        result = repo.intake(ctx.user_id, ctx.email, body.project_id, body.filename,
                             body.content_sha256, body.size_bytes)
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.to_dict()) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown project") from exc
    # The PUT is capped at the declared size (content-length-range), so a 1 MB intake can't smuggle a
    # 10 GB file (replaces main.py's old post-read buffer cap).
    upload = get_object_store().presign_put(result["key"], settings.s3_presign_ttl, body.size_bytes)
    return {"dataset": result["dataset"], "upload": upload}


@app.put("/uploads/local/{key:path}")
async def upload_local_put(key: str, request: Request):
    # Dev-only stand-in for the S3 direct PUT: the LocalObjectStore presign returns this in-app route
    # (there's no S3 to PUT to offline). The presigned URL IS the credential in the S3 model, so this
    # mirrors that — but it only ever accepts the known uploads/ prefix, never an arbitrary key.
    if not key.startswith("uploads/"):
        raise HTTPException(status_code=400, detail="local upload key must be under uploads/")
    body = await request.body()
    get_object_store().put_bytes(key, body)
    return {"ok": True, "key": key, "size": len(body)}


@app.post("/uploads/{dataset_id}/confirm")
def upload_confirm(dataset_id: str, body: ConfirmRequest, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    # Flip pending_upload → ready once the object has landed. S3 is the source of truth for "did it
    # land" — we head the key (server-derived from the row) and stamp the real size. A dropped confirm
    # still self-heals via the S3-event path (spec §7); this is the latency-optimised happy path.
    ds = repo.get_dataset(ctx.user_id, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    size = get_object_store().head_size(ds["upload_s3_key"])
    if size is None:
        raise HTTPException(status_code=409, detail="object not found in store (upload not completed)")
    return repo.confirm(ctx.user_id, dataset_id, size_bytes=size, sha256=body.sha256)


@app.post("/uploads/{dataset_id}/parse")
def upload_parse(dataset_id: str, repo=Depends(_uploads_repo),
                 ctx: AuthContext = Depends(require_user)):
    # Server-side, leak-free parse (spec §4.2): read the raw object, ingest, write the parsed matrix
    # to data/{sha256}.csv (CSV until the parquet substrate lands, owner gate Q5), stamp the pointer.
    try:
        ds = materialize_dataset(repo, get_object_store(), ctx.user_id, dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:  # an unloadable file is an honest 400 (mirrors /data/inspect)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    return ds


@app.get("/datasets")
def list_datasets(project_id: str | None = None, repo=Depends(_uploads_repo),
                  ctx: AuthContext = Depends(require_user)):
    return {"datasets": repo.list_datasets(ctx.user_id, project_id)}


@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, repo=Depends(_uploads_repo),
                ctx: AuthContext = Depends(require_user)):
    ds = repo.get_dataset(ctx.user_id, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    return ds


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
    # C2 render tier: theme.render caches the envelope by (figure hash, skill, style, theme version),
    # so a repeat style apply is a cache hit and no skill is re-run for a style change.
    if not isinstance(req.figure, dict) or "data" not in req.figure:
        raise HTTPException(status_code=400, detail="figure must be a Plotly spec with a data array")
    return {"figure": theme.render(req.figure, req.skill_id or "", req.style)}

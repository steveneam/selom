import asyncio
import json
import pathlib
import shutil
import tempfile
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
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
from jobs.queue import get_job, result_store, submit
from jobs.store import TERMINAL
from skills import styles, theme
from skills._engine import to_bool
from skills.contract import load_skill, run_bundle_with_table, run_skill_with_table
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
        from engine import ingest, route_data, run_qc

        bundle = ingest(path)
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
    from engine import ALL_KINDS, ingest, plan_cleaning, profile_data, route_profile, run_qc
    from engine import compat

    if hint is not None and hint not in ALL_KINDS:
        raise HTTPException(status_code=400, detail=f"hint must be one of {ALL_KINDS}")
    path = _save_upload(matrix)
    try:
        bundle = ingest(path, hint=hint, sheet=sheet)
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
        try:
            figure, table = (run_bundle_with_table(skill_id, bundle, params) if bundle is not None
                             else run_skill_with_table(skill_id, path, params))
        except ValueError as e:
            # A runner raises ValueError for a DATA problem (missing columns, no groups, an empty
            # result) — a 4xx the user can fix, NOT a 5xx outage. Surface the real cause so the FE
            # shows "missing required columns […]" instead of "the service is unavailable".
            raise HTTPException(status_code=400, detail=str(e))
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
        # analysis?" Reuses the already-ingested bundle (no second load); None when uninspectable.
        data_fit = None
        if bundle is not None:
            from engine import compat

            data_fit = compat.fit(skill_id, compat.assess_bundle(bundle)).model_dump()
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

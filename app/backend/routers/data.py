import json
import pathlib

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from routers._errors import RunError
from routers._run import _save_upload

router = APIRouter()


@router.post("/data/inspect")
async def inspect_data(matrix: UploadFile, sheet: str | None = None, hint: str | None = None,
                       profile: str | None = None, design: UploadFile | None = File(None)):
    # Engine spine front door (P1, docs/engine-spine/spec.md): drop a data file -> its layered
    # data-type (format -> keywords -> modality), an "is-my-data-clean?" QC report, AND the dynamic
    # cleaning plan for that type. Product A's entry point; library-only, runs no analysis. The cheap
    # routing inventory in extract.ingest is the paper-side complement. `sheet` selects an xlsx sheet;
    # `hint` forces the modality (Kind); `profile` is the user's L3 data-type override (e.g. "erg").
    # `design` is an optional sample sheet — when attached it becomes the design source of truth for the
    # questionnaire prefill (Layer A ingest followups #5: the reproducible fix for a mis-grouping).
    from engine import ALL_KINDS, ingest_cached, plan_cleaning, profile_data, route_profile, run_qc
    from engine import compat, suggest_design_hints

    if hint is not None and hint not in ALL_KINDS:
        raise RunError.bad_input(
            "invalid_hint", f"hint must be one of {ALL_KINDS}.",
            fix="Drop the hint to auto-detect, or pass one of the listed modalities.")
    path = _save_upload(matrix)
    design_path = _save_upload(design) if design is not None else None
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
            # Slice 2 (data-aware routing): the table shape the FE forwards to /ai/propose as the
            # data context (data_columns / data_n_numeric_cols), so the route composer's skill
            # suggestion is scored against the real data. Already on the FileAssessment — free.
            "columns": fa.columns,
            "n_numeric_cols": fa.n_numeric_cols,
            "fits": [f.model_dump() for f in fits],
        }
        # The DESIGN layer for the intake questionnaire (Layer A ingest, deterministic, AI-off): the
        # candidate group/condition column(s), their levels + replicate counts, and a control guess —
        # what the engine did NOT detect before. The confirmed answers map onto the deg run params
        # the runner already records (docs/intake-questionnaire/build-spec.md). Fail-soft → no design.
        # An attached sample sheet (design_path) is the source of truth (auto-join, never hand-match).
        design_hints = suggest_design_hints(bundle, design_path=design_path)
    except ValueError as e:
        # The engine raises ValueError for a file it can't read/parse (bad encoding, no loader, a
        # corrupt workbook) — the real cause (str(e)) is the taxonomy's `message`; a bad-input 400,
        # never a 500. Same envelope the run path uses (WS2.6).
        raise RunError.bad_input(
            "data_read_failed", str(e),
            fix="Check the file opens as a table (delimiter / header / sheet), "
                "or try a different export.") from e
    finally:
        pathlib.Path(path).unlink(missing_ok=True)
        if design_path is not None:
            pathlib.Path(design_path).unlink(missing_ok=True)
    return {
        "filename": matrix.filename or "",
        "kind": bundle.kind,
        "profile": prof.model_dump(),              # layered data-type label (format/keywords/modality)
        "cleaning_plan": plan.model_dump(),        # the dynamic "before & after cleaning" pane
        "source": bundle.source.model_dump(),
        "qc": bundle.qc.model_dump(),
        "routing": routing.model_dump(),           # suggested skill pipeline + honest note
        "data_fit": data_fit,                      # is-this-good-data verdict for own data (Slice 2)
        "design": design_hints.model_dump(),       # deterministic design prefill for the intake questionnaire
    }


@router.post("/data/combine")
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
        raise RunError.bad_input(
            "combine_no_files", "combine: no files.",
            fix="Attach two or more single-condition files to merge.")
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
        # A merge that can't reconcile the inputs (mismatched shapes, no common condition) — the
        # real cause as `message`, a bad-input 400 in the shared envelope (WS2.6).
        raise RunError.bad_input(
            "combine_failed", str(e),
            fix="Ensure each file is one condition with a shared column layout.") from e
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


@router.post("/data/assemble-scrna")
async def assemble_scrna_data(files: list[UploadFile] = File(...), obs_map: str | None = Form(None)):
    # The scRNA sibling of /data/combine: a real GEO scRNA deposit (e.g. Kim/Hani GSE201356) arrives
    # as a SET of per-sample 10x matrices (loose barcodes/features/matrix triplets or per-sample
    # .h5ad) with NO per-cell design in obs — the design (line/genotype, sample id) lives in the
    # FILENAMES. This reads that set, concatenates it into ONE AnnData, and materializes the
    # filename-encoded design into obs (sample_id always; plus the line/condition the caller keys per
    # sample in `obs_map`). Returns the assembled .h5ad bytes + a JSON summary header, exactly like
    # /data/combine returns the merged CSV — the FE turns it into a normal dataset (the usual
    # /uploads/intake → confirm → parse/materialize_dataset path), where the standard run path takes
    # over. `obs_map` is an optional JSON object {sample key → {obs field: value}} (the confirmed
    # intake answers); omit it for a filename-only assembly (sample_id per file, no design overlay).
    from engine import assemble, lineage

    if not files:
        raise RunError.bad_input(
            "assemble_no_files", "assemble-scrna: no files.",
            fix="Attach the per-sample 10x matrices (barcodes/features/matrix triplets, a 10x "
                "directory, or a per-sample .h5ad) to assemble.")
    parsed_obs_map = None
    if obs_map:
        try:
            parsed_obs_map = json.loads(obs_map)
        except (ValueError, TypeError) as e:
            raise RunError.bad_input(
                "assemble_bad_obs_map",
                "obs_map must be a JSON object mapping a sample key to its obs fields.",
                fix='e.g. {"GSM6061839_2niPE2-ANAI-3": {"line": "2niPE2", "condition": "iRPE"}}') from e
        if not isinstance(parsed_obs_map, dict):
            raise RunError.bad_input(
                "assemble_bad_obs_map",
                "obs_map must be a JSON object mapping a sample key to its obs fields.",
                fix='e.g. {"GSM6061839_2niPE2-ANAI-3": {"line": "2niPE2", "condition": "iRPE"}}')
    paths = [_save_upload(f) for f in files]
    # Parent refs by CONTENT SHA, captured before the `finally` deletes the temp uploads — the same
    # capture /data/combine does, so the assembled cohort's lineage renders "assembled from {…}".
    parent_refs = [lineage.source_parent(p, f.filename or "") for p, f in zip(paths, files)]
    adata = None
    try:
        adata = assemble.assemble_scrna(paths, obs_map=parsed_obs_map)
        summary = assemble.summarize(adata)
        h5ad_bytes = assemble.to_h5ad_bytes(adata)
    except ValueError as e:
        # A deposit we can't assemble (an unrecognized file, an incomplete triplet, an unreadable
        # matrix) — the real cause as `message`, a bad-input 400 in the shared envelope (WS2.6).
        raise RunError.bad_input(
            "assemble_failed", str(e),
            fix="Attach a complete 10x triplet (matrix + barcodes + features) per sample, a 10x "
                "directory, or one .h5ad per sample.") from e
    finally:
        for p in paths:
            pathlib.Path(p).unlink(missing_ok=True)
    summary["filename"] = "assembled_scrna.h5ad"
    summary["n_files"] = len(files)
    # D3 — record the assembled cohort like its /data/combine sibling. Without this the design that
    # was materialized into obs (which sample carried which line/condition, and from which file) was
    # unrecoverable once the temp uploads were deleted: the user re-uploads the .h5ad and it looks
    # hand-made (milestone review 2026-07-25, finding A8). An AnnData records meta-only (shape +
    # parents, no CSV) and lineage is fail-soft — a missing artifact never breaks the assembly.
    art = lineage.materialize(
        adata, kind=lineage.KIND_MATRIX, filename="assembled_scrna.h5ad", parents=parent_refs,
        recipe_note=(f"assembled {len(files)} per-sample matrix file(s) into one AnnData"
                     + (" with a filename-keyed obs design overlay" if parsed_obs_map else
                        " (sample_id from filenames only, no design overlay)")))
    if art is not None:
        summary["artifact_id"] = art.artifact_id
        summary["receipt"] = art.receipt
    return Response(
        content=h5ad_bytes, media_type="application/octet-stream",
        headers={"X-Assemble-Summary": json.dumps(summary),
                 "Access-Control-Expose-Headers": "X-Assemble-Summary",
                 "Content-Disposition": 'attachment; filename="assembled_scrna.h5ad"'})


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    # D3 — the lineage record for a materialized intermediate table: its metadata (shape, recipe,
    # parents, the "merged from {…}" receipt) + the ancestor chain. "Inspect the matrix the skill saw".
    from engine import lineage

    meta = lineage.get_meta(artifact_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"meta": meta.model_dump(),
            "lineage": [m.model_dump() for m in lineage.lineage(artifact_id)]}


@router.get("/artifacts/{artifact_id}/table")
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

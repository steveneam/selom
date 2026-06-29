import asyncio
import hashlib
import json
import pathlib
import shutil
import tempfile
import uuid

from fastapi import HTTPException, UploadFile

import guardrails
import legends
import methods
import provenance
from config import settings
from skills.contract import (
    load_skill,
    run_bundle_with_table,
    run_skill_with_table,
    validate_param_ranges,
)
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


def _dataset_to_temp(repo, store, user_id: str, dataset_id: str) -> tuple[str, str]:
    # Run-from-dataset_id (sub-spec §5): the bytes already live in the object store, so fetch them to
    # a temp instead of re-uploading. Prefer the parsed matrix (parquet_s3_key — a .csv key for now,
    # Q5); fall back to the raw upload. Raises KeyError (unknown dataset) / FileNotFoundError (no
    # bytes — an imported metadata-only row, or an object that never landed → 409 "re-upload").
    ds = repo.get_dataset(user_id, dataset_id)
    if ds is None:
        raise KeyError(dataset_id)
    key = ds.get("parquet_s3_key") or ds.get("upload_s3_key")
    if not key:
        raise FileNotFoundError("dataset has no stored bytes (re-upload to materialize)")
    name = pathlib.Path(ds.get("filename") or "").name or "data"
    stem = pathlib.Path(name).stem or "data"
    suffix = pathlib.Path(key).suffix or pathlib.Path(name).suffix or ".csv"
    dest = pathlib.Path(tempfile.mkdtemp()) / f"{stem}{suffix}"
    if not store.download_to_path(key, str(dest)):
        raise FileNotFoundError("stored object not found (re-upload to materialize)")
    return str(dest), name


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


def _stringify_params(params: dict | None) -> dict:
    # The multipart run path takes params as query strings (all str; the runners coerce). The
    # dataset/JSON path may carry real numbers/bools, so normalise to the same string shape.
    out: dict = {}
    for k, v in (params or {}).items():
        out[k] = ("true" if v else "false") if isinstance(v, bool) else str(v)
    return out


def _content_etag(payload) -> str:
    """A strong ETag — the content hash of a JSON-able payload (Task C2)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return '"' + hashlib.sha256(blob.encode("utf-8")).hexdigest() + '"'


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


async def _execute_skill_run(
    skill_id: str, path: str, filename: str | None, params: dict,
    override: bool, design_path: str | None,
):
    # Shared run body for the multipart /run and the run-from-dataset_id path (sub-spec §5): one
    # ingest → gates (QC / D1 / D2) → run → response. `filename` is the dropped name (or the dataset
    # filename) used for provenance + the engine's derived sample labels. `override` is already popped
    # from params by the caller; `design_path` (multipart only) is cleaned up in the finally.
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
        bundle, qc, routing = _inspect_for_run(path, filename)
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
        # L3 table synthesis (docs/records/table-synthesis/spec.md §4 / §8 step 4): a tableless skill that
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
            "provenance": provenance.build(spec, path, filename, params),
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

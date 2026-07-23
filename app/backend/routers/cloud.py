"""Cloud-storage import/export endpoints (docs — cloud/). Import streams a provider file into the
SAME ``intake → confirm → parse`` pipeline the local drop-zone uses (``uploads/``) — no parallel
ingest — and stamps ``datasets.source`` provenance. URL/S3 works today; the OAuth providers refuse
with a clean "not configured" until their feature flag is on. Export is scaffolded (dataset → S3).

Every handler derives the tenant from the verified claim (``ctx.user_id``) and the object key from
the tenant's own row — never a raw key from the request (T1, mirrors ``routers/library.py``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import AuthContext, require_user
from cloud import CloudError, CloudTooLarge, nango, registry
from cloud.ssrf import SsrfError
from config import settings
from storage.object_store import get_object_store
from uploads import QuotaExceeded, materialize_dataset

from routers.deps import _uploads_repo

router = APIRouter()


class RemoteIntakeRequest(BaseModel):
    project_id: str
    provider: str                       # "url" | "google" | "onedrive" | "dropbox"
    ref: str                            # a URL / s3:// URI, or a provider file id/path
    connection_id: str | None = None    # the Nango connection id (OAuth providers)
    filename: str | None = None         # optional; derived from a URL when omitted


class CloudExportRequest(BaseModel):
    provider: str
    dest: str                           # s3://bucket/key (URL provider) or a provider folder id
    dataset_id: str                     # the tenant dataset whose stored object is exported
    connection_id: str | None = None


def _derive_filename(kind: str, ref: str, given: str | None) -> str:
    if given and given.strip():
        return given.strip()
    if kind == registry.KIND_URL:
        name = PurePosixPath(unquote(urlsplit(ref).path)).name
        return name or "download"
    return "cloud-import"


def _not_configured(provider: registry.Provider) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": "provider_not_configured",
            "provider": provider.id,
            "message": (
                f"{provider.label} isn't connected yet — add your client IDs to Nango to enable it."
            ),
        },
    )


@router.post("/uploads/intake/remote")
def intake_remote(body: RemoteIntakeRequest, repo=Depends(_uploads_repo),
                  ctx: AuthContext = Depends(require_user)):
    provider = registry.get_provider(body.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {body.provider!r}")
    if not registry.is_enabled(provider, settings):
        raise _not_configured(provider)  # OAuth provider whose flag is off — "coming soon"

    ref = (body.ref or "").strip()
    if not ref:
        raise HTTPException(status_code=400, detail="a source reference (URL / file) is required")
    filename = _derive_filename(provider.kind, ref, body.filename)

    # Row-first (spec §7): reserve the pending_upload BEFORE fetching, so an object can never exist
    # without a row to reconcile. Size is unknown for a remote import → 0; the running byte-cap below
    # is the real ceiling, and confirm stamps the true size once streamed.
    try:
        reserved = repo.intake(ctx.user_id, ctx.email, body.project_id, filename, None, 0)
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.to_dict()) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown project") from exc
    ds_id = reserved["dataset"]["id"]
    key = reserved["key"]

    # OAuth providers: exchange the Nango connection id for a live provider token.
    token: str | None = None
    if provider.kind == registry.KIND_OAUTH:
        try:
            token = nango.get_access_token(body.connection_id or "", provider.provider_config_key)
        except CloudError as exc:
            repo.fail(ctx.user_id, ds_id)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Stream provider → store with a running byte-cap = the tenant's storage headroom (config cap when
    # the tenant has no quota row). Any failure marks the dataset failed (fail-soft) — the local path
    # is untouched.
    cap = repo.storage_headroom(ctx.user_id)
    if cap is None:
        cap = settings.cloud_import_max_bytes
    connector = registry.get_connector(provider.id)
    try:
        n_bytes = connector.fetch_to_store(ref, token, key, cap)
    except (SsrfError, CloudError) as exc:
        repo.fail(ctx.user_id, ds_id)
        code = 413 if isinstance(exc, CloudTooLarge) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    # Confirm (flip → ready + stamp the real size) then record import provenance.
    repo.confirm(ctx.user_id, ds_id, size_bytes=n_bytes)
    repo.set_source(ctx.user_id, ds_id, {
        "provider": provider.id, "ref": ref,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })

    # Parse (best-effort, mirrors the local upload path): an unparseable file keeps its ready row +
    # raw bytes so run-from-dataset_id still works; a genuinely missing object is a hard failure.
    try:
        ds = materialize_dataset(repo, get_object_store(), ctx.user_id, ds_id)
    except ValueError:
        ds = repo.get_dataset(ctx.user_id, ds_id)
    except FileNotFoundError as exc:
        repo.fail(ctx.user_id, ds_id)
        raise HTTPException(status_code=502, detail=f"import landed no object: {exc}") from exc
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    return ds


@router.post("/export/cloud")
def export_cloud(body: CloudExportRequest, repo=Depends(_uploads_repo),
                 ctx: AuthContext = Depends(require_user)):
    # Scaffold: export a tenant dataset's stored object to a provider. The key is resolved from the
    # tenant's own row (never a raw client key — T1). URL/S3 (s3:// dest) is functional; the OAuth
    # providers refuse until their flag is on.
    provider = registry.get_provider(body.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {body.provider!r}")
    if not registry.is_enabled(provider, settings):
        raise _not_configured(provider)

    ds = repo.get_dataset(ctx.user_id, body.dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    key = ds.get("parquet_s3_key") or ds.get("upload_s3_key")
    if not key:
        raise HTTPException(status_code=409, detail="dataset has no stored object to export")

    token: str | None = None
    if provider.kind == registry.KIND_OAUTH:
        try:
            token = nango.get_access_token(body.connection_id or "", provider.provider_config_key)
        except CloudError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    connector = registry.get_connector(provider.id)
    try:
        n_bytes = connector.push_from_store(key, body.dest, token)
    except (SsrfError, CloudError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "provider": provider.id, "dest": body.dest, "bytes": n_bytes}

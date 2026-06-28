from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import AuthContext, require_user
from config import settings
from storage.object_store import get_object_store
from uploads import QuotaExceeded, materialize_dataset

from routers.deps import _library_repo, _uploads_repo

router = APIRouter()


# ── Projects + presigned uploads + datasets (materialization step 6, spec §4.2/§6/§7) ──────────
# The genuine flow rewrite: a client uploads bytes straight to S3 via a presigned PUT (bypassing the
# API Gateway body cap); the server only ever holds pointers + tenant rows. Every handler derives the
# tenant from the verified claim (ctx.user_id) — NEVER a request param (spec §6.2); no request model
# below carries a user_id. Uploads require a DB (the datasets/users tables): a missing
# SELOM_DATABASE_URL surfaces as a clean 503, not a silent default.


class ProjectCreate(BaseModel):
    name: str
    color: str = "blue"
    id: str | None = None                 # client-authoritative id (sub-spec §2.2); omit → server mints


class IntakeRequest(BaseModel):
    project_id: str
    filename: str
    size_bytes: int                       # the client declares the size (browser file.size); caps the PUT
    content_sha256: str | None = None     # optional client-declared hash (the parse recomputes the truth)


class ConfirmRequest(BaseModel):
    sha256: str | None = None             # optional; size comes from the object head, not the client


@router.post("/projects")
def create_project(body: ProjectCreate, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="project name is required")
    try:
        return repo.create_project(ctx.user_id, ctx.email, name, body.color, body.id)
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.to_dict()) from exc


@router.get("/projects")
def list_projects(repo=Depends(_uploads_repo), ctx: AuthContext = Depends(require_user)):
    return {"projects": repo.list_projects(ctx.user_id)}


class ProjectPatch(BaseModel):
    model_config = {"extra": "ignore"}
    name: str | None = None
    color: str | None = None


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectPatch, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    proj = repo.update_project(ctx.user_id, project_id, **body.model_dump(exclude_unset=True))
    if proj is None:
        raise HTTPException(status_code=404, detail="unknown project")
    return proj


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    if repo.delete_project(ctx.user_id, project_id) == 0:
        raise HTTPException(status_code=404, detail="unknown project")
    return {"ok": True, "id": project_id}


@router.post("/uploads/intake")
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


@router.put("/uploads/local/{key:path}")
async def upload_local_put(key: str, request: Request):
    # Dev-only stand-in for the S3 direct PUT: the LocalObjectStore presign returns this in-app route
    # (there's no S3 to PUT to offline). The presigned URL IS the credential in the S3 model, so this
    # mirrors that — but it only ever accepts the known uploads/ prefix, never an arbitrary key.
    if not key.startswith("uploads/"):
        raise HTTPException(status_code=400, detail="local upload key must be under uploads/")
    body = await request.body()
    get_object_store().put_bytes(key, body)
    return {"ok": True, "key": key, "size": len(body)}


@router.post("/uploads/{dataset_id}/confirm")
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


@router.post("/uploads/{dataset_id}/parse")
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


class DatasetCreate(BaseModel):
    model_config = {"extra": "ignore"}
    id: str | None = None                 # client-authoritative id (sub-spec §2.2)
    project_id: str
    filename: str
    modality: str | None = None
    qc: dict | None = None
    current_sha256: str | None = None


@router.post("/datasets")
def create_dataset(body: DatasetCreate, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    # Metadata-only dataset (FE addDataset) — the classified file the FE doesn't upload to the store.
    # The real presigned-upload path is POST /uploads/intake; this is its no-bytes twin.
    try:
        return repo.create_dataset(ctx.user_id, ctx.email, body.project_id, body.filename,
                                   body.id, body.modality, body.qc, body.current_sha256)
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.to_dict()) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown project") from exc


@router.get("/datasets")
def list_datasets(project_id: str | None = None, repo=Depends(_uploads_repo),
                  ctx: AuthContext = Depends(require_user)):
    return {"datasets": repo.list_datasets(ctx.user_id, project_id)}


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, repo=Depends(_uploads_repo),
                ctx: AuthContext = Depends(require_user)):
    ds = repo.get_dataset(ctx.user_id, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    return ds


class DatasetPatch(BaseModel):
    model_config = {"extra": "ignore"}
    label: str | None = None
    modality: str | None = None
    qc: dict | None = None
    current_sha256: str | None = None


@router.patch("/datasets/{dataset_id}")
def update_dataset(dataset_id: str, body: DatasetPatch, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    ds = repo.update_dataset(ctx.user_id, dataset_id, **body.model_dump(exclude_unset=True))
    if ds is None:
        raise HTTPException(status_code=404, detail="unknown dataset")
    return ds


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, repo=Depends(_uploads_repo),
                   ctx: AuthContext = Depends(require_user)):
    if repo.delete_dataset(ctx.user_id, dataset_id) == 0:
        raise HTTPException(status_code=404, detail="unknown dataset")
    return {"ok": True, "id": dataset_id}


class ImportStateRequest(BaseModel):
    # The decoded localStorage blobs (FE camelCase shapes): selom.projects.v1 + selom.workspace.v1.
    projects: dict | None = None
    workspace: dict | None = None


@router.post("/import/local-state")
def import_local_state(body: ImportStateRequest, repo=Depends(_library_repo),
                       ctx: AuthContext = Depends(require_user)):
    # One-time localStorage → Postgres import (sub-spec §4): atomic, dependency-ordered, idempotent
    # (skip-if-exists on the client id). Safe to retry — converges to the same state. Stamps
    # users.local_import_at so the FE prompt doesn't reappear (Q1).
    counts = repo.import_local_state(ctx.user_id, ctx.email, body.projects, body.workspace)
    return {"ok": True, "imported": counts}


# ── account library: workspace · gene sets · papers · skill installs (sub-spec §3, BE-2) ─────────
# Namespaced under /workspace/* to avoid colliding with the read-only catalog/live routes /papers,
# /gene-sets, /reproduction-runs (sub-spec §3.2). Tenant = ctx.user_id only (§6.2).


class GeneSetBody(BaseModel):
    model_config = {"extra": "ignore"}
    id: str | None = None
    name: str = "Gene set"
    genes: list = []
    source: str = ""
    source_label: str = ""
    license: str = ""
    created_from: str | None = None


class PaperBody(BaseModel):
    model_config = {"extra": "ignore"}
    id: str | None = None
    filename: str = "paper.pdf"
    doi: str | None = None
    pmid: str | None = None
    title: str | None = None
    authors: list | None = None
    venue: str | None = None
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    is_preprint: bool = False
    url: str | None = None
    modality: str | None = None
    skills: list | None = None
    out_of_scope: list | None = None
    figure_count: int = 0
    tier_summary: dict | None = None
    reproduction_run_id: str | None = None
    data_map: dict | None = None
    supplements: list | None = None


class InstallBody(BaseModel):
    id: str | None = None                 # client-authoritative id (sub-spec §2.2)
    skill_id: str
    project_id: str | None = None         # null ⇒ workspace-wide install


@router.get("/workspace")
def get_workspace(repo=Depends(_library_repo), ctx: AuthContext = Depends(require_user)):
    return repo.get_workspace(ctx.user_id, ctx.email)


@router.get("/workspace/gene-sets")
def list_gene_sets(repo=Depends(_library_repo), ctx: AuthContext = Depends(require_user)):
    return {"gene_sets": repo.list_gene_sets(ctx.user_id)}


@router.post("/workspace/gene-sets")
def save_gene_set(body: GeneSetBody, repo=Depends(_library_repo),
                  ctx: AuthContext = Depends(require_user)):
    return repo.save_gene_set(ctx.user_id, ctx.email, body.model_dump())


@router.delete("/workspace/gene-sets/{gene_set_id}")
def delete_gene_set(gene_set_id: str, repo=Depends(_library_repo),
                    ctx: AuthContext = Depends(require_user)):
    if repo.delete_gene_set(ctx.user_id, gene_set_id) == 0:
        raise HTTPException(status_code=404, detail="unknown gene set")
    return {"ok": True, "id": gene_set_id}


@router.get("/workspace/papers")
def list_saved_papers(repo=Depends(_library_repo), ctx: AuthContext = Depends(require_user)):
    return {"papers": repo.list_papers(ctx.user_id)}


@router.post("/workspace/papers")
def save_paper(body: PaperBody, repo=Depends(_library_repo),
               ctx: AuthContext = Depends(require_user)):
    return repo.upsert_paper(ctx.user_id, ctx.email, body.model_dump())


@router.get("/workspace/papers/{paper_id}")
def get_saved_paper(paper_id: str, repo=Depends(_library_repo),
                    ctx: AuthContext = Depends(require_user)):
    paper = repo.get_paper(ctx.user_id, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="unknown paper")
    return paper


@router.delete("/workspace/papers/{paper_id}")
def delete_saved_paper(paper_id: str, repo=Depends(_library_repo),
                       ctx: AuthContext = Depends(require_user)):
    if repo.delete_paper(ctx.user_id, paper_id) == 0:
        raise HTTPException(status_code=404, detail="unknown paper")
    return {"ok": True, "id": paper_id}


@router.get("/skill-installs")
def list_skill_installs(project_id: str | None = None, repo=Depends(_library_repo),
                        ctx: AuthContext = Depends(require_user)):
    return {"installs": repo.list_installs(ctx.user_id, project_id)}


@router.post("/skill-installs")
def install_skill(body: InstallBody, repo=Depends(_library_repo),
                  ctx: AuthContext = Depends(require_user)):
    try:
        return repo.install_skill(ctx.user_id, ctx.email, body.skill_id, body.project_id, body.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown project") from exc


@router.delete("/skill-installs")
def uninstall_skill(skill_id: str, project_id: str | None = None, repo=Depends(_library_repo),
                    ctx: AuthContext = Depends(require_user)):
    removed = repo.uninstall_skill(ctx.user_id, skill_id, project_id)
    return {"ok": True, "removed": removed}

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

import export
from auth import AuthContext, require_user
from skills import styles, theme

from routers.deps import _library_repo

router = APIRouter()

_EXPORT_MEDIA = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf"}


# ── static /figures/* routes — MUST be declared before /figures/{figure_id} ──────────────────────
# FastAPI matches in declaration order; these static paths must win over the param route (sub-spec
# §3.2). /figures/export, /figures/styles are same-depth as /figures/{figure_id} and would be
# shadowed if the param route came first.


@router.get("/figures/export/presets")
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


@router.post("/figures/export")
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


@router.get("/figures/styles")
def figure_styles():
    # Journal style catalog (journal-styles v1): the FE style picker renders from this.
    return {"styles": styles.list_styles()}


class StyleApplyRequest(BaseModel):
    figure: dict                       # Plotly {data, layout} spec to restyle
    skill_id: str | None = None        # drives figure-type polish (volcano/embedding/…)
    style: str = styles.DEFAULT_STYLE  # target style id (export.styles.STYLES)


@router.post("/figures/style/apply")
def apply_figure_style(req: StyleApplyRequest):
    # Live editor preview: re-skin a figure in a journal style and return the styled
    # spec (one Python source of the transform — the FE commits it as an undoable edit).
    # C2 render tier: theme.render caches the envelope by (figure hash, skill, style, theme version),
    # so a repeat style apply is a cache hit and no skill is re-run for a style change.
    if not isinstance(req.figure, dict) or "data" not in req.figure:
        raise HTTPException(status_code=400, detail="figure must be a Plotly spec with a data array")
    return {"figure": theme.render(req.figure, req.skill_id or "", req.style)}


# ── figures CRUD (sub-spec §3, BE-1) ──────────────────────────────────────────────────────────────
# The durable produced figure (db/schema.py figures; types.ts Figure) — backs the FE projectStore
# figure mutators. Declared AFTER the static /figures/* routes above so /figures/{figure_id} can't
# shadow /figures/styles or /figures/export (FastAPI matches in declaration order; sub-spec §3.2).
# Tenant = ctx.user_id only (§6.2); the figure id is client-authoritative + idempotent (§2.2).


class FigureBody(BaseModel):
    # The FE Figure on the wire (snake_case + opaque JSONB blobs the FE owns). The FE store adapter
    # owns the single camel↔snake translation; created_at is server-stamped, not honoured from input.
    model_config = {"extra": "ignore"}
    id: str | None = None
    project_id: str
    dataset_id: str | None = None
    skill_id: str | None = None
    job_id: str | None = None
    title: str = "Untitled figure"
    spec: dict | None = None
    provenance: dict | None = None
    methods: dict | None = None
    legend: dict | None = None
    guardrails: list | None = None
    table_stats: dict | None = None
    data_check: dict | None = None
    data_fit: dict | None = None
    parent_figure_id: str | None = None
    variant_label: str | None = None
    frozen: bool = False


class FigurePatch(BaseModel):
    # Partial update — only the editable fields (sub-spec §3.3); unset fields are left untouched.
    model_config = {"extra": "ignore"}
    title: str | None = None
    spec: dict | None = None
    frozen: bool | None = None
    variant_label: str | None = None


@router.get("/figures")
def list_figures(project_id: str | None = None, repo=Depends(_library_repo),
                 ctx: AuthContext = Depends(require_user)):
    return {"figures": repo.list_figures(ctx.user_id, project_id)}


@router.post("/figures")
def create_figure(body: FigureBody, repo=Depends(_library_repo),
                  ctx: AuthContext = Depends(require_user)):
    try:
        return repo.upsert_figure(ctx.user_id, ctx.email, body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown project") from exc


@router.get("/figures/{figure_id}")
def get_figure(figure_id: str, repo=Depends(_library_repo),
               ctx: AuthContext = Depends(require_user)):
    fig = repo.get_figure(ctx.user_id, figure_id)
    if fig is None:
        raise HTTPException(status_code=404, detail="unknown figure")
    return fig


@router.patch("/figures/{figure_id}")
def patch_figure(figure_id: str, body: FigurePatch, repo=Depends(_library_repo),
                 ctx: AuthContext = Depends(require_user)):
    fig = repo.update_figure(ctx.user_id, figure_id, body.model_dump(exclude_unset=True))
    if fig is None:
        raise HTTPException(status_code=404, detail="unknown figure")
    return fig


@router.delete("/figures/{figure_id}")
def delete_figure(figure_id: str, repo=Depends(_library_repo),
                  ctx: AuthContext = Depends(require_user)):
    removed = repo.delete_figure(ctx.user_id, figure_id)
    if removed == 0:
        raise HTTPException(status_code=404, detail="unknown figure")
    return {"ok": True, "id": figure_id}

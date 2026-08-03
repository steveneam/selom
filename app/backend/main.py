import pathlib

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from auth.policy import enforce_auth
from routers import ai, cloud, data, extract, figures, gene_sets, jobs, library, litsynth, papers, reproduction, skills, system

# Deny-by-default (auth-multitenancy spec D2). The verifier runs on EVERY route; `auth/policy.py`
# holds the explicit public allow-list, so a new route is private unless someone writes down that it
# is not. No-op in `dev` mode (DevVerifier returns a fixed tenant and never raises), so the inner
# loop and every existing test are unaffected — it only bites under SELOM_AUTH_MODE=clerk.
app = FastAPI(title="Selom API", dependencies=[Depends(enforce_auth)])

# ★D bridge: serve the staged X3 panel thumbnails (repro_assets) as read-only static files at
# /repro-assets/{slug}/{panel_key}.png. Presentational only — never a score input. Mounted only
# when the tree exists so a fresh clone without staged assets still boots.
_REPRO_ASSETS = pathlib.Path(__file__).resolve().parent / "repro-assets"
if _REPRO_ASSETS.is_dir():
    app.mount("/repro-assets", StaticFiles(directory=str(_REPRO_ASSETS)), name="repro-assets")

app.include_router(ai.router)
app.include_router(system.router)
app.include_router(skills.router)
app.include_router(gene_sets.router)
app.include_router(papers.router)
app.include_router(reproduction.router)
app.include_router(data.router)
app.include_router(extract.router)
app.include_router(jobs.router)
app.include_router(litsynth.router)
app.include_router(figures.router)
app.include_router(library.router)
app.include_router(cloud.router)

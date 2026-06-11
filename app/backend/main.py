from fastapi import FastAPI, Request, UploadFile
from skills.contract import run_skill, load_skill
import pathlib
import tempfile
import shutil

app = FastAPI(title="Selom API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/skills/{skill_id}")
def describe(skill_id: str):
    return load_skill(skill_id).model_dump()        # registry-driven UI reads this


@app.post("/skills/{skill_id}/run")
async def run(skill_id: str, request: Request, matrix: UploadFile):
    # Preserve the upload's extension so skills can tell .h5ad (scRNA) from .csv (bulk).
    suffix = pathlib.Path(matrix.filename or "").suffix or ".h5ad"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        shutil.copyfileobj(matrix.file, f)
        path = f.name
    # Tuning params arrive as the query string; the contract fills skill defaults and
    # each runner coerces types. This is skill-agnostic — every Verified skill runs here.
    params = dict(request.query_params)
    spec = run_skill(skill_id, path, params)
    return {"figure": spec}                          # Plotly JSON -> frontend

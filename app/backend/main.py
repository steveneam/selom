from fastapi import FastAPI, UploadFile
from skills.contract import run_skill, load_skill
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
async def run(skill_id: str, matrix: UploadFile, n_neighbors: int = 15,
              n_pcs: int = 50, color_by: str = "leiden"):
    with tempfile.NamedTemporaryFile(suffix=".h5ad", delete=False) as f:
        shutil.copyfileobj(matrix.file, f)
        path = f.name
    spec = run_skill(skill_id, path,
                     {"n_neighbors": n_neighbors, "n_pcs": n_pcs, "color_by": color_by})
    return {"figure": spec}                          # Plotly JSON -> frontend

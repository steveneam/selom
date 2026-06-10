# Selom backend

FastAPI skeleton for the Selom no-code multi-omics figure SaaS. Skills are self-describing
`skill.json` contracts + a runner that returns an **editable Plotly figure spec** (never a
baked image). The default install is LIGHT and runs offline stub skills; the heavy scverse
stack is opt-in behind the `omics` extra.

## Prerequisites

`uv` is installed at `C:/Users/seamegdool/.local/bin/uv.exe`. The system Python is 3.10, so
install the pinned interpreter (`.python-version` -> 3.12) with uv:

```
uv python install 3.12
```

## Run (light — offline stubs, zero heavy deps)

```
uv sync                              # installs the light core only
uv run uvicorn main:app --reload     # serves on http://127.0.0.1:8000
```

Endpoints:
- `GET  /health`              -> `{"status": "ok"}`
- `GET  /skills/{skill_id}`   -> the SkillSpec (describe; drives the UI)
- `POST /skills/{skill_id}/run` (multipart `matrix` upload) -> `{"figure": <Plotly spec>}`

The default `umap_scrna` run path uses the offline stub in `skills/umap_scrna/run.py`, so the
full spine (registry -> contract -> engine -> editable spec) works with no heavy deps.

## Enable the real scanpy skills

```
uv sync --extra omics                # scanpy, anndata, scvi-tools, kaleido, ...
```

Then point the `umap_scrna` skill at the real engine (`skills/umap_scrna/run_scanpy.py`),
which runs Scanpy QC -> normalize -> PCA -> neighbors -> Leiden -> UMAP -> Plotly.

## Tests

```
uv sync --extra dev
uv run pytest
```

`tests/test_contract.py` validates the SkillSpec loads and the stub runner returns a Plotly
figure spec (`data` + `layout`) — no heavy deps required.

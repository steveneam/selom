"""Live regression for the integration (Melody) skill on real multi-library scRNA.

The dependency-free stub is covered by the golden suite (``test_skills_golden``). This adds
the REAL-engine check: Selom Melody (our clean-room Harmony-method engine — no harmonypy)
actually co-embeds the 4 deposited GSE201356 organoid libraries into one editable UMAP,
taking the integration branch (not the single-batch fallback). Skipped when scanpy or the
owner-machine h5ad is absent, so CI stays green.
"""

import importlib.util
from pathlib import Path

import pytest

from skills.contract import run_skill

HANI_H5AD = Path("D:/selom-data/hani/processed/hani_irpe_subset.h5ad")
_HAS_SCANPY = importlib.util.find_spec("scanpy") is not None


@pytest.mark.skipif(
    not (_HAS_SCANPY and HANI_H5AD.exists()),
    reason="scanpy or the Hani organoid h5ad not present (owner machine only)",
)
def test_integration_melody_mixes_hani_libraries(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")
    fig = run_skill(
        "integration",
        str(HANI_H5AD),
        {"batch_key": "sample", "color_by": "sample", "n_pcs": 50, "n_neighbors": 15},
    )
    # The real Melody branch ran (title names it) — not the single-batch fallback.
    assert "Melody" in fig["layout"]["title"]["text"]
    # Each of the 4 deposited libraries appears as a trace in the integrated UMAP,
    # and every trace carries real coordinates.
    assert len(fig["data"]) == 4
    assert all(t.get("x") and t.get("y") for t in fig["data"])

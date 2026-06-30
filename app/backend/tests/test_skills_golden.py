"""B2 skills: contract + golden-image snapshot tests.

Each skill emits an editable Plotly spec from its dependency-free STUB (pinned via
``SELOM_SKILLS_ENGINE=stub``), compared byte-for-byte to a committed golden
snapshot in ``tests/golden/``. This mirrors ``test_contract``'s stub-pinning: the
goldens stay deterministic regardless of which heavy deps are installed. Real-engine
numerical validation against an R oracle is a later bucket (B4 / RISKS #7).

Regenerate goldens after an intentional change: ``python tests/regen_golden.py``.
"""

import json
import pathlib

import pytest

from skills.contract import load_skill, run_skill

SKILLS = [
    "cluster", "violin", "deg", "volcano", "heatmap", "enrichment", "go_graph", "pathway",
    "markers", "annotate", "trajectory", "pca", "composition", "proteomics_de", "gsea",
    "corr_heatmap", "upset", "scorecard", "normalization_qc", "sankey", "string_network",
    "cepo", "boxplot", "pvca", "regression", "integration", "pseudotime_genes",
    "diff_abundance", "ssgsea", "erg_traces", "erg_bwave_bar", "erg_intensity_response",
    "erg_flicker", "mixing_metrics",
]
GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


@pytest.mark.parametrize("skill_id", SKILLS)
def test_skill_spec_loads(skill_id):
    spec = load_skill(skill_id)
    assert spec.id == skill_id
    assert spec.engine == "python"
    # Skills live flat (skills/<id>/) or in the proprietary namespace (skills/proprietary/<id>/).
    assert spec.entrypoint in (
        f"skills.{skill_id}.run:run", f"skills.proprietary.{skill_id}.run:run"
    )
    assert any(o["kind"] == "plotly_spec" for o in spec.outputs)


@pytest.mark.parametrize("skill_id", SKILLS)
def test_skill_golden(skill_id):
    figure = run_skill(skill_id, "unused", {})

    # Editable Plotly spec: a non-empty data list + a layout dict.
    assert isinstance(figure, dict)
    assert isinstance(figure.get("data"), list) and figure["data"]
    assert isinstance(figure.get("layout"), dict)
    # Plain JSON only — no numpy / Plotly base64 leakage (round-trips unchanged).
    assert json.loads(json.dumps(figure)) == figure

    golden_path = GOLDEN_DIR / f"{skill_id}.json"
    assert golden_path.exists(), f"missing golden for {skill_id} (run tests/regen_golden.py)"
    golden = json.loads(golden_path.read_text())
    assert figure == golden, f"{skill_id} stub output drifted from its golden snapshot"

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
    "erg_flicker", "mixing_metrics", "facs_gating", "venn", "forest", "qq",
    "umap_scrna",
]
GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


def test_every_installed_skill_has_a_golden():
    """The list above is HAND-maintained, so a new skill can ship with no pinned stub and
    nothing fails — the gap this closes. (The source review claimed this file "picks it up
    automatically"; it does not, and a new plot type is exactly when that costs you.)

    Extending the parametrize list is the whole fix: add the id, run
    ``python tests/regen_golden.py``, commit the snapshot.
    """
    from skills.registry import list_skill_ids

    missing = sorted(set(list_skill_ids()) - set(SKILLS))
    assert not missing, (
        f"installed skills with no golden snapshot: {', '.join(missing)} — add them to "
        "SKILLS above and run `python tests/regen_golden.py`"
    )


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    # `umap_scrna` predates the shared selector and reads its OWN env var, so the line above
    # never reached it — with scanpy installed it resolved to the real scanpy engine, tried to
    # open the literal path "unused", and raised. That is the whole reason the flagship P0 skill
    # had no golden: it could not be added without this line, and nothing said so.
    monkeypatch.setenv("SELOM_UMAP_ENGINE", "stub")


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

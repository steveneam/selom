from skills.contract import load_skill, run_skill


def test_load_skill_validates():
    spec = load_skill("umap_scrna")
    assert spec.id == "umap_scrna"
    assert spec.engine == "python"
    assert spec.entrypoint == "skills.umap_scrna.run:run"


def test_run_skill_returns_figure_spec():
    # Uses the offline stub (no heavy deps); data_path is ignored by the stub.
    figure = run_skill("umap_scrna", "unused", {})
    assert isinstance(figure, dict)
    assert "data" in figure
    assert "layout" in figure

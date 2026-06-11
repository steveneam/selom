from skills.contract import load_skill, run_skill


def test_load_skill_validates():
    spec = load_skill("umap_scrna")
    assert spec.id == "umap_scrna"
    assert spec.engine == "python"
    assert spec.entrypoint == "skills.umap_scrna.run:run"


def test_run_skill_returns_figure_spec(monkeypatch):
    # Force the dependency-free stub so this passes identically whether or not the
    # scverse stack is installed; data_path is ignored by the stub.
    monkeypatch.setenv("SELOM_UMAP_ENGINE", "stub")
    figure = run_skill("umap_scrna", "unused", {})
    assert isinstance(figure, dict)
    assert "data" in figure
    assert "layout" in figure

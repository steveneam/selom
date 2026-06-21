"""L3 — table synthesis (P2): tableless skill figure -> canonical Statistics table.

Each synthetic figure mirrors the real trace/string shape documented in
``docs/reproduction-engine/skill-table-schemas.md``. Read-only, recomputes nothing (S1);
every synthesized table is tagged ``synthesized: True`` (S3); an unsupported skill -> None (S4).
"""

from __future__ import annotations

from extract.synthesize import synthesize_table


def test_pca_from_axis_titles():
    fig = {"layout": {"xaxis": {"title": {"text": "PC1 (39.7%)"}},
                      "yaxis": {"title": {"text": "PC2 (18.2%)"}}}}
    t = synthesize_table("pca", fig)
    assert t["columns"] == ["component", "variance %"]
    assert t["rows"] == [["PC1", 39.7], ["PC2", 18.2]]
    assert t["synthesized"] is True


def test_composition_from_bar_traces():
    fig = {"data": [
        {"name": "Control", "x": ["Müller", "Rod", "Cone"], "y": [40.0, 30.0, 30.0]},
        {"name": "AMD", "x": ["Müller", "Rod", "Cone"], "y": [35.0, 40.0, 25.0]},
    ]}
    t = synthesize_table("composition", fig)
    assert t["columns"] == ["category", "Control", "AMD"]
    assert t["rows"][0] == ["Müller", 40.0, 35.0]


def test_cluster_sizes_and_silhouette():
    fig = {"data": [{"type": "bar", "x": ["0", "1", "2"], "y": [100, 50, 50]}],
           "layout": {"title": {"subtitle": {"text": "3 clusters · silhouette 0.42 · res 1.0"}}}}
    t = synthesize_table("cluster", fig)
    assert t["rows"] == [["0", 100, 50.0], ["1", 50, 25.0], ["2", 50, 25.0]]
    assert "silhouette 0.42" in t["title"]


def test_pvca_fractions_to_percent():
    fig = {"data": [{"type": "bar", "x": ["batch", "condition", "residual"], "y": [0.2, 0.5, 0.3]}]}
    t = synthesize_table("pvca", fig)
    assert t["rows"] == [["batch", 20.0], ["condition", 50.0], ["residual", 30.0]]


def test_regression_from_annotation():
    fig = {"layout": {"annotations": [{"text": "R² = 0.97   slope = 0.0186   p = 1.3e-04"}]}}
    t = synthesize_table("regression", fig)
    assert t["rows"] == [["R²", "0.97"], ["slope", "0.0186"], ["p", "1.3e-04"]]


def test_integration_before_after():
    fig = {"layout": {"title": {"subtitle": {"text": "batch mixing 0.49 → 0.83 (kNN entropy, 1=fully mixed)"}}}}
    t = synthesize_table("integration", fig)
    assert t["rows"] == [["batch mixing (kNN entropy)", 0.49, 0.83]]


def test_trajectory_structure_counts():
    fig = {"layout": {"title": {"subtitle": {"text": "DPT · 9 clusters · 12 edges (≥0.1) · 3 lineage(s)"}}}}
    t = synthesize_table("trajectory", fig)
    assert t["rows"] == [["clusters", 9], ["edges", 12], ["lineages", 3]]


def test_unsupported_skill_returns_none():
    assert synthesize_table("go_graph", {"data": []}) is None       # L4 territory, never forced
    assert synthesize_table("pca", "not a figure") is None
    assert synthesize_table("volcano", {"data": []}) is None        # already has a native table


def test_empty_figure_is_honest_none():
    assert synthesize_table("composition", {"data": []}) is None
    assert synthesize_table("regression", {"layout": {}}) is None

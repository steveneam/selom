"""Layered metric reader (extract/readers.py) — L1 skill-specific + L2 generic.

Fixtures mirror the REAL skill output shapes inventoried in
``docs/reproduction-engine/skill-table-schemas.md`` (volcano de_table, pca axis titles, the gsea/
cepo key→value tables, figure-string percentages), so the reader is tested against the contract it
reads, not a hopeful mock.
"""

from __future__ import annotations

import reproduction as R

from extract.readers import (
    L1,
    L2,
    L3,
    SRC_FIGURE,
    SRC_SYNTH,
    SRC_TABLE,
    panel_extractor,
    panel_readings,
    read_metric,
)


def _de_table(rows, title="Differential expression"):
    return {"columns": ["gene", "log2FC", "padj", "direction"], "rows": rows, "title": title}


# --- L1: volcano DE counts ----------------------------------------------------


def test_volcano_de_counts_uncapped_exact():
    rows = [["A", 2.1, 0.001, "up"], ["B", 1.5, 0.01, "up"], ["C", -2.0, 0.002, "down"],
            ["D", 0.1, 0.9, "n.s."]]
    table = _de_table(rows)
    up = read_metric("volcano", "de_up", None, table)
    down = read_metric("volcano", "de_down", None, table)
    total = read_metric("volcano", "de_total", None, table)
    assert (up.value, down.value, total.value) == (2, 1, 3)
    assert up.layer == L1 and up.source == SRC_TABLE and up.confidence == 1.0
    # n.s. rows never count toward the DE total.


def test_volcano_de_total_capped_is_lower_bound_with_low_confidence():
    rows = [["g%d" % i, 2.0, 0.001, "up"] for i in range(300)]
    table = _de_table(rows, title="Differential expression (top 300 of 1450 by adjusted p)")
    total = read_metric("volcano", "de_total", None, table)
    assert total.value == 300 and total.confidence == 0.7
    assert "lower bound" in total.note


def test_volcano_only_handles_de_metrics():
    assert read_metric("volcano", "pc1_var", None, _de_table([])) is None


# --- L1: pca variance from axis titles ----------------------------------------


def _pca_fig(pc1="PC1 (39.7%)", pc2="PC2 (18.5%)"):
    return {"data": [], "layout": {"xaxis": {"title": {"text": pc1}},
                                    "yaxis": {"title": {"text": pc2}}}}


def test_pca_variance_from_axis_titles():
    fig = _pca_fig()
    assert read_metric("pca", "pc1_var", fig, None).value == 39.7
    pc2 = read_metric("pca", "pc2_var", fig, None)
    assert pc2.value == 18.5 and pc2.layer == L1 and pc2.source == SRC_FIGURE


def test_pca_handles_bare_string_title():
    fig = {"layout": {"xaxis": {"title": "PC1 (42.0%)"}}}
    assert read_metric("pca", "pc1_var", fig, None).value == 42.0


# --- L2: generic count (enrichment / unknown direction tables) ----------------


def test_generic_count_rows_for_n_terms():
    table = {"columns": ["pathway", "-log10 padj", "overlap genes"],
             "rows": [["P1", 5.0, 12], ["P2", 4.1, 8], ["P3", 3.0, 5]]}
    r = read_metric("enrichment", "n_terms", None, table)
    assert r.value == 3 and r.layer == L2


def test_generic_directional_count_for_unknown_skill():
    # diff_abundance-style direction vocab (expanding/shrinking) handled generically.
    table = {"columns": ["cluster", "log2FC abundance", "adj p", "cells", "direction"],
             "rows": [["0", 1.2, 0.01, 500, "expanding"], ["1", -0.9, 0.04, 300, "shrinking"],
                      ["2", 1.1, 0.02, 220, "expanding"]]}
    up = read_metric("diff_abundance", "de_up", None, table)
    assert up.value == 2 and up.layer == L2  # no L1 reader → generic directional count


def test_generic_total_prefers_title_total():
    rows = [["g%d" % i, 2.0, 0.001, "up"] for i in range(300)]
    table = _de_table(rows, title="Differential expression (top 300 of 980 by adjusted p)")
    # an unknown skill (no L1) asking for a *total* should read the true total from the title.
    r = read_metric("someskill", "n_total", None, table)
    assert r.value == 980 and r.layer == L2


# --- L2: named cell lookup (gsea NES of a named term) -------------------------


def test_named_cell_lookup_by_key():
    table = {"columns": ["gene set", "NES", "NOM p", "FDR q"],
             "rows": [["HALLMARK_INFLAMMATION", 2.31, 0.001, 0.01],
                      ["HALLMARK_APOPTOSIS", -1.8, 0.02, 0.08]]}
    r = read_metric("gsea", "nes", None, table, key="HALLMARK_INFLAMMATION")
    assert r.value == 2.31 and r.source == SRC_TABLE


# --- L2: figure-string percentage ---------------------------------------------


def test_figure_number_percentage():
    fig = {"layout": {"title": {"text": "PVCA — 12 PCs, 86% of variance",
                                "subtitle": {"text": "batch 42.0% · residual 12.0%"}}}}
    r = read_metric("pvca", "batch_var", fig, None)
    assert r.value == 86.0 and r.layer == L2 and r.source == SRC_FIGURE


# --- L3: synthesize a table when the skill emits none -------------------------


def test_l3_synthesizes_table_for_tableless_composition():
    # composition emits no native table; its %s live in bar traces. L3 synthesizes a canonical
    # table from the figure, then the named-cell reader resolves the category — tagged synthesized.
    fig = {"data": [
        {"name": "Control", "x": ["Müller", "Rod"], "y": [40.0, 60.0]},
        {"name": "AMD", "x": ["Müller", "Rod"], "y": [35.0, 65.0]},
    ]}
    r = read_metric("composition", "muller_pct", fig, None, key="Müller")
    assert r.layer == L3 and r.source == SRC_SYNTH
    assert r.value == 40.0                     # Control (first numeric column)
    assert 0 < r.confidence < 0.6              # synthesized → below a native-table read
    assert "synthesized" in r.note


def test_l3_umap_cluster_count_via_synthesis():
    fig = {"data": [
        {"type": "scatter", "name": "0", "x": [1, 2, 3], "y": [1, 2, 3]},
        {"type": "scatter", "name": "1", "x": [4, 5], "y": [4, 5]},
        {"type": "scatter", "name": "2", "x": [6], "y": [6]},
    ]}
    r = read_metric("umap_scrna", "n_clusters", fig, None)
    assert r.layer == L3 and r.value == 3      # 3 named scatter traces = 3 clusters


def test_l3_never_overrides_a_native_table():
    # when a native table is present, L3 synthesis is not consulted (S5).
    table = {"columns": ["pathway", "-log10 padj"], "rows": [["P1", 5.0], ["P2", 4.0]]}
    r = read_metric("enrichment", "n_terms", None, table)
    assert r.layer == L2 and r.source == SRC_TABLE


# --- panel-level extractor (run_panel-compatible) -----------------------------


def _panel(skill_id, metrics):
    return R.Panel(paper_id="t", figure="1", panel="", skill_id=skill_id,
                   golden=[R.Golden(metric=m, value=0) for m in metrics])


def test_panel_extractor_omits_unreadable_metrics():
    panel = _panel("volcano", ["de_up", "de_down", "de_total", "mystery_metric"])
    table = _de_table([["A", 2.0, 0.01, "up"], ["B", -1.0, 0.02, "down"]])
    computed = panel_extractor(panel, None, table)
    assert computed == {"de_up": 1, "de_down": 1, "de_total": 2}
    assert "mystery_metric" not in computed  # unreadable → omitted, not None (≠ a FAIL)


def test_panel_readings_record_every_attempt():
    panel = _panel("volcano", ["de_up", "mystery_metric"])
    table = _de_table([["A", 2.0, 0.01, "up"]])
    readings = {r.metric: r for r in panel_readings(panel, None, table)}
    assert readings["de_up"].value == 1
    assert readings["mystery_metric"].value is None and readings["mystery_metric"].confidence == 0.0

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


def test_proteomics_de_shares_the_de_table_l1_reader():
    # proteomics_de emits the canonical de_table; it must read at L1 so de_total = up + down,
    # NOT the L2 row count (which would return the tested-protein total — the schema-doc trap).
    rows = [["A", 2.1, 0.001, "up"], ["B", 1.5, 0.01, "up"], ["C", -2.0, 0.002, "down"],
            ["D", 0.1, 0.9, "n.s."]]
    table = _de_table(rows)
    up = read_metric("proteomics_de", "de_up", None, table)
    total = read_metric("proteomics_de", "de_total", None, table)
    assert (up.value, total.value) == (2, 3)  # 3 = up + down, not 4 (all rows)
    assert up.layer == L1 and up.source == SRC_TABLE


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


# --- L1: umap_scrna analyzed cell count (Slice 1) -----------------------------


def _umap_fig():
    # The real umap_scrna output shape: one scatter trace per cluster, x/y point arrays.
    return {"data": [
        {"type": "scatter", "name": "0", "x": [1, 2, 3], "y": [1, 2, 3]},
        {"type": "scatter", "name": "1", "x": [4, 5], "y": [4, 5]},
        {"type": "scatter", "name": "2", "x": [6], "y": [6]},
    ]}


def test_umap_n_cells_from_plotted_points():
    # n_cells = total plotted points across the embedding traces — the read-back twin of the
    # printed dataset size (extract.golden.extract_dataset_size). 3 + 2 + 1 = 6.
    r = read_metric("umap_scrna", "n_cells", _umap_fig(), None)
    assert r.value == 6 and r.layer == L1 and r.source == SRC_FIGURE and r.confidence == 1.0


def test_umap_l1_n_cells_and_l3_n_clusters_coexist():
    # The same skill: n_cells reads at L1 (point count), n_clusters still falls to L3 synthesis
    # (trace count) — the L1 reader returns None for anything but n_cells, so neither shadows.
    fig = _umap_fig()
    assert read_metric("umap_scrna", "n_cells", fig, None).layer == L1
    assert read_metric("umap_scrna", "n_clusters", fig, None).layer == L3


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


# --- the multi-table union (docs/stats-tables/spec.md D1/D4) -------------------


def test_g2b_the_l3_synthesis_gate_survives_the_union():
    """G2b — the single most dangerous line in this change.

    ``read_metric`` gates L3 synthesis on "the skill emitted no native table". Under the normalizer
    the old ``table is None`` test is permanently False for any caller passing a list, which would
    silently convert every tableless skill to NEEDS_RECIPE — a plumbing regression wearing the
    costume of an honest verdict. ``[]`` must therefore behave EXACTLY as ``None`` did."""
    fig = {"data": [
        {"type": "scatter", "name": "0", "x": [1, 2, 3], "y": [1, 2, 3]},
        {"type": "scatter", "name": "1", "x": [4, 5], "y": [4, 5]},
        {"type": "scatter", "name": "2", "x": [6], "y": [6]},
    ]}
    from_none = read_metric("umap_scrna", "n_clusters", fig, None)
    from_empty = read_metric("umap_scrna", "n_clusters", fig, [])
    assert from_none is not None and from_none.layer == L3 and from_none.value == 3
    assert from_empty is not None, "[] must synthesize exactly as None did — else the score drops silently"
    assert from_empty.model_dump() == from_none.model_dump()


def test_l3_never_overrides_a_native_table_in_a_list():
    """S5 through the union: a present table — bare OR in a list — still blocks synthesis."""
    table = {"columns": ["pathway", "-log10 padj"], "rows": [["P1", 5.0], ["P2", 4.0]]}
    bare = read_metric("enrichment", "n_terms", None, table)
    listed = read_metric("enrichment", "n_terms", None, [table])
    assert bare.layer == L2 and bare.source == SRC_TABLE
    assert listed.model_dump() == bare.model_dump()


def test_a_one_element_list_reads_identically_to_a_bare_table():
    """G3 at the reader: wrapping the only table in a list changes no reading, on any layer."""
    table = _de_table([["A", 2.0, 0.01, "up"], ["B", -1.0, 0.02, "down"]])
    for metric in ("de_up", "de_down", "de_total"):
        bare = read_metric("volcano", metric, None, table)
        listed = read_metric("volcano", metric, None, [table])
        assert listed.model_dump() == bare.model_dump(), metric


def test_n_tables_are_tried_in_array_order_and_first_hit_wins():
    """D4 — no `role` field: order is array order, and a metric is read off the first table that
    yields it. A second table is genuinely reachable; a first table that answers still wins."""
    ranked = {"columns": ["arm", "median"], "rows": [["WT", 12.0], ["KO", 4.0]], "title": "Ranked values"}
    pairwise = {"columns": ["pair", "p"], "rows": [["WT vs KO", 0.004]], "title": "Pairwise p-values"}

    # `n_total` is a row count: table 1 has 2 rows, table 2 has 1 — first in order wins.
    assert read_metric("lollipop", "n_total", None, [ranked, pairwise]).value == 2
    assert read_metric("lollipop", "n_total", None, [pairwise, ranked]).value == 1
    # A named cell only table 2 carries IS reachable — that is the point of the second table.
    hit = read_metric("lollipop", "wtvsko", None, [ranked, pairwise], key="WT vs KO")
    assert hit is not None and hit.value == 0.004


def test_the_figure_reader_stays_the_last_resort_across_n_tables():
    """The figure layer is the weakest (confidence 0.4), so a TABLE read on the second table must
    still beat it — it cannot join the per-table loop or table 2 becomes unreachable for any metric
    a figure string happens to answer."""
    fig = {"layout": {"xaxis": {"title": {"text": "PC1 (39.7%)"}}}}
    empty = {"columns": ["k", "v"], "rows": [], "title": "nothing"}
    real = {"columns": ["term", "score_pct"], "rows": [["shared_var", 12.5]], "title": "Variance"}
    r = read_metric("someskill", "shared_var", fig, [empty, real], key="shared_var")
    assert r is not None and r.source == SRC_TABLE and r.value == 12.5


def test_panel_extractor_and_readings_accept_the_union():
    """Both public entry points take the union — they delegate to `read_metric`, and that delegation
    is the reason neither needs its own narrowing."""
    panel = _panel("volcano", ["de_up", "de_down"])
    table = _de_table([["A", 2.0, 0.01, "up"], ["B", -1.0, 0.02, "down"]])
    assert panel_extractor(panel, None, [table]) == panel_extractor(panel, None, table)
    listed = {r.metric: r.value for r in panel_readings(panel, None, [table])}
    assert listed == {"de_up": 1, "de_down": 1}


def test_a_synthesized_table_INLINE_in_a_list_is_still_scored_as_synthesized():
    """The trap slice 4 opens, and the one worth guarding hardest.

    Provenance used to be decided by POSITION: only `read_metric`'s own L3 fallback branch re-tagged,
    so a synthesized table was known to be synthesized because of where it was built. Once a skill
    may attach a native table AND its L3 summary in one list (`ALSO_SYNTHESIZE`), that stops holding
    — and the appended table would have been read at full native confidence, silently OVERSTATING
    the provenance of a re-shaped value on a reproducibility score. Every synthesizer stamps
    `synthesized: True`, so the flag on the table is the honest authority."""
    native = {"columns": ["group A", "group B", "p"], "rows": [["Control", "KO", 0.004]],
              "title": "Pairwise comparisons"}
    synth = {"columns": ["group", "n", "median"],
             "rows": [["Control", 12, 412.5], ["Rescue", 9, 301.4]],
             "title": "Distribution summary", "synthesized": True, "source": "figure"}

    # "Rescue" exists ONLY in the appended table, so this read must come from it. The metric is
    # deliberately not `*_n`/`*_count`: those match `_COUNT_RE`, and a row-count read would be
    # answered by table 1 first — correctly, but it would not exercise the appended table at all.
    tagged = read_metric("boxplot", "rescue_median", None, [native, synth], key="Rescue")
    assert tagged.layer == L3 and tagged.source == SRC_SYNTH
    assert "via L3-synthesized table" in tagged.note

    # The identical table without the flag is a native read — the flag, not the shape, decides.
    bare = {k: v for k, v in synth.items() if k not in ("synthesized", "source")}
    plain = read_metric("boxplot", "rescue_median", None, [native, bare], key="Rescue")
    assert plain.layer == L2 and plain.source == SRC_TABLE
    assert tagged.value == plain.value, "only the provenance differs, never the number"
    assert tagged.confidence < plain.confidence, "synthesized provenance must cost confidence"


def test_the_l3_fallback_is_not_double_tagged():
    """`_read_generic` tags by the table's flag, so the fallback branch must NOT re-tag on top —
    compounding the penalty twice would quietly halve a legitimate synthesized reading's confidence
    every time the code path changed."""
    fig = {"data": [
        {"type": "scatter", "name": "0", "x": [1, 2, 3], "y": [1, 2, 3]},
        {"type": "scatter", "name": "1", "x": [4, 5], "y": [4, 5]},
    ]}
    r = read_metric("umap_scrna", "n_clusters", fig, None)
    assert r.layer == L3 and r.source == SRC_SYNTH
    assert r.note.count("via L3-synthesized table") == 1, "tagged once, by one rule"
    assert r.confidence == round(min(0.5, 0.6) * 0.9, 3)

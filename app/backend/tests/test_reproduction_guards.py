"""Reproduction Engine guard registry (R1) — each guard fires on its trigger fixture.

The 14 SOP edge-case guards as first-class checks; the data-logic helpers are tested
directly (filter ceiling, batch purity, species prefixes, cell-type set delta).
"""

import reproduction_guards as G
from reproduction import (
    Golden,
    Inconsistency,
    MethodSub,
    OracleResult,
    Panel,
    DEPOSITED_RAW,
    WET_LAB,
)


# --- pure helpers -------------------------------------------------------------


def test_filter_ceiling_helper():
    assert G.filter_ceiling_unreachable(882, 1133) is True   # RPGRIP1 Fig 5 ceiling
    assert G.filter_ceiling_unreachable(1133, 78) is False


def test_batch_purity_helper():
    # Rod-2 is 4/4 MS-VUS (a batch cluster); Rod-1 is mixed.
    clusters = ["Rod-2", "Rod-2", "Rod-2", "Rod-2", "Rod-1", "Rod-1"]
    batches = ["MSVUS", "MSVUS", "MSVUS", "MSVUS", "Control", "MSVUS"]
    purity = G.batch_purity(clusters, batches)
    assert purity["Rod-2"] == 1.0
    assert purity["Rod-1"] == 0.5


def test_species_prefixes_helper():
    genes = ["GRCh38_RHO", "GRCh38_PDE6B", "mm10___Rho"]
    assert G.species_prefixes(genes) == {"GRCh38", "mm10"}
    assert G.species_prefixes(["RHO", "PDE6B"]) == set()  # no prefixes → single genome


def test_celltype_set_delta_helper():
    delta = G.celltype_set_delta(
        expected=["Rod", "Cone", "RGC"],
        recovered=["Rod", "Cone", "RPE"],
    )
    assert delta == {"missing": ["RGC"], "spurious": ["RPE"]}


# --- guards fire on their triggers --------------------------------------------


def _fired_ids(findings):
    return {f.guard_id for f in findings}


def test_registry_lists_all_14():
    reg = G.registry()
    assert len(reg) == 14
    assert [g["num"] for g in reg] == list(range(1, 15))


def test_inconsistency_guards():
    ctx = {"inconsistencies": [
        Inconsistency(kind="methods_vs_numbers"),
        Inconsistency(kind="figures_vs_methods"),
    ]}
    fired = _fired_ids(G.run_guards(ctx))
    assert {"methods_vs_numbers", "figures_vs_methods"} <= fired


def test_oracle_and_filter_guards():
    ctx = {
        "oracle": OracleResult(tool="edgeR", ran_on=DEPOSITED_RAW, agrees_with_paper=False),
        "filter": {"n_pass": 882, "golden": 1133},
    }
    fired = _fired_ids(G.run_guards(ctx))
    assert "authors_tool_misses" in fired   # → paper-irreproducible
    assert "filter_ceiling" in fired        # → structural-limit


def test_batch_and_genome_guards():
    ctx = {
        "batch_purity": {"Rod-2": 0.99, "Rod-1": 0.4},
        "gene_names": ["GRCh38_RHO", "mm10___Rho"],
        "integrated": False,
        "subclustering": True,
    }
    fired = _fired_ids(G.run_guards(ctx))
    assert {"batch_genotype_confound", "combined_genome_deposit", "subclustering_batch_confounded"} <= fired


def test_scope_and_method_sub_guards():
    panel = Panel(paper_id="p", figure="5", panel="D", scope=WET_LAB,
                  method_subs=[MethodSub(paper_tool="GLM-PCA", selom_tool="Harmony")])
    fired = _fired_ids(G.run_guards({"panel": panel}))
    assert "wet_lab_out_of_scope" in fired      # guard 7
    assert "measure_dont_assume" in fired       # guard 8 (delta_measured is None)


def test_gsea_term_count_guard():
    panel = Panel(paper_id="p", figure="6", panel="E", skill_id="gsea",
                  golden=[Golden(metric="venn.count.Rod-2", value=52)])
    fired = _fired_ids(G.run_guards({"panel": panel}))
    assert "gsea_engine_sensitivity" in fired   # guard 12


def test_mild_contrast_and_celltype_guards():
    ctx = {
        "contrast_term_counts": {"LCA-1": 17, "MS-VUS": 0},
        "celltypes": {"expected": ["Rod", "RGC"], "recovered": ["Rod", "RPE"]},
    }
    fired = _fired_ids(G.run_guards(ctx))
    assert "mild_contrast_zero_terms" in fired  # guard 5
    assert "annotation_set_delta" in fired      # guard 14


def test_no_guards_fire_on_clean_context():
    # A clean transcriptomic panel with measured substitutions and no traps.
    panel = Panel(paper_id="p", figure="1", panel="A", skill_id="pca",
                  method_subs=[MethodSub(paper_tool="edgeR", selom_tool="pyDESeq2",
                                         delta_measured="near-exact")])
    fired = _fired_ids(G.run_guards({"panel": panel, "env": {"pythonioencoding": "utf-8"}}))
    assert fired == set()

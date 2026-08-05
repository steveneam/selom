"""B4 auto methods-text — every skill yields cited, parameterized prose."""

from companions import methods
from skills.contract import SkillSpec, load_skill
from skills.registry import list_skill_ids


def test_every_skill_has_methods_text_and_citations():
    for skill_id in list_skill_ids():
        spec = load_skill(skill_id)
        out = methods.build(spec, {})
        assert out["text"].strip()
        # Each template names the skill via the Selom attribution sentence.
        assert f"v{spec.version}" in out["text"]
        assert f"skill '{skill_id}'" in out["text"]
        assert isinstance(out["citations"], list)


def test_methods_quote_resolved_params():
    deg = methods.build(load_skill("deg"), {"top_n": "25"})
    assert "top 25 genes" in deg["text"]
    assert any("DESeq2" in c for c in deg["citations"])

    volcano = methods.build(load_skill("volcano"), {"fc_threshold": "1.5"})
    assert "1.5" in volcano["text"]
    assert any("false discovery rate" in c for c in volcano["citations"])


def test_gsea_methods_template_is_specific_not_generic():
    # Library mode (no pasted gene_set) names the GO library + permutation NES + FDR.
    lib = methods.build(load_skill("gsea"), {"n_perm": "500"})
    assert "Gene Set Enrichment Analysis" in lib["text"]
    assert "gene=" not in lib["text"] and "gene_set=" not in lib["text"]  # not the raw-param dump
    assert "500 gene-set permutations" in lib["text"]
    assert any("PNAS" in c for c in lib["citations"])      # Subramanian 2005
    assert any("GSEApy" in c for c in lib["citations"])    # Fang 2023
    assert any("Gene Ontology" in c for c in lib["citations"])

    # Single-set mode (pasted members) names the set, drops the GO-library citation.
    single = methods.build(load_skill("gsea"), {"gene_set": "RHO,PRPH2,NRL", "set_name": "Rod set"})
    assert "Rod set" in single["text"]
    assert not any("Gene Ontology" in c for c in single["citations"])


def test_go_graph_methods_template_is_specific():
    out = methods.build(load_skill("go_graph"), {"top_n": "15", "namespace": "BP"})
    assert "is_a/part_of hierarchy" in out["text"]
    assert "top 15" in out["text"] and "BP namespace" in out["text"]
    assert any("Gene Ontology" in c for c in out["citations"])
    assert any("false discovery rate" in c for c in out["citations"])


def test_cepo_methods_template_is_specific():
    out = methods.build(load_skill("cepo"), {"n_genes": "12"})
    assert "differential stability" in out["text"]
    assert "top 12 differential-stability genes" in out["text"]
    assert any("Cepo" in c for c in out["citations"])


def test_pvca_methods_template_is_specific():
    out = methods.build(load_skill("pvca"), {"factors": "batch, cell_type"})
    assert "Principal Variance Component Analysis" in out["text"]
    assert "batch, cell_type" in out["text"]
    assert "factors=" not in out["text"]  # not the raw-param dump
    assert any("Sources of variation" in c for c in out["citations"])  # Boedigheimer 2008


def test_regression_methods_template_is_specific():
    out = methods.build(load_skill("regression"), {"x": "age", "y": "score"})
    assert "ordinary-least-squares" in out["text"]
    assert "score" in out["text"] and "age" in out["text"]
    assert any("SciPy" in c for c in out["citations"])


def test_unknown_skill_falls_back_to_generic():
    spec = SkillSpec(
        id="mystery",
        version="9.9.9",
        title="Mystery Skill",
        engine="python",
        omics="proteomics",
        entrypoint="x:y",
        inputs=[],
        param_spec={"alpha": {"type": "float", "default": 0.5}},
        outputs=[],
    )
    out = methods.build(spec, {"alpha": "0.9"})
    assert "Mystery Skill" in out["text"]
    assert "alpha=0.9" in out["text"]
    assert out["citations"] == []


# --- boxplot: two printed-vs-computed lies the prose↔param backlog pointed at -------------------


def _boxplot_text(params: dict) -> str:
    from skills.contract import load_skill

    return methods.build(load_skill("boxplot"), {"group": "condition", "value": "b_wave_uv",
                                                 **params})["text"]


def test_boxplot_strip_mode_claims_no_box_it_does_not_draw():
    """`style="strip"` hides the box entirely (zero width, no fill) and plots every value. The
    methods text used to describe "box-and-whisker … whiskers extending to 1.5× the IQR"
    UNCONDITIONALLY, so a strip figure shipped with prose about furniture the reader cannot see."""
    strip = _boxplot_text({"style": "strip"})
    assert "strip plot" in strip
    assert "every individual value" in strip
    assert "IQR" not in strip and "whisker" not in strip, "no box is drawn, so no box may be claimed"

    box = _boxplot_text({})
    assert "box-and-whisker" in box and "1.5× the IQR" in box, "the box branch must keep its claim"


def test_boxplot_ordering_sentence_follows_the_order_param():
    """`resolve_order` puts the categories the user NAMED first, in the order given, and only the
    remainder follow the descending-median sort. "groups are ordered by descending median" is
    therefore true exactly when the user named none — it was stated unconditionally."""
    auto = _boxplot_text({})
    assert "ordered by descending median" in auto

    named = _boxplot_text({"order": "Control, Untreated"})
    assert "Control, Untreated lead in that order" in named
    assert "remaining groups by descending median" in named


def test_boxplot_names_the_test_behind_its_stars_only_when_pairs_was_asked_for():
    """The stars are a published claim, so the test and any multiplicity correction are named. With
    no `pairs` there is no comparison, and the sentence must not appear at all."""
    none = _boxplot_text({})
    assert "compared with" not in none

    bh = _boxplot_text({"pairs": "Control~Untreated", "sig_test": "mannwhitney", "correction": "bh"})
    assert "Mann-Whitney U" in bh and "Benjamini-Hochberg" in bh

    raw = _boxplot_text({"pairs": "Control~Untreated"})
    assert "Welch" in raw
    assert "uncorrected for multiple comparisons" in raw, \
        "silence about multiplicity reads as 'corrected'; say which it is"

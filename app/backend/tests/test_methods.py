"""B4 auto methods-text — every skill yields cited, parameterized prose."""

import methods
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

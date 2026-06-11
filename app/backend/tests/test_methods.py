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

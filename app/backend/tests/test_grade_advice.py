"""grade_advice — the Layer A Phase 3 statistics advisory (POST /ai/explain request="grade_advice").

Advisory-only (spine invariant #4): grounds a per-skill statistics card (ai.grade) on the figure's
method, degrades clean with the gateway off (source="deterministic"), and never mutates. See
docs/ai-cross-stage-entry-points/build-spec.md Phase 3."""

from ai.gateway import (
    NullActionGateway,
    OperatorActionGateway,
    _deterministic_explain,
    _operator_input_key,
)
from ai.grade import grade_card


# --- the deterministic per-skill knowledge (ai.grade) -----------------------------------------------

def test_grade_card_deg_bulk_names_the_real_test():
    card = grade_card({"skill_id": "deg", "mode": "bulk"})
    assert card is not None
    assert "pyDESeq2" in card and "Wald" in card
    assert "Benjamini-Hochberg" in card


def test_grade_card_deg_modes_differ():
    # deg's advice must be mode-specific (the runner runs genuinely different tests per mode).
    tc = grade_card({"skill_id": "deg", "mode": "timecourse"})
    pb = grade_card({"skill_id": "deg", "mode": "pseudobulk"})
    sc = grade_card({"skill_id": "deg", "mode": "scrna"})
    assert "continuous" in tc and "trend" in tc.lower()
    assert "pseudobulk" in pb.lower()
    assert "Wilcoxon" in sc
    assert tc != pb != sc


def test_grade_card_deg_unresolved_mode_is_generic_not_bulk():
    # auto / absent mode is resolved from the DATA at run time (an .h5ad → scRNA Wilcoxon, else bulk),
    # which grade.py can't see from the figure — so it must give the generic deg card, NEVER commit to
    # bulk pyDESeq2 (that mislabels an scRNA deg). The `selom.` prefix is tolerated (either FE form).
    generic = grade_card({"skill_id": "deg"})
    assert generic == grade_card({"skill_id": "deg", "mode": "auto"})
    assert generic == grade_card({"skill_id": "selom.deg"})
    # The generic card names the modes without committing to one; the pinned bulk card is specific.
    assert "auto" in generic and "Wilcoxon" in generic
    assert generic != grade_card({"skill_id": "deg", "mode": "bulk"})


def test_deg_mode_aliases_all_resolve_to_a_real_card():
    # Catalog-subset guard: every alias target must be a real _DEG_MODE_CARDS key (a typo would KeyError),
    # and "auto" is intentionally unmapped (it falls through to the generic card, not a specific one).
    from ai.grade import _DEG_MODE_ALIASES, _DEG_MODE_CARDS

    assert set(_DEG_MODE_ALIASES.values()) <= set(_DEG_MODE_CARDS)
    assert "auto" not in _DEG_MODE_ALIASES


def test_grade_card_other_stat_skills_mapped():
    assert "hypergeometric" in grade_card({"skill_id": "enrichment"}).lower()
    assert "GSEA" in grade_card({"skill_id": "gsea"})
    assert "VISUALIZES" in grade_card({"skill_id": "volcano"}) or "visualizes" in grade_card({"skill_id": "volcano"}).lower()


def test_grade_card_unmapped_skill_is_none():
    # An unknown skill → None, so the caller emits an honest generic note (never a fabricated test).
    assert grade_card({"skill_id": "umap"}) is None
    assert grade_card({}) is None
    assert grade_card(None) is None


# --- _deterministic_explain + the gateway seam ------------------------------------------------------

def test_deterministic_explain_grade_advice_uses_the_card():
    text = _deterministic_explain("grade_advice", {"stats": {"skill_id": "deg", "mode": "bulk"}}, "")
    assert "pyDESeq2" in text


def test_deterministic_explain_grade_advice_generic_when_unmapped():
    # Unmapped skill → an honest generic advisory that names the skill, never a fabricated test.
    text = _deterministic_explain("grade_advice", {"stats": {"skill_id": "umap"}}, "")
    assert "umap" in text
    assert "pyDESeq2" not in text and "Wilcoxon" not in text


def test_null_gateway_grade_advice_degrade_clean():
    gw = NullActionGateway()
    text = gw.explain("grade_advice", {"stats": {"skill_id": "deg", "mode": "timecourse"}}, "which test?")
    assert isinstance(text, str) and "trend" in text.lower()


def test_operator_input_key_grade_advice_keys_on_skill_and_mode():
    assert _operator_input_key("grade_advice", {"stats": {"skill_id": "deg", "mode": "bulk"}}) == "deg:bulk"
    assert _operator_input_key("grade_advice", {"stats": {"skill_id": "enrichment"}}) == "enrichment"
    assert _operator_input_key("grade_advice", {"stats": {}}) is None


def test_operator_recording_replays_grade_advice():
    # The bundled recordings file carries a deg:bulk grade_advice entry (the zero-credit demo).
    gw = OperatorActionGateway.from_recordings()
    text = gw.explain("grade_advice", {"stats": {"skill_id": "deg", "mode": "bulk"}}, "any goal")
    assert "pyDESeq2" in text
    # differs from the deterministic card → the endpoint will label it source="ai" honestly
    assert text != _deterministic_explain("grade_advice", {"stats": {"skill_id": "deg", "mode": "bulk"}}, "any goal")


# --- POST /ai/explain endpoint ----------------------------------------------------------------------

def test_explain_endpoint_grade_advice_deterministic_source():
    from routers.ai import ExplainRequest, explain

    resp = explain(ExplainRequest(request="grade_advice", stats={"skill_id": "deg", "mode": "bulk"}))
    assert resp["request"] == "grade_advice"
    assert resp["source"] == "deterministic"  # NullActionGateway default
    assert "pyDESeq2" in resp["text"]
    assert resp["suggestions"] == []  # sweep suggestions are propose_sweep-only


def test_explain_endpoint_grade_advice_never_records_a_gap():
    from ai import gaps as g
    from routers.ai import ExplainRequest, explain

    explain(ExplainRequest(request="grade_advice", stats={"skill_id": "deg"}))
    assert g.list_gaps() == []

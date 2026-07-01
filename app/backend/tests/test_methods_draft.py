"""draft_methods — the Layer A Phase 4 methods draft (POST /ai/explain request="draft_methods").

Informational + draft-discipline (spine invariant #4): polishes a figure's DETERMINISTIC methods
prose (``base_text``, from ``companions.methods``). The deterministic fallback IS ``base_text``
verbatim, so gateway-off returns the honest draft (``source="deterministic"``, no ✨) and a no-op
polish stays deterministic — the honesty lever. Never mutates, never records a gap. See
docs/methods-draft/spec.md."""

from ai.gateway import (
    NullActionGateway,
    OperatorActionGateway,
    _deterministic_explain,
    _operator_input_key,
    build_explain_prompt,
)

_BASE = (
    "Differential expression was assessed for the KO-versus-WT contrast with PyDESeq2 and the Wald "
    "test; the top 50 genes are reported (Benjamini-Hochberg padj). Analysis was performed using "
    "Selom (skill 'deg' v3)."
)


# --- the deterministic fallback IS base_text (the honesty lever) ------------------------------------

def test_deterministic_explain_draft_methods_returns_base_text_verbatim():
    # The deterministic draft is the run's own methods prose, returned UNCHANGED — the fallback the
    # live polish is compared against, so a no-op polish is honestly labelled deterministic.
    assert _deterministic_explain("draft_methods", {"base_text": _BASE}, "tighten it") == _BASE


def test_deterministic_explain_draft_methods_empty_when_no_base_text():
    # No prose to polish → an empty string (never a fabricated methods paragraph).
    assert _deterministic_explain("draft_methods", {}, "polish") == ""
    assert _deterministic_explain("draft_methods", {"base_text": None}, "polish") == ""


def test_null_gateway_draft_methods_degrade_clean():
    gw = NullActionGateway()
    assert gw.explain("draft_methods", {"base_text": _BASE}, "match Nature's tone") == _BASE


# --- the live prompt grounds on base_text + preserves every fact ------------------------------------

def test_build_explain_prompt_draft_methods_grounds_and_guards():
    prompt = build_explain_prompt("draft_methods", {"base_text": _BASE}, "tighten and match a journal")
    assert "base_text" in prompt
    # It must instruct polish-only + preservation (no invented / dropped numbers or citations).
    assert "POLISH" in prompt and "PRESERVE" in prompt
    assert _BASE in prompt  # the exact prose is appended so the model rewrites the real text


# --- operator keying + replay (the zero-credit demo) -----------------------------------------------

def test_operator_input_key_draft_methods_keys_on_skill_and_strips_prefix():
    assert _operator_input_key("draft_methods", {"skill_id": "deg"}) == "deg"
    assert _operator_input_key("draft_methods", {"skill_id": "selom.deg"}) == "deg"
    assert _operator_input_key("draft_methods", {}) is None


def test_operator_recording_replays_draft_methods():
    # The bundled recordings file carries a draft_methods:deg entry (the zero-credit demo). The
    # operator ignores base_text and replays the recorded polished prose.
    gw = OperatorActionGateway.from_recordings()
    text = gw.explain("draft_methods", {"skill_id": "deg", "base_text": _BASE}, "polish it")
    assert "PyDESeq2" in text
    # Differs from the deterministic fallback (= base_text) → the endpoint labels it source="ai" honestly.
    assert text != _BASE
    assert text != _deterministic_explain("draft_methods", {"skill_id": "deg", "base_text": _BASE}, "polish it")


def test_operator_unknown_skill_draft_methods_falls_back_to_base_text():
    gw = OperatorActionGateway.from_recordings()
    text = gw.explain("draft_methods", {"skill_id": "umap", "base_text": _BASE}, "polish it")
    # No recording for umap → the deterministic fallback (base_text verbatim), never a fabricated draft.
    assert text == _BASE


# --- POST /ai/explain endpoint ----------------------------------------------------------------------

def test_explain_endpoint_draft_methods_deterministic_source_gateway_off():
    from routers.ai import ExplainRequest, explain

    resp = explain(ExplainRequest(request="draft_methods", skill_id="deg", base_text=_BASE))
    assert resp["request"] == "draft_methods"
    assert resp["source"] == "deterministic"  # NullActionGateway default → no ✨
    assert resp["text"] == _BASE  # the deterministic draft is base_text verbatim
    assert resp["suggestions"] == []  # sweep suggestions are propose_sweep-only


def test_explain_endpoint_draft_methods_source_ai_when_gateway_changes_text(monkeypatch):
    # A stub gateway that actually rewrites base_text → the endpoint stamps source="ai" (honesty by
    # comparison: text != the deterministic fallback, and the gateway is not Null).
    class _StubGateway:
        model_id = "stub"

        def propose(self, ctx, goal):  # pragma: no cover — not exercised by explain
            raise NotImplementedError

        def explain(self, request_type, data, goal):
            return "POLISHED — " + (data.get("base_text") or "")

    from routers import ai as ai_router

    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: _StubGateway())
    resp = ai_router.explain(
        ai_router.ExplainRequest(request="draft_methods", skill_id="deg", base_text=_BASE)
    )
    assert resp["source"] == "ai"
    assert resp["text"].startswith("POLISHED — ")


def test_explain_endpoint_draft_methods_noop_polish_stays_deterministic(monkeypatch):
    # A gateway that returns base_text UNCHANGED (a no-op polish) must NOT be labelled ✨ — the
    # by-comparison check keeps the ✨ marker honest even for a non-Null gateway.
    class _EchoGateway:
        model_id = "echo"

        def propose(self, ctx, goal):  # pragma: no cover
            raise NotImplementedError

        def explain(self, request_type, data, goal):
            return data.get("base_text") or ""

    from routers import ai as ai_router

    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: _EchoGateway())
    resp = ai_router.explain(
        ai_router.ExplainRequest(request="draft_methods", skill_id="deg", base_text=_BASE)
    )
    assert resp["source"] == "deterministic"
    assert resp["text"] == _BASE


def test_explain_endpoint_draft_methods_never_records_a_gap():
    from ai import gaps as g
    from routers.ai import ExplainRequest, explain

    explain(ExplainRequest(request="draft_methods", skill_id="deg", base_text=_BASE))
    assert g.list_gaps() == []


# --- draft_legend — the symmetric sibling over a figure's caption ------------------------------------

_LEGEND = "Volcano plot of differential expression; genes with |log2FC| >= 3 and FDR <= 0.05 highlighted."


def test_deterministic_explain_draft_legend_returns_base_text_verbatim():
    # Same honesty lever as draft_methods: the deterministic legend draft is base_text unchanged.
    assert _deterministic_explain("draft_legend", {"base_text": _LEGEND}, "tighten") == _LEGEND
    assert _deterministic_explain("draft_legend", {}, "polish") == ""


def test_build_explain_prompt_draft_legend_grounds_on_caption():
    prompt = build_explain_prompt("draft_legend", {"base_text": _LEGEND}, "match a journal caption")
    assert "LEGEND" in prompt and "POLISH" in prompt and "PRESERVE" in prompt
    assert _LEGEND in prompt


def test_operator_input_key_draft_legend_keys_on_skill():
    assert _operator_input_key("draft_legend", {"skill_id": "selom.volcano"}) == "volcano"
    assert _operator_input_key("draft_legend", {}) is None


def test_operator_recording_replays_draft_legend_volcano():
    # The bundled recordings carry a draft_legend:volcano entry (the zero-credit demo).
    gw = OperatorActionGateway.from_recordings()
    text = gw.explain("draft_legend", {"skill_id": "volcano", "base_text": _LEGEND}, "polish it")
    assert "Volcano plot" in text
    assert text != _LEGEND  # differs from base_text → endpoint labels source="ai" honestly


def test_explain_endpoint_draft_legend_deterministic_source_gateway_off():
    from routers.ai import ExplainRequest, explain

    resp = explain(ExplainRequest(request="draft_legend", skill_id="volcano", base_text=_LEGEND))
    assert resp["request"] == "draft_legend"
    assert resp["source"] == "deterministic"
    assert resp["text"] == _LEGEND

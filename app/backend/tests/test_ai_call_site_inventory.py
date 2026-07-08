"""M-003 -- LLM/AI call-site inventory + accessor allowlist (eng-practices port, port M1).

The AI write/explain surface is small and security-sensitive: every LLM call must go through an
audited gateway, provenance must be stamped at ONE chokepoint, and the guarded operation-label set
must stay closed. The existing structural guard (test_structure_guard) pins routers/ai.py as the
sole feeder of stamp_ai_actions, but a new site reusing an existing label, or a raw model client
constructed in a new file, slips past a single-caller check. This inventory COUNTS the sites and
pins the exact sets, so a new label / caller / raw-client construction is red until the matching
EXPECTED_* set below is updated on purpose.

SPINE sentence (update in the SAME change as the code): AI provenance is stamped only via
provenance.stamp_ai_actions; the guarded operation-label set is closed; raw LLM model clients live
only in the gateway impls; the gateway is selected by the single factory get_action_gateway.
See docs/eng-practices-port/plan.md M-003 + docs/hardening-port/gate-ledger.md.
"""

import os
import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# --- EXPECTED sets (the pinned inventory) -------------------------------------------------------
# Guarded AI operation labels — the request_type values dispatched across the explain/gateway
# surface (ai/gateway.py: _deterministic_explain / build_explain_prompt / _operator_input_key).
EXPECTED_OPERATION_LABELS = frozenset({
    "explain_score",
    "propose_sweep",
    "grade_advice",
    "draft_methods",
    "draft_legend",
})
# The ONLY files that call the provenance.stamp_ai_actions chokepoint (its definition lives in
# companions/provenance.py and is excluded).
EXPECTED_STAMP_CALLERS = frozenset({"ai/execute.py", "routers/ai.py"})
# Raw pydantic-ai model clients (the actual wire to a provider) may be constructed ONLY here.
RAW_MODEL_CLIENT_ALLOWLIST = frozenset({"ai/live/pydantic_gateway.py"})
# Gateway impl files the selection factory imports — their existence is asserted so a moved file
# fails loudly instead of silently degrading to Null.
GATEWAY_IMPL_FILES = ("ai/gateway.py", "ai/live/pydantic_gateway.py", "ai/live/vercel_gateway.py")

_SKIP_DIRS = frozenset({
    ".venv", "venv", "__pycache__", "node_modules", "data", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "graphify-out", ".git", "build", "dist",
})


def _iter_backend_py():
    for dirpath, dirnames, filenames in os.walk(BACKEND):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield pathlib.Path(dirpath) / fn


def test_operation_label_set_is_closed():
    """The guarded AI operation-label set is exactly EXPECTED_OPERATION_LABELS.

    Extracted from the request_type dispatch in ai/gateway.py — a new `request_type == "..."` (or a
    new member of a `request_type in (...)` tuple) changes the found set and fails here until
    EXPECTED_OPERATION_LABELS is bumped in the same change.
    """
    src = (BACKEND / "ai" / "gateway.py").read_text(encoding="utf-8")
    found: set[str] = set()
    for rhs in re.findall(r'request_type\s*(?:==|in)\s*(\([^)]*\)|"[^"]*")', src):
        found.update(re.findall(r'"([^"]+)"', rhs))
    assert found, "extracted no request_type labels — the extractor or the dispatch shape changed."
    assert found == set(EXPECTED_OPERATION_LABELS), (
        f"AI operation labels drifted: found {sorted(found)}, expected "
        f"{sorted(EXPECTED_OPERATION_LABELS)}. Update EXPECTED_OPERATION_LABELS in the SAME change "
        "that adds/removes a request_type handler (the guarded label set is closed)."
    )


def test_stamp_ai_actions_callers_are_pinned():
    """provenance.stamp_ai_actions is called from exactly EXPECTED_STAMP_CALLERS.

    Its definition (companions/provenance.py `def stamp_ai_actions(`) is excluded, tests are exempt.
    A new stamping caller is red — AI attribution has ONE server-controlled chokepoint.
    """
    callers: set[str] = set()
    for p in _iter_backend_py():
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith("tests/"):
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if "stamp_ai_actions(" in line and "def stamp_ai_actions(" not in line:
                callers.add(rel)
                break
    assert callers == set(EXPECTED_STAMP_CALLERS), (
        f"stamp_ai_actions caller set drifted: found {sorted(callers)}, expected "
        f"{sorted(EXPECTED_STAMP_CALLERS)}. A new stamping site must route through the same "
        "chokepoint AND be added to EXPECTED_STAMP_CALLERS on purpose (no parallel attribution path)."
    )


def test_raw_model_client_construction_is_allowlisted():
    """Raw pydantic-ai model clients are constructed ONLY in the gateway impls (RAW_MODEL_CLIENT_
    ALLOWLIST). A raw client constructed elsewhere bypasses the audited gateway seam (token budget,
    timeout, degrade-clean fallback) — the exact hole this inventory closes.
    """
    pat = re.compile(
        r"\b(?:AnthropicModel|OpenAIModel|GroqModel|GoogleModel|MistralModel|BedrockConverseModel)\s*\("
    )
    offenders = []
    for p in _iter_backend_py():
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith("tests/") or rel in RAW_MODEL_CLIENT_ALLOWLIST:
            continue
        if pat.search(p.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert not offenders, (
        f"raw model client constructed outside the gateway impls: {sorted(offenders)}. Construct it "
        "inside a gateway impl (RAW_MODEL_CLIENT_ALLOWLIST) so it inherits the budget/timeout/degrade "
        "wiring, or extend the allowlist deliberately."
    )


def test_gateway_factory_is_single_and_impls_exist():
    """The gateway SELECTION factory get_action_gateway lives only in routers/ai.py (one seam), and
    each gateway impl path the factory imports still exists — a moved impl must fail loudly, not
    silently degrade to NullActionGateway.
    """
    factory_files = sorted(
        p.relative_to(BACKEND).as_posix()
        for p in _iter_backend_py()
        if not p.relative_to(BACKEND).as_posix().startswith("tests/")
        and "def get_action_gateway(" in p.read_text(encoding="utf-8")
    )
    assert factory_files == ["routers/ai.py"], (
        f"get_action_gateway defined in {factory_files}, expected only ['routers/ai.py']. The gateway "
        "is selected by ONE factory; a second factory is a parallel un-audited construction path."
    )
    missing = [rel for rel in GATEWAY_IMPL_FILES if not (BACKEND / rel).is_file()]
    assert not missing, (
        f"gateway impl file(s) missing: {missing}. get_action_gateway imports these lazily; a moved "
        "file would silently fall through to NullActionGateway. Update GATEWAY_IMPL_FILES if renamed."
    )

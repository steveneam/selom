"""Enforce backend structure conventions (repo-structure plan §1.4) in the fast gate.

Chat memory and docs rot; a convention only holds if a check fails when it drifts. These
guards backstop the rules in CLAUDE.md / docs/repo-structure/plan.md so re-introducing a
flat handler or a flat domain module fails CI/local before it lands.
"""

import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_main_has_no_app_route_decorators():
    """Route handlers must live in routers/ (plan §1.1), not main.py."""
    import re

    main_src = (BACKEND / "main.py").read_text(encoding="utf-8")
    matches = re.compile(r"@app\.(get|post|put|patch|delete)\b").findall(main_src)
    assert not matches, (
        f"main.py contains {len(matches)} @app.<method> decorator(s): {matches}. "
        "Route handlers must live in routers/, not main.py."
    )


def test_no_flat_reproduction_modules():
    """The reproduction engine is a package (plan §3A) — no flat reproduction_*.py at root.

    New engine modules go in reproduction/ (per-paper ledgers in reproduction/papers/).
    repro_assets.py and skill_gaps.py stay flat by design and don't match this glob.
    """
    strays = sorted(p.name for p in BACKEND.glob("reproduction_*.py"))
    assert not strays, (
        f"flat reproduction_*.py at the backend root: {strays}. The reproduction engine is "
        "a package — add new modules under reproduction/ (reproduction/papers/ for per-paper "
        "ledgers) and import via the dotted path. See docs/repo-structure/plan.md §3A."
    )


def test_companion_builders_live_in_package():
    """The figure-companion builders live in companions/ (plan §3B), not flat at root."""
    strays = sorted(
        name
        for name in ("methods.py", "legends.py", "provenance.py", "guardrails.py")
        if (BACKEND / name).is_file()
    )
    assert not strays, (
        f"companion builder(s) flat at the backend root: {strays}. methods/legends/provenance/"
        "guardrails belong in companions/ (import via `from companions import X`). "
        "See docs/repo-structure/plan.md §3B."
    )


def test_ai_reuses_core_validation():
    """ai/ must import validate_param_ranges from skills.contract — no parallel validation path.

    The AI action gateway must validate through the exact same function that the HTTP layer
    uses (``routers/_run.py``).  A duplicate implementation in ai/ would allow AI-proposed
    params to pass checks that human-submitted params would fail, violating Requirement 3.
    If this guard fails, ai/registry.py or ai/execute.py has reimplemented validation
    instead of delegating to skills.contract.validate_param_ranges.
    """
    found = False
    for src_file in ("ai/registry.py", "ai/execute.py"):
        src = (BACKEND / src_file).read_text(encoding="utf-8")
        if "validate_param_ranges" in src:
            found = True
            break
    assert found, (
        "Neither ai/registry.py nor ai/execute.py references validate_param_ranges. "
        "AI validation must reuse skills.contract.validate_param_ranges — no parallel path. "
        "See spec.md Invariant 'Validation reuse'."
    )


def test_ai_live_package_structure():
    """ai/live/ must exist and contain pydantic_gateway.py without re-implementing validation.

    The live gateway is a structured-output *translator* only — it maps NL goal +
    context into an ActionPlan.  Validation lives exclusively in ai/execute.py and
    ai/registry.py (the existing structure guard already asserts this for those files).
    The live gateway must not add a third path.
    """
    live_dir = BACKEND / "ai" / "live"
    assert live_dir.is_dir(), (
        "ai/live/ directory must exist (Slice 2). "
        "Create it with ai/live/__init__.py + ai/live/pydantic_gateway.py."
    )
    assert (live_dir / "pydantic_gateway.py").is_file(), (
        "ai/live/pydantic_gateway.py must exist (PydanticAIGateway, Slice 2)."
    )
    gw_src = (live_dir / "pydantic_gateway.py").read_text(encoding="utf-8")
    assert "validate_param_ranges" not in gw_src, (
        "ai/live/pydantic_gateway.py must not reimplement validation. "
        "The live gateway is a structured-output translator only; "
        "validate_param_ranges is called by ai/registry.py via ai/execute.py."
    )


def test_ai_apply_router_uses_execute_skill_run():
    """POST /ai/apply must route through _execute_skill_run — no second gated path.

    Inspection: routers/ai.py must import and call _execute_skill_run (the shared
    human run body) so AI-assisted runs go through the exact same QC / D1 / D2
    gates as human runs.  A separate AI execution path would violate the
    'same gateway as humans' invariant (spec invariant 3).
    """
    ai_router_src = (BACKEND / "routers" / "ai.py").read_text(encoding="utf-8")
    assert "_execute_skill_run" in ai_router_src, (
        "routers/ai.py must call _execute_skill_run for POST /ai/apply. "
        "AI-assisted runs must use the same gated body as human runs."
    )


def test_ai_action_registry_matches_action_types():
    """ACTION_REGISTRY keys, ACTION_TYPES tuple, and ActionType Literal must be identical.

    All three declarations live in different files but describe the same closed set.
    This guard catches the common mistake of adding a new action type to only one of the
    three places — which would let the Literal parse it, but the registry never execute it
    (or vice-versa).  Completeness + disjointness both checked, mirroring the
    skill-table-contract guard pattern.
    """
    from typing import get_args

    from ai import models, registry

    registry_keys = set(registry.ACTION_REGISTRY)
    types_tuple = set(models.ACTION_TYPES)
    literal_members = set(get_args(models.ActionType))

    assert registry_keys == types_tuple, (
        f"ACTION_REGISTRY keys {sorted(registry_keys)} don't match ACTION_TYPES tuple "
        f"{sorted(types_tuple)}.  Add/remove from both in the same commit."
    )
    assert types_tuple == literal_members, (
        f"ACTION_TYPES tuple {sorted(types_tuple)} doesn't match ActionType Literal members "
        f"{sorted(literal_members)}.  Keep models.ACTION_TYPES and models.ActionType in sync."
    )

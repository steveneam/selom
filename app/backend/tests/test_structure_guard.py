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

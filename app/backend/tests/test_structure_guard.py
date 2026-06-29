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

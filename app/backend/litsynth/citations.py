"""Canonical citation access for the synthesizer — single-sourced from ``methods.py``.

``methods.py`` owns the canonical per-tool references *and* the per-skill template that
decides WHICH refs a skill emits for given params. We do NOT re-encode that mapping here
(it would drift); instead we re-export the reference constants and delegate the per-skill
lookup to ``methods.build_body``. ``methods.py`` stays the single source of truth
(scope: import, don't copy).
"""

from __future__ import annotations

import methods
from skills.contract import load_skill

# The canonical reference strings, by their methods.py constant name (advisory — the
# authoritative per-skill selection still flows through methods.build_body below).
CANONICAL_REFS: dict[str, str] = {
    name: value
    for name, value in vars(methods).items()
    if name.isupper() and isinstance(value, str)
}


def citations_for(skill_id: str, params: dict | None = None) -> list[str]:
    """The canonical citations one skill emits for given params — straight from methods.py."""
    return methods.build_body(load_skill(skill_id), params or {})[1]

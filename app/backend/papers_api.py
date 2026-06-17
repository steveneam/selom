"""Read-only Reproduction-ledger API surface (spec ``§Endpoints``; the R5 data layer).

Serves the three captured reproduction ledgers + their derived scorecards to the frontend
Reproduction view. Each ledger is built by its module's ``drive_captured()`` — the *captured*
verdicts (no GEO download, no heavy compute), so a request is fast and deterministic — and the
driven :class:`reproduction.Ledger` (which bundles paper + panels + validations + the derived
scorecard) is cached per slug.

This module is deliberately FastAPI-free so it stays unit-testable; ``main.py`` owns the routes
+ 404s. v1 is the internal dogfood view (spec D12), so the data is the real engine output, not a
hand-authored mock.
"""

from __future__ import annotations

from functools import lru_cache

import reproduction as R

# slug -> the ledger module that builds + drives it. Imported lazily (inside the cache) so app
# startup never pays to import the three ledgers + their skills unless /papers is actually hit.
_LEDGER_MODULES: dict[str, str] = {
    "rpgrip1": "reproduction_rpgrip1",
    "jev": "reproduction_jev",
    "hani": "reproduction_hani",
}

# Spectrum order for the index — ascending reproducibility so the row reads red -> green
# (RPGRIP1 63 -> JEV 86 -> Hani 96, the headline "reproducibility spectrum").
SLUGS: tuple[str, ...] = ("rpgrip1", "jev", "hani")


@lru_cache(maxsize=None)
def driven_ledger(slug: str) -> R.Ledger:
    """The captured-and-driven ledger for ``slug`` (cached). KeyError if unknown."""
    module = __import__(_LEDGER_MODULES[slug])
    return module.drive_captured()


def _strip(ledger: R.Ledger) -> dict:
    """A compact per-panel heatmap strip for the index card (one cell per scored/oos panel)."""
    sc = ledger.scorecard
    return [
        {
            "panel_key": ps.panel_key,
            "reproducibility": ps.reproducibility,
            "tier": ps.tier,
            "color": ps.color,
            "attribution_icon": ps.attribution_icon,
            "in_scope": ps.in_scope,
        }
        for ps in (sc.panel_scores if sc else [])
    ]


def list_papers() -> list[dict]:
    """The 3-paper reproducibility spectrum for the index view (ascending reproducibility)."""
    out: list[dict] = []
    for slug in SLUGS:
        ledger = driven_ledger(slug)
        sc = ledger.scorecard
        out.append(
            {
                "slug": slug,
                "title": ledger.paper.title,
                "doi": ledger.paper.doi,
                "geo": ledger.paper.geo,
                "score": sc.score.model_dump() if sc and sc.score else None,
                "n_panels": sc.n_panels if sc else 0,
                "n_in_scope": sc.n_in_scope if sc else 0,
                "findings": sc.findings if sc else {},
                "provenance_divergences": sc.provenance_divergences if sc else [],
                "cells": _strip(ledger),
            }
        )
    return out

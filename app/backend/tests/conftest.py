"""Shared pytest fixtures for the backend suite.

The Task C1 result cache (skills/_result_cache.py) is a *production* optimization. In the test
suite it must stay **off**: the golden-figure tests exist to catch an output change from a code
edit, and a content-addressed cache that survives on disk between sessions would serve the stale
pre-edit figure (a false green) when a skill changes without a version bump. Disabling it suite-wide
also keeps tests from writing entries into the real ``data/result_cache/``. Tests that exercise the
cache itself (test_result_cache.py) opt back in by swapping in their own enabled instance.
"""

import os
import tempfile

import pytest

from config import settings
from skills import _result_cache

# --- E2 fast/slow test split -------------------------------------------------------------
# A feature commit runs the fast "contract gate" — `pytest -m "not slow"` — in seconds; the
# heavy lanes (reproduction drives over real data, golden-figure renders across every skill,
# real-engine scverse validations) carry @slow and only run in the full/CI pass (`pytest -m
# slow`). Auto-marked by FILE here so no per-test edits are needed — a new heavy file just
# joins the set below. (Telemetry split, architecture-consistency Task E2.)
_SLOW_PREFIXES = ("test_reproduction",)
_SLOW_FILES = {
    "test_skills_golden.py",
    "test_styles.py",
    "test_charts.py",
    "test_export.py",
    "test_iwx.py",
    "test_gsea.py",
    "test_ssgsea.py",
    "test_melody.py",
    "test_cepo.py",
    "test_integration_skill.py",
    "test_scrna_hvg_mixing.py",
    "test_deg_bulk.py",
    "test_deg_pseudobulk.py",
    "test_diff_abundance.py",
    "test_pseudotime_genes.py",
    "test_reconstruct.py",
    "test_repro_assets.py",
}


def pytest_collection_modifyitems(config, items):
    """Tag the heavy lanes @slow by file (see the split note above)."""
    slow = pytest.mark.slow
    for item in items:
        name = os.path.basename(str(item.fspath))
        if name.startswith(_SLOW_PREFIXES) or name in _SLOW_FILES:
            item.add_marker(slow)


@pytest.fixture(autouse=True)
def _caches_off(monkeypatch):
    prev = _result_cache._default
    _result_cache.set_cache(
        _result_cache.ResultCache(root=tempfile.gettempdir(), mem_max=0, enabled=False)
    )
    # The C3 parsed-input cache is content-addressed (staleness-safe), but keep tests parsing fresh
    # so endpoint tests don't share state through the in-process cache. (The settings singleton is
    # built at import, so flip the attribute, not the env var; the property reads it live per call.)
    monkeypatch.setattr(settings, "input_cache", "off")
    import engine

    engine.clear_input_cache()
    # The D3 intermediate-table lineage store writes content-addressed CSVs under data/artifacts/; in
    # the suite it stays off so tests hitting /run don't litter the real store. Tests that exercise it
    # (test_lineage.py) swap in their own enabled instance. Off via a disabled temp-dir store.
    from engine import lineage

    prev_store = lineage._default
    lineage.set_store(lineage.ArtifactStore(root=tempfile.gettempdir(), enabled=False))
    yield
    _result_cache.set_cache(prev)
    lineage.set_store(prev_store)
    engine.clear_input_cache()

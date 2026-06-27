"""Shared pytest fixtures for the backend suite.

The Task C1 result cache (skills/_result_cache.py) is a *production* optimization. In the test
suite it must stay **off**: the golden-figure tests exist to catch an output change from a code
edit, and a content-addressed cache that survives on disk between sessions would serve the stale
pre-edit figure (a false green) when a skill changes without a version bump. Disabling it suite-wide
also keeps tests from writing entries into the real ``data/result_cache/``. Tests that exercise the
cache itself (test_result_cache.py) opt back in by swapping in their own enabled instance.
"""

import tempfile

import pytest

from config import settings
from skills import _result_cache


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

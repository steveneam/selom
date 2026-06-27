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

from skills import _result_cache


@pytest.fixture(autouse=True)
def _result_cache_off():
    prev = _result_cache._default
    _result_cache.set_cache(
        _result_cache.ResultCache(root=tempfile.gettempdir(), mem_max=0, enabled=False)
    )
    yield
    _result_cache.set_cache(prev)

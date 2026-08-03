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

import anndata
import pandas as pd
import pytest

from config import settings
from skills import _result_cache

# --- h5ad round-trip on pandas 3 + pyarrow -----------------------------------------------
# `pyarrow` is in the lock, so on pandas 3 a categorical's `.categories` is backed by
# `ArrowStringArray`, and anndata 0.12.6 has no writer registered for it -- every fixture that
# builds an AnnData and calls `write_h5ad` dies with IORegistryError (test_cepo.py and all of
# test_deg_pseudobulk.py). Both lines are needed: forcing python-backed strings gets past the
# Arrow writer, and the resulting `StringArray` is then refused as a nullable dtype unless
# anndata is told to allow it.
#
# This is a TEST-ONLY concern, which is why it lives here and not in production code: `write_h5ad`
# appears nowhere outside the suite -- production only ever READS h5ad. The breakage went unnoticed
# for so long because both files are `slow`, and the slow lane was gated NOWHERE; since 2026-08-03
# `verify.sh` (be-slow) and the CI backend job both run `-m slow`, so these two lines are now
# exercised by the gate rather than only by a hand-run full suite.
pd.options.mode.string_storage = "python"
anndata.settings.allow_write_nullable_strings = True

# --- E2 fast/slow test split -------------------------------------------------------------
# A feature commit runs the fast "contract gate" — `pytest -m "not slow"` — in seconds; the
# heavy lanes (reproduction drives over real data, golden-figure renders across every skill,
# real-engine scverse validations) carry @slow and run in the SEPARATE slow gate (`pytest -m
# slow`) — corpus-free in CI and in verify.sh's be-slow (~16s, a breakage gate), and with the real
# corpus in a full local run (~7.5 min, the numerical check). Auto-marked by FILE here so no
# per-test edits are needed — a new heavy file just joins the set below, and it is gated the moment
# it does. (Telemetry split, architecture-consistency Task E2.)
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

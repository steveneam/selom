"""Materialized-decode temp lifecycle (materialization step 6, acceptance D).

The decoded-CSV / combined-frame temps (formerly ``NamedTemporaryFile(delete=False)``) were never
cleaned — a per-invocation leak on Lambda's ephemeral disk. The holistic fix (not a naive
``finally``, because ``bundle.path`` is reused across requests by the C3 cache):
  * content-addressed names → the same bytes REUSE one temp instead of multiplying;
  * a managed dir (atexit backstop);
  * eviction-tied deletion so the C3 cache owns + frees its temps.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import pytest

from config import settings
from engine import clear_input_cache

ing = sys.modules["engine.ingest"]  # reach the module to read its private temp helpers


@pytest.fixture(autouse=True)
def _enable_cache(monkeypatch):
    monkeypatch.setattr(settings, "input_cache", "on")
    clear_input_cache()
    yield
    clear_input_cache()


def test_materialize_csv_is_content_addressed_and_managed():
    df = pd.DataFrame({"gene": ["A", "B"], "x": [1, 2]})
    p1 = ing._materialize_csv(df)
    p2 = ing._materialize_csv(df.copy())  # identical bytes → SAME path, no duplicate temp
    assert p1 == p2
    path = pathlib.Path(p1)
    assert path.exists() and path.suffix == ".csv"
    assert ing._is_managed_temp(p1)  # under the one process-managed dir
    # different content → a different content-addressed temp
    assert ing._materialize_csv(pd.DataFrame({"g": [9]})) != p1


def test_release_deletes_only_when_unreferenced():
    df = pd.DataFrame({"a": [1]})
    p = ing._materialize_csv(df)
    assert pathlib.Path(p).exists()
    # no cache entry references it → released (deleted)
    ing._release_materialized(p)
    assert not pathlib.Path(p).exists()


def test_clear_input_cache_frees_materialized_temps():
    from engine.databundle import DataBundle
    from engine.models import SourceRef

    df = pd.DataFrame({"a": [1, 2]})
    p = ing._materialize_csv(df)
    bundle = DataBundle(payload=df, kind="generic_table",
                        source=SourceRef(filename="x.csv", n_bytes=0, sha256=""), path=p)
    with ing._INPUT_LOCK:
        ing._INPUT_CACHE[("sha", None, "None", None)] = (bundle, True)  # a materialized entry
    assert pathlib.Path(p).exists()
    clear_input_cache()
    assert not pathlib.Path(p).exists()  # cache clear frees the temp it owned


def test_lru_eviction_deletes_owned_temp(monkeypatch):
    from engine.databundle import DataBundle
    from engine.models import SourceRef

    monkeypatch.setattr(settings, "input_cache_max", 1)
    df = pd.DataFrame({"a": [1]})
    t1 = ing._materialize_csv(df)
    bundle = DataBundle(payload=df, kind="generic_table",
                        source=SourceRef(filename="x.csv", n_bytes=0, sha256=""), path=t1)
    with ing._INPUT_LOCK:  # seed an oldest materialized entry
        ing._INPUT_CACHE[("old", None, "None", None)] = (bundle, True)
    assert pathlib.Path(t1).exists()

    # ingesting a fresh CSV inserts a new entry → evicts the oldest → frees its temp
    fresh = pathlib.Path(t1).parent.parent / "fresh.csv"
    fresh.write_text("gene,x\nACTB,1\nGAPDH,2\n", encoding="utf-8")
    ing.ingest_cached(str(fresh))
    assert not pathlib.Path(t1).exists()

"""Task C3 — the parsed-input cache (``engine.ingest_cached``).

The same bytes uploaded to two endpoints (``/data/inspect`` then ``/run``) land at two different
temp paths but hash the same, so the second parse is served from the in-process cache. The shared
payload is read-only; per-request ``source``/``qc``/``path`` are rebound on each hit.
"""

import pathlib
import sys

import pytest

from config import settings
from engine import clear_input_cache, ingest_cached

# The engine package re-exports the `ingest` function as the `engine.ingest` attribute, shadowing the
# submodule — so reach the module (where ingest_cached looks up `ingest`) via sys.modules to patch it.
ing = sys.modules["engine.ingest"]


@pytest.fixture(autouse=True)
def _enable_input_cache(monkeypatch):
    # The suite-wide conftest turns the input cache OFF; this module needs it ON.
    monkeypatch.setattr(settings, "input_cache", "on")
    clear_input_cache()
    yield
    clear_input_cache()


def _csv(tmp_path, name, text="gene,ctrl,treat\nACTB,10,20\nGAPDH,30,40\nB2M,5,8\n"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_same_bytes_parse_once(tmp_path, monkeypatch):
    calls = {"n": 0}
    real_ingest = ing.ingest

    def counting(src, **kw):
        calls["n"] += 1
        return real_ingest(src, **kw)

    monkeypatch.setattr(ing, "ingest", counting)

    a = _csv(tmp_path, "inspect_copy.csv")
    b = _csv(tmp_path, "run_copy.csv")  # identical bytes, different path

    ba = ingest_cached(a)
    bb = ingest_cached(b)
    assert calls["n"] == 1, "identical bytes must parse once (the /inspect->/run reuse)"
    assert ba.kind == bb.kind
    # Payload is shared (read-only); path is rebound to THIS request's file.
    assert ba.payload is bb.payload
    assert bb.path == str(pathlib.Path(b))


def test_distinct_inputs_and_hints_miss(tmp_path, monkeypatch):
    calls = {"n": 0}
    real_ingest = ing.ingest

    def counting(src, **kw):
        calls["n"] += 1
        return real_ingest(src, **kw)

    monkeypatch.setattr(ing, "ingest", counting)

    a = _csv(tmp_path, "a.csv")
    c = _csv(tmp_path, "c.csv", text="gene,ctrl,treat\nXIST,1,2\nMALAT1,9,9\nRPL13,4,4\n")
    ingest_cached(a)
    ingest_cached(c)                 # different bytes -> miss
    ingest_cached(a, hint="bulk_counts")  # same bytes, different hint -> miss
    assert calls["n"] == 3


def test_disabled_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "input_cache", "off")
    calls = {"n": 0}
    real_ingest = ing.ingest

    def counting(src, **kw):
        calls["n"] += 1
        return real_ingest(src, **kw)

    monkeypatch.setattr(ing, "ingest", counting)
    a = _csv(tmp_path, "a.csv")
    ingest_cached(a)
    ingest_cached(a)
    assert calls["n"] == 2  # no memoization when disabled

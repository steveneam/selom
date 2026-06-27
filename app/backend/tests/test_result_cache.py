"""Task C1 — content-addressed result cache.

Two layers of proof:
  * the cache primitives in isolation (key derivation, the two tiers, LRU eviction, isolation),
  * the acceptance, end-to-end through ``contract._execute`` with a fake call-counting skill:
    *an identical re-run is a measured cache hit (no recompute); a skill_version bump misses cleanly.*
"""

import types

import pytest

from skills import _result_cache, contract
from skills._result_cache import ResultCache, cache_key, canonical_params
from skills.contract import SkillSpec

# --- canonicalization -------------------------------------------------------------------------

_SPEC = {
    "fc_threshold": {"type": "float", "default": 2.0},
    "top_n": {"type": "int", "default": 10},
    "log": {"type": "bool", "default": True},
}


def test_canonical_drops_defaults_and_coerces_types():
    # An omitted param and an explicit default (as a query string) canonicalize identically.
    assert canonical_params(_SPEC, {}) == {}
    assert canonical_params(_SPEC, {"fc_threshold": "2.0", "top_n": "10", "log": "true"}) == {}
    # A non-default value is kept, coerced to its declared type.
    assert canonical_params(_SPEC, {"fc_threshold": "3"}) == {"fc_threshold": 3.0}
    assert canonical_params(_SPEC, {"top_n": "25"}) == {"top_n": 25}
    assert canonical_params(_SPEC, {"log": "false"}) == {"log": False}


def test_canonical_float_precision_is_stable():
    a = canonical_params(_SPEC, {"fc_threshold": 0.1 + 0.2})
    b = canonical_params(_SPEC, {"fc_threshold": 0.3})
    assert a == b == {"fc_threshold": 0.3}


def test_canonical_keeps_unknown_keys():
    assert canonical_params(_SPEC, {"mystery": "x"}) == {"mystery": "x"}


def test_canonical_hashes_runtime_file_params(tmp_path):
    sheet = tmp_path / "design.csv"
    sheet.write_text("sample,group\nA,ctrl\n", encoding="utf-8")
    canon = canonical_params(_SPEC, {"_design_path": str(sheet)})
    assert "_design_path" in canon and "__file_sha256__" in canon["_design_path"]
    # A different design sheet -> a different hash -> a different key downstream.
    sheet.write_text("sample,group\nA,treat\n", encoding="utf-8")
    assert canonical_params(_SPEC, {"_design_path": str(sheet)}) != canon


# --- key derivation ---------------------------------------------------------------------------

def _input(tmp_path, text="a,b\n1,2\n"):
    p = tmp_path / "matrix.csv"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_key_is_stable_and_version_sensitive(tmp_path):
    src = _input(tmp_path)
    k1 = cache_key("deg", "1", _SPEC, src, {})
    assert k1 == cache_key("deg", "1", _SPEC, src, {"fc_threshold": "2.0"})  # default omitted == passed
    assert k1 != cache_key("deg", "2", _SPEC, src, {})                       # version bump -> miss
    assert k1 != cache_key("deg", "1", _SPEC, src, {"fc_threshold": "3"})    # param change -> miss
    assert k1 != cache_key("other", "1", _SPEC, src, {})                     # skill change -> miss


def test_key_tracks_input_bytes(tmp_path):
    k1 = cache_key("deg", "1", _SPEC, _input(tmp_path, "a,b\n1,2\n"), {})
    k2 = cache_key("deg", "1", _SPEC, _input(tmp_path, "a,b\n9,9\n"), {})
    assert k1 != k2


def test_key_is_none_for_missing_input(tmp_path):
    assert cache_key("deg", "1", _SPEC, str(tmp_path / "absent.csv"), {}) is None


# --- the store --------------------------------------------------------------------------------

def test_set_get_roundtrip_and_isolation(tmp_path):
    cache = ResultCache(tmp_path / "rc", mem_max=8)
    fig = {"data": [{"x": [1]}], "layout": {}}
    cache.set("k", fig, {"rows": [1]})
    got = cache.get("k")
    assert got == {"figure": fig, "table": {"rows": [1]}}
    assert cache.stats["mem_hits"] == 1
    # Mutating the returned value must not corrupt the cache (deep-copy on both boundaries).
    got["figure"]["data"][0]["x"].append(999)
    assert cache.get("k")["figure"]["data"][0]["x"] == [1]


def test_disk_tier_survives_a_new_instance(tmp_path):
    a = ResultCache(tmp_path / "rc", mem_max=8)
    a.set("k", {"data": [], "layout": {}}, None)
    # Fresh instance, cold in-proc tier -> the hit must come from disk.
    b = ResultCache(tmp_path / "rc", mem_max=8)
    assert b.get("k") is not None
    assert b.stats["disk_hits"] == 1 and b.stats["mem_hits"] == 0


def test_lru_evicts_oldest(tmp_path):
    cache = ResultCache(tmp_path / "rc", mem_max=2)
    for k in ("a", "b", "c"):
        cache.set(k, {"data": [], "layout": {}}, None)
    # "a" fell out of the in-proc tier, but the disk tier still holds it.
    assert "a" not in cache._mem and "c" in cache._mem
    assert cache.get("a") is not None and cache.stats["disk_hits"] == 1


def test_disabled_cache_never_stores(tmp_path):
    cache = ResultCache(tmp_path / "rc", mem_max=8, enabled=False)
    cache.set("k", {"data": [], "layout": {}}, None)
    assert cache.get("k") is None
    assert not list((tmp_path / "rc").glob("*.json")) if (tmp_path / "rc").exists() else True


def test_miss_counts(tmp_path):
    cache = ResultCache(tmp_path / "rc", mem_max=8)
    assert cache.get("nope") is None
    assert cache.stats["misses"] == 1


# --- acceptance: identical re-run is a measured hit; a version bump misses ---------------------

@pytest.fixture
def fresh_cache(tmp_path, monkeypatch):
    cache = ResultCache(tmp_path / "rc", mem_max=8)
    monkeypatch.setattr(_result_cache, "_default", cache)  # auto-restored after the test
    return cache


def _fake_spec(version="1"):
    return SkillSpec(
        id="fake",
        version=version,
        title="Fake",
        engine="python",
        omics="bulk-rna-seq",
        entrypoint="skills.fake.run:run",
        inputs=[],
        param_spec={"fc_threshold": {"type": "float", "default": 2.0}},
        outputs=[{"name": "figure"}],
    )


def test_execute_caches_and_skips_recompute(tmp_path, monkeypatch, fresh_cache):
    calls = {"n": 0}

    def fake_run(data_path, params):
        calls["n"] += 1
        return {"data": [{"type": "scatter", "x": [1], "y": [params["fc_threshold"]]}], "layout": {}}

    monkeypatch.setattr(contract, "load_skill", lambda sid: _fake_spec("1"))
    monkeypatch.setattr(contract, "import_module", lambda path: types.SimpleNamespace(run=fake_run))
    src = _input(tmp_path)

    fig1, _ = contract.run_skill_with_table("fake", src, {})
    fig2, _ = contract.run_skill_with_table("fake", src, {})
    assert calls["n"] == 1, "the 2nd identical run must be served from cache (no recompute)"
    # Two tiers both hit on a fully-cached re-run: the compute fetch + the render (envelope) fetch.
    assert fresh_cache.stats["mem_hits"] == 2
    assert fig1 == fig2  # the served figure is the themed compute result, identical

    # A non-default param is a clean miss -> recompute.
    contract.run_skill_with_table("fake", src, {"fc_threshold": "3"})
    assert calls["n"] == 2

    # A skill_version bump is a clean miss -> recompute, even for the original params.
    monkeypatch.setattr(contract, "load_skill", lambda sid: _fake_spec("2"))
    contract.run_skill_with_table("fake", src, {})
    assert calls["n"] == 3


def test_real_skill_path_caches_end_to_end(tmp_path, monkeypatch, fresh_cache):
    """The genuine path — real load_skill + runner + theme.apply + capability stamp — caches.
    Uses the dependency-free stub engine for determinism, over a real (hashable) input file."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    src = _input(tmp_path)

    fig1 = contract.run_skill("volcano", src, {})
    fig2 = contract.run_skill("volcano", src, {})
    # 2nd run is served from cache (runner not re-entered) — both tiers hit: compute + render.
    assert fresh_cache.stats["mem_hits"] == 2
    assert fig2 == fig1                         # the themed result is identical

    # And the disk tier serves a cold (empty in-proc) instance over the same dir (both tiers).
    cold = ResultCache(root=fresh_cache.root, mem_max=8, enabled=True)
    _result_cache.set_cache(cold)
    fig3 = contract.run_skill("volcano", src, {})
    assert cold.stats["disk_hits"] == 2 and cold.stats["mem_hits"] == 0
    assert fig3 == fig1
    # No silent disk-write failures (e.g. a filename-unsafe cache key on Windows).
    assert fresh_cache.stats["errors"] == 0 and cold.stats["errors"] == 0


def test_stub_run_with_missing_input_is_uncached(tmp_path, fresh_cache, monkeypatch):
    """A run whose input path doesn't exist (the golden harness's ``"unused"``) is unhashable,
    so the cache is skipped entirely — never a spurious key collision across distinct stub runs."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    contract.run_skill("volcano", "unused", {})
    contract.run_skill("volcano", "unused", {})
    assert fresh_cache.stats == {"mem_hits": 0, "disk_hits": 0, "misses": 0, "sets": 0, "errors": 0}


# --- C2: render / figure-envelope cache (the source/render split) ------------------------------

def test_render_caches_the_envelope(monkeypatch, fresh_cache):
    """A repeat render of the same (figure, skill, style) is a cache hit — theme.apply is not
    re-run; a different style and a THEME_VERSION bump each miss cleanly."""
    from skills import theme

    applies = {"n": 0}
    real_apply = theme.apply

    def counting_apply(spec, skill_id, style=theme.DEFAULT_STYLE):
        applies["n"] += 1
        return real_apply(spec, skill_id, style)

    monkeypatch.setattr(theme, "apply", counting_apply)
    fig = {"data": [{"type": "scatter", "x": [1], "y": [2]}], "layout": {}}

    a = theme.render(fig, "volcano", "selom")
    b = theme.render(fig, "volcano", "selom")
    assert applies["n"] == 1 and a == b          # 2nd identical render served from the envelope cache
    theme.render(fig, "volcano", "nature")
    assert applies["n"] == 2                      # a style change -> a clean miss -> re-theme
    monkeypatch.setattr(theme, "THEME_VERSION", "2")
    theme.render(fig, "volcano", "selom")
    assert applies["n"] == 3                      # a theme-version bump -> a clean miss


def test_style_change_does_not_rerun_the_skill(tmp_path, monkeypatch, fresh_cache):
    """Acceptance: a theme/style change re-renders WITHOUT re-running the skill — the compute and
    the render are separately-keyed tiers, so restyling never re-enters the runner."""
    from skills import theme

    calls = {"n": 0}

    def fake_run(data_path, params):
        calls["n"] += 1
        return {"data": [{"type": "scatter", "x": [1], "y": [params["fc_threshold"]]}], "layout": {}}

    monkeypatch.setattr(contract, "load_skill", lambda sid: _fake_spec("1"))
    monkeypatch.setattr(contract, "import_module", lambda path: types.SimpleNamespace(run=fake_run))
    src = _input(tmp_path)

    fig_default, _ = contract.run_skill_with_table("fake", src, {})
    assert calls["n"] == 1
    restyled = theme.render(fig_default, "fake", "nature")  # the FE's /figures/style/apply flow
    assert calls["n"] == 1                                  # the skill was NOT re-run
    assert isinstance(restyled, dict) and "data" in restyled

"""WS1.1 — the no-fabricated-figures-off-dev guard (RISKS #11).

Three things are pinned here:
  * ``resolve_engine_policy`` honestly reports "real" vs the synthetic "stub" — including the
    REACHABILITY assertion that with the full science stack present the stub is unreachable.
  * the prod boot guard (``config.Settings``) refuses to start when the engine would resolve to
    stub off-dev, and stays inert in dev.
  * a DRIFT guard: every module any skill gates its real engine on is covered by
    ``REQUIRED_ENGINE_MODULES`` (so a new skill's new dep can't slip past the boot guard).
"""

import pathlib
import re

import pytest
from pydantic import ValidationError

from skills import _engine

_SKILLS_DIR = pathlib.Path(__file__).resolve().parent.parent / "skills"


def _fake_find_spec(present: set[str]):
    """A find_spec stand-in: a module is importable iff it's in ``present`` — so a test can force a
    partial/complete install regardless of what's actually pip-installed in CI."""
    def _spec(name: str):
        return object() if name in present else None
    return _spec


# ---- resolve_engine_policy + reachability -------------------------------------------------------

def test_forced_stub_resolves_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    assert _engine.resolve_engine_policy() == "stub"


def test_forced_real_resolves_real_even_if_deps_missing(monkeypatch):
    # Forced real with a dep absent raises an honest ImportError inside the runner (an error, not a
    # fabricated figure) — so it must NOT be mislabelled "stub".
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set()))
    assert _engine.resolve_engine_policy() == "real"


def test_auto_with_full_stack_is_real_stub_unreachable(monkeypatch):
    # THE reachability assertion: with every required module present, `auto` resolves to real —
    # the stub path is unreachable when the extras are installed.
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "auto")
    monkeypatch.setattr(
        _engine, "find_spec", _fake_find_spec(set(_engine.REQUIRED_ENGINE_MODULES)))
    assert _engine.missing_engine_modules() == []
    assert _engine.resolve_engine_policy() == "real"


def test_auto_with_missing_dep_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "auto")
    present = set(_engine.REQUIRED_ENGINE_MODULES) - {"scanpy"}
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(present))
    assert _engine.missing_engine_modules() == ["scanpy"]
    assert _engine.resolve_engine_policy() == "stub"


# ---- prod boot guard ----------------------------------------------------------------------------

def _fresh_settings(monkeypatch, **env):
    import config
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return config.Settings()


def test_prod_refuses_forced_stub(monkeypatch):
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set(_engine.REQUIRED_ENGINE_MODULES)))
    with pytest.raises(ValidationError, match="fabricated stub"):
        _fresh_settings(monkeypatch, SELOM_ENV="prod", SELOM_SKILLS_ENGINE="stub")


def test_prod_refuses_missing_extras_under_auto(monkeypatch):
    monkeypatch.setattr(
        _engine, "find_spec", _fake_find_spec(set(_engine.REQUIRED_ENGINE_MODULES) - {"pydeseq2"}))
    with pytest.raises(ValidationError, match="fabricated stub"):
        _fresh_settings(monkeypatch, SELOM_ENV="prod", SELOM_SKILLS_ENGINE="auto")


def test_prod_refuses_forced_real_with_missing_dep(monkeypatch):
    monkeypatch.setattr(
        _engine, "find_spec", _fake_find_spec(set(_engine.REQUIRED_ENGINE_MODULES) - {"scanpy"}))
    with pytest.raises(ValidationError, match="not\n?.*importable|not importable"):
        _fresh_settings(monkeypatch, SELOM_ENV="prod", SELOM_SKILLS_ENGINE="real")


def test_prod_boots_with_full_stack(monkeypatch):
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set(_engine.REQUIRED_ENGINE_MODULES)))
    s = _fresh_settings(monkeypatch, SELOM_ENV="prod", SELOM_SKILLS_ENGINE="auto")
    assert s.is_production is True


def test_clerk_auth_counts_as_production(monkeypatch):
    # A live Clerk deploy is production even if SELOM_ENV is unset → the guard still fires.
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set()))
    with pytest.raises(ValidationError, match="fabricated stub"):
        _fresh_settings(
            monkeypatch, SELOM_AUTH_MODE="clerk", SELOM_CLERK_ISSUER="https://x.clerk.accounts.dev",
            SELOM_SKILLS_ENGINE="auto")


def test_dev_allows_stub(monkeypatch):
    # The offline inner loop / golden tests / canned demo: stubs are legit, guard inert.
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set()))
    s = _fresh_settings(monkeypatch, SELOM_ENV="dev", SELOM_SKILLS_ENGINE="stub")
    assert s.is_production is False


def test_dogfood_sql_sqlite_is_not_production(monkeypatch):
    # The documented local dogfood (SQL job store on SQLite, local files, dev auth) must stay dev,
    # so a box without the heavy extras can still run stubs. It must NOT trip the prod guard.
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set()))
    s = _fresh_settings(
        monkeypatch, SELOM_JOB_STORE="sql", SELOM_DATABASE_URL="sqlite:///dev.db",
        SELOM_SKILLS_ENGINE="stub")
    assert s.is_production is False


# ---- drift guard: the required set mirrors every skill's real-engine gate -----------------------

def test_required_modules_cover_every_skill_gate():
    referenced: set[str] = set()
    for run_py in _SKILLS_DIR.rglob("run.py"):
        text = run_py.read_text(encoding="utf-8")
        for call in re.findall(r"use_real_engine\(([^)]*)\)", text):
            referenced.update(re.findall(r"""["']([^"']+)["']""", call))
    missing = referenced - set(_engine.REQUIRED_ENGINE_MODULES)
    assert not missing, (
        f"skills gate on modules not in REQUIRED_ENGINE_MODULES: {sorted(missing)} — add them so "
        f"the prod boot guard can see them")
    assert referenced, "expected to find use_real_engine(...) calls across the skills"

"""Ratchet (boot item B): the external-corpus resolvers are env-driven with NO drive-letter
default, and an absent env var resolves to ``None`` so the reproduction/build tests SKIP — never
fail — on a host that does not hold the corpora.

This is the ONLY executable proof of the resolver available here: ``pytest`` is green with every
data-dependent test skipped, and that green proves nothing about resolution (it is the documented
silent-failure trap). This test asserts resolution directly instead.
"""

import pathlib

import config


def test_datasets_dir_resolves_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SELOM_DATASETS_DIR", str(tmp_path))
    assert config.datasets_dir() == tmp_path


def test_papers_dir_resolves_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SELOM_PAPERS_DIR", str(tmp_path))
    assert config.papers_dir() == tmp_path


def test_datasets_dir_none_when_unset(monkeypatch):
    monkeypatch.delenv("SELOM_DATASETS_DIR", raising=False)
    assert config.datasets_dir() is None


def test_papers_dir_none_when_unset(monkeypatch):
    monkeypatch.delenv("SELOM_PAPERS_DIR", raising=False)
    assert config.papers_dir() is None


def test_no_drive_letter_default(monkeypatch):
    """Neither resolver may fall back to any absolute path when its env var is unset — an absent
    corpus MUST surface as None (→ the guarded test skips), not a stale hardcoded location."""
    monkeypatch.delenv("SELOM_DATASETS_DIR", raising=False)
    monkeypatch.delenv("SELOM_PAPERS_DIR", raising=False)
    assert config.datasets_dir() is None
    assert config.papers_dir() is None


def test_resolvers_return_pathlib_when_set(monkeypatch, tmp_path):
    """When set, the resolver hands back a real ``pathlib.Path`` the guarded tests can ``.exists()``
    against — the skip idiom is ``X is None or not X.exists()``."""
    monkeypatch.setenv("SELOM_DATASETS_DIR", str(tmp_path))
    monkeypatch.setenv("SELOM_PAPERS_DIR", str(tmp_path))
    assert isinstance(config.datasets_dir(), pathlib.Path)
    assert isinstance(config.papers_dir(), pathlib.Path)

"""Startup config validation + the /ready readiness probe (hardening pre-7c).

Fail-fast config: a non-local backend selected without its required setting raises at boot,
not as a cryptic boto/SQL/JWKS error on the first request. /ready reports the backends this
instance actually depends on (vs /health, the cheap liveness probe).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from config import Settings
from skills import _engine


def _fake_find_spec(present: set[str]):
    """A find_spec stand-in (mirrors test_engine_policy_guard): a module is importable iff it's in
    ``present``, so a Settings-construction test is deterministic regardless of the extras actually
    installed. CI runs the light fast-gate closure (no pydeseq2/gseapy), so without this a valid
    production-like config would trip the WS1.1 stub-engine guard on CI while passing on the dev box."""
    def _spec(name: str):
        return object() if name in present else None
    return _spec


def _clear_selom_env(monkeypatch):
    # Fields use validation_alias (the SELOM_* env names), so drive them via env, not kwargs.
    for var in (
        "SELOM_OBJECT_STORE", "SELOM_S3_BUCKET", "SELOM_JOB_STORE", "SELOM_DATABASE_URL",
        "SELOM_AUTH_MODE", "SELOM_CLERK_ISSUER",
    ):
        monkeypatch.delenv(var, raising=False)


def test_config_rejects_s3_without_bucket(monkeypatch):
    _clear_selom_env(monkeypatch)
    monkeypatch.setenv("SELOM_OBJECT_STORE", "s3")  # bucket left unset
    with pytest.raises(ValidationError):
        Settings()


def test_config_rejects_sql_without_database_url(monkeypatch):
    _clear_selom_env(monkeypatch)
    monkeypatch.setenv("SELOM_JOB_STORE", "sql")  # database_url left unset
    with pytest.raises(ValidationError):
        Settings()


def test_config_rejects_clerk_without_issuer(monkeypatch):
    _clear_selom_env(monkeypatch)
    monkeypatch.setenv("SELOM_AUTH_MODE", "clerk")  # issuer left unset
    with pytest.raises(ValidationError):
        Settings()


def test_config_accepts_valid_s3(monkeypatch):
    _clear_selom_env(monkeypatch)
    # S3 makes this config production (is_production), so the WS1.1 guard requires a real engine.
    # Force the full science stack importable so this test verifies S3 *parsing* — not whatever
    # extras happen to be installed (the prod+stub refusal is covered in test_engine_policy_guard).
    monkeypatch.setattr(_engine, "find_spec", _fake_find_spec(set(_engine.REQUIRED_ENGINE_MODULES)))
    monkeypatch.setenv("SELOM_OBJECT_STORE", "s3")
    monkeypatch.setenv("SELOM_S3_BUCKET", "b")
    assert Settings().s3_bucket == "b"


def test_config_default_is_valid(monkeypatch):
    # local / memory / dev trips none of the cross-field checks (offline inner loop unaffected).
    _clear_selom_env(monkeypatch)
    assert Settings().object_store == "local"


def test_health_is_unconditional():
    from main import app

    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_ok_on_default_backends():
    # Default: object_store=local (head never errors), job_store=memory (no DB check) -> 200 ok.
    from main import app

    r = TestClient(app).get("/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["object_store"] == "ok"
    assert "database" not in body["checks"]  # memory job store -> DB not probed

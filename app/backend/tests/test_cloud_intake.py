"""Remote-intake endpoint (POST /uploads/intake/remote) — a URL import must ride the existing
intake→confirm→parse pipeline and terminate in a **ready, parsed** dataset with import provenance.
The URL connector is swapped for a MockTransport-backed one (no network); the rest is the real repo +
LocalObjectStore, exactly like tests/test_uploads.py.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from cloud import registry
from cloud.connectors.url import UrlConnector
from storage.object_store import LocalObjectStore, set_object_store
from uploads.repo import UploadRepo, set_upload_repo

CSV = b"gene,ctrl,treat\nACTB,10,20\nGAPDH,30,40\n"
PUBLIC = "http://93.184.216.34/counts.csv"


class _SwitchVerifier:
    def __init__(self, user_id: str = "A") -> None:
        self.user_id = user_id

    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id=self.user_id, email=f"{self.user_id}@x.com")


def _mock_url_connector(content: bytes) -> UrlConnector:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": "text/csv"})
    return UrlConnector(transport=httpx.MockTransport(handler))


@pytest.fixture
def env(tmp_path):
    from main import app

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'up.db'}", future=True)
    set_upload_repo(UploadRepo(engine=engine, create=True))
    set_object_store(LocalObjectStore(tmp_path / "obj"))
    app.dependency_overrides[get_verifier] = lambda: _SwitchVerifier("A")
    original_url_connector = registry.get_connector("url")
    registry.set_connector("url", _mock_url_connector(CSV))
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        registry.set_connector("url", original_url_connector)
        set_upload_repo(None)
        set_object_store(None)
        engine.dispose()


def _project(client) -> str:
    r = client.post("/projects", json={"name": "P1"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_url_import_terminates_in_ready_parsed_dataset(env):
    client = env
    pid = _project(client)

    r = client.post("/uploads/intake/remote",
                    json={"project_id": pid, "provider": "url", "ref": PUBLIC})
    assert r.status_code == 200, r.text
    ds = r.json()
    assert ds["status"] == "ready"
    assert ds["size_bytes"] == len(CSV)                       # confirm stamped the streamed size
    assert ds["parquet_s3_key"] and ds["parquet_s3_key"].startswith("data/")
    assert ds["parquet_s3_key"].endswith(".csv")             # parsed the CSV (materialize ran)
    assert ds["source"]["provider"] == "url"                 # import provenance
    assert ds["source"]["ref"] == PUBLIC
    assert ds["source"]["fetched_at"]


def test_unknown_provider_is_404(env):
    client = env
    pid = _project(client)
    r = client.post("/uploads/intake/remote",
                    json={"project_id": pid, "provider": "nope", "ref": PUBLIC})
    assert r.status_code == 404


def test_oauth_provider_refuses_cleanly_while_its_flag_is_off(env, monkeypatch):
    """A flag-off OAuth provider gives a clean "not configured" (never a 500).

    The flag is forced OFF here rather than assumed off. It used to rely on the default, which made
    the test pass only while nobody had enabled the provider in their own ``.env`` — so L2-02
    (enabling Google + Dropbox for real) turned a correct config change into a red gate that said
    nothing about the code. Flag state is an input to this assertion, so it is set, not inherited.
    """
    import routers.cloud as cloud_router

    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", False, raising=False)
    client = env
    pid = _project(client)
    r = client.post("/uploads/intake/remote",
                    json={"project_id": pid, "provider": "google", "ref": "file-id-123"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "provider_not_configured"


def test_enabled_oauth_provider_gets_past_the_flag_gate_and_fails_at_the_broker(env, monkeypatch):
    """The other half, and the one that proves L2-02 actually opened something.

    With the flag ON the request is no longer refused by the gate — it reaches the Nango exchange and
    fails there for want of a connection id. A different error from a different layer is the evidence
    the gate is open; asserting only the flag-off case would pass just as well with the feature still
    sealed.
    """
    import routers.cloud as cloud_router

    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", True, raising=False)
    client = env
    pid = _project(client)
    r = client.post("/uploads/intake/remote",
                    json={"project_id": pid, "provider": "google", "ref": "file-id-123"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert not isinstance(detail, dict) or detail.get("error") != "provider_not_configured", (
        "the flag gate still refused an ENABLED provider"
    )
    assert "connection" in str(detail).lower() or "nango" in str(detail).lower()


def test_import_into_foreign_project_is_404(env):
    # T1: a tenant can't import into another tenant's project.
    client = env
    pid = _project(client)
    app_overrides = client.app.dependency_overrides
    app_overrides[get_verifier] = lambda: _SwitchVerifier("B")
    r = client.post("/uploads/intake/remote",
                    json={"project_id": pid, "provider": "url", "ref": PUBLIC})
    assert r.status_code == 404

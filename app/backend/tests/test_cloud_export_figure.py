"""``POST /export/cloud`` with a **figure** source (Track E / docs/cloud-export/spec.md D2).

A figure has no stored object — it is rendered on demand and streamed straight to the provider.
These tests pin the routing and the guards; the connector wire itself is covered by
``test_cloud_export.py``, and the real round trip is owed by `E-3` in a browser
([[selom-mock-is-wire-only-verify-real]]).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from cloud import registry
from cloud.errors import CloudFetchError

FIGURE = {"data": [{"type": "scatter", "x": [1, 2], "y": [3, 4]}], "layout": {}}


class _Verifier:
    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id="A", email="a@x.com")


class RecordingConnector:
    """Stands in for a provider: records what it was asked to upload."""

    def __init__(self, fail: Exception | None = None):
        self.calls: list[dict] = []
        self.fail = fail

    def push_path(self, local_path, dest, token, *, filename):
        if self.fail:
            raise self.fail
        payload = local_path.read_bytes()
        self.calls.append({"dest": dest, "token": token, "filename": filename,
                           "bytes": len(payload), "existed": local_path.is_file()})
        return len(payload)

    def push_from_store(self, key, dest, token):  # pragma: no cover - dataset path unused here
        raise AssertionError("figure export must not go through push_from_store")


@pytest.fixture
def client():
    from main import app

    app.dependency_overrides[get_verifier] = lambda: _Verifier()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_verifier, None)


@pytest.fixture
def wired(monkeypatch):
    """Enable the URL provider path with a recording connector and a stubbed renderer."""
    conn = RecordingConnector()
    monkeypatch.setattr(registry, "get_connector", lambda pid: conn)
    monkeypatch.setattr("export.render", lambda *a, **k: b"RENDERED-BYTES")
    return conn


def test_figure_is_rendered_and_pushed(client, wired):
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "s3://bucket/figs/", "figure": FIGURE,
        "format": "png", "filename": "erg-traces"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["bytes"] == len(b"RENDERED-BYTES")
    assert body["filename"] == "erg-traces.png"

    assert len(wired.calls) == 1
    call = wired.calls[0]
    assert call["filename"] == "erg-traces.png"
    assert call["bytes"] == len(b"RENDERED-BYTES")
    assert call["existed"] is True          # the file was on disk when the connector ran
    assert call["dest"] == "s3://bucket/figs/"


def test_filename_extension_is_forced_to_match_the_format(client, wired):
    """A user typing "figure.png" while exporting SVG must not get a mislabelled file."""
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": FIGURE,
        "format": "svg", "filename": "figure.png"})
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "figure.svg"
    assert wired.calls[0]["filename"] == "figure.svg"


def test_default_filename_when_none_given(client, wired):
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": FIGURE, "format": "pdf"})
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "selom-figure.pdf"


def test_sending_both_sources_is_rejected(client, wired):
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": FIGURE, "dataset_id": "ds-1"})
    assert r.status_code == 400
    assert "exactly one" in r.text


def test_sending_neither_source_is_rejected(client, wired):
    r = client.post("/export/cloud", json={"provider": "url", "dest": "d"})
    assert r.status_code == 400
    assert "exactly one" in r.text


def test_unsupported_format_is_rejected_before_rendering(client, monkeypatch):
    def boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("render must not be reached for a bad format")

    monkeypatch.setattr("export.render", boom)
    monkeypatch.setattr(registry, "get_connector", lambda pid: RecordingConnector())
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": FIGURE, "format": "bmp"})
    assert r.status_code == 400
    assert "unsupported format" in r.text


def test_figure_without_data_array_is_rejected(client, wired):
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": {"layout": {}}})
    assert r.status_code == 400
    assert "Plotly spec" in r.text


def test_renderer_unavailable_degrades_to_503(client, monkeypatch):
    import export as figure_export

    def unavailable(*a, **k):
        raise figure_export.ExportUnavailable("kaleido missing")

    monkeypatch.setattr("export.render", unavailable)
    monkeypatch.setattr(registry, "get_connector", lambda pid: RecordingConnector())
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": FIGURE})
    assert r.status_code == 503


def test_provider_error_surfaces_as_400(client, monkeypatch):
    monkeypatch.setattr("export.render", lambda *a, **k: b"X")
    monkeypatch.setattr(registry, "get_connector",
                        lambda pid: RecordingConnector(fail=CloudFetchError("drive said no")))
    r = client.post("/export/cloud", json={
        "provider": "url", "dest": "d", "figure": FIGURE})
    assert r.status_code == 400
    assert "drive said no" in r.text


def test_unknown_provider_is_404(client, wired):
    r = client.post("/export/cloud", json={
        "provider": "nope", "dest": "d", "figure": FIGURE})
    assert r.status_code == 404


def test_disabled_oauth_provider_refuses_cleanly(client, wired, monkeypatch):
    """A flag-off provider must not reach the connector -- the user gets the connect prompt."""
    monkeypatch.setattr(registry, "is_enabled", lambda p, s: False)
    r = client.post("/export/cloud", json={
        "provider": "google", "dest": "folder", "figure": FIGURE})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "provider_not_configured"
    assert wired.calls == []

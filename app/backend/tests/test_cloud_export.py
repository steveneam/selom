"""Cloud export (Track E / docs/cloud-export/spec.md) — the OAuth connectors' ``push_path``.

Wire-level tests against ``httpx.MockTransport``, mirroring the import-side tests. A mock proves
the wire, not the product ([[selom-mock-is-wire-only-verify-real]]) — the real round trip against
the live broker is owed by `E-3`, in a browser.
"""

from __future__ import annotations

import json

import httpx
import pytest

from cloud.connectors.dropbox import SIMPLE_UPLOAD_MAX, DropboxConnector
from cloud.connectors.google import GoogleDriveConnector
from cloud.errors import CloudFetchError

SESSION_URI = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=x"


def _file(tmp_path, name="selom-figure.png", size=2048):
    p = tmp_path / name
    p.write_bytes(b"\xff" * size)
    return p


# --- Google Drive -------------------------------------------------------------------------

def test_google_push_path_resumable_round_trip(tmp_path):
    """Session is opened with the metadata, then the bytes go to the returned session URI."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["metadata"] = json.loads(request.content)
            seen["upload_len"] = request.headers.get("x-upload-content-length")
            return httpx.Response(200, headers={"Location": SESSION_URI})
        seen["put_url"] = str(request.url)
        seen["body_len"] = len(request.content)
        return httpx.Response(200, json={"id": "drive-file-1"})

    src = _file(tmp_path)
    n = GoogleDriveConnector().push_path(
        src, "folder-123", "tok", filename="selom-figure.png",
        transport=httpx.MockTransport(handler))

    assert n == 2048
    assert seen["metadata"] == {"name": "selom-figure.png", "parents": ["folder-123"]}
    assert seen["upload_len"] == "2048"
    assert seen["put_url"] == SESSION_URI
    assert seen["body_len"] == 2048          # the payload actually reached the session URI


@pytest.mark.parametrize("dest", ["", "root", "/"])
def test_google_empty_dest_is_my_drive(tmp_path, dest):
    """An unset folder must mean My Drive -- not a literal folder named "" or "root"."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["metadata"] = json.loads(request.content)
            return httpx.Response(200, headers={"Location": SESSION_URI})
        return httpx.Response(200)

    GoogleDriveConnector().push_path(_file(tmp_path), dest, "tok", filename="f.png",
                                     transport=httpx.MockTransport(handler))
    assert "parents" not in seen["metadata"]


def test_google_session_uri_on_a_308_is_read_not_followed(tmp_path):
    """Drive's resumable protocol also answers with **308** + Location, and a redirect must be READ
    here, never followed.

    Followed, httpx re-POSTs the *metadata* JSON to the session URI instead of reading it: measured
    against the real API path, that loops to httpx's redirect cap with a 17-byte metadata body on
    every hop, so the figure's bytes never leave the box and the upload still looks plausible from
    the outside. Found by A1, the first real round trip (2026-08-02).
    """
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), len(request.content)))
        if request.method == "POST":
            return httpx.Response(308, headers={"Location": SESSION_URI})
        return httpx.Response(200, json={"id": "drive-file-1"})

    n = GoogleDriveConnector().push_path(
        _file(tmp_path), "", "tok", filename="f.png", transport=httpx.MockTransport(handler))

    assert n == 2048
    posts = [c for c in seen if c[0] == "POST"]
    puts = [c for c in seen if c[0] == "PUT"]
    assert len(posts) == 1, f"the session init was retried/followed: {posts}"
    assert len(puts) == 1 and puts[0][1] == SESSION_URI
    assert puts[0][2] == 2048, "the PAYLOAD must reach the session URI, not the metadata"


def test_google_missing_session_uri_is_an_error(tmp_path):
    """A 200 with no Location must not be read as success -- nothing was uploaded."""
    transport = httpx.MockTransport(lambda r: httpx.Response(200))
    with pytest.raises(CloudFetchError, match="no resumable session URI"):
        GoogleDriveConnector().push_path(_file(tmp_path), "f", "tok", filename="f.png",
                                         transport=transport)


def test_google_upload_failure_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, headers={"Location": SESSION_URI})
        return httpx.Response(403)

    with pytest.raises(CloudFetchError, match="HTTP 403"):
        GoogleDriveConnector().push_path(_file(tmp_path), "f", "tok", filename="f.png",
                                         transport=httpx.MockTransport(handler))


def test_google_export_without_token_refuses(tmp_path):
    with pytest.raises(CloudFetchError, match="connected account"):
        GoogleDriveConnector().push_path(_file(tmp_path), "f", None, filename="f.png")


# --- Dropbox ------------------------------------------------------------------------------

def test_dropbox_simple_upload_uses_add_and_autorename(tmp_path):
    """An export must never silently overwrite a user's file (spec R7)."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["arg"] = json.loads(request.headers["dropbox-api-arg"])
        seen["body_len"] = len(request.content)
        return httpx.Response(200, json={"name": "f.png"})

    n = DropboxConnector().push_path(_file(tmp_path), "/Reports", "tok", filename="f.png",
                                     transport=httpx.MockTransport(handler))
    assert n == 2048
    assert seen["url"].endswith("/files/upload")
    assert seen["arg"]["path"] == "/Reports/f.png"
    assert seen["arg"]["mode"] == "add"
    assert seen["arg"]["autorename"] is True
    assert seen["body_len"] == 2048


def test_dropbox_empty_dest_is_app_folder_root(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["arg"] = json.loads(request.headers["dropbox-api-arg"])
        return httpx.Response(200)

    DropboxConnector().push_path(_file(tmp_path), "", "tok", filename="f.png",
                                 transport=httpx.MockTransport(handler))
    assert seen["arg"]["path"] == "/f.png"


def test_dropbox_api_arg_header_is_ascii_only(tmp_path):
    """``Dropbox-API-Arg`` is an HTTP header, so it must be **pure ASCII** — and a Selom figure name
    very often is not ("µV", an en dash, a Greek gene symbol).

    ``json.dumps`` defaults to ``ensure_ascii=True``, which escapes them to ``\\uXXXX`` — exactly
    what Dropbox documents. That makes the requirement satisfied *implicitly*: switching to
    ``ensure_ascii=False`` "for readability" would keep every mock green while breaking every real
    upload with a non-ASCII name. This is the executable form of that constraint.
    """
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["raw"] = request.headers["dropbox-api-arg"]
        return httpx.Response(200)

    name = "Selom — b-wave µV.png"
    DropboxConnector().push_path(_file(tmp_path), "", "tok", filename=name,
                                 transport=httpx.MockTransport(handler))

    seen["raw"].encode("ascii")                      # raises if a raw non-ASCII byte got through
    assert "µ" not in seen["raw"] and "—" not in seen["raw"]
    assert json.loads(seen["raw"])["path"] == f"/{name}"   # …and it still decodes to the real name


def test_dropbox_large_file_uses_upload_session(tmp_path, monkeypatch):
    """Over the 150 MB single-call ceiling the session path must run, and the offsets must be
    contiguous -- a wrong offset is the classic chunked-upload corruption, and it would still
    return a plausible byte count."""
    # Shrink the ceiling + chunk instead of writing 150 MB to disk.
    monkeypatch.setattr("cloud.connectors.dropbox.SIMPLE_UPLOAD_MAX", 4096)
    monkeypatch.setattr("cloud.connectors.dropbox._CHUNK", 1024)

    calls: list[tuple[str, int]] = []
    body_total = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        arg = json.loads(request.headers["dropbox-api-arg"])
        body_total["n"] += len(request.content)
        if str(request.url).endswith("/upload_session/start"):
            calls.append(("start", 0))
            return httpx.Response(200, json={"session_id": "sess-1"})
        if str(request.url).endswith("/upload_session/append_v2"):
            calls.append(("append", arg["cursor"]["offset"]))
            return httpx.Response(200)
        calls.append(("finish", arg["cursor"]["offset"]))
        return httpx.Response(200, json={"name": "big.h5ad"})

    src = _file(tmp_path, "big.h5ad", size=5000)   # > 4096 ceiling, 1024 chunks
    n = DropboxConnector().push_path(src, "/data", "tok", filename="big.h5ad",
                                     transport=httpx.MockTransport(handler))

    assert n == 5000
    assert body_total["n"] == 5000                     # every byte was sent exactly once
    assert calls[0][0] == "start"
    assert calls[-1][0] == "finish"
    assert [o for _k, o in calls[1:-1]] == [1024, 2048, 3072, 4096]   # contiguous offsets
    assert calls[-1][1] == 5000                        # finish commits at the full length


def test_dropbox_session_failure_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("cloud.connectors.dropbox.SIMPLE_UPLOAD_MAX", 1024)
    monkeypatch.setattr("cloud.connectors.dropbox._CHUNK", 512)

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/upload_session/start"):
            return httpx.Response(200, json={"session_id": "s"})
        return httpx.Response(500)

    with pytest.raises(CloudFetchError, match="offset"):
        DropboxConnector().push_path(_file(tmp_path, size=2000), "", "tok", filename="f",
                                     transport=httpx.MockTransport(handler))


def test_dropbox_export_without_token_refuses(tmp_path):
    with pytest.raises(CloudFetchError, match="connected account"):
        DropboxConnector().push_path(_file(tmp_path), "", None, filename="f.png")


def test_simple_upload_ceiling_matches_dropbox_api():
    """Guard the documented limit: raising it past 150 MB breaks real uploads silently."""
    assert SIMPLE_UPLOAD_MAX == 150 * 1024 * 1024


# --- the shared seam ----------------------------------------------------------------------

def test_push_from_store_downloads_then_delegates_to_push_path(tmp_path, monkeypatch):
    """``push_from_store`` must be the download half plus ``push_path`` -- and must clean up the
    temp copy even though the upload succeeded."""
    from cloud.connectors import base

    seen = {}

    class FakeStore:
        def download_to_path(self, key, dest):
            seen["temp_dir"] = dest.parent
            dest.write_bytes(b"payload")
            return True

    monkeypatch.setattr("storage.object_store.get_object_store", lambda: FakeStore())

    class Recorder:
        def push_path(self, local_path, dest, token, *, filename):
            seen["filename"] = filename
            seen["bytes"] = local_path.read_bytes()
            return len(seen["bytes"])

    n = base.push_store_object_via_path(Recorder(), "tenant/abc/figure.png", "folder", "tok")
    assert n == 7
    assert seen["filename"] == "figure.png"      # basename, not the whole key
    assert seen["bytes"] == b"payload"
    assert not seen["temp_dir"].exists()         # temp dir removed on the way out


def test_push_from_store_raises_when_object_missing(monkeypatch):
    from cloud.connectors import base

    class EmptyStore:
        def download_to_path(self, key, dest):
            return False

    monkeypatch.setattr("storage.object_store.get_object_store", lambda: EmptyStore())
    with pytest.raises(CloudFetchError, match="object not in store"):
        base.push_store_object_via_path(object(), "k", "d", "t")

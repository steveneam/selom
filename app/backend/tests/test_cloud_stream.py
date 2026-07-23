"""Streaming import mechanics: the ObjectStore streaming put, the byte-cap reader, and the URL
connector happy-path (an httpx MockTransport serves the bytes so no network is touched; a public IP
literal keeps the SSRF guard satisfied without DNS)."""

from __future__ import annotations

import io

import httpx
import pytest

from cloud._stream import CappedReader
from cloud.connectors.url import UrlConnector
from cloud.errors import CloudTooLarge
from storage.object_store import LocalObjectStore, set_object_store

CSV = b"gene,ctrl,treat\nACTB,10,20\nGAPDH,30,40\n"
PUBLIC = "http://93.184.216.34/counts.csv"   # public IP literal → SSRF guard passes, no DNS


@pytest.fixture
def store(tmp_path):
    s = LocalObjectStore(tmp_path / "obj")
    set_object_store(s)
    try:
        yield s
    finally:
        set_object_store(None)


# --- ObjectStore.put_stream -------------------------------------------------------------------

def test_local_put_stream_writes_without_buffering(store):
    store.put_stream("data/x.csv", io.BytesIO(CSV), "text/csv")
    assert store.get_bytes("data/x.csv") == CSV
    assert store.head_size("data/x.csv") == len(CSV)


# --- CappedReader -----------------------------------------------------------------------------

def test_capped_reader_passes_under_cap():
    r = CappedReader([b"ab", b"cd", b"ef"], max_bytes=100)
    assert r.read() == b"abcdef"
    assert r.bytes_read == 6


def test_capped_reader_raises_over_cap():
    r = CappedReader([b"x" * 50, b"y" * 60], max_bytes=100)
    with pytest.raises(CloudTooLarge):
        r.read()   # pulling the 2nd chunk crosses 100 → raises


# --- UrlConnector.fetch_to_store (happy + cap) via MockTransport -------------------------------

def _connector(content: bytes, status: int = 200) -> UrlConnector:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content, headers={"content-type": "text/csv"})
    return UrlConnector(transport=httpx.MockTransport(handler))


def test_url_connector_streams_to_store(store):
    n = _connector(CSV).fetch_to_store(PUBLIC, None, "data/counts.csv", 10_000_000)
    assert n == len(CSV)
    assert store.get_bytes("data/counts.csv") == CSV


def test_url_connector_enforces_byte_cap(store):
    with pytest.raises(CloudTooLarge):
        _connector(b"z" * 5000).fetch_to_store(PUBLIC, None, "data/big.csv", 1000)
    # the aborted stream leaves no finished object behind
    assert store.get_bytes("data/big.csv") is None


def test_url_connector_maps_http_error(store):
    from cloud.errors import CloudFetchError

    with pytest.raises(CloudFetchError):
        _connector(b"", status=404).fetch_to_store(PUBLIC, None, "data/x.csv", 10_000)

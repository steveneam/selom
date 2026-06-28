"""§14 local↔backend parity for the ObjectStore seam (materialization step 1).

The dev path (`local`) must be a faithful stand-in for prod (`s3`): the same adapter
over the same Protocol behaves identically across the seam (plan D6, "the dev path never
requires AWS"). We assert that transparency here without boto3/network by parametrizing
over the filesystem `LocalObjectStore` and a dict-backed `InMemoryObjectStore` that mimics
S3-style presigning. The real-boto3 S3 backend is proven by the live round-trip script
(docs/aws-materialization/spec.md §14, §15-A).
"""

from __future__ import annotations

import pytest

from storage.object_store import LocalObjectStore
from storage.results import ObjectStoreResultStore, make_result_store


class InMemoryObjectStore:
    """An S3-shaped ObjectStore (dict-backed) — `presign_get` signs a URL the way
    `S3ObjectStore` does (a signing op, independent of existence)."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def get_bytes(self, key: str) -> bytes | None:
        return self._data.get(key)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._data[key] = data

    def head(self, key: str) -> bool:
        return key in self._data

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def presign_get(self, key: str, ttl: int) -> str | None:
        return f"https://s3.example.test/{key}?X-Amz-Expires={ttl}&X-Amz-Signature=test"


@pytest.fixture(params=["local", "memory"])
def store(request, tmp_path):
    if request.param == "local":
        return LocalObjectStore(tmp_path / "objstore")
    return InMemoryObjectStore()


# --- ObjectStore byte parity (identical on both backends) ------------------------------------

def test_get_absent_is_none(store):
    assert store.get_bytes("results/nope.json") is None


def test_put_get_roundtrip_byte_identical(store):
    payload = b'{"figure": {"data": [1, 2, 3]}}'
    store.put_bytes("results/abc.json", payload, "application/json")
    assert store.get_bytes("results/abc.json") == payload  # byte-identical


def test_head_matches_existence(store):
    assert store.head("results/k.json") is False
    store.put_bytes("results/k.json", b"x")
    assert store.head("results/k.json") is True


def test_overwrite_is_idempotent_same_bytes(store):
    # Content-addressed keys mean a re-write carries identical bytes -> a no-op in effect.
    store.put_bytes("results/k.json", b"same")
    store.put_bytes("results/k.json", b"same")
    assert store.get_bytes("results/k.json") == b"same"


def test_delete_removes(store):
    store.put_bytes("results/k.json", b"x")
    store.delete("results/k.json")
    assert store.head("results/k.json") is False
    assert store.get_bytes("results/k.json") is None
    store.delete("results/k.json")  # delete-absent is a no-op


# --- Result adapter parity over the seam -----------------------------------------------------

_BUNDLE = {"figure": {"data": [{"x": [1], "y": [2]}]}, "provenance": {"skill": "volcano"}, "methods": "t"}


def test_result_adapter_roundtrip(store):
    rs = ObjectStoreResultStore(store, presign_ttl=900)
    url = rs.put("job-abc", _BUNDLE)
    assert isinstance(url, str) and url
    assert rs.get("job-abc") == _BUNDLE                       # JSON round-trip
    assert rs.url_if_exists("job-abc") == url                 # same URL when present
    assert rs.get("missing") is None
    assert rs.url_if_exists("missing") is None
    assert store.head("results/job-abc.json") is True         # key placement per §3


def test_local_url_is_in_app_route(tmp_path):
    rs = ObjectStoreResultStore(LocalObjectStore(tmp_path), presign_ttl=900)
    assert rs.put("job-xyz", _BUNDLE) == "/jobs/job-xyz/result"


def test_s3_shaped_url_is_presigned():
    rs = ObjectStoreResultStore(InMemoryObjectStore(), presign_ttl=900)
    url = rs.put("job-xyz", _BUNDLE)
    assert url.startswith("https://") and "results/job-xyz.json" in url


def test_same_bundle_yields_identical_bytes_across_backends(tmp_path):
    """A full result write is backend-independent: same bundle -> same results/{id}.json bytes."""
    local = LocalObjectStore(tmp_path / "l")
    mem = InMemoryObjectStore()
    ObjectStoreResultStore(local, 900).put("j", _BUNDLE)
    ObjectStoreResultStore(mem, 900).put("j", _BUNDLE)
    assert local.get_bytes("results/j.json") == mem.get_bytes("results/j.json")


# --- the config seam selects the backend (mirrors make_result_store) -------------------------

def test_make_result_store_selects_local(tmp_path):
    import types

    settings = types.SimpleNamespace(object_store="local", data_dir=tmp_path, s3_presign_ttl=3600)
    rs = make_result_store(settings)
    rs.put("j1", _BUNDLE)
    assert rs.get("j1") == _BUNDLE
    assert (tmp_path / "results" / "j1.json").exists()  # lands under data_dir/results, unchanged

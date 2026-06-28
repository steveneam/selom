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

    def head_size(self, key: str) -> int | None:
        v = self._data.get(key)
        return len(v) if v is not None else None

    def download_to_path(self, key: str, dest) -> bool:
        import pathlib

        v = self._data.get(key)
        if v is None:
            return False
        dest = pathlib.Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(v)
        return True

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


def test_head_size_matches(store):
    assert store.head_size("results/s.json") is None
    store.put_bytes("results/s.json", b"12345")
    assert store.head_size("results/s.json") == 5


def test_download_to_path_streams(store, tmp_path):
    dest = tmp_path / "out" / "f.csv"
    assert store.download_to_path("data/x.csv", dest) is False  # absent -> False, no file
    assert not dest.exists()
    store.put_bytes("data/x.csv", b"a,b\n1,2\n")
    assert store.download_to_path("data/x.csv", dest) is True
    assert dest.read_bytes() == b"a,b\n1,2\n"                     # streamed byte-identical


# --- head_size error semantics (M3): "absent" -> None, but a broken call MUST raise -----------
# Swallowing every exception made a throttle/403/5xx look identical to "not there", so
# upload-confirm returned a misleading 409 on a transient error. Distinguish absent from broken.


def _stub_s3_store(raiser):
    from storage.object_store import S3ObjectStore

    store = S3ObjectStore.__new__(S3ObjectStore)  # bypass __init__ (no boto3 client/creds)
    store.bucket = "b"

    class _Client:
        def head_object(self, **kw):
            raise raiser()

    store.client = _Client()
    return store


def test_head_size_404_is_none():
    pytest.importorskip("botocore")
    from botocore.exceptions import ClientError

    store = _stub_s3_store(
        lambda: ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
    )
    assert store.head_size("k") is None


def test_head_size_reraises_non_404():
    pytest.importorskip("botocore")
    from botocore.exceptions import ClientError

    store = _stub_s3_store(
        lambda: ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject")
    )
    with pytest.raises(ClientError):
        store.head_size("k")  # a 403 is NOT "absent" — it must surface, not return None


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


def test_local_presign_put_is_in_app_shape(tmp_path):
    # The local upload presign returns the same {url, fields} shape as S3 so the FE upload code is
    # backend-agnostic; the key is bound (T1 — server-derived, not client input).
    out = LocalObjectStore(tmp_path).presign_put("uploads/A/p/d/x.csv", ttl=300, max_bytes=1024)
    assert set(out) == {"url", "fields"}
    assert out["fields"]["key"] == "uploads/A/p/d/x.csv"
    assert out["fields"]["max_bytes"] == 1024


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


# --- cache / lineage / ledger adapter parity (the other three converged stores) --------------
# §14: every content-addressed store rides the ONE ObjectStore seam, so each behaves identically
# on both backends and places its bytes under its own prefix (cache/result/, artifacts/, repro/).


def test_result_cache_durable_tier_over_the_seam(store):
    from skills._result_cache import ResultCache

    # mem_max=0 forces every read past the in-proc tier onto the durable (object-store) tier.
    cache = ResultCache(object_store=store, mem_max=0)
    cache.set("ck", {"data": [1]}, {"rows": [2]})
    assert cache.get("ck") == {"figure": {"data": [1]}, "table": {"rows": [2]}}
    assert cache.stats["disk_hits"] == 1 and cache.stats["errors"] == 0
    assert store.head("cache/result/ck.json") is True        # key placement per §3
    assert cache.get("absent") is None


def test_artifact_store_over_the_seam(store):
    from engine.lineage import ArtifactMeta, ArtifactStore

    meta = ArtifactMeta(artifact_id="aid123", kind="ingested", filename="de.csv",
                        n_rows=1, n_cols=2, columns=["a", "b"])
    ArtifactStore(object_store=store).put("aid123", meta, b"a,b\n1,2\n")
    # a cold instance (empty in-proc meta cache) reads both table + meta back over the seam
    cold = ArtifactStore(object_store=store)
    assert cold.get_table("aid123") == b"a,b\n1,2\n"          # round-trip the bytes
    back = cold.get_meta("aid123")
    assert back is not None and back.artifact_id == "aid123" and back.columns == ["a", "b"]
    assert store.head("artifacts/aid123.csv") and store.head("artifacts/aid123.meta.json")
    assert cold.get_table("missing") is None


def test_ledger_store_over_the_seam(store):
    import reproduction as R

    ledger = R.Ledger(paper=R.Paper(id="p1", slug="parity-paper", title="T"))
    ls = R.ObjectStoreLedgerStore(object_store=store)
    assert ls.exists("parity-paper") is False
    key = ls.save(ledger)
    assert key == "repro/parity-paper/ledger.json"           # key placement per §3
    assert store.head(key) is True and ls.exists("parity-paper") is True
    back = ls.load("parity-paper")                            # cold load over the seam
    assert back.paper.slug == "parity-paper" and back.paper.title == "T"


def test_ledger_load_absent_raises(store):
    import reproduction as R

    with pytest.raises(FileNotFoundError):
        R.ObjectStoreLedgerStore(object_store=store).load("nope")


# --- the config seam selects the backend (mirrors make_result_store) -------------------------

def test_make_result_store_selects_local(tmp_path):
    import types

    settings = types.SimpleNamespace(object_store="local", data_dir=tmp_path, s3_presign_ttl=3600)
    rs = make_result_store(settings)
    rs.put("j1", _BUNDLE)
    assert rs.get("j1") == _BUNDLE
    assert (tmp_path / "results" / "j1.json").exists()  # lands under data_dir/results, unchanged


# --- the REAL S3ObjectStore (boto3) against an in-memory S3 (moto) ---------------------------
# Proves the actual boto3 code path — get/put/head/delete/presign — in the fast suite, with no
# network or real AWS. The live HTTP fetch through a presigned URL is covered by the live script
# (scratchpad/verify_s3_roundtrip.py); moto's presigned URL is well-formed but not HTTP-fetchable
# in decorator mode, so we assert its shape, not a fetch. Skipped cleanly if moto is absent.

_REGION = "ap-southeast-2"


def test_real_s3objectstore_against_moto():
    moto = pytest.importorskip("moto")
    import types

    import boto3

    from storage.object_store import S3ObjectStore

    with moto.mock_aws():
        boto3.client("s3", region_name=_REGION).create_bucket(
            Bucket="parity-bucket",
            CreateBucketConfiguration={"LocationConstraint": _REGION},
        )
        store = S3ObjectStore(types.SimpleNamespace(s3_bucket="parity-bucket", s3_region=_REGION))

        # ObjectStore byte parity through the real boto3 client (moto intercepts the calls)
        assert store.get_bytes("results/x.json") is None
        store.put_bytes("results/x.json", b'{"k": 1}', "application/json")
        assert store.get_bytes("results/x.json") == b'{"k": 1}'
        assert store.head("results/x.json") is True
        store.put_bytes("results/x.json", b'{"k": 1}')  # idempotent re-write
        assert store.get_bytes("results/x.json") == b'{"k": 1}'
        assert store.head_size("results/x.json") == len(b'{"k": 1}')
        url = store.presign_get("results/x.json", 300)
        assert url and url.startswith("https://") and "results/x.json" in url
        # download_to_path streams to disk (the large-omics parse reads from here, not get_bytes)
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            dest = pathlib.Path(td) / "x.json"
            assert store.download_to_path("results/x.json", dest) is True
            assert dest.read_bytes() == b'{"k": 1}'
            assert store.download_to_path("results/absent.json", dest.with_name("absent")) is False
        # presign_put: a POST policy ({url, fields}) with the key bound + a size ceiling signed in.
        post = store.presign_put("uploads/A/p/d/x.csv", 300, 1_000_000)
        assert post["url"].startswith("https://") and post["fields"]["key"] == "uploads/A/p/d/x.csv"
        # the size ceiling is signed into the policy (field name varies by sig version)
        assert "policy" in post["fields"]
        assert any("signature" in k.lower() for k in post["fields"])
        store.delete("results/x.json")
        assert store.head("results/x.json") is False

        # the result adapter over the real S3 backend
        rs = ObjectStoreResultStore(store, presign_ttl=300)
        put_url = rs.put("job1", _BUNDLE)
        assert put_url.startswith("https://")        # S3 -> presigned, not the local route
        assert rs.get("job1") == _BUNDLE              # JSON round-trip via boto3
        assert rs.url_if_exists("job1")               # truthy URL (signing time varies — no eq)
        assert rs.get("absent") is None
        assert store.head("results/job1.json") is True

        # all four converged stores ride the SAME real S3 backend (cache · lineage · ledger)
        from engine.lineage import ArtifactMeta, ArtifactStore
        from skills._result_cache import ResultCache

        import reproduction as R

        cache = ResultCache(object_store=store, mem_max=0)
        cache.set("ck", {"data": [1]}, {"rows": [2]})
        assert cache.get("ck") == {"figure": {"data": [1]}, "table": {"rows": [2]}}
        assert store.head("cache/result/ck.json") is True

        meta = ArtifactMeta(artifact_id="aidS3", kind="ingested", filename="de.csv",
                            n_rows=1, n_cols=2, columns=["a", "b"])
        ArtifactStore(object_store=store).put("aidS3", meta, b"a,b\n1,2\n")
        assert ArtifactStore(object_store=store).get_table("aidS3") == b"a,b\n1,2\n"
        assert store.head("artifacts/aidS3.meta.json") is True

        ls = R.ObjectStoreLedgerStore(object_store=store)
        ls.save(R.Ledger(paper=R.Paper(id="p1", slug="s3-paper", title="T")))
        assert ls.load("s3-paper").paper.title == "T"
        assert store.head("repro/s3-paper/ledger.json") is True

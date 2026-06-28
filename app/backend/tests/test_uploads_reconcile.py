"""T2 orphan reconciliation (materialization step 6, spec §7).

Neither orphan class may become silent data loss:
  * **PUT ok, confirm POST lost** → the S3-event ``heal_from_key`` (and the sweep) bring the row to
    ``ready`` from the object that actually landed.
  * **row pending, PUT never happened** → the sweep removes the stale row past its TTL.
  * **object with no row** (deleted-row leftover / duplicate) → the sweep deletes the object.

Driven directly against ``UploadRepo`` + ``LocalObjectStore`` (no HTTP). In-memory SQLite is fine
here — every call runs on the test thread (unlike the TestClient flow in test_uploads).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from storage.object_store import LocalObjectStore
from uploads.repo import UploadRepo
from uploads.service import sweep_orphans


def _repo() -> UploadRepo:
    return UploadRepo(engine=sa.create_engine("sqlite://", future=True), create=True)


def _seed_pending(repo, store, *, put_object: bool, user="A", filename="f.csv", size=10):
    pid = repo.create_project(user, f"{user}@x", "P")["id"]
    res = repo.intake(user, f"{user}@x", pid, filename, None, size)
    key = res["key"]
    if put_object:
        store.put_bytes(key, b"x" * size)
    return res["dataset"]["id"], key


def test_heal_from_key_flips_pending_to_ready(tmp_path):
    repo, store = _repo(), LocalObjectStore(tmp_path)
    dsid, key = _seed_pending(repo, store, put_object=True)
    assert repo.get_dataset("A", dsid)["status"] == "pending_upload"

    healed = repo.heal_from_key(key, size_bytes=10, sha256="abc")
    assert healed is not None and healed["status"] == "ready"
    # idempotent: a re-fired event for an already-ready row is a no-op that still returns it
    assert repo.heal_from_key(key)["status"] == "ready"


def test_heal_ignores_unknown_or_non_upload_keys(tmp_path):
    repo = _repo()
    assert repo.heal_from_key("data/abc.csv") is None              # not an uploads/ key
    assert repo.heal_from_key("uploads/A/p/ghost/x.csv") is None    # no matching row


def test_sweep_heals_deletes_and_prunes(tmp_path):
    repo, store = _repo(), LocalObjectStore(tmp_path)
    # 1) PUT landed but confirm lost → should heal
    healed_id, healed_key = _seed_pending(repo, store, put_object=True, filename="landed.csv")
    # 2) pending, PUT never happened → should be pruned
    gone_id, _gone_key = _seed_pending(repo, store, put_object=False, filename="never.csv")
    # 3) an object with no row at all → should be deleted
    store.put_bytes("uploads/A/p/orphan/stray.csv", b"junk")

    # Everything is "stale" relative to a sweep run in the future with a 0h TTL.
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    summary = sweep_orphans(repo, store, now=future, ttl_hours=0)

    assert summary == {"healed": 1, "pending_deleted": 1, "objects_deleted": 1}
    assert repo.get_dataset("A", healed_id)["status"] == "ready"   # healed
    assert repo.get_dataset("A", gone_id) is None                  # pruned
    assert store.get_bytes("uploads/A/p/orphan/stray.csv") is None  # stray object deleted
    assert store.get_bytes(healed_key) is not None                 # the real object is kept


def test_sweep_respects_ttl(tmp_path):
    repo, store = _repo(), LocalObjectStore(tmp_path)
    _seed_pending(repo, store, put_object=False, filename="fresh.csv")
    # a fresh pending row inside the TTL window is left alone
    summary = sweep_orphans(repo, store, now=datetime.now(timezone.utc), ttl_hours=24)
    assert summary["pending_deleted"] == 0

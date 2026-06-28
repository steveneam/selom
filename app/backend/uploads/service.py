"""Server-side parse + orphan reconciliation for the upload flow (materialization step 6).

Two concerns the ``UploadRepo`` (pure DB) and the ``ObjectStore`` (pure bytes) compose into:

  * **Parse moves server-side, leak-free** (spec §4.2). The raw object is read from the store into a
    temp this function OWNS and deletes in a ``finally`` (the discipline the old ``ingest`` temps
    lacked — acceptance D), ingested, and the parsed matrix is written content-addressed to
    ``data/{sha256}.csv``. CSV until the parquet/DuckDB substrate lands (owner gate Q5); the column
    is ``datasets.parquet_s3_key``, its eventual target. A non-tabular payload (AnnData) keeps no CSV
    — the CSV substrate is tabular-only for now (honest, not silently wrong).
  * **T2 orphan reconciliation** (spec §7). ``heal_from_key`` (called by the S3-event Lambda) and
    ``sweep_orphans`` (the scheduled job) keep a dropped confirm POST from becoming silent data loss
    and keep stray objects/rows from accumulating. The S3-event + cron WIRING is deploy infra (step
    8); the LOGIC lives here, tested now.
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import tempfile
from datetime import datetime, timezone

from uploads.keys import data_key, safe_filename


def materialize_dataset(repo, object_store, user_id: str, dataset_id: str) -> dict | None:
    """Read a ``ready`` dataset's raw object, ingest it leak-free, and write the parsed matrix to
    ``data/{sha256}.csv``. Stamps ``parquet_s3_key`` + the authoritative ``current_sha256`` + ``qc``.

    Returns the updated dataset dict, or ``None`` if it isn't this tenant's dataset. Raises
    ``FileNotFoundError`` if the row points at an object that isn't in the store yet.
    """
    row = repo.get_dataset(user_id, dataset_id)
    if row is None:
        return None
    key = row.get("upload_s3_key")
    if not key:
        raise FileNotFoundError(f"dataset {dataset_id} has no upload key")
    raw = object_store.get_bytes(key)
    if raw is None:
        raise FileNotFoundError(f"object not in store: {key}")

    # The raw upload's authoritative content hash (staleness key). The presigned PUT can't be trusted
    # to match the client's declared sha, so we recompute from the bytes we actually parsed.
    raw_sha = hashlib.sha256(raw).hexdigest()

    # Own a temp dir + delete it in finally — the leak the old ingest temps had (acceptance D). The
    # file keeps the original name so the suffix-based loader picks correctly (.h5ad vs .csv …).
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="selom-parse-"))
    parquet_s3_key = None
    qc_dict = None
    try:
        local = workdir / safe_filename(row.get("filename"))
        local.write_bytes(raw)
        from engine import ingest, run_qc

        bundle = ingest(str(local))
        try:
            bundle.qc = run_qc(bundle)
            qc_dict = bundle.qc.model_dump()
        except Exception:  # noqa: BLE001 — QC is advisory; a parse that loads but won't QC still stamps
            qc_dict = None
        if _is_dataframe(bundle.payload):
            csv_bytes = bundle.payload.to_csv(index=False).encode("utf-8")
            parsed_sha = hashlib.sha256(csv_bytes).hexdigest()
            parquet_s3_key = data_key(parsed_sha, "csv")
            object_store.put_bytes(parquet_s3_key, csv_bytes, "text/csv")
        # else: a non-tabular payload (AnnData) — no CSV substrate yet (Q5). parquet_s3_key stays None.
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return repo.stamp_parsed(user_id, dataset_id, parquet_s3_key=parquet_s3_key,
                             current_sha256=raw_sha, qc=qc_dict)


def _is_dataframe(obj) -> bool:
    return any(t.__name__ == "DataFrame" for t in type(obj).__mro__)


def sweep_orphans(repo, object_store, *, now: datetime | None = None,
                  ttl_hours: int | None = None) -> dict:
    """The scheduled reconciliation (spec §7). Heals/removes both orphan classes; idempotent.

    System job (not tenant-scoped) — on Postgres it needs a BYPASSRLS role for the cross-tenant
    listing (resolved at the deploy step); on SQLite it runs as-is.
    """
    from config import settings

    now = now or datetime.now(timezone.utc)
    ttl_hours = settings.upload_ttl_hours if ttl_hours is None else ttl_hours
    healed = pending_deleted = objects_deleted = 0

    # Reverse orphan — a pending row past its TTL. If the object actually LANDED, the confirm POST was
    # lost: heal to ready (not delete). If it never landed, the PUT never happened: drop the row.
    for stale in repo.list_stale_pending(now, ttl_hours):
        key = stale.get("upload_s3_key")
        if key and object_store.head(key):
            if repo.heal_from_key(key):
                healed += 1
        else:
            repo.purge_dataset(stale["user_id"], stale["id"])
            pending_deleted += 1

    # Forward orphan — an object under uploads/ with no live row (a deleted-row leftover / duplicate).
    # Row-first intake (§4.2) means a real pending/ready object always has a row, so this only ever
    # catches genuine strays.
    active = repo.list_active_upload_keys()
    for key in object_store.list_keys("uploads/"):
        if key not in active:
            object_store.delete(key)
            objects_deleted += 1

    return {"healed": healed, "pending_deleted": pending_deleted, "objects_deleted": objects_deleted}

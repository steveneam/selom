"""S3 object-key construction for the presigned-upload flow (materialization step 6, spec §3/§5).

Every ``uploads/...`` key is built **server-side** from the JWT-verified ``user_id`` (T1, spec §6.3):
the only client-influenced segment is the filename, which is reduced to a bare basename here so a
malicious ``../`` or absolute path can never escape the tenant's prefix. The presigned PUT signs this
exact key, so a client cannot write outside its own ``uploads/{user_id}/`` space.

Keys are the content-addressed layout from the plan §5 / spec §3:

  * ``uploads/{user_id}/{project_id}/{dataset_id}/{filename}`` — the raw drop (presigned PUT)
  * ``uploads/{user_id}/supplements/{sha256}.{ext}``           — a paper supplement
  * ``data/{sha256}.{ext}``                                    — the parsed/cleaned matrix

``parse_upload_key`` is the inverse for the S3-event heal path (T2, spec §7): the confirm Lambda
parses ``{user_id}/{project_id}/{dataset_id}`` back out of an ``s3:ObjectCreated`` key to find the
``pending_upload`` row, so a failed confirm POST still self-heals.
"""

from __future__ import annotations

import pathlib

_UPLOADS = "uploads"
_SUPPLEMENTS = "supplements"
_DATA = "data"


def safe_filename(filename: str | None) -> str:
    """Reduce a client-supplied name to a bare basename — no directories, no traversal.

    POSIX *and* Windows separators are stripped (a browser on Windows may send a backslash path), so
    the result can never contain ``/`` and can't widen the key beyond the dataset's own folder."""
    raw = (filename or "").replace("\\", "/")
    name = pathlib.PurePosixPath(raw).name.strip()
    return name or "data"


def upload_key(user_id: str, project_id: str, dataset_id: str, filename: str) -> str:
    """The raw-drop key. ``user_id`` is the verified tenant — NEVER a request param (spec §6.2/§6.3)."""
    if not (user_id and project_id and dataset_id):
        raise ValueError("upload_key requires user_id, project_id, dataset_id")
    return f"{_UPLOADS}/{user_id}/{project_id}/{dataset_id}/{safe_filename(filename)}"


def supplement_key(user_id: str, sha256: str, ext: str) -> str:
    """A paper supplement key (content-addressed by sha). Tenant-prefixed like every upload."""
    if not (user_id and sha256):
        raise ValueError("supplement_key requires user_id and sha256")
    ext = (ext or "").lstrip(".") or "bin"
    return f"{_UPLOADS}/{user_id}/{_SUPPLEMENTS}/{sha256}.{ext}"


def data_key(sha256: str, ext: str = "csv") -> str:
    """The parsed-matrix key — content-addressed, tenant-agnostic (the same bytes self-identify).

    CSV until the parquet/DuckDB substrate lands (owner gate Q5; the column is ``parquet_s3_key``,
    its eventual target). Not under ``uploads/`` — it's derived, not a raw client drop."""
    if not sha256:
        raise ValueError("data_key requires a content sha256")
    ext = (ext or "csv").lstrip(".") or "csv"
    return f"{_DATA}/{sha256}.{ext}"


def parse_upload_key(key: str) -> dict | None:
    """Inverse of :func:`upload_key` for the S3-event heal path (T2). Returns
    ``{user_id, project_id, dataset_id, filename}`` for a raw-drop key, else ``None`` (a supplement or
    a non-upload key isn't a dataset to heal)."""
    parts = (key or "").split("/")
    # uploads / {user_id} / {project_id} / {dataset_id} / {filename}
    if len(parts) != 5 or parts[0] != _UPLOADS or parts[2] == _SUPPLEMENTS:
        return None
    _, user_id, project_id, dataset_id, filename = parts
    if not (user_id and project_id and dataset_id and filename):
        return None
    return {
        "user_id": user_id,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "filename": filename,
    }

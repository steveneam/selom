"""Presigned-upload + parsed-matrix package (AWS materialization step 6, spec §4.2/§6/§7).

The genuine flow rewrite: a client uploads bytes **straight to S3** via a presigned PUT (bypassing
the API Gateway body cap), the server only ever holds pointers. Built on the real ``datasets`` /
``users`` tables + the JWT-derived ``user_id`` (steps 7a/7b), so a forgotten tenant filter is
structurally impossible (``TenantQuery``) and an upload can't escape its ``uploads/{user_id}/`` prefix
(server-derived keys, T1). T2 reconciliation (heal + sweep) keeps a failed confirm from becoming
silent data loss.
"""

from uploads.keys import data_key, parse_upload_key, supplement_key, upload_key
from uploads.repo import QuotaExceeded, UploadRepo, get_upload_repo, set_upload_repo
from uploads.service import materialize_dataset, sweep_orphans

__all__ = [
    "QuotaExceeded", "UploadRepo", "get_upload_repo", "set_upload_repo",
    "data_key", "parse_upload_key", "supplement_key", "upload_key",
    "materialize_dataset", "sweep_orphans",
]

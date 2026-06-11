"""Result store — where a finished figure spec lives, and how it's fetched.

Two interchangeable backends behind one ``ResultStore`` interface (the same
swap-when-infra-lands pattern as the stub/real skill engines and the FE's
localStorage ProjectStore):

  * ``LocalResultStore`` (default) — writes JSON under ``data/results/``; the
    "presigned URL" is just the local ``GET /jobs/{id}/result`` route.
  * ``R2ResultStore`` — Cloudflare R2 (S3-compatible) with real presigned GET URLs.
    Active only when every ``SELOM_R2_*`` var is set. boto3 is lazy-imported so the
    light core install never needs it.

RISKS #5: boto3 >=1.36 breaks R2 checksums unless the client is configured with
``request_checksum_calculation='when_required'`` — applied below.
"""

from __future__ import annotations

import json
import pathlib
from typing import Protocol


class ResultStore(Protocol):
    def put(self, key: str, figure: dict) -> str:
        """Persist a figure spec; return a URL the client can fetch it from."""
        ...

    def get(self, key: str) -> dict | None:
        """Return the stored figure spec, or None if absent."""
        ...

    def url_if_exists(self, key: str) -> str | None:
        """A fetch URL if the result is present, else None (cross-process completion probe)."""
        ...


class LocalResultStore:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> pathlib.Path:
        return self.root / f"{key}.json"

    def put(self, key: str, figure: dict) -> str:
        self._path(key).write_text(json.dumps(figure))
        return f"/jobs/{key}/result"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        return json.loads(p.read_text()) if p.exists() else None

    def url_if_exists(self, key: str) -> str | None:
        return f"/jobs/{key}/result" if self._path(key).exists() else None


class R2ResultStore:
    def __init__(self, settings) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = settings.r2_bucket
        self.ttl = settings.r2_presign_ttl
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(
                request_checksum_calculation="when_required",   # RISKS #5
                response_checksum_validation="when_supported",
            ),
        )

    def _obj(self, key: str) -> str:
        return f"results/{key}.json"

    def put(self, key: str, figure: dict) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._obj(key),
            Body=json.dumps(figure).encode(),
            ContentType="application/json",
        )
        return self._presign(key)

    def get(self, key: str) -> dict | None:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self._obj(key))
        except self.client.exceptions.NoSuchKey:
            return None
        return json.loads(obj["Body"].read())

    def url_if_exists(self, key: str) -> str | None:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._obj(key))
        except Exception:
            return None
        return self._presign(key)

    def _presign(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._obj(key)},
            ExpiresIn=self.ttl,
        )


def make_result_store(settings) -> ResultStore:
    if settings.use_r2:
        return R2ResultStore(settings)
    return LocalResultStore(settings.data_dir / "results")

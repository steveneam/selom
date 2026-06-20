"""Runtime configuration (env-driven, with dev-safe defaults).

Everything heavy is OFF by default so a fresh `uv sync` + `uvicorn` runs the full
job API with zero infra: jobs execute inline, results land on the local filesystem.
Set ``SELOM_QUEUE=arq`` (+ Redis) and the ``R2_*`` vars (+ Cloudflare R2) to flip on
the distributed/cloud path. Env-var names match the repo-root ``.env.example``.
"""

import pathlib

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent  # D:/selom


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT / ".env", extra="ignore")

    # Job queue backend: "inline" (run on-request, no infra) | "arq" (Redis worker).
    queue: str = Field(default="inline", validation_alias="SELOM_QUEUE")
    redis_url: str = Field(default="redis://localhost:6379", validation_alias="REDIS_URL")

    # Where the local filesystem stores live (gitignored: app/backend/data/).
    data_dir: pathlib.Path = Field(
        default=pathlib.Path(__file__).parent / "data", validation_alias="SELOM_DATA_DIR"
    )

    # Per-file upload cap (MB) for the live-reproduction intake (POST /papers/{id}/reproduce).
    # Oversized uploads are rejected with 413. Large-file/BAM async ingest is out of scope here.
    max_upload_mb: int = Field(default=50, validation_alias="SELOM_MAX_UPLOAD_MB")

    # Reproduction-engine R oracle (validation-only, ADR 0002 — NEVER on the shipped path).
    # OFF by default: the blame instrument runs the authors' actual R tool (edgeR/fgsea) to
    # split engine-delta / upstream-delta / paper-irreproducible. Disabled -> blame degrades
    # to ``delta-unmeasured`` honestly (config.py docstring + spec D9/D12).
    oracle: str = Field(default="off", validation_alias="SELOM_ORACLE")  # off | r
    r_oracle_bin: str = Field(default="", validation_alias="SELOM_R_ORACLE_BIN")  # Rscript.exe

    @property
    def oracle_enabled(self) -> bool:
        return self.oracle.strip().lower() in {"r", "1", "true", "on"}

    # Cloudflare R2 result store — canonical names shared with .env.example. All set -> R2;
    # otherwise the local filesystem store is used.
    r2_account_id: str = Field(default="", validation_alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", validation_alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field(default="", validation_alias="R2_BUCKET")
    r2_presign_ttl: int = Field(default=3600, validation_alias="R2_PRESIGN_TTL")

    @property
    def r2_endpoint_url(self) -> str:
        # R2's S3 endpoint is derived from the account id.
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com" if self.r2_account_id else ""

    @property
    def use_r2(self) -> bool:
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
        )


settings = Settings()

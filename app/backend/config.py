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

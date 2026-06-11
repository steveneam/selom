"""Runtime configuration (env-driven, with dev-safe defaults).

Everything heavy is OFF by default so a fresh `uv sync` + `uvicorn` runs the full
job API with zero infra: jobs execute inline, results land on the local filesystem.
Set ``SELOM_QUEUE=arq`` (+ Redis) and the ``SELOM_R2_*`` vars (+ Cloudflare R2) to
flip on the distributed/cloud path — see plans/v2-backend.md (B3).
"""

import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SELOM_", env_file=".env", extra="ignore")

    # Job queue backend: "inline" (run on-request, no infra) | "arq" (Redis worker).
    queue: str = "inline"
    redis_url: str = "redis://localhost:6379"

    # Where the local filesystem stores live (gitignored: app/backend/data/).
    data_dir: pathlib.Path = pathlib.Path(__file__).parent / "data"

    # Cloudflare R2 result store. All four set -> R2; otherwise local filesystem.
    r2_bucket: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_presign_ttl: int = 3600  # seconds a presigned result URL stays valid

    @property
    def use_r2(self) -> bool:
        return bool(
            self.r2_bucket
            and self.r2_endpoint_url
            and self.r2_access_key_id
            and self.r2_secret_access_key
        )


settings = Settings()

"""Runtime configuration (env-driven, with dev-safe defaults).

Everything heavy is OFF by default so a fresh `uv sync` + `uvicorn` runs the full
job API with zero infra: jobs execute inline, results land on the local filesystem.
Set ``SELOM_QUEUE=arq`` (+ Redis) and ``SELOM_OBJECT_STORE=s3`` (+ an AWS bucket) to
flip on the distributed/cloud path. Env-var names match the repo-root ``.env.example``.
"""

import pathlib

from pydantic import Field, model_validator
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

    # Content-addressed result cache (Task C1) — an in-proc LRU + a local-disk JSON tier keyed by
    # (skill_id+version, canonical params, input sha256). Invalidation is automatic (the skill
    # version is part of the key); there is no TTL. `off` flips to always-recompute (for a forced
    # cold run / benchmarking). The durable R2 tier is C4 (deferred). See skills/_result_cache.py.
    result_cache: str = Field(default="on", validation_alias="SELOM_RESULT_CACHE")
    result_cache_mem_max: int = Field(default=64, validation_alias="SELOM_RESULT_CACHE_MEM_MAX")

    @property
    def result_cache_enabled(self) -> bool:
        return self.result_cache.strip().lower() in {"on", "1", "true", "yes"}

    # Parsed-input cache (Task C3) — an in-process memoization of ``engine.ingest`` keyed by the
    # input content hash, so the same file isn't re-parsed across ``/data/inspect`` + ``/run``. The
    # parsed payload is shared (read-only); per-request source/qc/path are rebound on each hit.
    input_cache: str = Field(default="on", validation_alias="SELOM_INPUT_CACHE")
    input_cache_max: int = Field(default=16, validation_alias="SELOM_INPUT_CACHE_MAX")

    @property
    def input_cache_enabled(self) -> bool:
        return self.input_cache.strip().lower() in {"on", "1", "true", "yes"}

    # Intermediate-table lineage (Task D3) — content-addressed materialization of the table a skill
    # consumes (and a combined cohort table) under ``data/artifacts/``, with parent-hash lineage + the
    # cleaning recipe / merge receipt. Lets the user "inspect the matrix the skill saw" and makes a
    # cleaned re-run reproducible (the id IS the content hash). `off` disables materialization. The
    # durable DuckDB/Parquet tier is D4 (deferred). See engine/lineage.py.
    artifacts: str = Field(default="on", validation_alias="SELOM_ARTIFACTS")

    @property
    def artifacts_enabled(self) -> bool:
        return self.artifacts.strip().lower() in {"on", "1", "true", "yes"}

    # Per-skill execution timeout (Task C3), seconds. A skill is run in a worker thread under this
    # ceiling so a hung run returns 504 promptly and the event loop stays responsive instead of the
    # whole server freezing. 0 disables. (A true kill needs a subprocess worker — deferred infra.)
    skill_timeout_s: int = Field(default=120, validation_alias="SELOM_SKILL_TIMEOUT_S")

    # Reproduction-engine R oracle (validation-only, ADR 0002 — NEVER on the shipped path).
    # OFF by default: the blame instrument runs the authors' actual R tool (edgeR/fgsea) to
    # split engine-delta / upstream-delta / paper-irreproducible. Disabled -> blame degrades
    # to ``delta-unmeasured`` honestly (config.py docstring + spec D9/D12).
    oracle: str = Field(default="off", validation_alias="SELOM_ORACLE")  # off | r
    r_oracle_bin: str = Field(default="", validation_alias="SELOM_R_ORACLE_BIN")  # Rscript.exe

    @property
    def oracle_enabled(self) -> bool:
        return self.oracle.strip().lower() in {"r", "1", "true", "on"}

    # Object store — the single byte-IO seam every content-addressed store rides on
    # (result · cache disk tier · lineage · ledger). `local` (default) keeps bytes on the
    # filesystem under data_dir so the dev path never needs AWS (plan D6); `s3` flips to
    # regional AWS S3 (boto3, lazy-imported). AWS creds come from the standard chain
    # (~/.aws/credentials in dev, the Lambda execution role in prod) — not Selom env vars.
    # See storage/object_store.py + docs/aws-materialization/spec.md §1.
    object_store: str = Field(default="local", validation_alias="SELOM_OBJECT_STORE")  # local | s3
    s3_bucket: str = Field(default="", validation_alias="SELOM_S3_BUCKET")
    s3_region: str = Field(default="", validation_alias="SELOM_S3_REGION")
    s3_presign_ttl: int = Field(default=3600, validation_alias="SELOM_S3_PRESIGN_TTL")

    # Job store — the statelessness fix (materialization step 2). `memory` (default) keeps the
    # in-process JobStore (inline dev, zero infra). `sql` moves jobs onto the `analysis_jobs`
    # table so a poll on one instance sees a job created on another (a Lambda poll on a cold
    # instance sees nothing today). The dev/test path runs on SQLite, prod on Aurora Postgres,
    # selected by `database_url`. See jobs/sql_store.py + docs/aws-materialization/spec.md §4.1.
    job_store: str = Field(default="memory", validation_alias="SELOM_JOB_STORE")  # memory | sql
    database_url: str = Field(default="", validation_alias="SELOM_DATABASE_URL")
    # Dev/test convenience: auto-create tables from the schema (SQLite). Prod stays False and
    # applies the Alembic migration instead (never auto-create against Aurora).
    db_auto_create: bool = Field(default=False, validation_alias="SELOM_DB_AUTO_CREATE")

    # Auth / tenancy (materialization step 7b). `dev` (default) trusts a fixed dev user_id so the
    # inner loop stays offline + single-tenant — nothing changes locally. `clerk` verifies the
    # Clerk JWT (issuer + JWKS) and derives the tenant from the verified `sub` claim, never a
    # request param (spec §4.3, §6.2). The same config seam as make_object_store/make_job_store.
    # See auth/context.py + docs/aws-materialization/spec.md §4.3.
    auth_mode: str = Field(default="dev", validation_alias="SELOM_AUTH_MODE")  # dev | clerk
    dev_user_id: str = Field(default="dev-user", validation_alias="SELOM_DEV_USER_ID")
    dev_user_email: str = Field(default="dev@selom.local", validation_alias="SELOM_DEV_USER_EMAIL")
    clerk_issuer: str = Field(default="", validation_alias="SELOM_CLERK_ISSUER")  # https://<inst>.clerk.accounts.dev
    clerk_jwks_url: str = Field(default="", validation_alias="SELOM_CLERK_JWKS_URL")  # default: {issuer}/.well-known/jwks.json
    clerk_audience: str = Field(default="", validation_alias="SELOM_CLERK_AUDIENCE")  # optional aud claim check

    # Presigned upload (materialization step 6). A `pending_upload` datasets row whose object never
    # landed (the client PUT failed) is swept after this TTL (spec §7/T2 reverse-orphan). Hours.
    upload_ttl_hours: int = Field(default=24, validation_alias="SELOM_UPLOAD_TTL_HOURS")

    @model_validator(mode="after")
    def _validate_backend_combos(self):
        """Fail fast at boot if a non-local backend is selected without its required setting,
        instead of a cryptic boto/SQL/JWKS error on the first request that touches it. The
        default (local/memory/dev) trips none of these, so the offline inner loop is unaffected."""
        problems = []
        if self.object_store.strip().lower() == "s3" and not self.s3_bucket.strip():
            problems.append("SELOM_OBJECT_STORE=s3 requires SELOM_S3_BUCKET")
        if self.job_store.strip().lower() == "sql" and not self.database_url.strip():
            problems.append("SELOM_JOB_STORE=sql requires SELOM_DATABASE_URL")
        if self.auth_mode.strip().lower() == "clerk" and not self.clerk_issuer.strip():
            problems.append("SELOM_AUTH_MODE=clerk requires SELOM_CLERK_ISSUER")
        if problems:
            raise ValueError("Invalid Selom configuration — " + "; ".join(problems))
        return self


settings = Settings()

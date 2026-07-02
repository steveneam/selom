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

    # Deployment posture. `dev` (default) is the offline inner loop; `prod` a real deployment
    # serving real users. It is only an EXPLICIT marker — `is_production` also treats a live Clerk
    # auth or an S3 object store as production, so the honesty guards still fire even if a deploy
    # forgets to set this. The local dogfood (SQLite job store, local files, dev auth) is NOT prod.
    environment: str = Field(default="dev", validation_alias="SELOM_ENV")  # dev | prod

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

    # Job idempotency (M2). When ON, `submit` short-circuits to an existing SUCCEEDED job with the
    # same content cache key (skill+version+params+input sha) instead of creating a duplicate job +
    # recomputing — the cross-instance dedup a Lambda retry needs. OFF by default so the inline dev
    # path is unchanged (single-process, no retry duplication); prod (SQL store) turns it on. The
    # result_cache_key/input_sha256 columns are stamped on every job regardless (metadata).
    job_idempotency: bool = Field(default=False, validation_alias="SELOM_JOB_IDEMPOTENCY")

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

    # AI Action Gateway — the active gateway is opt-in (default "null" = NullActionGateway,
    # zero regression).  Mirrors the OperatorVisionGateway seam in extract/vision.py.  Modes:
    #   null     — NullActionGateway (deterministic fallback; the default)
    #   operator — OperatorActionGateway.from_recordings(): Claude-authored recorded outputs, NO
    #              credit; the build/optimize default AND the canned demo engine (the 3 demo papers)
    #   gateway  — VercelAIGateway (live Llama via the Vercel AI Gateway); needs AI_GATEWAY_API_KEY;
    #              the real gated-product path.  Provider-agnostic: swap ai_gateway_model to change
    #              model/provider (groq/openai/anthropic/google/mistral), zero feature-code change.
    #   live     — PydanticAIGateway (direct Anthropic); needs ANTHROPIC_API_KEY (kept, optional)
    # See docs/ai-gateway-wiring/spec.md; demo/product split: docs/pricing strategy memory.
    ai_gateway: str = Field(default="null", validation_alias="SELOM_AI_GATEWAY")  # null|operator|gateway|live
    ai_token_budget: int = Field(default=20_000, validation_alias="SELOM_AI_TOKEN_BUDGET")
    ai_timeout_s: float = Field(default=30.0, validation_alias="SELOM_AI_TIMEOUT_S")

    # Vercel AI Gateway (mode "gateway") — OpenAI-compatible endpoint; one bearer key (AI_GATEWAY_API_KEY,
    # bare name to match the shared shell/Render var) routes provider failover server-side.  Field
    # names mirror the eamos gateway broker.  Inert unless ai_gateway == "gateway" + key present.
    ai_gateway_api_key: str | None = Field(default=None, validation_alias="AI_GATEWAY_API_KEY")
    ai_gateway_base_url: str = Field(
        default="https://ai-gateway.vercel.sh/v1", validation_alias="SELOM_AI_GATEWAY_BASE_URL"
    )
    ai_gateway_model: str = Field(
        default="meta/llama-3.3-70b", validation_alias="SELOM_AI_GATEWAY_MODEL"
    )
    ai_gateway_provider_order_raw: str = Field(
        default="groq,bedrock", validation_alias="SELOM_AI_GATEWAY_PROVIDER_ORDER"
    )
    ai_gateway_temperature: float = Field(
        default=0.3, validation_alias="SELOM_AI_GATEWAY_TEMPERATURE"
    )
    ai_gateway_max_tokens: int = Field(
        default=700, validation_alias="SELOM_AI_GATEWAY_MAX_TOKENS"
    )

    # Operator gateway (mode "operator") — path to the Claude-authored recordings JSON.  Default None
    # → the bundled ai/recordings/explain.json (resolved in OperatorActionGateway.from_recordings).
    ai_operator_recordings_path: str | None = Field(
        default=None, validation_alias="SELOM_AI_OPERATOR_RECORDINGS"
    )

    @property
    def ai_gateway_provider_order(self) -> list[str]:
        """Provider failover order parsed from the comma-separated raw env value."""
        return [p.strip() for p in self.ai_gateway_provider_order_raw.split(",") if p.strip()]

    # Capability-gap store (S4) — "memory" (default, zero-infra) or "jsonl" (persistent JSONL
    # file that survives process restarts).  The "jsonl" backend requires SELOM_GAP_STORE_PATH.
    # Default behaviour is unchanged (in-memory) so zero-regression is guaranteed.
    gap_store: str = Field(default="memory", validation_alias="SELOM_GAP_STORE")  # memory | jsonl
    gap_store_path: pathlib.Path | None = Field(
        default=None, validation_alias="SELOM_GAP_STORE_PATH"
    )

    @property
    def is_production(self) -> bool:
        """A real deployment serving real users. True when explicitly `SELOM_ENV=prod`, OR when an
        unambiguous prod backend is active — live Clerk auth (real users) or an S3 object store
        (real cloud storage). Deliberately does NOT include `job_store=sql`: the local dogfood runs
        the SQL job store on SQLite, and that must stay a dev environment (stubs allowed there)."""
        return (
            self.environment.strip().lower() == "prod"
            or self.auth_mode.strip().lower() == "clerk"
            or self.object_store.strip().lower() == "s3"
        )

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
        # WS1.1 — no fabricated figures off-dev (RISKS #11). In production the skills engine must
        # NOT be able to resolve to the synthetic stub: a deploy missing the science extras (or one
        # left on SELOM_SKILLS_ENGINE=stub) would serve fake science as HTTP 200 — a direct breach
        # of the "no black box" promise. Fail LOUD at startup, not per-request. Dev is untouched
        # (stubs are legit for the offline loop / golden tests / the canned demo).
        if self.is_production:
            from skills._engine import missing_engine_modules, resolve_engine_policy

            missing = missing_engine_modules()
            if resolve_engine_policy() == "stub":
                why = (f"required science modules are not importable ({', '.join(missing)})"
                       if missing else "SELOM_SKILLS_ENGINE=stub is set")
                problems.append(
                    "production must serve real analyses but the skills engine resolves to the "
                    f"fabricated stub ({why}) — install the science extras and unset "
                    "SELOM_SKILLS_ENGINE (or set it to 'real')")
            elif missing:
                # Engine forced 'real' but a dep is genuinely absent → every skill needing it 500s
                # per-request. Surface it at boot too, so the deploy fails visibly instead of on the
                # first user run.
                problems.append(
                    "production forces the real skills engine but these required modules are not "
                    f"importable: {', '.join(missing)} — install the science extras")
        if problems:
            raise ValueError("Invalid Selom configuration — " + "; ".join(problems))
        return self


settings = Settings()

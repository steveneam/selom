from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import settings
from storage.object_store import get_object_store

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    """Readiness probe — liveness PLUS the backends this instance actually depends on, so a
    deploy/smoke test gets a real signal (not a 200 from a process that can't reach S3/Postgres).
    Returns 503 if a configured backend errors. `/health` stays the cheap liveness probe."""
    checks: dict[str, str] = {}
    ok = True
    # Object store: head a sentinel. Absent is fine; an ERROR (creds/permission/throttle) is not —
    # head_size now re-raises non-404s, so a misconfigured S3 surfaces here instead of silently.
    try:
        get_object_store().head("__readiness__/probe")
        checks["object_store"] = "ok"
    except Exception as e:  # noqa: BLE001
        ok = False
        checks["object_store"] = f"error: {type(e).__name__}"
    # Database: only when this instance uses the SQL job store.
    if settings.job_store.strip().lower() == "sql":
        try:
            import sqlalchemy as sa

            from db.engine import make_engine

            with make_engine(settings.database_url).connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:  # noqa: BLE001
            ok = False
            checks["database"] = f"error: {type(e).__name__}"
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "checks": checks},
        status_code=200 if ok else 503,
    )

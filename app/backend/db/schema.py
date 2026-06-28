"""SQLAlchemy Core schema — the relational tables (materialization step 2).

One ``MetaData``; step 2 defines only ``analysis_jobs`` (the statelessness fix). The columns
mirror the spec §2.3 table 6, minus the cross-table FKs (``users``/``intermediate_tables``) and
RLS, which land in step 7 once auth exists — the tenant ``user_id`` is here now (nullable,
forward-compatible) so step 7 tightens constraints rather than adding columns.

Portable on purpose: ``JSON().with_variant(JSONB, "postgresql")`` is plain JSON text on the
SQLite dev/test path and JSONB on Aurora; ``DateTime(timezone=True)`` round-trips a Python
datetime on both. The ``id`` is the uuid4 hex the in-memory ``JobStore`` already emits (a 32-char
string), so the wire id the FE polls is unchanged across the seam.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

# JSONB on Postgres, JSON (text) on SQLite — same Python dict round-trip either way.
JSON_PORTABLE = sa.JSON().with_variant(JSONB, "postgresql")

# analysis_jobs — REPLACES the in-memory JobStore (jobs/store.py). Poll-safe across instances:
# any worker reads the row, not a local dict. Mirrors the Job dataclass + the content-addressed
# pointer columns (result_cache_key / result_json_s3_key / artifact_id) that later steps populate.
analysis_jobs = sa.Table(
    "analysis_jobs",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),       # uuid4 hex (matches Job.id today)
    # tenant key — forward-compatible; step 7 adds the users FK + RLS (nullable until auth lands).
    sa.Column("user_id", sa.Text, nullable=True),
    sa.Column("project_id", sa.String(64), nullable=True),
    sa.Column("dataset_id", sa.String(64), nullable=True),
    sa.Column("skill_id", sa.Text, nullable=False),
    sa.Column("skill_version", sa.Text, nullable=True),     # part of the cache key
    sa.Column("status", sa.Text, nullable=False),           # queued|running|succeeded|failed
    sa.Column("params", JSON_PORTABLE, nullable=False),
    sa.Column("filename", sa.Text, nullable=True),          # original upload name (B4 provenance)
    sa.Column("input_sha256", sa.Text, nullable=True),      # input content hash (idempotency)
    sa.Column("result_cache_key", sa.Text, nullable=True),  # the C1 cache key (idempotent reuse)
    sa.Column("result_json_s3_key", sa.Text, nullable=True),  # results/{id}.json pointer
    sa.Column("artifact_id", sa.Text, nullable=True),       # the matrix the skill saw (lineage)
    sa.Column("result_url", sa.Text, nullable=True),        # presigned GET / in-app route
    sa.Column("error", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("idx_jobs_user", "user_id"),
    sa.Index("idx_jobs_status", "status"),
    sa.Index("idx_jobs_cachekey", "result_cache_key"),
)

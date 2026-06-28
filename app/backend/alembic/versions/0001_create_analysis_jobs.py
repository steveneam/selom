"""create analysis_jobs (AWS materialization step 2 — statelessness fix)

Replaces the in-memory JobStore with a row-backed store so a poll on one instance sees a job
created on another. Columns mirror db.schema.analysis_jobs (kept self-contained per Alembic
convention). The cross-table FKs (users / intermediate_tables) + RLS are deferred to step 7
(auth/tenancy); the tenant `user_id` ships now as a nullable, forward-compatible column.

Revision ID: 0001_analysis_jobs
Revises:
Create Date: 2026-06-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_analysis_jobs"
down_revision = None
branch_labels = None
depends_on = None

# JSONB on Postgres, JSON (text) on SQLite — matches db.schema.JSON_PORTABLE.
_JSON = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("dataset_id", sa.String(64), nullable=True),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("skill_version", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("params", _JSON, nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("input_sha256", sa.Text(), nullable=True),
        sa.Column("result_cache_key", sa.Text(), nullable=True),
        sa.Column("result_json_s3_key", sa.Text(), nullable=True),
        sa.Column("artifact_id", sa.Text(), nullable=True),
        sa.Column("result_url", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_jobs_user", "analysis_jobs", ["user_id"])
    op.create_index("idx_jobs_status", "analysis_jobs", ["status"])
    op.create_index("idx_jobs_cachekey", "analysis_jobs", ["result_cache_key"])


def downgrade() -> None:
    op.drop_index("idx_jobs_cachekey", table_name="analysis_jobs")
    op.drop_index("idx_jobs_status", table_name="analysis_jobs")
    op.drop_index("idx_jobs_user", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")

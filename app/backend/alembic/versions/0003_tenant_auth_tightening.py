"""tenant auth tightening + skill_requests (AWS materialization step 7b)

Two changes, both pairing the schema with the now-live auth layer:

  * **skill_requests** — the M-003 AI-skills "safe slice" admin queue, folded into the unified
    M-001 schema here (plan §10 reconciliation item 1). A net-new tenant table.
  * **analysis_jobs tightening** — jobs are now tenant-owned: the ``user_id`` gains the users FK,
    NOT NULL, and RLS. Like the 0002 RLS block these are emitted **Postgres-only** (the Aurora
    enforcement target) — SQLite is the permissive dev/test path and the *application* guarantee
    (``SqlJobStore.create`` always stamps the verified tenant + upserts the user) holds on both
    dialects. Keeping the DDL Postgres-gated avoids fragile SQLite ALTER-rebuilds and keeps the
    SQLite Alembic path aligned with ``metadata.create_all`` (both leave analysis_jobs permissive).

RLS for the two tables (ENABLE + FORCE + tenant_isolation) is Postgres-only, same as 0002.

Revision ID: 0003_tenant_auth
Revises: 0002_tenant_schema
Create Date: 2026-06-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_tenant_auth"
down_revision = "0002_tenant_schema"
branch_labels = None
depends_on = None

# Tables that gain RLS in THIS migration (Postgres only).
_RLS_TABLES = ("skill_requests", "analysis_jobs")


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    # --- M-003 admin queue ---
    op.create_table(
        "skill_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("matched_skill_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        _created_at(),
    )
    op.create_index("idx_skill_requests_user", "skill_requests", ["user_id"])
    op.create_index("idx_skill_requests_fingerprint", "skill_requests", ["fingerprint"])
    op.create_index("idx_skill_requests_status", "skill_requests", ["status"])

    # --- analysis_jobs: tenant-owned now (Postgres enforcement only) ---
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column("analysis_jobs", "user_id", existing_type=sa.Text(), nullable=False)
        op.create_foreign_key(
            "fk_analysis_jobs_user", "analysis_jobs", "users",
            ["user_id"], ["user_id"], ondelete="CASCADE",
        )

    _apply_rls(_RLS_TABLES)


def _apply_rls(tables) -> None:
    """Native Postgres RLS for the step-7b tables (defense-in-depth behind TenantQuery). PG-only."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (user_id = current_setting('app.user_id', true)) "
            f"WITH CHECK (user_id = current_setting('app.user_id', true))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in _RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_constraint("fk_analysis_jobs_user", "analysis_jobs", type_="foreignkey")
        op.alter_column("analysis_jobs", "user_id", existing_type=sa.Text(), nullable=True)

    op.drop_index("idx_skill_requests_status", table_name="skill_requests")
    op.drop_index("idx_skill_requests_fingerprint", table_name="skill_requests")
    op.drop_index("idx_skill_requests_user", table_name="skill_requests")
    op.drop_table("skill_requests")

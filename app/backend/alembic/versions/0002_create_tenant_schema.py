"""create the tenant schema (AWS materialization step 7a)

The remaining 12 tenant tables from spec §2.3 (users → … → skill_installs), so the full schema
exists ahead of auth. Created in FK dependency order; columns mirror db.schema (kept self-contained
per Alembic convention — a migration is an immutable snapshot, not a live import of app models).

Tenant model: every row-owning table carries a direct ``user_id`` (the Clerk id) for a uniform,
join-free isolation predicate (spec §2.1). Native Postgres RLS (ENABLE + FORCE + a tenant_isolation
policy) is emitted **only on Postgres** — SQLite has no RLS and the dev/test path doesn't need it;
the ``TenantQuery`` application wrapper that pairs with RLS lands in step 7b. ``analysis_jobs``
(migration 0001) is intentionally left untouched here — its ``user_id`` stays nullable + FK/RLS-free
until 7b backfills the tenant, so a poll on an existing job still resolves.

PKs are app-supplied uuid hex (the ``analysis_jobs`` precedent — the 7b repo layer emits them),
not a ``gen_random_uuid()`` server default, to keep one portable schema with no dialect-divergent
column defaults.

Revision ID: 0002_tenant_schema
Revises: 0001_analysis_jobs
Create Date: 2026-06-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_tenant_schema"
down_revision = "0001_analysis_jobs"
branch_labels = None
depends_on = None

# JSONB on Postgres, JSON (text) on SQLite — matches db.schema.JSON_PORTABLE.
_JSON = sa.JSON().with_variant(JSONB, "postgresql")

# The order the tables are created in (FK dependency order) — RLS + downgrade reuse it.
_TENANT_TABLES = (
    "users", "workspaces", "projects", "datasets", "intermediate_tables", "artifact_parents",
    "reproduction_runs", "figures", "papers", "supplements", "cleaning_recipes", "gene_sets",
    "skill_installs",
)


def _user_fk(nullable: bool = False) -> sa.Column:
    return sa.Column(
        "user_id", sa.Text(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=nullable
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.Column("is_subscribed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tier", sa.Text(), nullable=False, server_default="free"),
        sa.Column("max_projects", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("max_datasets", sa.Integer(), nullable=False, server_default=sa.text("200")),
        sa.Column("max_storage_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("53687091200")),  # 50 GiB
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("name", sa.Text(), nullable=False, server_default="My workspace"),
        _created_at(),
    )
    op.create_index("idx_workspaces_user", "workspaces", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False, server_default="blue"),
        _created_at(),
    )
    op.create_index("idx_projects_user", "projects", ["user_id"])

    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("modality", sa.Text(), nullable=True),
        sa.Column("upload_s3_key", sa.Text(), nullable=True),
        sa.Column("current_sha256", sa.Text(), nullable=True),
        sa.Column("parquet_s3_key", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("qc", _JSON, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending_upload"),
        _created_at(),
    )
    op.create_index("idx_datasets_project", "datasets", ["project_id"])
    op.create_index("idx_datasets_user", "datasets", ["user_id"])
    op.create_index("idx_datasets_sha", "datasets", ["current_sha256"])

    op.create_table(
        "intermediate_tables",
        sa.Column("artifact_id", sa.Text(), primary_key=True),
        _user_fk(),
        sa.Column("kind", sa.Text(), nullable=False, server_default="ingested"),
        sa.Column("filename", sa.Text(), nullable=False, server_default=""),
        sa.Column("materialized", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("n_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("n_cols", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("columns", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("csv_s3_key", sa.Text(), nullable=True),
        sa.Column("recipe", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recipe_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        _created_at(),
    )
    op.create_index("idx_intermediate_user", "intermediate_tables", ["user_id"])

    op.create_table(
        "artifact_parents",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("child_id", sa.Text(), sa.ForeignKey("intermediate_tables.artifact_id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_kind", sa.Text(), nullable=False, server_default="source"),
        sa.Column("parent_id", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("child_id", "parent_kind", "parent_id", name="uq_artifact_parents_edge"),
    )
    op.create_index("idx_artifact_parents_child", "artifact_parents", ["child_id"])

    op.create_table(
        "reproduction_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("paper_slug", sa.Text(), nullable=False),
        sa.Column("ledger_s3_key", sa.Text(), nullable=True),
        sa.Column("reproducibility", sa.Integer(), nullable=True),
        sa.Column("selom_confidence", sa.Integer(), nullable=True),
        sa.Column("tier", sa.Text(), nullable=True),
        sa.Column("n_panels", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        _created_at(),
    )
    op.create_index("idx_repro_user", "reproduction_runs", ["user_id"])
    op.create_index("idx_repro_slug", "reproduction_runs", ["paper_slug"])

    op.create_table(
        "figures",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="SET NULL")),
        sa.Column("skill_id", sa.Text(), nullable=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("analysis_jobs.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text(), nullable=False, server_default="Untitled figure"),
        sa.Column("spec", _JSON, nullable=True),
        sa.Column("result_s3_key", sa.Text(), nullable=True),
        sa.Column("provenance", _JSON, nullable=True),
        sa.Column("methods", _JSON, nullable=True),
        sa.Column("legend", _JSON, nullable=True),
        sa.Column("table_stats", _JSON, nullable=True),
        sa.Column("data_check", _JSON, nullable=True),
        sa.Column("data_fit", _JSON, nullable=True),
        sa.Column("parent_figure_id", sa.String(36), sa.ForeignKey("figures.id", ondelete="SET NULL")),
        sa.Column("variant_label", sa.Text(), nullable=True),
        sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        _created_at(),
    )
    op.create_index("idx_figures_project", "figures", ["project_id"])
    op.create_index("idx_figures_user", "figures", ["user_id"])
    op.create_index("idx_figures_parent", "figures", ["parent_figure_id"])

    op.create_table(
        "papers",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("doi", sa.Text(), nullable=True),
        sa.Column("pmid", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("authors", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("venue", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Text(), nullable=True),
        sa.Column("issue", sa.Text(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("is_preprint", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("modality", sa.Text(), nullable=True),
        sa.Column("skills", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("out_of_scope", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("figure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tier_summary", _JSON, nullable=True),
        sa.Column("reproduction_run_id", sa.String(36), sa.ForeignKey("reproduction_runs.id", ondelete="SET NULL")),
        sa.Column("data_map", _JSON, nullable=True),
        _created_at(),
    )
    op.create_index("idx_papers_user", "papers", ["user_id"])

    op.create_table(
        "supplements",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("paper_id", sa.String(36), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending_upload"),
        _created_at(),
    )
    op.create_index("idx_supplements_paper", "supplements", ["paper_id"])

    op.create_table(
        "cleaning_recipes",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("steps", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("produces_artifact_id", sa.Text(), sa.ForeignKey("intermediate_tables.artifact_id", ondelete="SET NULL")),
        _created_at(),
    )
    op.create_index("idx_cleaning_dataset", "cleaning_recipes", ["dataset_id"])

    op.create_table(
        "gene_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("genes", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("source", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_label", sa.Text(), nullable=False, server_default=""),
        sa.Column("license", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_from", sa.Text(), nullable=True),
        _created_at(),
    )
    op.create_index("idx_gene_sets_user", "gene_sets", ["user_id"])

    op.create_table(
        "skill_installs",
        sa.Column("id", sa.String(36), primary_key=True),
        _user_fk(),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_skill_installs_user", "skill_installs", ["user_id"])
    # Functional unique: one install per scope (a null project_id ⇒ a workspace-wide install).
    # COALESCE over two same-typed uuid-text columns is portable (SQLite + Postgres).
    op.create_index(
        "uq_skill_installs_scope",
        "skill_installs",
        [sa.text("COALESCE(project_id, workspace_id)"), "skill_id"],
        unique=True,
    )

    _apply_rls()


def _apply_rls() -> None:
    """Native Postgres RLS (defense-in-depth behind the app TenantQuery, step 7b). Postgres-only —
    SQLite has no RLS. FORCE applies the policy even to the table owner; the predicate denies by
    default when ``app.user_id`` is unset (``current_setting(..., true)`` -> NULL -> no rows)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (user_id = current_setting('app.user_id', true)) "
            f"WITH CHECK (user_id = current_setting('app.user_id', true))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in _TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    # Drop in reverse FK dependency order (children before parents).
    for table in reversed(_TENANT_TABLES):
        op.drop_table(table)

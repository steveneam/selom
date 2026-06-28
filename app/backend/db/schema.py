"""SQLAlchemy Core schema — the relational tables (materialization steps 2 + 7a).

One ``MetaData``. Step 2 defined ``analysis_jobs`` (the statelessness fix); **step 7a adds the
remaining 12 tenant tables** (spec §2.3) so the full schema exists ahead of auth. Every
row-owning table carries a direct ``user_id`` (the Clerk id) for a uniform, join-free tenant
predicate — the cheapest path to "a forgotten filter is impossible" (spec §2.1, plan R-3). The
``TenantQuery`` wrapper + native Postgres RLS that enforce that predicate land in step 7b; the
Alembic migration (0002) emits the RLS policy block (Postgres-only). ``analysis_jobs`` keeps its
nullable ``user_id`` + no FKs/RLS until 7b backfills the tenant (a poll on an existing job must
still resolve) — only the net-new tables get RLS now, since nothing writes them until 6b/7c.

Portable on purpose: ``JSON().with_variant(JSONB, "postgresql")`` is plain JSON text on the
SQLite dev/test path and JSONB on Aurora; ``DateTime(timezone=True)`` round-trips a Python
datetime on both; ``server_default=func.now()`` renders ``CURRENT_TIMESTAMP`` (SQLite) / ``now()``
(Postgres). PKs are **app-supplied uuid hex** (the ``analysis_jobs`` precedent — the 7b repo layer
emits ``uuid4().hex`` exactly as ``SqlJobStore`` does), not a ``gen_random_uuid()`` server default:
one portable schema, no dialect-divergent column defaults. ``intermediate_tables.artifact_id`` and
``users.user_id`` are natural text PKs (sha-256 / Clerk id), mirroring the live code.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

# JSONB on Postgres, JSON (text) on SQLite — same Python dict round-trip either way.
JSON_PORTABLE = sa.JSON().with_variant(JSONB, "postgresql")

# Every row-owning tenant table gets RLS in migration 0002 (Postgres only); listed here so the
# migration and any audit share one source of truth for "which tables are tenant-scoped".
TENANT_TABLES = (
    "users", "workspaces", "projects", "datasets", "intermediate_tables", "artifact_parents",
    "reproduction_runs", "figures", "papers", "supplements", "cleaning_recipes", "gene_sets",
    "skill_installs",
)


def _pk() -> sa.Column:
    """An app-supplied uuid-hex primary key (matches the ``SqlJobStore`` id convention)."""
    return sa.Column("id", sa.String(36), primary_key=True)


def _user_fk(nullable: bool = False) -> sa.Column:
    """The denormalized tenant key — direct ``user_id`` FK on every row-owning table (spec §2.1)."""
    return sa.Column(
        "user_id", sa.Text, sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=nullable
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

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

# --- step 7a: the tenant tables (spec §2.3) ---------------------------------------------------
# Defined in FK dependency order so metadata.create_all (the dev/test path) and the Alembic
# migration (prod) build them cleanly. Bytes never live here — a *_s3_key column is the pointer,
# a *_sha256 is the content hash; small JSON the FE reads inline is jsonb.

# 1. users — the tenant root (Clerk user_id PK = the tenant key everywhere). Net-new (inventory
#    was single-tenant). Carries the tier/quota/Stripe fields now; numbers gated at launch.
users = sa.Table(
    "users",
    metadata,
    sa.Column("user_id", sa.Text, primary_key=True),         # Clerk user id (sub claim)
    sa.Column("email", sa.Text, nullable=False),
    sa.Column("stripe_customer_id", sa.Text, nullable=True),
    sa.Column("is_subscribed", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("tier", sa.Text, nullable=False, server_default="free"),
    sa.Column("max_projects", sa.Integer, nullable=False, server_default=sa.text("3")),
    sa.Column("max_datasets", sa.Integer, nullable=False, server_default=sa.text("10")),
    sa.Column("max_storage_bytes", sa.BigInteger, nullable=False, server_default=sa.text("1073741824")),
    _created_at(),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)

# 2. workspaces — the account-level container (lib/workspace is account-scoped).
workspaces = sa.Table(
    "workspaces",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("name", sa.Text, nullable=False, server_default="My workspace"),
    _created_at(),
    sa.Index("idx_workspaces_user", "user_id"),
)

# 3. projects — the sidebar folders (lib/projects/types.ts Project).
projects = sa.Table(
    "projects",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("color", sa.Text, nullable=False, server_default="blue"),  # chart token hue
    _created_at(),
    sa.Index("idx_projects_user", "user_id"),
)

# 4. datasets — one uploaded file (types.ts Dataset). Bytes in S3; the row is the pointer.
datasets = sa.Table(
    "datasets",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    sa.Column("filename", sa.Text, nullable=False),
    sa.Column("label", sa.Text, nullable=True),
    sa.Column("modality", sa.Text, nullable=True),
    sa.Column("upload_s3_key", sa.Text, nullable=True),     # uploads/{user_id}/{project_id}/{id}/{filename}
    sa.Column("current_sha256", sa.Text, nullable=True),    # live bytes hash -> staleness
    sa.Column("parquet_s3_key", sa.Text, nullable=True),    # data/{sha256}.parquet (parsed)
    sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default=sa.text("0")),
    sa.Column("qc", JSON_PORTABLE, nullable=True),          # QcReport — small, FE reads inline
    sa.Column("status", sa.Text, nullable=False, server_default="pending_upload"),  # |ready|failed (T2)
    _created_at(),
    sa.Index("idx_datasets_project", "project_id"),
    sa.Index("idx_datasets_user", "user_id"),
    sa.Index("idx_datasets_sha", "current_sha256"),
)

# 5. intermediate_tables — content-addressed lineage (engine/lineage.py). artifact_id = the sha PK;
#    the CSV bytes live at artifacts/{id}.csv in S3.
intermediate_tables = sa.Table(
    "intermediate_tables",
    metadata,
    sa.Column("artifact_id", sa.Text, primary_key=True),   # sha-256 of the table bytes / descriptor
    _user_fk(),
    sa.Column("kind", sa.Text, nullable=False, server_default="ingested"),  # ingested|combined|cleaned|matrix
    sa.Column("filename", sa.Text, nullable=False, server_default=""),
    sa.Column("materialized", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("n_rows", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("n_cols", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("columns", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),
    sa.Column("csv_s3_key", sa.Text, nullable=True),        # artifacts/{artifact_id}.csv (null if meta-only)
    sa.Column("recipe", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),  # RecipeStep[]
    sa.Column("recipe_note", sa.Text, nullable=False, server_default=""),
    sa.Column("note", sa.Text, nullable=False, server_default=""),
    _created_at(),
    sa.Index("idx_intermediate_user", "user_id"),
)

# 6. artifact_parents — the D3 lineage DAG edges (lineage.py ParentRef).
artifact_parents = sa.Table(
    "artifact_parents",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("child_id", sa.Text, sa.ForeignKey("intermediate_tables.artifact_id", ondelete="CASCADE"), nullable=False),
    sa.Column("parent_kind", sa.Text, nullable=False, server_default="source"),  # source | artifact
    sa.Column("parent_id", sa.Text, nullable=False),       # sha of a source file, or a parent artifact_id
    sa.Column("label", sa.Text, nullable=False, server_default=""),
    sa.UniqueConstraint("child_id", "parent_kind", "parent_id", name="uq_artifact_parents_edge"),
    sa.Index("idx_artifact_parents_child", "child_id"),
)

# 7. reproduction_runs — the Ledger pointer (reproduction.py Ledger). Full ledger JSON in S3
#    (repro/{slug}/ledger.json); this row is the queryable handle + the headline score.
reproduction_runs = sa.Table(
    "reproduction_runs",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("paper_slug", sa.Text, nullable=False),
    sa.Column("ledger_s3_key", sa.Text, nullable=True),    # repro/{slug}/ledger.json
    sa.Column("reproducibility", sa.Integer, nullable=True),
    sa.Column("selom_confidence", sa.Integer, nullable=True),
    sa.Column("tier", sa.Text, nullable=True),
    sa.Column("n_panels", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("status", sa.Text, nullable=False, server_default="pending"),  # pending|driven|failed
    _created_at(),
    sa.Index("idx_repro_user", "user_id"),
    sa.Index("idx_repro_slug", "paper_slug"),
)

# 8. figures — the durable produced figure (types.ts Figure). Small editable Plotly spec inlined;
#    a large rendered bundle points at S3. parent_figure_id = the fork/variant self-FK.
figures = sa.Table(
    "figures",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="SET NULL")),
    sa.Column("skill_id", sa.Text, nullable=True),
    sa.Column("job_id", sa.String(64), sa.ForeignKey("analysis_jobs.id", ondelete="SET NULL")),
    sa.Column("title", sa.Text, nullable=False, server_default="Untitled figure"),
    sa.Column("spec", JSON_PORTABLE, nullable=True),       # editable Plotly spec (small -> inline)
    sa.Column("result_s3_key", sa.Text, nullable=True),    # results/{job_id}.json (large bundle)
    sa.Column("provenance", JSON_PORTABLE, nullable=True),
    sa.Column("methods", JSON_PORTABLE, nullable=True),
    sa.Column("legend", JSON_PORTABLE, nullable=True),
    sa.Column("table_stats", JSON_PORTABLE, nullable=True),
    sa.Column("data_check", JSON_PORTABLE, nullable=True),
    sa.Column("data_fit", JSON_PORTABLE, nullable=True),
    sa.Column("parent_figure_id", sa.String(36), sa.ForeignKey("figures.id", ondelete="SET NULL")),
    sa.Column("variant_label", sa.Text, nullable=True),
    sa.Column("frozen", sa.Boolean, nullable=False, server_default=sa.false()),  # the "paper" tag
    _created_at(),
    sa.Index("idx_figures_project", "project_id"),
    sa.Index("idx_figures_user", "user_id"),
    sa.Index("idx_figures_parent", "parent_figure_id"),
)

# 11a. papers — the saved Skill-Match / Reproduction anchor (workspace/types.ts SavedPaper +
#      reproduction.py Paper). Bibliographic metadata kept structured.
papers = sa.Table(
    "papers",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
    sa.Column("filename", sa.Text, nullable=False),
    sa.Column("doi", sa.Text, nullable=True),
    sa.Column("pmid", sa.Text, nullable=True),
    sa.Column("title", sa.Text, nullable=True),
    sa.Column("authors", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),
    sa.Column("venue", sa.Text, nullable=True),
    sa.Column("year", sa.Integer, nullable=True),
    sa.Column("volume", sa.Text, nullable=True),
    sa.Column("issue", sa.Text, nullable=True),
    sa.Column("pages", sa.Text, nullable=True),
    sa.Column("is_preprint", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("url", sa.Text, nullable=True),
    sa.Column("modality", sa.Text, nullable=True),         # scrna|bulk|proteomics
    sa.Column("skills", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),  # routed slugs
    sa.Column("out_of_scope", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),
    sa.Column("figure_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("tier_summary", JSON_PORTABLE, nullable=True),
    sa.Column("reproduction_run_id", sa.String(36), sa.ForeignKey("reproduction_runs.id", ondelete="SET NULL")),
    sa.Column("data_map", JSON_PORTABLE, nullable=True),   # per-panel picker overrides
    _created_at(),
    sa.Index("idx_papers_user", "user_id"),
)

# 11b. supplements — files attached to a saved paper (workspace/types.ts SavedSupplement). Bytes in
#      S3 at uploads/{user_id}/supplements/{sha256}.{ext}; the row is the pointer.
supplements = sa.Table(
    "supplements",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("paper_id", sa.String(36), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    sa.Column("filename", sa.Text, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),            # pdf | xlsx | csv
    sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default=sa.text("0")),
    sa.Column("sha256", sa.Text, nullable=True),
    sa.Column("s3_key", sa.Text, nullable=True),           # uploads/{user_id}/supplements/{sha256}.{ext}
    sa.Column("status", sa.Text, nullable=False, server_default="pending_upload"),  # T2 reconciliation
    _created_at(),
    sa.Index("idx_supplements_paper", "paper_id"),
)

# 9. cleaning_recipes — the persisted cleaning plan (makes a cleaned re-run reproducible).
cleaning_recipes = sa.Table(
    "cleaning_recipes",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    sa.Column("steps", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),  # CleaningStep[]
    sa.Column("applied", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("produces_artifact_id", sa.Text, sa.ForeignKey("intermediate_tables.artifact_id", ondelete="SET NULL")),
    _created_at(),
    sa.Index("idx_cleaning_dataset", "dataset_id"),
)

# 10. gene_sets — provenance-stamped gene set (types.ts GeneSet). Account-level (workspace scope).
gene_sets = sa.Table(
    "gene_sets",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("genes", JSON_PORTABLE, nullable=False, server_default=sa.text("'[]'")),
    sa.Column("source", sa.Text, nullable=False, server_default=""),  # go|wikipathways|curated|compiled
    sa.Column("source_label", sa.Text, nullable=False, server_default=""),
    sa.Column("license", sa.Text, nullable=False, server_default=""),
    sa.Column("created_from", sa.Text, nullable=True),
    _created_at(),
    sa.Index("idx_gene_sets_user", "user_id"),
)

# 13. skill_installs — a skill added to a project/workspace (types.ts SkillInstall / WorkspaceSkill).
#     The functional unique (one install per scope) lives on COALESCE(project_id, workspace_id) — a
#     null project_id ⇒ a workspace-wide install. Portable expression (both cols are uuid text).
skill_installs = sa.Table(
    "skill_installs",
    metadata,
    _pk(),
    _user_fk(),
    sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),   # null ⇒ workspace-wide
    sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
    sa.Column("skill_id", sa.Text, nullable=False),
    sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Index("idx_skill_installs_user", "user_id"),
    sa.Index(
        "uq_skill_installs_scope",
        sa.text("COALESCE(project_id, workspace_id)"),
        "skill_id",
        unique=True,
    ),
)

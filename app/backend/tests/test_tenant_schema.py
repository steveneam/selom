"""Tenant schema (AWS materialization step 7a — the 12 tables behind auth).

Validated on stdlib SQLite (no Aurora): the SQLAlchemy-portable schema builds the same via the
Alembic prod path and the metadata.create_all dev path (plan D6 — the dev path is a faithful
stand-in for prod). RLS is Postgres-only and exercised when Aurora lands + the 7b isolation test;
here we prove the migration applies, the keys/FKs/indexes are shaped per spec §2.3, the two build
paths don't drift, and the migration is reversible.
"""

from __future__ import annotations

import argparse
import pathlib

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

_BACKEND = pathlib.Path(__file__).resolve().parent.parent

# The full schema = analysis_jobs (0001) + the 13 tenant tables (0002).
_TENANT_TABLES = {
    "users", "workspaces", "projects", "datasets", "intermediate_tables", "artifact_parents",
    "reproduction_runs", "figures", "papers", "supplements", "cleaning_recipes", "gene_sets",
    "skill_installs",
}
_ALL_TABLES = _TENANT_TABLES | {"analysis_jobs"}


def _sqlite_url(tmp_path, name: str = "schema.db") -> str:
    return f"sqlite:///{tmp_path / name}"


def _alembic_cfg(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    cfg.cmd_opts = argparse.Namespace(x=[f"url={url}"])  # env.py reads -x url=…
    return cfg


def test_migration_creates_all_tenant_tables(tmp_path):
    url = _sqlite_url(tmp_path)
    command.upgrade(_alembic_cfg(url), "head")

    insp = sa.inspect(sa.create_engine(url))
    names = set(insp.get_table_names())
    assert _ALL_TABLES <= names, f"missing: {_ALL_TABLES - names}"


def test_keys_and_tenant_column(tmp_path):
    url = _sqlite_url(tmp_path)
    command.upgrade(_alembic_cfg(url), "head")
    insp = sa.inspect(sa.create_engine(url))

    # natural text PKs match the live code (Clerk id / sha-256)
    assert insp.get_pk_constraint("users")["constrained_columns"] == ["user_id"]
    assert insp.get_pk_constraint("intermediate_tables")["constrained_columns"] == ["artifact_id"]

    # every row-owning tenant table carries a direct user_id (the join-free isolation predicate)
    for table in _TENANT_TABLES:
        cols = {c["name"] for c in insp.get_columns(table)}
        assert "user_id" in cols, f"{table} is missing the tenant user_id"


def test_foreign_keys_and_unique(tmp_path):
    url = _sqlite_url(tmp_path)
    command.upgrade(_alembic_cfg(url), "head")
    insp = sa.inspect(sa.create_engine(url))

    # a representative FK chain: datasets.project_id -> projects, figures.job_id -> analysis_jobs
    ds_fks = {(fk["constrained_columns"][0], fk["referred_table"]) for fk in insp.get_foreign_keys("datasets")}
    assert ("project_id", "projects") in ds_fks
    assert ("user_id", "users") in ds_fks
    fig_fks = {(fk["constrained_columns"][0], fk["referred_table"]) for fk in insp.get_foreign_keys("figures")}
    assert ("job_id", "analysis_jobs") in fig_fks


def test_skill_installs_scope_is_unique(tmp_path):
    """The functional unique (COALESCE(project_id, workspace_id), skill_id) — one install per scope.
    SQLite can't *reflect* an expression index, so prove it by behaviour: a duplicate scope+skill is
    rejected. (The index name is present in sqlite_master.)"""
    url = _sqlite_url(tmp_path)
    command.upgrade(_alembic_cfg(url), "head")
    eng = sa.create_engine(url)

    names = [r[0] for r in eng.connect().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='index'"))]
    assert "uq_skill_installs_scope" in names

    ins = sa.text(
        "INSERT INTO skill_installs (id, user_id, project_id, skill_id, installed_at) "
        "VALUES (:id, 'u', 'p1', 'umap', CURRENT_TIMESTAMP)")
    with eng.begin() as conn:
        conn.execute(ins, {"id": "a"})
    with pytest.raises(IntegrityError):  # same project_id + skill_id -> the scope is taken
        with eng.begin() as conn:
            conn.execute(ins, {"id": "b"})


def test_alembic_and_create_all_agree(tmp_path):
    """No drift: the prod path (Alembic) and the dev path (metadata.create_all) build the same
    table set — the guard that schema.py and the migration stay in sync at creation time."""
    from db.schema import metadata

    alembic_url = _sqlite_url(tmp_path, "alembic.db")
    command.upgrade(_alembic_cfg(alembic_url), "head")
    alembic_tables = set(sa.inspect(sa.create_engine(alembic_url)).get_table_names())
    alembic_tables.discard("alembic_version")  # bookkeeping only

    create_all_eng = sa.create_engine(_sqlite_url(tmp_path, "create_all.db"))
    metadata.create_all(create_all_eng)
    create_all_tables = set(sa.inspect(create_all_eng).get_table_names())

    assert alembic_tables == create_all_tables == _ALL_TABLES


def test_downgrade_is_reversible(tmp_path):
    url = _sqlite_url(tmp_path)
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    names = set(sa.inspect(sa.create_engine(url)).get_table_names())
    assert not (_ALL_TABLES & names), f"left behind: {_ALL_TABLES & names}"

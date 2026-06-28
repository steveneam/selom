"""7c FE-state columns: figures.guardrails + users.local_import_at (AWS materialization step 7c)

Two additive nullable columns the FE-state swap needs (sub-spec
``docs/aws-materialization/7c-frontend-state-migration.md``):

  * **figures.guardrails** — the ``SkillGuardrail[]`` the FE ``Figure`` carries (types.ts:141);
    7a's figures table modelled every other result field but not this one, so a reloaded figure
    would lose its guardrail chips. JSONB on Postgres, JSON text on SQLite (the portable type).
  * **users.local_import_at** — the one-time localStorage→Postgres import marker (Q1): set when a
    dogfood user imports their existing local projects, so the prompt doesn't reappear on another
    device.

Plain ``ADD COLUMN`` (nullable, no default) works natively on both dialects — no Postgres gate, no
SQLite rebuild. Drops use ``batch_alter_table`` so the downgrade is SQLite-version-proof. Mirrors the
``db/schema.py`` edits in the same slice so the create_all dev path and the Alembic prod path stay
drift-free (``tests/test_tenant_schema.py``).

Revision ID: 0004_7c_columns
Revises: 0003_tenant_auth
Create Date: 2026-06-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_7c_columns"
down_revision = "0003_tenant_auth"
branch_labels = None
depends_on = None

# JSONB on Postgres, JSON (text) on SQLite — same column type as db/schema.py:JSON_PORTABLE.
_JSON_PORTABLE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.add_column("figures", sa.Column("guardrails", _JSON_PORTABLE, nullable=True))
    op.add_column("users", sa.Column("local_import_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("local_import_at")
    with op.batch_alter_table("figures") as batch:
        batch.drop_column("guardrails")

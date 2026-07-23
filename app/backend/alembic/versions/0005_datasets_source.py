"""datasets.source — cloud-import provenance (cloud-storage integrations foundation)

One additive nullable column the remote-intake flow (``routers/cloud.py``) stamps after streaming a
file from a cloud provider into the object store: ``{provider, ref, fetched_at}`` (e.g. a URL/S3
import, or a Nango-brokered Google/OneDrive/Dropbox fetch). Import provenance the local-upload path
never had — a locally dropped file has no external source.

Plain ``ADD COLUMN`` (nullable, no default) works natively on both dialects — no Postgres gate, no
SQLite rebuild. The drop uses ``batch_alter_table`` so the downgrade is SQLite-version-proof.
Mirrors the ``db/schema.py`` edit in the same slice so the ``create_all`` dev path and the Alembic
prod path stay drift-free (``tests/test_tenant_schema.py``).

Revision ID: 0005_datasets_source
Revises: 0004_7c_columns
Create Date: 2026-07-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_datasets_source"
down_revision = "0004_7c_columns"
branch_labels = None
depends_on = None

# JSONB on Postgres, JSON (text) on SQLite — same type as db/schema.py:JSON_PORTABLE.
_JSON_PORTABLE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.add_column("datasets", sa.Column("source", _JSON_PORTABLE, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch:
        batch.drop_column("source")

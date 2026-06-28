"""Relational store package (AWS materialization step 2).

The statelessness fix: the in-memory ``JobStore`` (a process-wide dict — a Lambda poll on a
cold instance sees nothing) moves onto a SQL backend behind the SAME create/get/update surface.
SQLAlchemy Core keeps it backend-portable — the dev/test path runs on stdlib SQLite, prod on
Aurora Postgres — selected once by config (``SELOM_DATABASE_URL`` + ``SELOM_JOB_STORE=sql``),
the same local-dev/AWS-prod seam as the ObjectStore. Alembic owns the prod migrations.

Scope (step 2): the ``analysis_jobs`` table + ``SqlJobStore`` only. The full tenant schema
(``users``/``figures``/… + the cross-table FKs + RLS) and the JWT-derived ``user_id`` land in
step 7 (auth/tenancy); ``analysis_jobs`` already carries the forward-compatible columns
(nullable ``user_id`` etc.) so step 7 adds constraints, not columns. See
docs/aws-materialization/spec.md §2, §4.1.
"""

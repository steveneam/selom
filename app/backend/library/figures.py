"""Figures CRUD — the durable produced figure (``db/schema.py`` ``figures``; types.ts ``Figure``).

Backs the FE ``projectStore`` figure mutators (``addFigure`` / ``updateFigureSpec`` / ``freezeFigure``
/ ``removeFigure`` / ``forkFigure``). Key design point (sub-spec §2.2): **client-authoritative ids**
— the FE mints the figure id and POSTs it; ``upsert_figure`` honours it and is idempotent on
``(tenant, id)`` so a retried optimistic write (or a fork re-insert / import) is harmless, never a
duplicate. A fork is just another create with ``parent_figure_id`` set — no special endpoint.

Wire shape is snake_case + ISO timestamps (matching ``UploadRepo``'s ``_dataset_public`` /
``_project_public``); the single camel↔snake translation lives in the FE store adapter.
"""

from __future__ import annotations

from db.retry import run_with_db_retry
from db.schema import figures, projects
from db.tenant import TenantQuery, set_tenant, upsert_user
from library.base import iso

# Opaque JSONB blobs the FE owns end-to-end — stored + returned verbatim (no server-side modelling).
_PASSTHROUGH = (
    "spec", "provenance", "methods", "legend", "guardrails",
    "table_stats", "data_check", "data_fit",
)
# Scalar FK / label columns carried straight from the FE Figure.
_SCALARS = ("dataset_id", "skill_id", "job_id", "parent_figure_id", "variant_label")
# The only fields a PATCH may change (sub-spec §3.3) — ownership/lineage are immutable post-create.
_PATCHABLE = ("title", "spec", "frozen", "variant_label")


def figure_public(row) -> dict:
    return {
        "id": row.id, "project_id": row.project_id, "dataset_id": row.dataset_id,
        "skill_id": row.skill_id, "job_id": row.job_id, "title": row.title,
        "spec": row.spec, "provenance": row.provenance, "methods": row.methods,
        "legend": row.legend, "guardrails": row.guardrails, "table_stats": row.table_stats,
        "data_check": row.data_check, "data_fit": row.data_fit,
        "parent_figure_id": row.parent_figure_id, "variant_label": row.variant_label,
        "frozen": bool(row.frozen), "created_at": iso(row.created_at),
    }


class FigureMixin:
    """Figure CRUD bound to one tenant via ``TenantQuery``."""

    def list_figures(self, user_id: str, project_id: str | None = None) -> list[dict]:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                rows = tq.select(figures, project_id=project_id) if project_id else tq.select(figures)
                return [figure_public(r) for r in rows]
        return run_with_db_retry(_work)

    def get_figure(self, user_id: str, figure_id: str) -> dict | None:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                row = TenantQuery(conn, user_id).get(figures, figure_id)
                return figure_public(row) if row is not None else None
        return run_with_db_retry(_work)

    def upsert_figure(self, user_id: str, email: str | None, fig: dict) -> dict:
        """Create (or idempotently re-apply) a figure with its client-supplied id. Raises ``KeyError``
        if ``project_id`` isn't this tenant's project (→ 404 upstream)."""
        fig_id = fig.get("id")
        project_id = fig.get("project_id")

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                if project_id is None or tq.get(projects, project_id) is None:
                    raise KeyError(project_id)  # not this tenant's project
                values: dict = {k: fig.get(k) for k in _SCALARS}
                values["project_id"] = project_id
                values["title"] = (fig.get("title") or "").strip() or "Untitled figure"
                values["frozen"] = bool(fig.get("frozen", False))
                for k in _PASSTHROUGH:
                    values[k] = fig.get(k)
                if fig_id and tq.get(figures, fig_id) is not None:
                    tq.update(figures, fig_id, **values)
                    out_id = fig_id
                else:
                    if fig_id:
                        values["id"] = fig_id
                    out_id = tq.insert(figures, **values)
                return figure_public(tq.get(figures, out_id))
        return run_with_db_retry(_work)

    def update_figure(self, user_id: str, figure_id: str, changes: dict) -> dict | None:
        """Partial update (PATCH): only ``_PATCHABLE`` fields. ``None`` ⇒ row not this tenant's."""
        patch = {k: v for k, v in changes.items() if k in _PATCHABLE}

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(figures, figure_id) is None:
                    return None
                if patch:
                    tq.update(figures, figure_id, **patch)
                return figure_public(tq.get(figures, figure_id))
        return run_with_db_retry(_work)

    def delete_figure(self, user_id: str, figure_id: str) -> int:
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                return TenantQuery(conn, user_id).delete(figures, figure_id)
        return run_with_db_retry(_work)

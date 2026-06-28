"""Account-level library: the workspace container, gene sets, and skill installs (step 7c, BE-2).

Backs the FE ``workspaceStore`` (gene sets + skills) and the ``projectStore`` install mutators. All
account-scoped rows carry ``workspace_id`` (the tenant's single workspace) — see
``base.ensure_workspace`` for why. Tenant = ``ctx.user_id`` via ``TenantQuery`` throughout.
"""

from __future__ import annotations

import sqlalchemy as sa

from db.retry import run_with_db_retry
from db.schema import gene_sets, projects, skill_installs, workspaces
from db.tenant import TenantQuery, set_tenant, upsert_user
from library.base import ensure_workspace, iso


def _gene_set_public(row) -> dict:
    return {
        "id": row.id, "name": row.name, "genes": row.genes, "source": row.source,
        "source_label": row.source_label, "license": row.license,
        "created_from": row.created_from, "created_at": iso(row.created_at),
    }


def _install_public(row) -> dict:
    return {
        "id": row.id, "skill_id": row.skill_id, "project_id": row.project_id,
        "workspace_id": row.workspace_id, "installed_at": iso(row.installed_at),
    }


class WorkspaceMixin:
    def get_workspace(self, user_id: str, email: str | None = None) -> dict:
        """The account workspace (auto-created on first read). The FE doesn't need its id directly,
        but a GET gives the store a single place to provision + a name to show."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                ws_id = ensure_workspace(conn, tq)
                row = conn.execute(sa.select(workspaces).where(workspaces.c.id == ws_id)).first()
                return {"id": row.id, "name": row.name, "created_at": iso(row.created_at)}
        return run_with_db_retry(_work)


class GeneSetMixin:
    def list_gene_sets(self, user_id: str) -> list[dict]:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                return [_gene_set_public(r) for r in TenantQuery(conn, user_id).select(gene_sets)]
        return run_with_db_retry(_work)

    def save_gene_set(self, user_id: str, email: str | None, gs: dict) -> dict:
        """Save a gene set (account-level). Idempotent on ``created_from`` (the source catalog id) —
        mirrors ``workspaceStore.saveGeneSet`` — and on the client id (a retried optimistic write)."""
        gs_id = gs.get("id")
        created_from = gs.get("created_from")

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                ws_id = ensure_workspace(conn, tq)
                if gs_id and tq.get(gene_sets, gs_id) is not None:
                    return _gene_set_public(tq.get(gene_sets, gs_id))  # idempotent re-POST
                if created_from:  # dedup on the source catalog id (one workspace entry per panel)
                    dup = tq.select(gene_sets, created_from=created_from)
                    if dup:
                        return _gene_set_public(dup[0])
                values = {
                    "workspace_id": ws_id,
                    "name": gs.get("name") or "Gene set",
                    "genes": gs.get("genes") or [],
                    "source": gs.get("source") or "",
                    "source_label": gs.get("source_label") or "",
                    "license": gs.get("license") or "",
                    "created_from": created_from,
                }
                if gs_id:
                    values["id"] = gs_id
                new_id = tq.insert(gene_sets, **values)
                return _gene_set_public(tq.get(gene_sets, new_id))
        return run_with_db_retry(_work)

    def delete_gene_set(self, user_id: str, gene_set_id: str) -> int:
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                return TenantQuery(conn, user_id).delete(gene_sets, gene_set_id)
        return run_with_db_retry(_work)


class InstallMixin:
    def list_installs(self, user_id: str, project_id: str | None = None) -> list[dict]:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                rows = tq.select(skill_installs, project_id=project_id) if project_id else tq.select(skill_installs)
                return [_install_public(r) for r in rows]
        return run_with_db_retry(_work)

    def install_skill(self, user_id: str, email: str | None, skill_id: str,
                      project_id: str | None = None, install_id: str | None = None) -> dict:
        """Install a skill into a project (``project_id`` set) or workspace-wide (``project_id`` null →
        ``workspace_id`` set). Idempotent on the scope — a re-install returns the existing row. The
        client-authoritative ``install_id`` (sub-spec §2.2) keeps the optimistic local row and the
        server row in sync so reconcile can't duplicate the install."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                if project_id is not None:
                    if tq.get(projects, project_id) is None:
                        raise KeyError(project_id)  # not this tenant's project
                    existing = tq.select(skill_installs, project_id=project_id, skill_id=skill_id)
                    ws_id = None
                else:
                    ws_id = ensure_workspace(conn, tq)
                    existing = [r for r in tq.select(skill_installs, skill_id=skill_id)
                                if r.project_id is None]
                if existing:
                    return _install_public(existing[0])  # idempotent
                values = {"skill_id": skill_id, "project_id": project_id, "workspace_id": ws_id}
                if install_id:
                    values["id"] = install_id
                new_id = tq.insert(skill_installs, **values)
                return _install_public(tq.get(skill_installs, new_id))
        return run_with_db_retry(_work)

    def uninstall_skill(self, user_id: str, skill_id: str,
                        project_id: str | None = None) -> int:
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if project_id is not None:
                    matches = tq.select(skill_installs, project_id=project_id, skill_id=skill_id)
                else:
                    matches = [r for r in tq.select(skill_installs, skill_id=skill_id)
                               if r.project_id is None]
                for r in matches:
                    tq.delete(skill_installs, r.id)
                return len(matches)
        return run_with_db_retry(_work)

"""One-time localStorage → Postgres import (step 7c, BE-3, sub-spec §4).

Takes the decoded ``selom.projects.v1`` + ``selom.workspace.v1`` blobs (the FE camelCase shapes) and
upserts them in FK-dependency order inside ONE tenant transaction — so a failed import leaves nothing
half-written. Every row is skip-if-exists (idempotent on the client-authoritative id), so a retry or
a re-run converges to the same state. Datasets are imported metadata-only (the mock never had real
bytes — a run on one returns "re-upload to materialize"); ``users.local_import_at`` is stamped so the
prompt doesn't reappear (Q1).
"""

from __future__ import annotations

import sqlalchemy as sa

from db.retry import run_with_db_retry
from db.schema import (
    datasets, figures, gene_sets, papers, projects, skill_installs, supplements, users,
)
from db.tenant import TenantQuery, set_tenant, upsert_user
from library.base import ensure_workspace


class ImportMixin:
    def import_local_state(self, user_id: str, email: str | None,
                           projects_blob: dict | None, workspace_blob: dict | None) -> dict:
        pb = projects_blob or {}
        wb = workspace_blob or {}
        counts = {k: 0 for k in (
            "projects", "datasets", "figures", "installs", "gene_sets", "papers", "supplements")}

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                ws_id = ensure_workspace(conn, tq)

                # 1. projects
                for p in pb.get("projects", []):
                    pid = p.get("id")
                    if not pid or tq.get(projects, pid) is not None:
                        continue
                    tq.insert(projects, id=pid, name=p.get("name") or "Untitled project",
                              color=p.get("color") or "blue", workspace_id=ws_id)
                    counts["projects"] += 1
                valid_projects = {r.id for r in tq.select(projects)}

                # 2. datasets (metadata-only — no bytes in the mock; status=ready, no upload key)
                for d in pb.get("datasets", []):
                    did = d.get("id")
                    if not did or d.get("projectId") not in valid_projects:
                        continue
                    if tq.get(datasets, did) is not None:
                        continue
                    tq.insert(datasets, id=did, project_id=d["projectId"],
                              filename=d.get("filename") or "data.csv", label=d.get("label"),
                              modality=d.get("modality"), current_sha256=d.get("currentSha256"),
                              qc=d.get("qc"), status="ready", size_bytes=0)
                    counts["datasets"] += 1
                valid_datasets = {r.id for r in tq.select(datasets)}

                # 3. figures (parent_figure_id only when the parent is already imported — FK-safe)
                imported_figs: set[str] = set()
                for f in pb.get("figures", []):
                    fid = f.get("id")
                    if not fid or f.get("projectId") not in valid_projects:
                        continue
                    if tq.get(figures, fid) is not None:
                        continue
                    parent = f.get("parentFigureId")
                    tq.insert(
                        figures, id=fid, project_id=f["projectId"],
                        dataset_id=f.get("datasetId") if f.get("datasetId") in valid_datasets else None,
                        skill_id=f.get("skillId"), title=f.get("title") or "Untitled figure",
                        spec=f.get("spec"), provenance=f.get("provenance"), methods=f.get("methods"),
                        legend=f.get("legend"), guardrails=f.get("guardrails"),
                        table_stats=f.get("table"), data_check=f.get("dataCheck"),
                        data_fit=f.get("dataFit"),
                        parent_figure_id=parent if parent in imported_figs else None,
                        variant_label=f.get("variantLabel"), frozen=bool(f.get("frozen", False)))
                    imported_figs.add(fid)
                    counts["figures"] += 1

                # 4. skill installs — project-scoped (projectStore.installs) + workspace-wide
                #    (workspace.skills). Dedup per scope.
                for i in pb.get("installs", []):
                    pid, sid = i.get("projectId"), i.get("skillId")
                    if not sid or pid not in valid_projects:
                        continue
                    if tq.select(skill_installs, project_id=pid, skill_id=sid):
                        continue
                    tq.insert(skill_installs, skill_id=sid, project_id=pid, workspace_id=None)
                    counts["installs"] += 1
                for s in wb.get("skills", []):
                    sid = s.get("skillId")
                    if not sid:
                        continue
                    if any(r.project_id is None for r in tq.select(skill_installs, skill_id=sid)):
                        continue
                    tq.insert(skill_installs, skill_id=sid, project_id=None, workspace_id=ws_id)
                    counts["installs"] += 1

                # 5. gene sets — from BOTH the project blob and the workspace blob, deduped on
                #    created_from (the source catalog id) like the FE.
                seen_from: set[str] = set()
                for r in tq.select(gene_sets):
                    if r.created_from:
                        seen_from.add(r.created_from)
                for gs in [*pb.get("geneSets", []), *wb.get("geneSets", [])]:
                    gid = gs.get("id")
                    cf = gs.get("createdFrom")
                    if cf and cf in seen_from:
                        continue
                    if gid and tq.get(gene_sets, gid) is not None:
                        continue
                    tq.insert(gene_sets, id=gid or None, workspace_id=ws_id,
                              name=gs.get("name") or "Gene set", genes=gs.get("genes") or [],
                              source=gs.get("source") or "", source_label=gs.get("sourceLabel") or "",
                              license=gs.get("license") or "", created_from=cf)
                    if cf:
                        seen_from.add(cf)
                    counts["gene_sets"] += 1

                # 6. saved papers (+ supplements), deduped on (doi||filename)
                seen_papers: dict[str, str] = {}  # dedup key -> id
                for r in tq.select(papers):
                    seen_papers[(r.doi or "").strip() or (r.filename or "")] = r.id
                for p in wb.get("papers", []):
                    key = (p.get("doi") or "").strip() or (p.get("filename") or "")
                    pid = p.get("id")
                    if (key and key in seen_papers) or (pid and tq.get(papers, pid) is not None):
                        continue
                    new_pid = tq.insert(
                        papers, id=pid or None, workspace_id=ws_id,
                        filename=p.get("filename") or "paper.pdf", doi=p.get("doi"), pmid=p.get("pmid"),
                        title=p.get("title"), authors=p.get("authors") or [], venue=p.get("venue"),
                        year=p.get("year"), volume=p.get("volume"), issue=p.get("issue"),
                        pages=p.get("pages"), is_preprint=bool(p.get("isPreprint", False)),
                        url=p.get("url"), modality=p.get("modality"), skills=p.get("skills") or [],
                        out_of_scope=p.get("outOfScope") or [],
                        figure_count=int(p.get("figureCount") or 0),
                        tier_summary=p.get("tierSummary"), data_map=p.get("dataMap"))
                    if key:
                        seen_papers[key] = new_pid
                    counts["papers"] += 1
                    for sup in p.get("supplements", []) or []:
                        tq.insert(supplements, id=sup.get("id") or None, paper_id=new_pid,
                                  filename=sup.get("filename") or "supplement",
                                  kind=sup.get("kind") or "csv",
                                  size_bytes=int(sup.get("size") or sup.get("size_bytes") or 0),
                                  status="ready")
                        counts["supplements"] += 1

                # stamp the import marker (Q1) so the prompt doesn't reappear cross-device
                conn.execute(sa.update(users).where(users.c.user_id == user_id)
                             .values(local_import_at=sa.func.now()))
                return counts
        return run_with_db_retry(_work)

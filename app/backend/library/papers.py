"""Saved papers + their supplements (step 7c, BE-2) — the FE ``workspaceStore`` paper anchor.

The whole-paper upsert carries the paper's ``supplements`` array and reconciles the child rows in one
call, so EVERY FE paper mutation (``savePaper`` · ``setPaperDataMap`` · ``setPaperReproductionRun`` ·
``addPaperSupplements`` · ``removePaperSupplement``) is a single ``POST /workspace/papers`` of the
current object — the optimistic store already holds the full paper. Dedup mirrors the FE
(``(doi||filename)``) so re-saving the same paper updates in place, and the client id makes a retried
write idempotent. Supplements are metadata-only (no bytes; spec I5).
"""

from __future__ import annotations

from db.retry import run_with_db_retry
from db.schema import papers, supplements
from db.tenant import TenantQuery, set_tenant, upsert_user
from library.base import ensure_workspace, iso

# Paper columns carried straight from the FE SavedPaper (snake_case wire shape).
_PAPER_COLS = (
    "filename", "doi", "pmid", "title", "venue", "year", "volume", "issue", "pages",
    "is_preprint", "url", "modality", "figure_count", "reproduction_run_id",
)
_PAPER_JSON = ("authors", "skills", "out_of_scope", "tier_summary", "data_map")


def _supplement_public(row) -> dict:
    return {"id": row.id, "filename": row.filename, "kind": row.kind,
            "size_bytes": int(row.size_bytes or 0), "created_at": iso(row.created_at)}


def _dedup_key(doi, filename) -> str:
    return (doi or "").strip() or (filename or "")


class PaperMixin:
    def _paper_public(self, conn, tq, paper_id: str) -> dict | None:
        row = tq.get(papers, paper_id)
        if row is None:
            return None
        out = {c: getattr(row, c) for c in _PAPER_COLS}
        out["id"] = row.id
        out["is_preprint"] = bool(row.is_preprint)
        for c in _PAPER_JSON:
            out[c] = getattr(row, c)
        out["created_at"] = iso(row.created_at)
        supps = tq.select(supplements, paper_id=paper_id)
        out["supplements"] = [_supplement_public(s) for s in supps]
        return out

    def list_papers(self, user_id: str) -> list[dict]:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                return [self._paper_public(conn, tq, r.id) for r in tq.select(papers)]
        return run_with_db_retry(_work)

    def get_paper(self, user_id: str, paper_id: str) -> dict | None:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                return self._paper_public(conn, tq, paper_id)
        return run_with_db_retry(_work)

    def upsert_paper(self, user_id: str, email: str | None, p: dict) -> dict:
        pid = p.get("id")
        dedup = _dedup_key(p.get("doi"), p.get("filename"))

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                ws_id = ensure_workspace(conn, tq)
                target = tq.get(papers, pid) if pid else None
                if target is None and dedup:  # dedup on (doi||filename), like the FE
                    for r in tq.select(papers):
                        if _dedup_key(r.doi, r.filename) == dedup:
                            target = r
                            break
                values = {c: p.get(c) for c in _PAPER_COLS}
                values["filename"] = values.get("filename") or "paper.pdf"
                values["is_preprint"] = bool(p.get("is_preprint", False))
                values["figure_count"] = int(p.get("figure_count") or 0)
                values["workspace_id"] = ws_id
                for c in _PAPER_JSON:
                    values[c] = p.get(c)
                if target is not None:
                    tq.update(papers, target.id, **values)
                    out_id = target.id
                else:
                    if pid:
                        values["id"] = pid
                    out_id = tq.insert(papers, **values)
                if p.get("supplements") is not None:
                    self._sync_supplements(tq, out_id, p["supplements"])
                return self._paper_public(conn, tq, out_id)
        return run_with_db_retry(_work)

    def _sync_supplements(self, tq, paper_id: str, items: list) -> None:
        """Replace the paper's supplement set with ``items`` (reconcile by id): keep/update provided,
        delete the rest, insert new. Metadata-only — no bytes (spec I5)."""
        existing = {r.id: r for r in tq.select(supplements, paper_id=paper_id)}
        provided_ids = {it.get("id") for it in items if it.get("id")}
        for sid in existing:
            if sid not in provided_ids:
                tq.delete(supplements, sid)
        for it in items:
            values = {
                "paper_id": paper_id,
                "filename": it.get("filename") or "supplement",
                "kind": it.get("kind") or "csv",
                "size_bytes": int(it.get("size_bytes") or it.get("size") or 0),
                "status": "ready",  # metadata-only (no upload flow for supplements in 7c)
            }
            sid = it.get("id")
            if sid and sid in existing:
                tq.update(supplements, sid, **values)
            else:
                if sid:
                    values["id"] = sid
                tq.insert(supplements, **values)

    def delete_paper(self, user_id: str, paper_id: str) -> int:
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                # supplements cascade on Postgres (FK ondelete=CASCADE); SQLite doesn't enforce FKs,
                # so delete the children explicitly to avoid orphans on the dev path.
                tq = TenantQuery(conn, user_id)
                for s in tq.select(supplements, paper_id=paper_id):
                    tq.delete(supplements, s.id)
                return tq.delete(papers, paper_id)
        return run_with_db_retry(_work)

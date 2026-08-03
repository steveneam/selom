"""D3 — content-addressed intermediate-table lineage (engine.lineage).

The store materializes the table a stage produced under its content hash, with parent-hash lineage +
the cleaning recipe / merge receipt. Covers the three acceptance points: "inspect the matrix the
skill saw" (round-trip the bytes), a cleaned re-run is reproducible (same bytes → same id, immutable),
and a combine records "merged from {A, B, C}". The suite-wide conftest disables the store; these tests
opt back in with an enabled temp-dir instance (mirrors test_result_cache).
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from engine import lineage
from engine.lineage import ArtifactStore, ParentRef
from main import app

# Every artifact belongs to a tenant now (auth-multitenancy §4 step 2) — these tests name one
# explicitly rather than relying on a default, because a default owner is exactly the shared-prefix
# bug the tenant-scoped keys exist to prevent.
OWNER_A = "user_a"
OWNER_B = "user_b"

_DE_DF = pd.DataFrame(
    {"gene": ["ACTB", "GAPDH", "B2M"],
     "log2FoldChange": [2.1, -1.4, 0.1],
     "padj": [0.001, 0.02, 0.9]}
)


@pytest.fixture(autouse=True)
def _artifacts_on(tmp_path, monkeypatch):
    """A fresh enabled store per test (the conftest turns the real one off)."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")  # endpoint tests run the stub runner
    prev = lineage._default
    lineage.set_store(ArtifactStore(root=tmp_path / "artifacts", enabled=True))
    yield
    lineage.set_store(prev)


# --- the store --------------------------------------------------------------------------------

def test_materialize_table_records_shape_and_hash():
    meta = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    assert meta is not None
    assert meta.materialized is True
    assert (meta.n_rows, meta.n_cols) == (3, 3)
    assert meta.columns == ["gene", "log2FoldChange", "padj"]
    assert len(meta.artifact_id) == 64  # a full sha256 hex


def test_same_table_is_reproducible_and_immutable():
    """The id IS the content hash → a re-materialize finds the existing immutable record (same id,
    same created_at) and never forks. The reproducibility acceptance."""
    a = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    b = lineage.materialize(_DE_DF.copy(), owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    assert a.artifact_id == b.artifact_id
    assert a.created_at == b.created_at        # the first record is returned, not rewritten
    # a different table → a different id (content-addressed).
    other = lineage.materialize(_DE_DF.assign(padj=[0.5, 0.5, 0.5]), owner=OWNER_A, kind=lineage.KIND_INGESTED)
    assert other.artifact_id != a.artifact_id


def test_inspect_the_matrix_round_trips_the_bytes():
    """"Inspect the matrix the skill saw": the materialized CSV reloads to the same table."""
    meta = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    raw = lineage.get_table(meta.artifact_id, owner=OWNER_A)
    assert raw is not None
    import io

    back = pd.read_csv(io.BytesIO(raw))
    pd.testing.assert_frame_equal(back, _DE_DF)


def test_survives_a_new_store_at_the_same_root(tmp_path):
    """The disk tier survives a process restart — a fresh store at the same root reads the record."""
    store1 = ArtifactStore(root=tmp_path / "art", enabled=True)
    lineage.set_store(store1)
    meta = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    store2 = ArtifactStore(root=tmp_path / "art", enabled=True)  # no in-proc cache — reads disk
    assert store2.get_meta(meta.artifact_id, owner=OWNER_A) is not None
    assert store2.get_table(meta.artifact_id, owner=OWNER_A) is not None


def test_combined_artifact_renders_merged_from_receipt():
    """A merge records "merged from {A, B, C}" — the combine acceptance."""
    parents = [ParentRef(kind="source", id="aaa", label="a.csv"),
               ParentRef(kind="source", id="bbb", label="b.csv"),
               ParentRef(kind="source", id="ccc", label="c.csv")]
    meta = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_COMBINED, filename="combined.csv",
                               parents=parents, recipe_note="merged 3 file(s)")
    assert meta.receipt == "merged from {a.csv, b.csv, c.csv}"
    assert meta.kind == lineage.KIND_COMBINED


def test_lineage_walks_artifact_parents():
    """An artifact derived from a prior artifact chains; source-file parents are leaves."""
    parent = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="raw.csv")
    child = lineage.materialize(
        _DE_DF.assign(extra=[1, 2, 3]), owner=OWNER_A, kind=lineage.KIND_CLEANED,
        filename="clean.csv",
        parents=[ParentRef(kind="artifact", id=parent.artifact_id, label="raw.csv")])
    chain = [m.artifact_id for m in lineage.lineage(child.artifact_id, owner=OWNER_A)]
    assert chain == [child.artifact_id, parent.artifact_id]


def test_matrix_payload_is_recorded_meta_only():
    """A single-cell matrix is recorded meta-only (shape + lineage), never a multi-GB CSV."""
    class AnnData:  # name-matched by engine.databundle._is_anndata (duck-typed, no anndata import)
        def __init__(self, n_obs, n_vars):
            self.n_obs, self.n_vars = n_obs, n_vars

    meta = lineage.materialize(AnnData(500, 20000), owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="cells.h5ad")
    assert meta.kind == lineage.KIND_MATRIX
    assert meta.materialized is False
    assert (meta.n_rows, meta.n_cols) == (500, 20000)
    assert lineage.get_table(meta.artifact_id, owner=OWNER_A) is None  # no table bytes
    assert "not materialized" in meta.note


def test_disabled_store_materializes_nothing():
    lineage.set_store(ArtifactStore(root="unused", enabled=False))
    assert lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED) is None


# --- the endpoints ----------------------------------------------------------------------------

client = TestClient(app)
_DE_CSV = ("de.csv", b"gene,log2FoldChange,padj\nACTB,2.1,0.001\nGAPDH,-1.4,0.02\nB2M,0.1,0.9\n",
           "text/csv")


def test_run_stamps_an_inspectable_artifact():
    """A run stamps the artifact of the matrix it consumed; the inspect endpoints round-trip it."""
    r = client.post("/skills/volcano/run", files={"matrix": _DE_CSV})
    assert r.status_code == 200
    art = r.json()["artifact"]
    assert art and art["kind"] == "ingested" and art["n_rows"] == 3
    assert art["receipt"].startswith("derived from")

    aid = art["artifact_id"]
    meta = client.get(f"/artifacts/{aid}")
    assert meta.status_code == 200
    assert meta.json()["meta"]["artifact_id"] == aid
    assert meta.json()["lineage"][0]["artifact_id"] == aid

    table = client.get(f"/artifacts/{aid}/table")
    assert table.status_code == 200
    assert b"ACTB" in table.content and b"log2FoldChange" in table.content


def test_unknown_artifact_is_404():
    assert client.get("/artifacts/deadbeef").status_code == 404
    assert client.get("/artifacts/deadbeef/table").status_code == 404


def test_combine_records_merged_from_receipt():
    """POST /data/combine materializes the cohort table and surfaces its "merged from {…}" receipt."""
    import json as _json

    files = [("files", ("wt.csv", b"sample_id,bwave\nW1,100\nW2,110\n", "text/csv")),
             ("files", ("ko.csv", b"sample_id,bwave\nK1,40\nK2,55\n", "text/csv"))]
    r = client.post("/data/combine", files=files, data={"labels": "WT,KO"})
    assert r.status_code == 200
    summary = _json.loads(r.headers["X-Combine-Summary"])
    assert "artifact_id" in summary
    assert summary["receipt"] == "merged from {wt.csv, ko.csv}"


# --- tenant isolation (auth-multitenancy §4 step 2) ----------------------------------------------
# The leak these close: /artifacts/{id}/table served the exact matrix a skill consumed to whoever
# held the id, with no tenant check at all. An opaque id is an identifier, not an authorization,
# and "you would have to guess it" is not a control.

def test_another_tenant_cannot_read_the_table_bytes():
    """The sharpest hole in the audit, closed at the engine layer."""
    meta = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    assert lineage.get_table(meta.artifact_id, owner=OWNER_A) is not None
    assert lineage.get_table(meta.artifact_id, owner=OWNER_B) is None


def test_another_tenant_cannot_read_the_lineage_record():
    meta = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="de.csv")
    assert lineage.get_meta(meta.artifact_id, owner=OWNER_A) is not None
    assert lineage.get_meta(meta.artifact_id, owner=OWNER_B) is None


def test_the_lineage_walk_cannot_cross_tenants():
    """A crafted parent edge pointing at another tenant's artifact must resolve to nothing, so the
    ancestor walk can never become a read-through into their records."""
    theirs = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="a.csv")
    mine = lineage.materialize(
        _DE_DF.assign(extra=[1, 2, 3]), owner=OWNER_B, kind=lineage.KIND_CLEANED, filename="b.csv",
        parents=[ParentRef(kind="artifact", id=theirs.artifact_id, label="not-mine.csv")])
    chain = [m.artifact_id for m in lineage.lineage(mine.artifact_id, owner=OWNER_B)]
    assert chain == [mine.artifact_id], "the walk leaked into another tenant's artifact"


def test_identical_tables_do_not_alias_across_tenants():
    """The content-addressed trap. The id IS the content hash, so two tenants who upload the SAME
    table derive the SAME id — sharing one key would make B's read a read of A's bytes. Each tenant
    keeps its own copy: cross-tenant dedup IS the leak."""
    a = lineage.materialize(_DE_DF, owner=OWNER_A, kind=lineage.KIND_INGESTED, filename="a.csv")
    b = lineage.materialize(_DE_DF.copy(), owner=OWNER_B, kind=lineage.KIND_INGESTED, filename="b.csv")
    assert a.artifact_id == b.artifact_id, "same bytes should still be the same content hash"
    # ...but each resolves within its own prefix, and to its own record.
    assert lineage.get_meta(a.artifact_id, owner=OWNER_A).filename == "a.csv"
    assert lineage.get_meta(b.artifact_id, owner=OWNER_B).filename == "b.csv"
    # Immutability is per tenant, so B's write is not silently discarded as a duplicate of A's.


def test_an_artifact_cannot_be_written_without_an_owner():
    """A blank owner would collapse every tenant back onto one shared prefix — refuse it loudly
    rather than defaulting, which is how the shared prefix existed in the first place."""
    with pytest.raises(ValueError, match="owner"):
        lineage.materialize(_DE_DF, owner="", kind=lineage.KIND_INGESTED)
    with pytest.raises(ValueError, match="owner"):
        lineage.materialize(_DE_DF, owner="   ", kind=lineage.KIND_INGESTED)


def test_a_path_shaped_tenant_id_cannot_escape_its_prefix():
    """Defence in depth. The tenant is a verified claim, never user input — but an object-store key
    is a PATH, and a future provider whose `sub` contains a separator must not be able to address
    another tenant's prefix."""
    from engine.lineage import _owner_seg

    for hostile in ("../user_b", "a/b", "user_a/../user_b", "..", "/"):
        seg = _owner_seg(hostile)
        assert "/" not in seg and ".." not in seg, f"{hostile!r} produced an escaping segment {seg!r}"
    # A plain id is passed through unchanged, so keys stay readable for the common case.
    assert _owner_seg("user_2abc-DEF.x") == "user_2abc-DEF.x"
    # Distinct hostile ids stay distinct (the hash is not a collapse-to-one).
    assert _owner_seg("../user_b") != _owner_seg("../user_c")

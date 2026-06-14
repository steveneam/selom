"""Gene-set builder Phase A — the unified library, the /gene-sets API, and the apply paths.

License-clean corpus (GO · WikiPathways CC0 · Selom curated) surfaced as a searchable
catalog, with two apply paths: the ``enrichment`` source-select and the ``volcano``
highlight panel. These exercise the committed corpus (curated + WikiPathways) so they
are deterministic even on a fresh clone where the large GO library is not built.
"""

from fastapi.testclient import TestClient

from gene_sets import library
from main import app

client = TestClient(app)


# --- the unified library --------------------------------------------------------------

def test_sources_include_open_and_curated():
    keys = {s["key"] for s in library.list_sources()}
    assert {"wikipathways", "curated"} <= keys      # committed → always present
    by_key = {s["key"]: s for s in library.list_sources()}
    assert by_key["wikipathways"]["license"] == "CC0-1.0"
    assert by_key["curated"]["license"] == "Selom (owned)"
    assert by_key["wikipathways"]["n_sets"] > 100    # 921 at build time


def test_search_finds_curated_panel_and_omits_full_gene_list():
    hits = library.search("phototransduction", source="curated")
    assert hits, "the curated phototransduction panel should be searchable"
    card = hits[0]
    assert card["source"] == "curated"
    assert card["size"] > 10
    assert "genes" not in card and card["sample_genes"]   # cards are lightweight


def test_get_set_returns_members_and_provenance():
    set_id = library.search("primary cilium", source="curated")[0]["id"]
    full = library.get_set(set_id)
    assert full is not None
    assert "RPGR" in full["genes"] and "CEP290" in full["genes"]
    assert full["provenance"]["license"] == "Selom (owned)"
    assert full["provenance"]["n_genes"] == len(full["genes"])


def test_get_set_unknown_id_is_none():
    assert library.get_set("curated:deadbeef00") is None


def test_load_collection_per_source_and_all():
    curated = library.load_collection("curated")
    assert len(curated) == 2                          # two owned panels
    wp = library.load_collection("wikipathways")
    assert len(wp) > 100
    merged = library.load_collection("all")
    assert len(merged) >= len(curated) + len(wp)      # union spans every source


# --- the API ---------------------------------------------------------------------------

def test_gene_sets_endpoint_lists_sources_and_results():
    r = client.get("/gene-sets", params={"q": "cilium", "limit": 20})
    assert r.status_code == 200
    body = r.json()
    assert any(s["key"] == "wikipathways" for s in body["sources"])
    assert body["results"] and all("cilium" in it["name"].lower() for it in body["results"])


def test_gene_set_detail_endpoint_round_trips():
    set_id = client.get("/gene-sets", params={"q": "phototransduction", "source": "curated"}).json()["results"][0]["id"]
    r = client.get(f"/gene-sets/{set_id}")
    assert r.status_code == 200
    assert "RHO" in r.json()["genes"]


def test_gene_set_detail_unknown_is_404():
    assert client.get("/gene-sets/curated:0000000000").status_code == 404


# --- apply path 1: enrichment source-select --------------------------------------------

def test_enrichment_resolves_source_aliases():
    from skills.enrichment.run_real import _load_gene_sets

    # The default/back-compat value still loads GO; 'curated' loads exactly our panels.
    assert _load_gene_sets("curated").keys() == library.load_collection("curated").keys()
    assert "RHO" in _load_gene_sets("curated")["Phototransduction & visual cycle"]
    assert _load_gene_sets("GO_Reactome").keys() == library.load_collection("go").keys()
    assert _load_gene_sets("nonsense").keys() == library.load_collection("go").keys()  # unknown → GO


# --- apply path 2: volcano highlight panel ---------------------------------------------

def test_volcano_assemble_adds_highlight_layer_only_when_given():
    from skills.volcano.run import _assemble

    base = _assemble(([1.0], [3.0]), ([-1.0], [3.0]), ([0.0], [0.5]), [], 1.0, 1.3, "t")
    assert not any(tr.get("name") == "highlighted" for tr in base["data"])

    hl = _assemble(([1.0], [3.0]), ([-1.0], [3.0]), ([0.0], [0.5]), [], 1.0, 1.3, "t",
                   highlight=[(1.0, 3.0, "RHO")])
    hl_traces = [tr for tr in hl["data"] if tr.get("name") == "highlighted"]
    assert len(hl_traces) == 1 and hl_traces[0]["text"] == ["RHO"]


def test_volcano_panel_parsing_is_separator_tolerant():
    from skills.volcano.run_real import _parse_panel

    assert _parse_panel("rho, GNAT1\nPDE6B  sag") == {"RHO", "GNAT1", "PDE6B", "SAG"}
    assert _parse_panel("") == set()


# --- Phase B: compile (union/intersect) + normalize ------------------------------------

def test_normalize_uppercases_and_dedups():
    from gene_sets.normalize import normalize

    out = normalize(["RHO", "rho", " Sag ", "RHO"])
    assert out["genes"] == sorted({"RHO", "SAG"})   # holds with or without the HGNC map


def test_compile_union_intersect_and_provenance():
    photo = library.search("phototransduction", source="curated")[0]["id"]
    cilium = library.search("primary cilium", source="curated")[0]["id"]

    u = library.compile_sets([photo, cilium], "union")
    assert u["op"] == "union"
    assert u["provenance"]["n_out"] == len(u["genes"]) > 0
    assert len(u["provenance"]["compiled_from"]) == 2
    assert "Selom (owned)" in u["provenance"]["licenses"]

    # intersect of a set with itself is itself (normalized) and lives within the union.
    i = library.compile_sets([cilium, cilium], "intersect")
    assert i["op"] == "intersect" and i["genes"]
    assert set(i["genes"]) <= set(u["genes"])

    # an unknown id is reported, not fatal.
    m = library.compile_sets([photo, "curated:doesnotexist"], "union")
    assert m["missing"] == ["curated:doesnotexist"] and len(m["provenance"]["compiled_from"]) == 1


def test_compile_endpoint_and_validation():
    photo = client.get("/gene-sets", params={"q": "phototransduction", "source": "curated"}).json()["results"][0]["id"]
    r = client.post("/gene-sets/compile", json={"set_ids": [photo], "op": "union", "name": "My panel"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "My panel" and body["genes"]
    assert client.post("/gene-sets/compile", json={"set_ids": []}).status_code == 400

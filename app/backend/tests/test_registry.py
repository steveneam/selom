"""GET /skills registry — shape + completeness.

The live registry is what the FE Store reads instead of its seed (B3). It must
list every on-disk skill in the SkillCatalogEntry shape the FE types expect.
"""

from fastapi.testclient import TestClient

from main import app
from skills.registry import list_skill_ids

client = TestClient(app)

# Fields the FE SkillCatalogEntry (app/frontend/lib/catalog/types.ts) requires.
_REQUIRED = {
    "id", "name", "summary", "source", "category", "omics", "tier", "status",
    "engine", "inputFormats", "chainsWith", "outputs", "license", "provenance",
    "version", "popularity",
}


def test_list_skills_covers_every_on_disk_skill():
    skills = client.get("/skills").json()
    assert isinstance(skills, list)
    ids = {s["id"] for s in skills}
    # One namespaced catalog entry per skill dir — nothing dropped, nothing invented.
    assert ids == {f"selom.{sid}" for sid in list_skill_ids()}
    assert "selom.umap_scrna" in ids and "selom.enrichment" in ids


def test_catalog_entry_shape():
    for s in client.get("/skills").json():
        assert _REQUIRED <= set(s), f"{s.get('id')} missing {_REQUIRED - set(s)}"
        assert s["id"].startswith("selom.")
        assert s["source"] == "selom"
        assert s["tier"] in ("verified", "community")
        assert isinstance(s["omics"], list) and s["omics"]
        assert isinstance(s["inputFormats"], list)
        assert all(c.startswith("selom.") for c in s["chainsWith"])


def test_enrichment_is_license_clean():
    # DECISIONS #9: in-house ORA over GO/Reactome — no gseapy/MSigDB, so MIT, not GPL.
    enr = next(s for s in client.get("/skills").json() if s["id"] == "selom.enrichment")
    assert enr["license"] == "MIT"


def test_origin_flag_classifies_proprietary_vs_commodity():
    # Open-core split (DECISIONS #8): every entry carries origin + a derived proprietary
    # boolean; the genuinely-original skills are flagged, the wrappers are not.
    by_id = {s["id"]: s for s in client.get("/skills").json()}
    for s in by_id.values():
        assert s["origin"] in ("proprietary", "commodity")
        assert s["proprietary"] == (s["origin"] == "proprietary")
    # In-house IP — flagged proprietary (+ branded display name).
    for sid in ("enrichment", "go_graph", "pathway", "string_network", "gsea"):
        e = by_id[f"selom.{sid}"]
        assert e["proprietary"] is True, f"{sid} should be proprietary"
        assert e["name"].startswith("Selom "), f"{sid} should carry a branded name"
    # Commodity wrappers — value is the editable output, not the algorithm.
    for sid in ("umap_scrna", "deg", "volcano", "heatmap"):
        assert by_id[f"selom.{sid}"]["proprietary"] is False, f"{sid} is a commodity wrapper"


def test_omics_type_navigation_facet():
    # External-tools study §1.3: every entry carries a non-empty omicsType list (domain
    # navigation), distinct from `omics` (input modalities). Default is transcriptomics;
    # cross-omics viz/stat/pathway skills use the `general` sentinel; proteomics is explicit.
    by_id = {s["id"]: s for s in client.get("/skills").json()}
    for s in by_id.values():
        assert isinstance(s["omicsType"], list) and s["omicsType"], f"{s['id']} omicsType empty"
    # Cross-omics tools — general (surface under every domain filter).
    for sid in ("heatmap", "volcano", "pca", "enrichment", "gsea", "ssgsea"):
        assert by_id[f"selom.{sid}"]["omicsType"] == ["general"], f"{sid} should be general"
    # Domain-specific skills.
    assert by_id["selom.proteomics_de"]["omicsType"] == ["proteomics"]
    # Transcriptomics-first default (the expression workflow), set implicitly.
    for sid in ("umap_scrna", "deg", "cluster", "markers"):
        assert by_id[f"selom.{sid}"]["omicsType"] == ["transcriptomics"], f"{sid} default"

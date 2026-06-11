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

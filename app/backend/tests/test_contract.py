import pytest

from skills.contract import load_skill, run_skill
from skills.references import REFERENCE_TYPES, validate_reference
from skills.registry import list_skill_ids, to_catalog_entry


def test_load_skill_validates():
    spec = load_skill("umap_scrna")
    assert spec.id == "umap_scrna"
    assert spec.engine == "python"
    assert spec.entrypoint == "skills.umap_scrna.run:run"


@pytest.mark.parametrize("skill_id", list_skill_ids())
def test_skill_references_well_formed(skill_id):
    """Every authored references[*] entry has a valid type + non-empty title (+ well-formed
    doi/url/year when present). A malformed entry fails the build here, never the runtime
    (docs/skill-references/spec.md R4)."""
    spec = load_skill(skill_id)
    assert isinstance(spec.references, list), f"{skill_id}: references must be a list"
    assert isinstance(spec.background, str), f"{skill_id}: background must be a string"
    for i, ref in enumerate(spec.references):
        assert validate_reference(ref), (
            f"{skill_id}: references[{i}] is malformed (need type in {sorted(REFERENCE_TYPES)} "
            f"+ non-empty title, well-formed doi/url/year): {ref!r}"
        )


def test_catalog_entry_emits_provenance_when_present():
    """to_catalog_entry surfaces background/references only when authored (additive)."""
    erg = to_catalog_entry(load_skill("erg_traces"))
    assert erg.get("background"), "erg_traces should carry a backfilled background"
    assert erg.get("references"), "erg_traces should carry backfilled references"
    assert all(validate_reference(r) for r in erg["references"])
    # A skill without provenance omits the keys entirely (Store card stays absent).
    bare = to_catalog_entry(load_skill("umap_scrna"))
    assert "references" not in bare or bare["references"] == []


def test_run_skill_returns_figure_spec(monkeypatch):
    # Force the dependency-free stub so this passes identically whether or not the
    # scverse stack is installed; data_path is ignored by the stub.
    monkeypatch.setenv("SELOM_UMAP_ENGINE", "stub")
    figure = run_skill("umap_scrna", "unused", {})
    assert isinstance(figure, dict)
    assert "data" in figure
    assert "layout" in figure

"""Skill registry — serves the Skill-Store catalog from the on-disk skill specs.

`GET /skills` reads every ``skills/<slug>/skill.json`` and maps it to the catalog
entry shape the frontend expects (``app/frontend/lib/catalog/types.ts``). The
backend is the source of truth for what is *Verified* (runnable now); the FE merges
this live set over its static Community long-tail seed, falling back to the seed when
the backend is down. So adding a new skill dir = the Store shows it, no FE edit.
"""

import pathlib

from skills.contract import PROPRIETARY_DIR, SkillSpec, load_skill
from skills.references import clean_references

SKILLS_DIR = pathlib.Path(__file__).parent

# Backend omics tokens -> the display facets the FE filters on (catalog seed copy).
_OMICS_DISPLAY = {
    "scrna-seq": "scRNA-seq",
    "bulk-rna-seq": "bulk RNA-seq",
    "proteomics": "proteomics",
    "genomics": "genomics",
    "metabolomics": "metabolomics",
    "epigenomics": "epigenomics",
    "spatial": "spatial",
    "transcriptomics": "transcriptomics",
}


def _omics_facets(omics: str) -> list[str]:
    return [_OMICS_DISPLAY.get(t, t) for t in omics.split("|") if t]


def list_skill_ids() -> list[str]:
    """Slugs of every skill that ships a ``skill.json``, sorted for stable output.
    Scans the flat ``skills/<id>/`` dirs and the proprietary namespace
    ``skills/proprietary/<id>/`` (deduped; the flat location wins on a clash)."""
    found = SKILLS_DIR.glob("*/skill.json"), PROPRIETARY_DIR.glob("*/skill.json")
    return sorted({p.parent.name for group in found for p in group})


def to_catalog_entry(spec: SkillSpec) -> dict:
    """Map a SkillSpec (+ its optional ``catalog`` block) to a SkillCatalogEntry."""
    cat = spec.catalog or {}
    # Provenance block (docs/skill-references/spec.md) — emitted only when present so the FE
    # "Skill Information" card stays absent for un-backfilled skills (additive, backward-compatible).
    # Malformed entries are dropped here defensively; the contract test is what fails the build on one.
    references = clean_references(spec.references)
    entry = {
        "id": f"selom.{spec.id}",
        # `title` is the ONE display name. A second `catalog.name` used to override it, and every
        # one of the 21 that existed was a lossy re-brand of the title it shadowed ("Box / strip
        # plot" → "Selom Box Plot", "Ridge plot (joyplot)" → "Selom Ridge Plot"). So a retitle
        # never reached the Store or the workbench, and the dropped words were the searchable ones.
        # The `source: "selom"` badge already carries the branding; the name carries the meaning.
        "name": spec.title,
        "summary": cat.get("summary") or spec.title,
        "source": "selom",
        # Open-core split marker (DECISIONS #8) — the FE Store can badge proprietary skills.
        "origin": spec.origin,
        "proprietary": spec.origin == "proprietary",
        "category": cat.get("category", "analysis"),
        "omics": _omics_facets(spec.omics),
        # Omics-domain navigation facet (external-tools study §1.3) — for Store grouping by
        # interest; `general` = cross-omics, surfaces under every domain filter. Distinct from
        # `omics` above (input modalities). Surfaced like `origin`; no FE-type change required.
        "omicsType": spec.omics_type,
        "tier": cat.get("tier", "verified"),
        "status": cat.get("status", "production"),
        "engine": spec.engine,
        "inputFormats": cat.get("input_formats", []),
        # chains_with is authored as bare backend slugs; namespace for the FE ids.
        "chainsWith": [f"selom.{c}" for c in cat.get("chains_with", [])],
        "outputs": [o["name"] for o in spec.outputs],
        "license": cat.get("license", "MIT"),
        "provenance": {"repo": "selom/skills", "path": spec.id},
        "version": spec.version,
        "popularity": cat.get("popularity", 50),
    }
    if spec.background:
        entry["background"] = spec.background
    if references:
        entry["references"] = references
    return entry


def list_catalog() -> list[dict]:
    """The full live Verified catalog, one entry per on-disk skill."""
    return [to_catalog_entry(load_skill(sid)) for sid in list_skill_ids()]

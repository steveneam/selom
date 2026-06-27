"""Central per-skill capability stamp (generalization-spec §C).

``_capabilities.stamp`` injects ``layout.meta.selom.capabilities`` for profiled skills, is a no-op
otherwise, and never clobbers a richer existing stamp (an ERG trace grid). ``theme.apply`` calls it
once on every figure.
"""

from skills import _capabilities, theme
from skills._capabilities import _PROFILES
from skills.registry import list_skill_ids

# The capability tools the FE editor actually resolves (lib/figure-model.ts → SelomCapabilities.tools).
# A tool declared in a _PROFILES profile that isn't here would be silently dropped by the FE — drift.
# Keep in sync with figure-model.ts when a new tool gate is added.
_KNOWN_TOOLS = {
    "landmarkMarks",
    "modelFit",
    "scaleBar",
    "thresholds",
    "geneLabels",
    "heatmapTones",
    "heatmapLabels",
}


def _spec() -> dict:
    return {"data": [{"type": "scattergl", "x": [1.0], "y": [2.0]}], "layout": {"title": {"text": "t"}}}


def test_stamp_adds_the_volcano_block():
    spec = _capabilities.stamp(_spec(), "volcano")
    caps = spec["layout"]["meta"]["selom"]["capabilities"]
    assert caps["tools"]["thresholds"] is True
    assert caps["tools"]["geneLabels"] is True
    assert caps["gesture"] == {"default": "none", "zoomTools": True, "scrollZoom": False}


def test_stamp_adds_the_heatmap_block():
    spec = _capabilities.stamp(_spec(), "heatmap")
    caps = spec["layout"]["meta"]["selom"]["capabilities"]
    assert caps["tools"]["heatmapTones"] is True
    assert caps["gesture"] == {"default": "none", "zoomTools": True, "scrollZoom": False}


def test_stamp_is_a_noop_for_an_unprofiled_skill():
    out = _capabilities.stamp(_spec(), "umap_scrna")
    assert "meta" not in out["layout"]


def test_stamp_never_clobbers_an_existing_block():
    spec = _spec()
    # A richer, figure-instance-aware stamp (the ERG trace grid shape).
    spec["layout"]["meta"] = {
        "selom": {"capabilities": {"gesture": {"default": "none"}, "tools": {"landmarkMarks": True}}}
    }
    _capabilities.stamp(spec, "volcano")
    caps = spec["layout"]["meta"]["selom"]["capabilities"]
    # Both keys pre-existed → neither is overwritten by the volcano profile.
    assert caps["tools"] == {"landmarkMarks": True}
    assert caps["gesture"] == {"default": "none"}


def test_stamp_tolerates_a_malformed_spec():
    assert _capabilities.stamp({"data": []}, "volcano") == {"data": []}  # no layout → no-op, no throw
    assert _capabilities.stamp("nope", "volcano") == "nope"


def test_apply_stamps_volcano_but_not_a_plain_skill():
    # A plain skill (kind "base") is never stamped at the central injection point.
    plain = theme.apply(_spec(), "deg")
    assert "selom" not in plain["layout"].get("meta", {})


# --- Registry-completeness gate (architecture-consistency Task B5) ------------------------
# Every capability profile must decorate a real skill, and every tool it declares must be one
# the FE knows how to resolve. Promotes drift (a typo'd / renamed skill id or tool) from a silent
# no-op to a failing test. The params half (params.ts overlay + dev:mock fixture ↔ skill.json) is
# FE-native and lives in app/frontend/lib/catalog/registry-completeness.test.ts.


def test_every_capability_profile_backs_a_real_skill():
    skills = set(list_skill_ids())
    orphans = [sid for sid in _PROFILES if sid not in skills]
    assert not orphans, f"_capabilities profiles with no backing skill.json: {orphans}"


def test_capability_tools_are_known_to_the_frontend():
    for skill_id, profile in _PROFILES.items():
        unknown = set(profile.get("tools", {})) - _KNOWN_TOOLS
        assert not unknown, f"{skill_id} declares capability tool(s) {unknown} the FE can't resolve (sync lib/figure-model.ts)"

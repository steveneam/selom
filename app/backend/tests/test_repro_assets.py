"""Staged panel-asset loader + the digitize ≠ reproduce invariant (★D bridge).

The bridge attaches X3 panel thumbnails to the read-only Reproduction ledger. The load-bearing
guarantee is that this is **purely presentational**: attaching a thumbnail (or a whole manifest of
them) must never move the Reproducibility Score. These tests enforce that mechanically.
"""

import json

import pytest

import repro_assets
import reproduction as R
import reproduction_hani as HN


def _write_manifest(root, slug, panels):
    d = root / slug
    d.mkdir(parents=True)
    (d / "panels.json").write_text(json.dumps({"panels": panels}), encoding="utf-8")


# --- loader ------------------------------------------------------------------


def test_missing_manifest_is_empty(tmp_path):
    assert repro_assets.load_lifts("hani", root=tmp_path) == {}


def test_malformed_manifest_degrades_to_empty(tmp_path):
    d = tmp_path / "hani"
    d.mkdir(parents=True)
    (d / "panels.json").write_text("{not json", encoding="utf-8")
    assert repro_assets.load_lifts("hani", root=tmp_path) == {}


def test_load_lifts_parses_rows_and_skips_bad_ones(tmp_path):
    _write_manifest(tmp_path, "hani", {
        "2B": {"page_index": 3, "bbox": [0, 0, 100, 80], "kind": "vector",
               "thumbnail_url": "/repro-assets/hani/2B.png", "digitizable": True},
        "BAD": {"bbox": "not-a-tuple"},  # invalid -> skipped, not fatal
    })
    lifts = repro_assets.load_lifts("hani", root=tmp_path)
    assert set(lifts) == {"2B"}
    assert lifts["2B"].kind == "vector" and lifts["2B"].digitizable is True


# --- attach ------------------------------------------------------------------


def test_attach_sets_lift_only_on_matching_panels(tmp_path):
    _write_manifest(tmp_path, "hani", {
        "2C": {"thumbnail_url": "/repro-assets/hani/2C.png", "digitizable": False, "kind": "vector"},
    })
    ledger = repro_assets.attach_lifts(HN.drive_captured(), root=tmp_path)
    assert ledger.panel("2C").lift is not None
    assert ledger.panel("2C").lift.thumbnail_url.endswith("2C.png")
    # an unstaged panel keeps lift=None
    assert ledger.panel("3C").lift is None


def test_digitizable_is_gated_to_chart_forms(tmp_path):
    # Fig 3C is a dotplot and Fig 2C a boxplot (no point series to trace): even if the manifest claims
    # digitizable, attach forces it off against the ledger's chart_form. Fig 4C is a scatter -> stays.
    _write_manifest(tmp_path, "hani", {
        "3C": {"thumbnail_url": "/r/3C.png", "digitizable": True},
        "2C": {"thumbnail_url": "/r/2C.png", "digitizable": True},
        "4C": {"thumbnail_url": "/r/4C.png", "digitizable": True},
    })
    ledger = repro_assets.attach_lifts(HN.drive_captured(), root=tmp_path)
    assert ledger.panel("3C").lift.digitizable is False   # dotplot: not traceable
    assert ledger.panel("2C").lift.digitizable is False   # boxplot: not traceable
    assert ledger.panel("4C").lift.digitizable is True    # scatter: traceable


# --- the invariant: digitize ≠ reproduce -------------------------------------


def _score_only(sc) -> dict:
    # Everything the scorecard asserts, minus the wall-clock generated_at stamp.
    d = sc.model_dump()
    d.pop("generated_at", None)
    return d


def test_attaching_thumbnails_never_moves_the_score(tmp_path):
    # Drive once with NO assets, snapshot the scorecard; drive again with a full manifest of
    # thumbnails (incl. ones claiming to be digitizable) and assert the score is identical.
    bare = _score_only(R.build_scorecard(HN.drive_captured()))

    _write_manifest(tmp_path, "hani", {
        p.key: {"thumbnail_url": f"/repro-assets/hani/{p.key}.png", "digitizable": True,
                "page_index": 1, "bbox": [0, 0, 10, 10], "kind": "raster"}
        for p in HN.build_ledger().panels
    })
    staged_ledger = repro_assets.attach_lifts(HN.drive_captured(), root=tmp_path)
    staged = _score_only(staged_ledger.scorecard)

    assert staged == bare, "a staged thumbnail must not change the Reproducibility Score"
    # And the lift rode along on the served panels (presentation only).
    assert any(p.lift is not None for p in staged_ledger.panels)


def test_panel_lift_carries_no_golden_or_computed():
    # Structural guard: PanelLift has no field that could feed validate_panel / the score.
    fields = set(R.PanelLift.model_fields)
    assert not (fields & {"golden", "value", "computed", "metric", "weight"})


@pytest.mark.skipif(
    not (repro_assets.ASSETS_ROOT / "hani" / "panels.json").exists(),
    reason="no staged Hani assets committed yet",
)
def test_committed_hani_assets_load():
    lifts = repro_assets.load_lifts("hani")
    assert lifts  # at least one staged panel
    for key, lift in lifts.items():
        assert lift.thumbnail_url.startswith("/repro-assets/hani/")

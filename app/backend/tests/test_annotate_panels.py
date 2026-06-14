"""annotate marker panels — retinal (canonical, now with a Microglia class) +
retinal_cepo (Cepo markers from Kim et al., Stem Cell Reports 18, 2023).

Validates the committed ``panels.json`` data + the scanpy-free ``_load_panel`` loader.
"""

import json
import pathlib

import pytest

from skills.annotate.run_real import _load_panel

PANELS = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / "skills/annotate/panels.json").read_text(
        encoding="utf-8"
    )
)


def test_panels_well_formed():
    assert set(PANELS) >= {"retinal", "retinal_cepo", "pbmc"}
    for key, panel in PANELS.items():
        assert panel.get("markers"), key
        assert panel.get("attribution"), key
        for ct, genes in panel["markers"].items():
            assert isinstance(genes, list) and len(genes) >= 2, (key, ct)
            assert all(isinstance(g, str) and g for g in genes), (key, ct)


def test_retinal_gained_microglia():
    micro = PANELS["retinal"]["markers"].get("Microglia")
    assert micro and "AIF1" in micro and "CX3CR1" in micro


def test_retinal_cepo_classes():
    cepo = PANELS["retinal_cepo"]["markers"]
    assert len(cepo) == 9
    assert "Microglia" in cepo
    assert all(len(v) == 50 for v in cepo.values())
    assert "Kim et al." in PANELS["retinal_cepo"]["attribution"]


def test_pbmc_panel_has_core_immune_types():
    pbmc = PANELS["pbmc"]["markers"]
    assert {"CD4+ T cells", "CD8+ T cells", "NK cells", "B cells", "CD14+ monocytes"} <= set(pbmc)
    assert "MS4A1" in pbmc["B cells"] and "CD14" in pbmc["CD14+ monocytes"]
    assert "10x" in PANELS["pbmc"]["attribution"] or "Seurat" in PANELS["pbmc"]["attribution"]


def test_load_panel_roundtrip_and_unknown():
    assert _load_panel("retinal_cepo")["markers"]
    with pytest.raises(ValueError):
        _load_panel("does-not-exist")

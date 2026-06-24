"""Ingest gene-symbol cleaning — genome-prefix strip + Ensembl-ID relabel (skills/_genes.py).

Surfaced dogfooding Hani GSE201356: 10x symbols prefixed ``GRCh38_RHO`` matched
zero marker-panel genes. The strip is conservative — only a *dominant* shared
prefix is removed, so a real gene that merely starts with such a token is safe.
The Ensembl-ID relabel is the sibling case (var_names keyed by ``ENSG…``); it is
tested against a tiny injected map so it does not depend on the large corpus.
"""

import skills._genes as genes_mod
from skills._genes import display_symbol, display_symbols, map_ensembl_to_symbol, strip_genome_prefix

_TINY_MAP = {
    "ENSG00000163914": "RHO",
    "ENSG00000075624": "ACTB",
    "ENSG00000111640": "GAPDH",
}


def test_strips_uniform_genome_prefix():
    assert strip_genome_prefix(["GRCh38_RHO", "GRCh38_RPE65", "GRCh38_PDE6B"]) == [
        "RHO", "RPE65", "PDE6B",
    ]


def test_leaves_clean_symbols_untouched():
    names = ["RHO", "RPE65", "PDE6B"]
    assert strip_genome_prefix(names) == names


def test_does_not_strip_when_prefix_not_dominant():
    # 1/4 carry the token -> below threshold -> a real gene starting with it is safe
    names = ["GRCh38_RHO", "ACTB", "GAPDH", "MALAT1"]
    assert strip_genome_prefix(names) == names


def test_threshold_is_eighty_percent():
    three_of_four = ["mm10_Rho", "mm10_Pde6b", "mm10_Gnat1", "Actb"]  # 0.75 -> unchanged
    assert strip_genome_prefix(three_of_four) == three_of_four
    all_four = ["mm10_Rho", "mm10_Pde6b", "mm10_Gnat1", "mm10_Actb"]  # 1.0 -> stripped
    assert strip_genome_prefix(all_four) == ["Rho", "Pde6b", "Gnat1", "Actb"]


def test_empty_input():
    assert strip_genome_prefix([]) == []


# --- Ensembl-ID -> symbol relabel ---------------------------------------------


def test_maps_ensembl_ids_to_symbols(monkeypatch):
    monkeypatch.setattr(genes_mod, "_ensembl_symbols", lambda: _TINY_MAP)
    assert map_ensembl_to_symbol(
        ["ENSG00000163914", "ENSG00000075624", "ENSG00000111640"]
    ) == ["RHO", "ACTB", "GAPDH"]


def test_strips_ensembl_version_suffix(monkeypatch):
    monkeypatch.setattr(genes_mod, "_ensembl_symbols", lambda: _TINY_MAP)
    assert map_ensembl_to_symbol(
        ["ENSG00000163914.4", "ENSG00000075624.12", "ENSG00000111640.1"]
    ) == ["RHO", "ACTB", "GAPDH"]


def test_unmapped_ensembl_id_is_kept(monkeypatch):
    monkeypatch.setattr(genes_mod, "_ensembl_symbols", lambda: _TINY_MAP)
    out = map_ensembl_to_symbol(["ENSG00000163914", "ENSG99999999999", "ENSG00000111640"])
    assert out == ["RHO", "ENSG99999999999", "GAPDH"]  # unknown ID stays, never dropped


def test_non_ensembl_symbols_untouched(monkeypatch):
    monkeypatch.setattr(genes_mod, "_ensembl_symbols", lambda: _TINY_MAP)
    names = ["RHO", "ACTB", "GAPDH"]
    assert map_ensembl_to_symbol(names) == names


def test_below_coverage_left_alone(monkeypatch):
    # 1/4 look like Ensembl -> below the 80% threshold -> untouched
    monkeypatch.setattr(genes_mod, "_ensembl_symbols", lambda: _TINY_MAP)
    names = ["ENSG00000163914", "ACTB", "GAPDH", "MALAT1"]
    assert map_ensembl_to_symbol(names) == names


def test_no_map_is_noop(monkeypatch):
    # corpus absent (fresh clone / CI) -> graceful no-op even for Ensembl-keyed input
    monkeypatch.setattr(genes_mod, "_ensembl_symbols", lambda: None)
    names = ["ENSG00000163914", "ENSG00000075624"]
    assert map_ensembl_to_symbol(names) == names


def test_empty_ensembl_input():
    assert map_ensembl_to_symbol([]) == []


# --- "<ID>~<SYMBOL>" display labels (figure axis readability) ------------------


def test_display_symbol_extracts_the_symbol_half():
    assert display_symbol("ENSG00000128578~STRIP2") == "STRIP2"
    assert display_symbol("ENSG00000111640~GAPDH") == "GAPDH"


def test_display_symbol_empty_symbol_falls_back_to_the_id():
    assert display_symbol("ENSG00000238009~") == "ENSG00000238009"


def test_display_symbol_passes_through_plain_names():
    assert display_symbol("GAPDH") == "GAPDH"  # plain symbol
    assert display_symbol("ENSG00000111640") == "ENSG00000111640"  # plain ID, no ~
    assert display_symbol("mt-Nd1") == "mt-Nd1"  # a real hyphenated symbol is untouched


def test_display_symbols_maps_a_list():
    assert display_symbols(["ENSG00000128578~STRIP2", "GAPDH", "ENSG00000238009~"]) == [
        "STRIP2", "GAPDH", "ENSG00000238009",
    ]

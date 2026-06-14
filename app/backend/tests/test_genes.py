"""Ingest gene-symbol cleaning — genome-prefix strip (skills/_genes.py).

Surfaced dogfooding Hani GSE201356: 10x symbols prefixed ``GRCh38_RHO`` matched
zero marker-panel genes. The strip is conservative — only a *dominant* shared
prefix is removed, so a real gene that merely starts with such a token is safe.
"""

from skills._genes import strip_genome_prefix


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

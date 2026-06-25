"""Shared design / sample-sheet loader.

A study's sample sheet maps each sample id → its experimental factors (condition, genotype,
batch, timepoint, …). Several skills consume it: ``deg`` reads a ``group_col`` for the contrast,
``heatmap`` paints categorical annotation tracks from chosen columns. This is the ONE reader so
the id-column heuristic + the optional Excel path stay identical everywhere (the file arrives as
the reserved ``_design_path`` param — see ``main.py``; kept out of provenance).
"""

from __future__ import annotations

_ID_ALIASES = ("sampleid", "sample", "sample_id", "id")


def load_design(params: dict):
    """Read the optional design sheet and return it indexed by sample id, or None when not supplied.

    The id column is the first of ``SampleID``/``sample``/``sample_id``/``id`` (case-insensitive),
    else the first column. ``.xlsx``/``.xls`` are read with the Excel engine; anything else as CSV.
    """
    import pandas as pd

    design_path = params.get("_design_path")
    if not design_path:
        return None
    if str(design_path).lower().endswith((".xlsx", ".xls")):
        design = pd.read_excel(design_path)
    else:
        design = pd.read_csv(design_path)  # comma-delimited even when named .tsv here
    id_col = next(
        (c for c in design.columns if str(c).strip().lower() in _ID_ALIASES),
        design.columns[0],
    )
    return design.set_index(design[id_col].astype(str))

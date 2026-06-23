"""Engine spine — RAW-data routing (P3, the guided half of Product A).

:func:`route_data` takes a classified :class:`~engine.databundle.DataBundle` and suggests the
skills / a minimal pipeline that fit its modality, **validated against the live skill registry**.
It is the data-side complement of ``extract.routing`` (which routes a *paper's* text). Honest:
an unrecognized modality returns no forced pipeline + a "here are options" note (E2/E3). See
``docs/engine-spine/spec.md`` and ``docs/pillars/plan.md`` (P3).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from engine.models import (
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    METABOLOMICS,
    PROTEOMICS,
    SC_COUNTS,
    UNKNOWN,
)


class SuggestedStep(BaseModel):
    skill_id: str
    role: str = ""        # qc | analyze | enrich | visualize
    reason: str = ""


class DataRouting(BaseModel):
    kind: str
    steps: list[SuggestedStep] = Field(default_factory=list)
    confident: bool = False   # a well-defined modality with an installed pipeline
    note: str = ""


# Curated minimal "happy path" per modality (skill_id, role, reason). Each id is validated
# against the live registry at route time, so a not-installed skill degrades honestly.
_PIPELINES: dict[str, list[tuple[str, str, str]]] = {
    SC_COUNTS: [
        ("normalization_qc", "qc", "QC + normalize before clustering"),
        ("umap_scrna", "analyze", "cluster the cells + embed (UMAP)"),
        ("markers", "analyze", "find each cluster's marker genes"),
        ("composition", "visualize", "cell-type composition across conditions"),
    ],
    BULK_COUNTS: [
        ("deg", "analyze", "differential expression between groups (attach a design / >=2 groups)"),
        ("volcano", "visualize", "volcano of the DE result"),
        ("enrichment", "enrich", "pathway over-representation of the hits"),
    ],
    DE_RESULTS: [
        ("volcano", "visualize", "volcano from the supplied logFC + p-values"),
        ("enrichment", "enrich", "over-representation of the significant genes"),
        ("gsea", "enrich", "rank-based GSEA over the full gene list"),
    ],
    PROTEOMICS: [
        ("proteomics_de", "analyze", "MNAR-aware differential abundance"),
        ("volcano", "visualize", "volcano of the protein-level result"),
        ("enrichment", "enrich", "pathway over-representation of the hits"),
    ],
    METABOLOMICS: [],
    GENERIC_TABLE: [
        ("pca", "analyze", "explore sample structure"),
        ("corr_heatmap", "visualize", "correlation structure across columns"),
    ],
    UNKNOWN: [],
}

_NOTES: dict[str, tuple[str, bool]] = {
    SC_COUNTS: ("Single-cell matrix detected — the standard scRNA path.", True),
    BULK_COUNTS: ("Bulk count matrix — attach a design (sample -> condition) to run DE.", True),
    DE_RESULTS: ("Pre-computed DE results — no re-analysis needed; visualize + enrich.", True),
    PROTEOMICS: ("Proteomics intensities — use the MNAR-aware differential-abundance path.", True),
    METABOLOMICS: ("Metabolomics detected — dedicated analysis is coming soon.", False),
    GENERIC_TABLE: ("Modality unclear — exploratory options below, or pick a skill manually.", False),
    UNKNOWN: ("Couldn't classify this table — inspect it or choose a skill manually.", False),
}
_DEFAULT_NOTE = "No routing available for this input."


# Profile pipelines — for data-type *profiles* that ride atop a Kind (engine.cleaning), e.g. an
# ERG table is a `generic_table` modality but, once recognized, routes to the electrophysiology
# figure skills rather than the generic pca/corr_heatmap options.
_PROFILE_PIPELINES: dict[str, list[tuple[str, str, str]]] = {
    "erg": [
        ("erg_traces", "visualize", "ERG waveform small-multiples grid"),
        ("erg_bwave_bar", "analyze", "peak b-wave per condition (mean ± SEM, every eye plotted)"),
        ("erg_intensity_response", "analyze", "b-wave vs flash intensity + Naka-Rushton fit"),
    ],
}
_PROFILE_NOTES: dict[str, str] = {
    "erg": "ERG / electrophysiology data — the electrophysiology figure skills.",
}


def route_data(bundle: Any) -> DataRouting:
    """Suggest a skill pipeline for a classified ``DataBundle``. Skills are filtered to the
    live registry, so the suggestion reflects what is actually runnable; an empty pipeline is
    honest, never a fabricated step."""
    from skills.registry import list_skill_ids

    kind = bundle.kind
    installed = set(list_skill_ids())
    steps = [
        SuggestedStep(skill_id=sid, role=role, reason=reason)
        for sid, role, reason in _PIPELINES.get(kind, [])
        if sid in installed
    ]
    note, confident = _NOTES.get(kind, (_DEFAULT_NOTE, False))
    if _PIPELINES.get(kind) and not steps:  # suggested, but none installed
        note = "Suggested analyses for this modality are not installed yet."
        confident = False
    return DataRouting(kind=kind, steps=steps, confident=confident and bool(steps), note=note)


def route_profile(bundle: Any, profile_code: str | None = None) -> DataRouting:
    """Routing that honours a recognized data-type *profile* (engine.cleaning). For a profile with
    its own pipeline (e.g. ``erg``) suggest those skills; otherwise fall back to modality routing.
    Same registry-validation + honest-empty contract as :func:`route_data`."""
    if profile_code and profile_code in _PROFILE_PIPELINES:
        from skills.registry import list_skill_ids

        installed = set(list_skill_ids())
        steps = [
            SuggestedStep(skill_id=sid, role=role, reason=reason)
            for sid, role, reason in _PROFILE_PIPELINES[profile_code]
            if sid in installed
        ]
        note = _PROFILE_NOTES.get(profile_code, _DEFAULT_NOTE)
        if not steps:
            note = "The skills for this data type are not installed yet."
        return DataRouting(kind=getattr(bundle, "kind", ""), steps=steps,
                           confident=bool(steps), note=note)
    return route_data(bundle)

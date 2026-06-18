"""The deterministic methods synthesizer — Phase A core. No network, no new deps.

Stitches an ordered sequence of skill runs into one Methods section: a modality-aware
intro, per-skill prose in run order (reusing ``methods.build_body`` so the citations stay
single-sourced), a deduped citation list, and ONE Selom attribution sentence at the end.
Mirrors ``reproduction.run_panel``'s discipline — this half is pure and never depends on
the (later) network citation-lookup layer.
"""

from __future__ import annotations

from collections.abc import Iterable

import methods
from litsynth.models import MethodsSection, SkillRunRef
from skills.contract import load_skill

# Modality -> the lead sentence that frames the whole analysis story. Unknown / empty
# modality degrades to a neutral lead; the per-skill paragraphs carry the real detail.
_MODALITY_INTRO = {
    "scrna": "Single-cell RNA-seq data were analyzed as follows.",
    "bulk": "Bulk RNA-seq data were analyzed as follows.",
    "proteomics": "Mass-spectrometry proteomics data were analyzed as follows.",
    "metabolomics": "Metabolomics data were analyzed as follows.",
    "spatial": "Spatial transcriptomics data were analyzed as follows.",
}
_GENERIC_INTRO = "The data were analyzed as follows."


def _intro(modality: str, dataset: str | None) -> str:
    lead = _MODALITY_INTRO.get((modality or "").strip().lower(), _GENERIC_INTRO)
    descriptor = (dataset or "").strip().rstrip(".")
    return f"{descriptor}. {lead}" if descriptor else lead


def _ordered(runs: Iterable) -> list[SkillRunRef]:
    """Coerce to SkillRunRef and order by explicit ``order`` then input position (stable)."""
    refs = [r if isinstance(r, SkillRunRef) else SkillRunRef(**r) for r in runs]
    keyed = sorted(
        enumerate(refs),
        key=lambda ir: (ir[1].order if ir[1].order is not None else ir[0], ir[0]),
    )
    return [ref for _, ref in keyed]


def _load(skill_id: str):
    try:
        return load_skill(skill_id)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError(f"unknown skill '{skill_id}'") from exc


def compose_methods(runs: Iterable, modality: str = "", dataset: str | None = None) -> MethodsSection:
    """Compose one Methods section from an ordered sequence of skill runs.

    Deterministic and offline. ``runs`` items may be ``SkillRunRef`` or plain dicts.
    Raises ``ValueError`` on an empty sequence or an unknown skill id.
    """
    ordered = _ordered(runs)
    if not ordered:
        raise ValueError("at least one skill run is required")

    intro = _intro(modality, dataset)
    paragraphs: list[str] = []
    citations: list[str] = []
    seen: set[str] = set()
    skill_ids: list[str] = []
    attrib_parts: list[str] = []

    for ref in ordered:
        spec = _load(ref.skill_id)
        text, cites = methods.build_body(spec, ref.params)
        paragraphs.append(text)
        skill_ids.append(spec.id)
        attrib_parts.append(f"{spec.id} v{spec.version}")
        for citation in cites:
            if citation not in seen:
                seen.add(citation)
                citations.append(citation)

    attribution = f"All analyses were performed using Selom (skills: {', '.join(attrib_parts)})."
    full_text = " ".join([intro, *paragraphs, attribution])
    return MethodsSection(
        intro=intro,
        paragraphs=paragraphs,
        text=full_text,
        citations=citations,
        modality=(modality or "").strip().lower(),
        skill_ids=skill_ids,
    )

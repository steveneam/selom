"""Classify stage — scope (guard 7) + chart form.

Scope classification is a **pure keyword rule** (high precision, no model): IHC / RT-qPCR /
staining-dye / microscopy → ``wet_lab`` (out-of-scope, excluded from the denominator), else
``transcriptomic``. Chart-form classification is **pluggable** behind :class:`Classifier`:
slice-1 ships a caption-keyword ``CaptionRuleClassifier``; the vision LLM is **gated** —
``VisionClassifier`` raises :class:`VisionUnavailable` until the shared AI gateway is wired,
exactly the degrade-cleanly posture as the R-oracle (ADR 0002, sub-spec open-Q#2).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import reproduction as R

# guard 7 — readouts that are NOT derivable from the sequencing data (out-of-scope).
_WET_LAB_MARKERS = (
    "immunostain", "immunohistochem", "immunofluoresc", "immunolab", " ihc", "(ihc)",
    "rt-qpcr", "rt qpcr", "qpcr", "qrt-pcr", "western blot", "immunoblot", "h&e",
    "haematoxylin", "hematoxylin", "proteostat", "aggresome", "tunel", "histolog",
    "in situ hybrid", "confocal", "microscopy", "staining", "stained",
)
# transcriptomic signals that override an incidental "microscopy/staining" mention.
_TRANSCRIPTOMIC_MARKERS = (
    "volcano", "heatmap", "differentially expressed", "umap", "t-sne", "pca",
    "principal component", "gene ontology", "enrichment", "deconvolution", "violin",
    "venn", "dot plot", "dotplot", "pseudotime", "trajectory", "log2", "logfc", "z-score",
)

# chart-form keyword lexicon (caption-rule classifier; vision refines later).
_CHART_KEYWORDS = (
    ("volcano", ("volcano",)),
    ("heatmap", ("heatmap", "heat map")),
    ("pca", ("pca", "principal component")),
    ("umap", ("umap", "t-sne", "tsne")),
    ("venn", ("venn",)),
    ("dotplot", ("dot plot", "dotplot", "bubble")),
    ("violin", ("violin",)),
    ("stacked_bar", ("stacked bar", "stacked-bar", "composition")),
    ("bar", ("bar chart", "bar plot", "bar graph", "barplot")),
    ("box", ("box plot", "boxplot", "box-and-whisker")),
    ("trajectory", ("trajectory", "pseudotime", "lineage")),
    ("stacked_area", ("stacked area", "area chart")),
    ("line", ("line plot", "line graph", "time course", "cdf")),
)


def classify_scope(text: str) -> str:
    """Scope of a panel from its caption/methods text (guard 7). Wet-lab markers win unless
    a transcriptomic signal is also present (a panel can mention 'confocal' yet plot DE)."""
    low = text.lower()
    wet = any(m in low for m in _WET_LAB_MARKERS)
    transcriptomic = any(m in low for m in _TRANSCRIPTOMIC_MARKERS)
    if wet and not transcriptomic:
        return R.WET_LAB
    return R.TRANSCRIPTOMIC


class VisionUnavailable(RuntimeError):
    """Raised when a vision-LLM classification is requested but no gateway is wired (dev-only,
    gated like the R-oracle). The pipeline degrades to the rule classifier, never crashes."""


@runtime_checkable
class Classifier(Protocol):
    """Assign a chart form to a panel from its caption (and, later, its raster)."""

    def classify_chart(self, caption: str, *, image: bytes | None = None) -> tuple[str, float]:
        """Return ``(chart_form, confidence)``; ``("", 0.0)`` when undecidable."""
        ...


class CaptionRuleClassifier:
    """Keyword chart-form classifier over the caption text (no model). The slice-1 default —
    high precision on the common scientific chart vocabulary, honest 0.0 when nothing matches."""

    def classify_chart(self, caption: str, *, image: bytes | None = None) -> tuple[str, float]:
        low = caption.lower()
        for form, keys in _CHART_KEYWORDS:
            if any(k in low for k in keys):
                return form, 0.8
        return "", 0.0


class VisionClassifier:
    """The gated vision-LLM classifier (dev/validation profile, sub-spec open-Q#2). Until the
    shared AI gateway is wired it raises :class:`VisionUnavailable`; callers fall back to the
    rule classifier so the pipeline always completes (the R-oracle degrade-cleanly pattern)."""

    def __init__(self, gateway=None):
        self._gateway = gateway

    def classify_chart(self, caption: str, *, image: bytes | None = None) -> tuple[str, float]:
        if self._gateway is None:
            raise VisionUnavailable(
                "vision chart-classification needs the shared AI gateway (not wired in this "
                "profile); use CaptionRuleClassifier or wire the gateway (X1 slice-2)"
            )
        return self._gateway.classify_chart(caption, image=image)  # pragma: no cover - gated

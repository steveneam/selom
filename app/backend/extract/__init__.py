"""Figure Extraction Subsystem (Reproduction Engine R4) — PDF → structured target spec.

Sub-spec: ``docs/reproduction-engine/figure-extraction-subsystem.md``. This package turns
**just a paper's PDF** into the artifacts the rest of the engine consumes — the structured
form of the hand-written ``<slug>_target_spec.md`` that ``reproduction_{rpgrip1,jev}.
build_ledger()`` encode by hand today (X1 auto-generates them).

Slice-1 = the **text-derivable** target-extraction core; slice-2 adds the **vision layer** and
**E7 two-input intake**:

* ``ingest``  — thin typed wrapper over ``papers.py`` (PDFium text + rasters; BSD, E1) + the E7
  ``ingest_paper(main, supplements=[...])`` two-input bundle (main PDF + N PDF/xlsx/csv supplements).
* ``golden``  — **text-layer-exact** golden extraction (E2), the methods-digest lexicon,
  inconsistency capture, and the bridge into the engine's ``Panel``/``Golden``.
* ``classify`` — rule-based scope classification (guard 7) + a pluggable ``Classifier``; the
  vision LLM is gated behind ``VisionClassifier``.
* ``vision`` (slice-2) — the live vision layer with **Claude acting as the gateway** for the
  dev/dogfood profile (``OperatorVisionGateway`` replays operator reads; CI-safe). Recovers chart
  forms and counts stated only graphically that the text reader misses; manual-assist segmentation.
* ``reconstruct`` (X2, Track B) — redraw a panel as an editable Plotly spec + **SSIM self-QA**
  against the original raster (pure-numpy SSIM; Kaleido render gated). Imported on demand
  (``from extract.reconstruct import …``) since it pulls ``skills.theme`` + (lazily) plotly.

One-directional dependency: ``extract`` may import ``reproduction``; never the reverse.
"""

from .classify import (
    CaptionRuleClassifier,
    Classifier,
    VisionClassifier,
    VisionUnavailable,
    classify_scope,
)
from .golden import (
    build_extracted_spec,
    extract_de_counts,
    extract_methods_digest,
    find_figures_vs_methods,
    to_engine_panels,
    to_golden,
)
from .ingest import (
    IngestedPaper,
    IngestedSupplement,
    PaperBundle,
    ingest_paper,
    ingest_pdf,
    ingest_supplement,
    page_raster,
)
from .models import ExtractedSpec, GoldenTarget, MethodsDigest, PanelDraft
from .vision import (
    OperatorVisionGateway,
    PanelBox,
    VisionGateway,
    VisionObservation,
    associate_counts,
    augment_with_vision,
    segment_panels,
    venn3_totals,
)

__all__ = [
    "CaptionRuleClassifier",
    "Classifier",
    "VisionClassifier",
    "VisionUnavailable",
    "classify_scope",
    "build_extracted_spec",
    "extract_de_counts",
    "extract_methods_digest",
    "find_figures_vs_methods",
    "to_engine_panels",
    "to_golden",
    "IngestedPaper",
    "IngestedSupplement",
    "PaperBundle",
    "ingest_paper",
    "ingest_pdf",
    "ingest_supplement",
    "page_raster",
    "ExtractedSpec",
    "GoldenTarget",
    "MethodsDigest",
    "PanelDraft",
    "OperatorVisionGateway",
    "PanelBox",
    "VisionGateway",
    "VisionObservation",
    "associate_counts",
    "augment_with_vision",
    "segment_panels",
    "venn3_totals",
]

"""lit-synthesizer — multi-skill methods + citation synthesis.

Phase A (this package, shipped): promote the per-figure auto-methods engine
(``methods.py``) to the project/story level — stitch an *ordered sequence* of skill runs
into one publication Methods section with a deduped citation list. Deterministic,
offline, no LLM, no new deps. Phases B/C add the stdlib PubMed/bioRxiv citation-lookup
layer (network injected as a fetcher, mockable). See ``docs/lit-synthesizer-scope.md``.
"""

from litsynth.models import MethodsSection, SkillRunRef
from litsynth.synth import compose_methods

__all__ = ["MethodsSection", "SkillRunRef", "compose_methods"]

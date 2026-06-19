"""The deterministic matcher (spec §Design).

Compiles the vocabulary into one alternation regex (longest term first, so "diffusion
pseudotime" wins over "pseudotime"; "ssGSEA" over "GSEA"). Matching is case-insensitive with
word-ish boundaries — a term may contain spaces/hyphens but must not be glued to surrounding
word characters (so "PCA" doesn't fire inside "PVCA", mirroring ``golden._has_token``). A short
left-window negation check drops "did not use Monocle"-style hits. No model.
"""

from __future__ import annotations

import re

from .models import VocabEntry

# negation cues in the ~40 chars before a term → drop the hit (conservative; ambiguous cases
# are better handled by the AI-verify seam than silently routed).
_NEG = re.compile(r"(?:\bnot\b|n't|\bwithout\b|\brather than\b|\binstead of\b|\bneither\b|\bno\b)",
                  re.I)


def _norm(term: str) -> str:
    return re.sub(r"\s+", " ", term).strip().lower()


def flatten(text: str) -> str:
    """Collapse all whitespace to single spaces so multi-word terms match across line breaks."""
    return re.sub(r"\s+", " ", text).strip()


class KeywordIndex:
    """An inverted keyword index: term → routing targets, plus the compiled multi-term matcher."""

    def __init__(self, entries: list[VocabEntry]):
        self.entries = entries
        self._targets: dict[str, list[tuple[str, float]]] = {}
        for e in entries:
            for t in e.terms:
                self._targets.setdefault(_norm(t), []).append((e.target, e.weight))
        terms = sorted(self._targets, key=len, reverse=True)
        # (?<![\w-]) / (?![\w-]): boundary that also forbids a hyphen, so "ATAC-seq" matches as a
        # whole but "PCA" won't match a hyphenated compound it is merely part of. A trailing ``s?``
        # absorbs simple plurals ("box plots" -> "box plot") without re-listing every plural.
        self._re = (
            re.compile(r"(?<![\w-])(" + "|".join(re.escape(t) for t in terms) + r")s?(?![\w-])", re.I)
            if terms else None
        )

    def targets_for(self, term: str) -> list[tuple[str, float]]:
        return self._targets.get(_norm(term), [])

    def find_in(self, flat: str):
        """Yield ``(term, target, weight, start)`` for every non-negated match in flattened text."""
        if not self._re:
            return
        for m in self._re.finditer(flat):
            start = m.start()
            if _NEG.search(flat[max(0, start - 40):start]):
                continue
            term = _norm(m.group(1))
            for target, weight in self.targets_for(term):
                yield term, target, weight, start

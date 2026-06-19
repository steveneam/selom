"""The deterministic matcher — two passes (spec §Design + 4-layer hardening).

**Exact pass (L1).** Compiles the vocabulary into one alternation regex (longest term first, so
"diffusion pseudotime" wins over "pseudotime"; "ssGSEA" over "GSEA"). Matching is case-insensitive
with word-ish boundaries — a term may contain spaces/hyphens but must not be glued to surrounding
word characters (so "PCA" doesn't fire inside "PVCA", mirroring ``golden._has_token``). High
precision; this is the structured layer.

**Relaxed pass (L3 recall).** A token-canonical matcher for the paper-level skill inventory and the
recovery sweep: it tokenises whole words and compares **canonical keys** (lowercased, space/hyphen
removed, conservatively stemmed) so surface variation is seen through — ``heat map`` / ``Heat maps``
both canonicalise to the same key as ``heatmap``; ``differentially expressed`` to the same key as
``differential expression``. It is **boundary-safe by construction** (it only ever compares whole
tokens, so ``PCA ∉ PVCA``, ``GSEA ∉ ssGSEA``) and longest-span-first. No model in either pass.

A short left-window negation check drops "did not use Monocle"-style hits in both passes.
"""

from __future__ import annotations

import re

from .models import VocabEntry

# negation cues in the ~40 chars before a term → drop the hit (conservative; ambiguous cases
# are better handled by the AI-verify seam than silently routed).
_NEG = re.compile(r"(?:\bnot\b|n't|\bwithout\b|\brather than\b|\binstead of\b|\bneither\b|\bno\b)",
                  re.I)

# a word token (letters first, then letters/digits/apostrophes) or a bare number.
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9'’]*|\d+")

# conservative inflectional suffixes, longest-first; stripped once, only if the stem stays ≥ 4 chars
# and the token isn't a short word / acronym / number (those need exact identity).
_SUFFIX = re.compile(r"(izations?|isations?|ations?|ized|ised|ing|ion|ed|ly|es|s)$", re.I)


def _norm(term: str) -> str:
    return re.sub(r"\s+", " ", term).strip().lower()


def _stem(tok: str) -> str:
    """Conservative stem: strip one inflectional suffix. Skips short tokens, all-caps acronyms, and
    tokens with digits, which must match by identity (PCA, ssGSEA, scATAC, MACS2)."""
    if len(tok) <= 4 or tok.isupper() or any(c.isdigit() for c in tok):
        return tok.lower()
    t = tok.lower()
    m = _SUFFIX.search(t)
    if m and m.start() >= 4:
        t = t[:m.start()]
    return t


def canon(text: str) -> str:
    """Canonical key: stemmed tokens concatenated, separators dropped. Unifies ``heat map`` /
    ``Heat maps`` / ``heatmap`` and ``differential expression`` / ``differentially expressed``."""
    return "".join(_stem(m.group()) for m in _TOKEN.finditer(text))


def flatten(text: str) -> str:
    """Collapse all whitespace to single spaces so multi-word terms match across line breaks."""
    return re.sub(r"\s+", " ", text).strip()


class KeywordIndex:
    """An inverted keyword index: term → routing targets, plus the compiled exact matcher (L1) and
    the token-canonical relaxed matcher (L3 recall)."""

    def __init__(self, entries: list[VocabEntry]):
        self.entries = entries
        self._targets: dict[str, list[tuple[str, float]]] = {}
        self._canon: dict[str, list[tuple[str, float]]] = {}
        self._max_tokens = 1
        for e in entries:
            for t in e.terms:
                self._targets.setdefault(_norm(t), []).append((e.target, e.weight))
                key = canon(t)
                if key:
                    self._canon.setdefault(key, []).append((e.target, e.weight))
                    self._max_tokens = max(self._max_tokens, len(_TOKEN.findall(t)))
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
        """Exact pass (L1). Yield ``(term, target, weight, start)`` for every non-negated match."""
        if not self._re:
            return
        for m in self._re.finditer(flat):
            start = m.start()
            if _NEG.search(flat[max(0, start - 40):start]):
                continue
            term = _norm(m.group(1))
            for target, weight in self.targets_for(term):
                yield term, target, weight, start

    def find_relaxed(self, flat: str):
        """Relaxed token-canonical pass (L3 recall). Yield ``(surface, target, weight, start, end)``
        for the longest canonical match at each token position, skipping negated spans. Whole-token
        comparison keeps it boundary-safe; multi-token terms only fire when all tokens are present."""
        if not self._canon:
            return
        toks = [(m.group(), m.start(), m.end()) for m in _TOKEN.finditer(flat)]
        stems = [_stem(t) for t, _, _ in toks]
        n = len(toks)
        i = 0
        while i < n:
            hit = False
            for span in range(min(self._max_tokens, n - i), 0, -1):
                tgts = self._canon.get("".join(stems[i:i + span]))
                if not tgts:
                    continue
                start, end = toks[i][1], toks[i + span - 1][2]
                if not _NEG.search(flat[max(0, start - 40):start]):
                    surface = flat[start:end]
                    for target, weight in tgts:
                        yield surface, target, weight, start, end
                i += span
                hit = True
                break
            if not hit:
                i += 1

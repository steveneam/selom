"""Skill references / provenance helpers (docs/skill-references/spec.md).

A skill's `references` list (on :class:`skills.contract.SkillSpec`) carries structured
citations — the paper, repo, community standard, validation dataset, named method, or
tool a skill is based on. This module owns the shape: the allowed `type` enum, a tolerant
per-entry validator used by the contract test (build-time hard check) and defensively by
serialization (runtime soft skip), so a malformed entry is *flagged in CI but never a 500*.

Kept deliberately dependency-free and citation-compatible: the entry shape is a subset of
what `/citations/*` returns, so a later "auto-populate references from the methods/citation
lookup" (Out of Scope here) is a mapping, not a redesign.
"""

# Fixed enum (D4): papers, GitHub/source repos, ISCEV/community standards, validation
# datasets/accessions, named methods (Naka-Rushton), and tools/libraries. Extendable.
REFERENCE_TYPES = frozenset({"publication", "repo", "standard", "dataset", "method", "tool"})

# Optional string fields beyond the required title; year is the one int field.
_STR_FIELDS = ("authors", "doi", "url", "note")


def validate_reference(entry: object) -> bool:
    """True iff ``entry`` is a well-formed reference (used by the contract test).

    Required: a ``type`` in :data:`REFERENCE_TYPES` and a non-empty ``title``. When present,
    ``doi``/``url`` must look well-formed (a DOI starts ``10.``; a URL is http(s)), ``year``
    is a plausible 4-digit int, and the optional strings are actually strings. Everything else
    optional. Never raises — a non-dict / wrong-typed field just returns False.
    """
    if not isinstance(entry, dict):
        return False
    if entry.get("type") not in REFERENCE_TYPES:
        return False
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        return False
    for field in _STR_FIELDS:
        val = entry.get(field)
        if val is not None and not isinstance(val, str):
            return False
    doi = entry.get("doi")
    if isinstance(doi, str) and doi and not doi.lstrip().startswith("10."):
        return False
    url = entry.get("url")
    if isinstance(url, str) and url and not url.lstrip().startswith(("http://", "https://")):
        return False
    year = entry.get("year")
    if year is not None and (not isinstance(year, int) or isinstance(year, bool) or not (1800 <= year <= 2100)):
        return False
    return True


def clean_references(references: object) -> list[dict]:
    """Return only the well-formed entries, order preserved (defensive serialization).

    The runtime tolerates and skips a malformed entry; the contract test is what fails the
    build on one. A non-list input yields ``[]``.
    """
    if not isinstance(references, list):
        return []
    return [entry for entry in references if validate_reference(entry)]

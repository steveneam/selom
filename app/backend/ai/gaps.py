"""In-process capability-gap store (Slice 1 — SQL persistence lands in Slice 4).

A gap is a coherent but unfulfillable action: the AI (or a user via the UI)
reached for a capability that the spine doesn't offer yet.  Gaps deduplicate by
``context_hash`` and accumulate a frequency count across calls — the recurrence
is the signal that separates a real backlog item from AI noise.

Integrity boundary: this module is APPEND + READ ONLY.  Nothing here modifies
the action registry, relaxes a validation rule, or widens a param_spec.  The
backlog produced by ``list_gaps()`` is surfaced for human review; it is never
acted on automatically.  (Mirrors the routing synonym-candidate discipline in
``extract/routing/verify.py::mine_synonym_candidates``.)
"""

from __future__ import annotations

import hashlib

from ai.models import CapabilityGap

# Module-level store keyed by context_hash → {"gap": CapabilityGap, "count": int}.
# In Slice 4 this becomes a SQL table; the interface (record / list_gaps / reset) is stable.
_GAPS: dict[str, dict] = {}


def context_hash(stage: str, intent_class: str, unmet: str, skill_id: str | None) -> str:
    """Stable dedup key for identical unmet intents.

    ``stage|intent_class|unmet|skill_id`` is hashed so the same unfulfillable
    request from different sessions produces the same key and increments count.
    First 16 hex chars (64-bit prefix) are enough given the low cardinality of
    the action vocabulary.
    """
    raw = f"{stage}|{intent_class}|{unmet}|{skill_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def record(gap: CapabilityGap) -> None:
    """Increment the frequency counter for this gap (dedup by context_hash)."""
    key = gap.context_hash
    if key in _GAPS:
        _GAPS[key]["count"] += 1
    else:
        _GAPS[key] = {"gap": gap, "count": 1}


def list_gaps() -> list[dict]:
    """Return all recorded gaps sorted by recurrence count descending."""
    return sorted(_GAPS.values(), key=lambda x: x["count"], reverse=True)


def reset() -> None:
    """Clear the in-process store — used in tests to prevent bleed between cases."""
    _GAPS.clear()

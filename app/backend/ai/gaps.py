"""Capability-gap store — the module-level interface ``ai/`` code calls (S4 refactor).

The active backend is selected lazily from config on first access:
  - ``InMemoryGapStore`` (default, zero-infra) when no gap-store config is set.
  - ``JsonlGapStore`` when ``SELOM_GAP_STORE=jsonl`` + ``SELOM_GAP_STORE_PATH`` is set.

The public interface (record / list_gaps / reset / context_hash) is stable — callers
are unaware of which backend is active.  ``_set_store_for_test`` overrides the active
store for test isolation; ``configure_gap_store`` re-initializes from explicit args
(useful for app-startup wiring or integration tests).

**Integrity boundary (unchanged from Slice 1):** APPEND + READ ONLY.  Nothing here
modifies the action registry, relaxes a validation rule, or widens a param_spec.  The
backlog produced by ``list_gaps()`` is surfaced for human review; it is never acted on
automatically.  (Mirrors the routing synonym-candidate discipline in
``extract/routing/verify.py::mine_synonym_candidates``.)
"""

from __future__ import annotations

import hashlib

from ai.models import CapabilityGap

# Module-level store — initialized lazily on first access.  InMemoryGapStore is
# the zero-infra default; JsonlGapStore is selected by config when persistence
# is needed.  _set_store_for_test() overrides this for test isolation.
_store = None


def _get_store():
    global _store
    if _store is None:
        _store = _init_store()
    return _store


def _init_store():
    """Select the concrete backend from config (fail-soft to InMemoryGapStore)."""
    from ai.gap_store import InMemoryGapStore, make_gap_store

    try:
        from config import settings

        store_type = getattr(settings, "gap_store", "memory")
        store_path = getattr(settings, "gap_store_path", None)
        return make_gap_store(store_type, store_path)
    except Exception:
        return InMemoryGapStore()


def configure_gap_store(store_type: str, path=None) -> None:
    """Re-initialize the module-level store from explicit args.

    Call from app startup or integration tests to activate the JSONL backend.
    Passing ``store_type="memory"`` resets to the zero-infra default.
    """
    global _store
    from ai.gap_store import make_gap_store

    _store = make_gap_store(store_type, path)


def _set_store_for_test(store) -> None:
    """Override the active store — test helper only, not for production use.

    Swap in any concrete store (InMemoryGapStore / JsonlGapStore) before a test;
    restore with a fresh InMemoryGapStore in teardown to prevent bleed.
    """
    global _store
    _store = store


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
    _get_store().record(gap)


def list_gaps() -> list[dict]:
    """Return all recorded gaps sorted by recurrence count descending.

    Each entry carries ``{gap: CapabilityGap, count: int, category: str}``.
    The ``category`` is derived from the gap's ``unmet`` code and ``intent``
    by the aggregation layer — see ``ai.gap_store._derive_category``.
    """
    return _get_store().list_gaps()


def reset() -> None:
    """Clear the active store — used in tests to prevent bleed between cases."""
    _get_store().reset()

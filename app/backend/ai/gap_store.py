"""CapabilityGap store backends — in-memory (default) and JSONL file (persistent, S4).

Two concrete stores share the ``GapStore`` interface (record / list_gaps / reset):

  ``InMemoryGapStore`` — default, dev-safe, zero-infra.  State is lost on restart.
  ``JsonlGapStore``    — simple append-then-aggregate JSONL file store.  Each
                         ``record()`` appends one event line; ``list_gaps()`` reads
                         all lines, aggregates by context_hash, and sorts by
                         frequency — survives process restarts.  Configured via
                         ``SELOM_GAP_STORE=jsonl`` + ``SELOM_GAP_STORE_PATH=<path>``.

``make_gap_store`` mirrors ``make_job_store`` / ``make_object_store``: one env-driven
seam, the rest of the codebase is store-agnostic.  Default behaviour (in-memory) is
unchanged when neither env var is set (zero-regression guarantee).

**Aggregation and categorization.**  Both stores deduplicate by ``context_hash`` and
frequency-rank.  ``list_gaps()`` adds a derived ``category`` to each entry so the
backlog reads consistently:

  ``engine_capability_missing`` — ``map_columns`` (unmet=missing_column_op) AND
                                   ``apply_cleaning_step`` (unmet=validation_blocked)
                                   both land here — same real gap: the engine doesn't
                                   support this capability yet (build-this backlog).
                                   Normalized in the aggregation layer so the registry
                                   handlers' honest unmet codes are unchanged (S3 tests
                                   stay green).
  ``param_blocked``             — validation_blocked on a real param (out-of-range or
                                   unknown param name).
  ``unknown_action``            — no_such_action (unregistered type).
  ``no_fitting_skill``          — no compatible skill for the current data.
  ``unknown``                   — catch-all for anything not yet categorised.

**Integrity boundary (non-negotiable).** APPEND + READ ONLY.  No store method
modifies the action registry, relaxes a validation rule, or widens a param_spec.
The backlog is surfaced for human review; it is never acted on automatically.
"""

from __future__ import annotations

import pathlib
from typing import Protocol, runtime_checkable

from ai.models import CapabilityGap


def _derive_category(gap: CapabilityGap) -> str:
    """Derive the aggregation category from a gap's unmet code and intent.

    ``map_columns`` (unmet=missing_column_op) and ``apply_cleaning_step``
    (unmet=validation_blocked) are normalized to ``engine_capability_missing``
    because both mean "the engine doesn't support this capability yet".  This
    normalization lives here in the aggregation layer — the registry handlers'
    precise unmet codes are unchanged.
    """
    if gap.unmet == "missing_column_op":
        return "engine_capability_missing"
    if gap.unmet == "no_fitting_skill":
        return "no_fitting_skill"
    if gap.unmet == "no_such_action":
        return "unknown_action"
    if gap.unmet in ("param_not_in_spec", "unsupported_filter"):
        return "param_blocked"
    if gap.unmet == "validation_blocked":
        # apply_cleaning_step's validation_blocked is an engine-level gap (no step-
        # toggle hook exists), not a param-range rejection — same backlog as map_columns.
        if gap.intent == "apply_cleaning_step":
            return "engine_capability_missing"
        return "param_blocked"
    return "unknown"


def _make_entry(gap: CapabilityGap, count: int) -> dict:
    """Build the standard list_gaps entry dict including the derived category."""
    return {"gap": gap, "count": count, "category": _derive_category(gap)}


@runtime_checkable
class GapStore(Protocol):
    """Interface every gap-store backend implements.

    Callers use the module-level functions in ``ai.gaps`` (record / list_gaps /
    reset) — they are unaware of which concrete store is active.
    """

    def record(self, gap: CapabilityGap) -> None: ...
    def list_gaps(self) -> list[dict]: ...
    def reset(self) -> None: ...


class InMemoryGapStore:
    """In-process gap store — default, dev-safe, zero-infra.

    State is lost on process exit.  Suitable for the dev inner loop and CI.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    def record(self, gap: CapabilityGap) -> None:
        key = gap.context_hash
        if key in self._data:
            self._data[key]["count"] += 1
        else:
            self._data[key] = _make_entry(gap, 1)

    def list_gaps(self) -> list[dict]:
        return sorted(self._data.values(), key=lambda x: x["count"], reverse=True)

    def reset(self) -> None:
        self._data.clear()


class JsonlGapStore:
    """JSONL-backed gap store — persists across process restarts, no SQL required.

    Each ``record()`` appends one JSON line (the serialized ``CapabilityGap``) to the
    backing file.  ``list_gaps()`` reads all lines, aggregates by context_hash, and
    sorts by frequency descending — the same semantics as ``InMemoryGapStore`` with
    the durability guarantee.  ``reset()`` removes the backing file.

    Configured via ``SELOM_GAP_STORE=jsonl`` + ``SELOM_GAP_STORE_PATH=<path>``.
    """

    def __init__(self, path: pathlib.Path) -> None:
        self._path = pathlib.Path(path)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # best-effort; record() will surface the error on the first write

    def record(self, gap: CapabilityGap) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(gap.model_dump_json() + "\n")

    def list_gaps(self) -> list[dict]:
        if not self._path.exists():
            return []
        aggregated: dict[str, dict] = {}
        try:
            with self._path.open(encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line:
                        continue
                    gap = CapabilityGap.model_validate_json(line)
                    key = gap.context_hash
                    if key in aggregated:
                        aggregated[key]["count"] += 1
                    else:
                        aggregated[key] = _make_entry(gap, 1)
        except (OSError, ValueError):
            return []
        return sorted(aggregated.values(), key=lambda x: x["count"], reverse=True)

    def reset(self) -> None:
        try:
            if self._path.exists():
                self._path.unlink()
        except OSError:
            pass


def make_gap_store(
    store_type: str = "memory",
    path: pathlib.Path | str | None = None,
) -> GapStore:
    """Factory mirroring ``make_job_store`` / ``make_object_store``.

    ``store_type`` is ``"memory"`` (default, zero-infra) or ``"jsonl"`` (persistent
    JSONL file).  With ``"jsonl"`` a ``path`` is required; without one, falls back to
    memory with a warning rather than raising (fail-soft on misconfiguration).
    """
    t = store_type.strip().lower()
    if t == "jsonl":
        if path is None:
            import warnings
            warnings.warn(
                "SELOM_GAP_STORE=jsonl requires SELOM_GAP_STORE_PATH; falling back to memory",
                stacklevel=2,
            )
            return InMemoryGapStore()
        return JsonlGapStore(pathlib.Path(path))
    return InMemoryGapStore()

"""Structured-logging seam — one JSON line per event to stdout.

On Lambda/CloudWatch, stdout-JSON is the only observability you get for free, and a CloudWatch
log group retains forever by default (set retention at deploy — spec/integrations). Use
``log(event, **fields)`` and thread the ids you have (``user_id``/``job_id``/``dataset_id``).
It never raises — logging must not break a request — and only emits JSON-serializable, *small*
field values (no raw matrices, no PII).
"""
from __future__ import annotations

import json
import logging
import sys

_logger = logging.getLogger("selom")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))  # the message IS the JSON line
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False  # don't double-emit through the root handler


def log(event: str, **fields) -> None:
    record = {"event": event}
    for key, value in fields.items():
        try:
            json.dumps(value)
            record[key] = value
        except (TypeError, ValueError):
            record[key] = repr(value)[:200]  # keep it a line, never throw
    try:
        _logger.info(json.dumps(record, separators=(",", ":")))
    except Exception:  # noqa: BLE001 — observability must never break the caller
        pass

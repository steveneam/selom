"""On-disk JSON cache for citation lookups — pins query->result snapshots (reproducibility
+ offline tests). A single JSON file holding a flat ``{key: value}`` map. Tolerant: a
missing, unreadable, or unwritable file degrades to an empty / no-op cache rather than
raising — a cache miss must never break a lookup.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any


class JsonCache:
    def __init__(self, path: str | pathlib.Path) -> None:
        self.path = pathlib.Path(path)

    def _load(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return {}

    def has(self, key: str) -> bool:
        # Distinguishes "cached as None" (a real, negative result) from "never cached".
        return key in self._load()

    def get(self, key: str) -> Any | None:
        return self._load().get(key)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass  # an unwritable cache degrades to a no-op

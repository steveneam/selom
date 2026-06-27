"""Content-addressed result cache (Task C1).

A skill run is a pure function of *(the skill + its version, the effective params, the
input bytes)*. So the result of the compute can be stored under a content hash and served
again without recomputing. Because the skill ``version`` is part of the key, a version bump
simply produces a *different* key — a clean miss, with **no TTL and no explicit invalidation**.
Each cached entry is therefore immutable.

Two tiers behind one ``get``/``set``:
  * an in-process LRU (the hot path within a worker),
  * a local-disk JSON tier under ``data/result_cache/`` (survives restarts, shared across
    workers on one box).

What is cached is the **pre-theme compute output** (``{figure, table}``); theming is re-applied
on every hit (it is cheap + deterministic — ``theme.apply`` deep-copies its input). That keeps
the cache forward-compatible with the C2 source/render split, where a theme-only change must
re-render *without* recomputing the skill.

Deliberately dependency-free (stdlib only). The roadmap named ``diskcache``; content-addressing
makes its eviction/concurrency machinery unnecessary at this local tier (every entry is immutable
and deduped by content), and avoids adding a dependency to the EDR-fragile venv. A future durable
R2 tier (C4, deferred) can swap the disk backend behind this same interface.

Assumes skills are **deterministic** given their inputs (the reproduction mission requires this
anyway); a non-deterministic skill served from cache returns its first result, which is the
reproducible answer. Errors are never cached — a runner that raises never reaches ``set``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import threading
from collections import OrderedDict

from skills._engine import to_bool

# Param-value casts, mirroring skills.contract._CASTS (kept local to avoid a contract<-cache
# import cycle — contract imports this module). Query params arrive as strings; canonicalizing
# to the declared type is what lets "fc=2 passed explicitly" hash-equal "fc default 2 omitted".
_CASTS = {"int": int, "float": float, "str": str, "bool": to_bool}

# Round floats to a stable precision so 0.1+0.2-style drift can't fork the cache key.
_FLOAT_NDIGITS = 10


def _norm(value):
    """Canonicalize a single param value: floats to a stable precision; bools/ints/str as-is."""
    if isinstance(value, bool):  # bool is an int subclass — keep it a bool, not 0/1
        return value
    if isinstance(value, float):
        return round(value, _FLOAT_NDIGITS)
    return value


def _try_cast(cast, value):
    if cast is None:
        return value
    try:
        return cast(value)
    except (ValueError, TypeError):
        return value


def _file_sha256(path) -> str | None:
    """Stream-hash a file's bytes. None when the path is missing/unreadable (uncacheable)."""
    if not path:
        return None
    p = pathlib.Path(path)
    try:
        if not p.is_file():
            return None
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _runtime_value(value):
    """A reserved ``_``-prefixed param (e.g. ``_design_path``) may point at a file whose *content*
    affects the output — hash it so two runs with different design sheets don't collide. A non-file
    runtime value is canonicalized like any other."""
    if isinstance(value, str):
        digest = _file_sha256(value)
        if digest is not None:
            return {"__file_sha256__": digest}
    return _norm(value)


def canonical_params(param_spec: dict, params: dict) -> dict:
    """The effective config reduced to a stable, comparable form:

    * overlay caller params on the skill defaults,
    * coerce each declared param to its ``param_spec`` type (string query args -> typed),
    * **drop any param equal to its default** (so an explicit default and an omitted one match),
    * round floats to a stable precision,
    * hash reserved ``_``-prefixed file paths by content.

    Unknown keys (absent from ``param_spec``, not ``_``-prefixed) pass through, canonicalized.
    """
    defaults = {k: v.get("default") for k, v in param_spec.items()}
    merged = {**defaults, **params}
    out: dict = {}
    for key in merged:
        skey = str(key)
        value = merged[key]
        if skey.startswith("_"):
            out[skey] = _runtime_value(value)
            continue
        entry = param_spec.get(key)
        if entry is None:
            out[skey] = _norm(value)  # unknown knob — can't drop-default, keep it
            continue
        cast = _CASTS.get(entry.get("type"))
        cv = _norm(_try_cast(cast, value))
        dv = _norm(_try_cast(cast, entry.get("default")))
        if cv == dv:
            continue  # equals the default -> omit from the key
        out[skey] = cv
    return out


def cache_key(skill_id: str, version: str, param_spec: dict, data_path, params: dict) -> str | None:
    """The content hash for one run, or None when the input is unhashable (don't cache)."""
    input_sha = _file_sha256(data_path)
    if input_sha is None:
        return None
    payload = {
        "skill": skill_id,
        "version": version,
        "params": canonical_params(param_spec, params),
        "input": input_sha,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def render_key(source, skill_id: str, style: str, theme_version: str) -> str:
    """The figure-envelope (render) key (Task C2): ``(source identity, skill, style, theme_version)``.

    ``source`` is either the pre-theme figure dict (hashed by content — the ``/figures/style/apply``
    path, where the caller hands us a raw figure) or the compute key string that already identifies
    that source (the ``_execute`` path — cheaper, no re-hash of a large figure). Prefixed ``render-``
    so it never collides with a bare compute hash in the shared store (a filename-safe separator —
    a ``:`` would be an invalid NTFS filename char and silently break the disk tier on Windows)."""
    blob = json.dumps(
        {"src": source, "skill": skill_id, "style": style, "theme": theme_version},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "render-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ResultCache:
    """Two-tier (in-proc LRU + local-disk JSON) content-addressed store.

    Entries are isolated from callers in both directions: ``set`` snapshots its input and ``get``
    returns a deep copy, so neither the producer nor a consumer can mutate a cached value. Costs
    one extra copy per hit — negligible for a dev-tier cache, and obviously correct.
    """

    def __init__(self, root, mem_max: int = 64, enabled: bool = True) -> None:
        self.root = pathlib.Path(root)
        self.mem_max = max(0, int(mem_max))
        self.enabled = enabled
        self._mem: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = threading.Lock()
        self.stats = {"mem_hits": 0, "disk_hits": 0, "misses": 0, "sets": 0, "errors": 0}

    def _path(self, key: str) -> pathlib.Path:
        return self.root / f"{key}.json"

    def _evict(self) -> None:
        while len(self._mem) > self.mem_max:
            self._mem.popitem(last=False)

    def _disk_read(self, key: str) -> dict | None:
        p = self._path(key)
        try:
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.stats["errors"] += 1
        return None

    def _disk_write(self, key: str, payload: dict) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self._path(key).with_name(f"{key}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, self._path(key))  # atomic — no torn reads across workers
        except (OSError, ValueError, TypeError):
            self.stats["errors"] += 1

    def fetch(self, key: str | None) -> dict | None:
        """Return a private deep copy of the JSON payload at ``key``, or None on a miss.

        The generic two-tier read primitive — :meth:`get` (compute entries) and the C2 render
        cache both go through it. Counts the hit (in-proc vs disk) / miss in ``stats``."""
        if not self.enabled or key is None:
            return None
        with self._lock:
            payload = self._mem.get(key)
            if payload is not None:
                self._mem.move_to_end(key)
                self.stats["mem_hits"] += 1
                return copy.deepcopy(payload)
        payload = self._disk_read(key)  # fresh from JSON -> no external refs, safe to own
        if payload is not None:
            with self._lock:
                if self.mem_max:
                    self._mem[key] = payload
                    self._mem.move_to_end(key)
                    self._evict()
                self.stats["disk_hits"] += 1
            return copy.deepcopy(payload)
        with self._lock:
            self.stats["misses"] += 1
        return None

    def put(self, key: str | None, payload: dict) -> None:
        """Store an arbitrary JSON-able payload under ``key`` (the generic write primitive)."""
        if not self.enabled or key is None:
            return
        snapshot = copy.deepcopy(payload)
        with self._lock:
            if self.mem_max:
                self._mem[key] = snapshot
                self._mem.move_to_end(key)
                self._evict()
            self.stats["sets"] += 1
        self._disk_write(key, snapshot)

    def get(self, key: str | None) -> dict | None:
        """A cached ``{figure, table}`` compute entry (a private deep copy), or None — see :meth:`fetch`."""
        return self.fetch(key)

    def set(self, key: str | None, figure, table) -> None:
        self.put(key, {"figure": figure, "table": table})

    def clear(self) -> None:
        """Drop the in-proc tier and remove the disk tier (test / forced-cold hygiene)."""
        with self._lock:
            self._mem.clear()
        try:
            for p in self.root.glob("*.json"):
                p.unlink(missing_ok=True)
        except OSError:
            pass

    def reset_stats(self) -> None:
        with self._lock:
            for k in self.stats:
                self.stats[k] = 0


# --- process-default instance (lazily built from config) -------------------------------------

_default: ResultCache | None = None
_default_lock = threading.Lock()


def get_cache() -> ResultCache:
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                from config import settings

                _default = ResultCache(
                    root=settings.data_dir / "result_cache",
                    mem_max=settings.result_cache_mem_max,
                    enabled=settings.result_cache_enabled,
                )
    return _default


def set_cache(cache: ResultCache | None) -> None:
    """Swap the process-default cache (test seam)."""
    global _default
    _default = cache


def lookup(skill_id, version, param_spec, data_path, params) -> tuple[str | None, dict | None]:
    """Compute the key once and probe the cache. Returns ``(key, cached | None)`` so the caller
    can reuse the key for :func:`store` on a miss (avoids hashing the input twice)."""
    cache = get_cache()
    if not cache.enabled:
        return None, None
    key = cache_key(skill_id, version, param_spec, data_path, params)
    return key, cache.get(key)


def store(key, figure, table) -> None:
    if key is None:
        return
    get_cache().set(key, figure, table)


def cache_stats() -> dict:
    return dict(get_cache().stats)

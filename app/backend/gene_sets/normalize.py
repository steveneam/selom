"""Gene-symbol normalization for the gene-set compile step (Phase B).

When a compiled set unions/intersects members from several sources, the same gene can
appear under an alias or a withdrawn symbol. ``normalize`` reconciles to a current
approved symbol using the HGNC-style map built from NCBI gene_info
(``scripts/build_symbols.py`` → ``corpus/hgnc_symbols.json``, gitignored/regenerable).

Non-destructive by design: it upper-cases + dedups always, remaps known aliases when the
map is present, and **keeps** unrecognized symbols (reporting them) rather than dropping
them — an incomplete map must never silently lose a real gene. Degrades to upper+dedup
when the map is absent (fresh clone / CI).
"""

from __future__ import annotations

import functools
import json
import pathlib

_MAP = pathlib.Path(__file__).resolve().parent / "corpus" / "hgnc_symbols.json"


@functools.lru_cache(maxsize=1)
def _symbols() -> tuple[frozenset[str], dict[str, str]] | None:
    if not _MAP.exists():
        return None
    raw = json.loads(_MAP.read_text())
    approved = frozenset(raw.get("approved", []))
    alias = {k.upper(): v for k, v in raw.get("alias", {}).items()}
    return approved, alias


def normalize(genes) -> dict:
    """Return ``{genes, remapped, unrecognized, mapped}`` for an iterable of symbols.

    ``genes`` is the deduped, sorted, approved-where-possible list; ``remapped`` is
    ``{alias: approved}``; ``unrecognized`` are symbols absent from the reference (kept,
    not dropped); ``mapped`` is False when the HGNC map was unavailable.
    """
    sym = _symbols()
    remapped: dict[str, str] = {}
    unrecognized: list[str] = []
    out: list[str] = []
    seen: set[str] = set()

    for g in genes:
        s = str(g).strip().upper()
        if not s:
            continue
        cur = s
        if sym is not None:
            approved, alias = sym
            if s not in approved:
                if s in alias:
                    cur = alias[s]
                    remapped[s] = cur
                else:
                    unrecognized.append(s)
        if cur not in seen:
            seen.add(cur)
            out.append(cur)

    return {
        "genes": sorted(out),
        "remapped": remapped,
        "unrecognized": sorted(set(unrecognized)),
        "mapped": sym is not None,
    }

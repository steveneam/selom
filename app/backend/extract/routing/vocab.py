"""Build the routing vocabulary = two layers (spec §Design).

1. **Registry-derived** (auto): every ``skills/<id>/skill.json`` inverts its own id/title into
   terms pointing back at ``skill:<id>``. Adding a skill extends the index for free — the same
   "drop a skill dir, the Store shows it" property ``skills/registry.py`` already has. Low weight
   (these terms are noisier than the curated nouns papers actually use).
2. **Curated synonyms** (``synonyms.json``): the method-nouns papers use → the Selom skill /
   out-of-scope modality. The domain-knowledge moat; the high-signal layer.

Every curated ``skill:`` target is validated against the live registry at build time, so the moat
layer can't silently rot when a skill is renamed/removed.
"""

from __future__ import annotations

import json
import pathlib
import re

from skills.registry import list_skill_ids

from .models import OOS_PREFIX, OOS_SCOPE, SKILL_PREFIX, VocabEntry, skill_id

_SYN_PATH = pathlib.Path(__file__).parent / "synonyms.json"

# title tokens that carry no routing signal (skipped when deriving registry terms).
_STOP = {
    "and", "the", "for", "with", "per", "scrna", "scrna-seq", "single", "cell", "seq",
    "analysis", "data", "plot", "chart", "graph", "score", "selom", "test", "based",
}


def _title_phrase(text: str) -> str:
    """A skill title as one routing phrase: parenthetical brands dropped, whitespace normalized,
    lowercased. Kept as a WHOLE phrase (not split into tokens) so a common word like 'enrichment'
    or 'heatmap' routes to at most the one skill literally named that — never cross-routes."""
    text = re.sub(r"\([^)]*\)", " ", text)  # drop "(Melody)" etc.
    return re.sub(r"[^a-z0-9 -]+", " ", re.sub(r"\s+", " ", text.lower())).strip()


def registry_entries() -> list[VocabEntry]:
    """One low-weight ``registry`` entry per skill: its id + full title phrase → ``skill:<id>``."""
    out: list[VocabEntry] = []
    for sid in list_skill_ids():
        # load_skill is cheap; import lazily to avoid a registry import cycle at module load.
        from skills.registry import load_skill
        terms = {sid, sid.replace("_", " "), _title_phrase(load_skill(sid).title)}
        terms = {t for t in terms if t and t not in _STOP}
        out.append(VocabEntry(terms=sorted(terms),
                              target=f"{SKILL_PREFIX}{sid}", kind="registry", weight=0.5))
    return out


def load_synonyms() -> list[VocabEntry]:
    """The curated synonym layer from ``synonyms.json`` (kind ``curated``, default weight 1.0)."""
    data = json.loads(_SYN_PATH.read_text(encoding="utf-8"))
    return [VocabEntry(kind="curated", **row) for row in data]


def _validate(synonyms: list[VocabEntry]) -> None:
    """Fail loudly if a curated target points at a skill/oos-reason that no longer exists —
    the guard that keeps the moat layer honest as the registry evolves."""
    ids = set(list_skill_ids())
    for e in synonyms:
        if e.target.startswith(SKILL_PREFIX):
            if skill_id(e.target) not in ids:
                raise ValueError(f"synonym targets unknown skill '{e.target}' (terms={e.terms})")
        elif e.target.startswith(OOS_PREFIX):
            reason = e.target[len(OOS_PREFIX):]
            if reason not in OOS_SCOPE:
                raise ValueError(f"synonym targets unknown oos reason '{e.target}'")
        else:
            raise ValueError(f"synonym target must be 'skill:<id>' or 'oos:<reason>': '{e.target}'")


def build_vocab(*, validate: bool = True) -> list[VocabEntry]:
    """The merged routing vocabulary (registry-derived + curated). Validates curated targets
    against the live registry unless ``validate=False``."""
    syn = load_synonyms()
    if validate:
        _validate(syn)
    return registry_entries() + syn

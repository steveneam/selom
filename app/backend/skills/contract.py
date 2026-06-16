from importlib import import_module
import json
import pathlib

from pydantic import BaseModel

from skills._engine import to_bool

SKILLS_DIR = pathlib.Path(__file__).parent
# Branded namespace for genuinely-original Selom IP. New proprietary skills live here
# (skills/proprietary/<id>/); the loader scans it alongside the flat skills/<id>/ dirs.
# See docs/proprietary-skills.md for the open-core boundary + classification.
PROPRIETARY_DIR = SKILLS_DIR / "proprietary"


class SkillSpec(BaseModel):
    id: str
    version: str
    title: str
    engine: str
    omics: str
    entrypoint: str
    inputs: list[dict]
    param_spec: dict
    outputs: list[dict]
    # Open-core split marker (DECISIONS #8): "proprietary" = genuinely Selom-original IP
    # — novel or clean-room-reimplemented algorithms, and the editable graph-figure skills
    # that turn public API data into editable Plotly figures. "commodity" = a thin wrapper
    # over a public library where the value is the editable output + provenance, not the
    # algorithm. Default commodity (existing flat skills omit it). See docs/proprietary-skills.md.
    origin: str = "commodity"
    # Optional Skill-Store display metadata (name/summary/category/tier/status/license/…).
    # Presentation only — the execution contract above is what the runner needs. `catalog.name`
    # carries the branded display name. The registry (skills/registry.py) reads this to serve GET /skills.
    catalog: dict | None = None


def _skill_dir(skill_id: str) -> pathlib.Path:
    """Resolve a skill slug to its directory. Skills live flat under ``skills/<id>/``;
    genuinely-original ones may instead live in the proprietary namespace
    ``skills/proprietary/<id>/``. Both are scanned; the flat location wins on a clash.
    Falls back to the flat path so a missing skill raises a clear error there."""
    flat = SKILLS_DIR / skill_id
    if (flat / "skill.json").exists():
        return flat
    prop = PROPRIETARY_DIR / skill_id
    if (prop / "skill.json").exists():
        return prop
    return flat


def load_skill(skill_id: str) -> SkillSpec:
    p = _skill_dir(skill_id) / "skill.json"
    return SkillSpec(**json.loads(p.read_text()))


def _execute(skill_id: str, data_path: str, params: dict) -> tuple[dict, dict | None]:
    from skills import theme  # central publication theme — one look across every skill

    spec = load_skill(skill_id)
    mod_path, fn = spec.entrypoint.split(":")
    run = getattr(import_module(mod_path), fn)
    figure = run(data_path=data_path, params={**defaults(spec), **params})  # Plotly spec dict
    # Pillar 1: a runner may attach a Statistics `table` to its figure dict. Pop it
    # BEFORE theming so the spec the FE renders stays a pure {data, layout}, and so the
    # golden figures (taken via run_skill) are unaffected.
    table = figure.pop("table", None) if isinstance(figure, dict) else None
    return theme.apply(figure, skill_id), table


def run_skill(skill_id: str, data_path: str, params: dict) -> dict:
    """Run a skill → its themed Plotly figure. Any Statistics table is dropped here —
    use run_skill_with_table when the bundle needs it (Pillar 1)."""
    figure, _table = _execute(skill_id, data_path, params)
    return figure


def run_skill_with_table(skill_id: str, data_path: str, params: dict) -> tuple[dict, dict | None]:
    """Run a skill → (themed figure, StatsTable | None). The Statistics node reads the
    table; the figure stays a pure {data, layout} spec (Decision D7)."""
    return _execute(skill_id, data_path, params)


def defaults(spec: SkillSpec) -> dict:
    return {k: v["default"] for k, v in spec.param_spec.items()}


_CASTS = {"int": int, "float": float, "str": str, "bool": to_bool}


def resolved_params(spec: SkillSpec, params: dict) -> dict:
    """Skill defaults overlaid with caller params, coerced to the param_spec types.

    Query-string params arrive as strings; this yields the exact *effective* config
    (typed) that ran — what the reproducibility bundle records and the methods text
    quotes. Unknown keys / failed casts pass through unchanged. The runners still
    coerce their own inputs; this never feeds them, so the proven path is untouched.
    """
    merged = {**defaults(spec), **params}
    out: dict = {}
    for key, value in merged.items():
        if str(key).startswith("_"):
            continue  # reserved runtime keys (e.g. _design_path) — not part of the recorded config
        cast = _CASTS.get(spec.param_spec.get(key, {}).get("type"))
        try:
            out[key] = cast(value) if cast else value
        except (ValueError, TypeError):
            out[key] = value
    return out

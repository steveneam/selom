from importlib import import_module
import json
import pathlib

from pydantic import BaseModel

from skills._engine import to_bool


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
    # Optional Skill-Store display metadata (summary/category/tier/status/license/…).
    # Presentation only — the execution contract above is what the runner needs.
    # The registry (skills/registry.py) reads this to serve GET /skills.
    catalog: dict | None = None


def load_skill(skill_id: str) -> SkillSpec:
    p = pathlib.Path(__file__).parent / skill_id / "skill.json"
    return SkillSpec(**json.loads(p.read_text()))


def run_skill(skill_id: str, data_path: str, params: dict) -> dict:
    from skills import theme  # central publication theme — one look across every skill

    spec = load_skill(skill_id)
    mod_path, fn = spec.entrypoint.split(":")
    run = getattr(import_module(mod_path), fn)
    figure = run(data_path=data_path, params={**defaults(spec), **params})  # Plotly spec dict
    return theme.apply(figure, skill_id)


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

from importlib import import_module
import json
import pathlib

from pydantic import BaseModel


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
    spec = load_skill(skill_id)
    mod_path, fn = spec.entrypoint.split(":")
    run = getattr(import_module(mod_path), fn)
    return run(data_path=data_path, params={**defaults(spec), **params})  # returns Plotly spec dict


def defaults(spec: SkillSpec) -> dict:
    return {k: v["default"] for k, v in spec.param_spec.items()}

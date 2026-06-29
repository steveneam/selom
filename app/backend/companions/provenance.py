"""Per-figure reproducibility bundle (charter B4 — publish-confidence).

Records the minimum needed to reproduce a figure: which skill+version ran, the
resolved parameters, a content hash of the input data, and the analysis environment
(interpreter + scientific-stack package versions). This is the machine-checkable
half of "is THIS the right, reproducible figure?"; ``methods.py`` is the prose half.

Pure-Python, no heavy deps, deterministic given (skill, params, data, env) — so it
attaches to every ``/run`` and job result without touching the figure wire shape.
"""

from __future__ import annotations

import hashlib
import os
import platform
from importlib.metadata import PackageNotFoundError, version

from skills.contract import SkillSpec, resolved_params

# The scientific stack whose versions pin a result's numerics. Distribution names
# (what importlib.metadata knows), not import names. Absent ones are omitted — the
# light skeleton install has almost none — rather than reported as null.
_TRACKED_PACKAGES = (
    "scanpy",
    "anndata",
    "scikit-learn",
    "leidenalg",
    "igraph",
    "pydeseq2",
    "numpy",
    "pandas",
    "scipy",
    "plotly",
    "kaleido",
)

_CHUNK = 1 << 20  # 1 MiB — hash large .h5ad uploads without loading them whole.


def sha256_file(path: str) -> str:
    """Streaming SHA-256 of the input file — the stable identity of the data run."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _packages() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in _TRACKED_PACKAGES:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            continue
    return found


def environment_snapshot() -> dict:
    """Interpreter + platform + which engine policy is in effect + stack versions."""
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "engine_policy": os.environ.get("SELOM_SKILLS_ENGINE", "auto").lower(),
        "packages": _packages(),
    }


def build(
    spec: SkillSpec,
    data_path: str,
    filename: str | None,
    params: dict,
    *,
    actions: list[dict] | None = None,
) -> dict:
    """The reproducibility bundle for one figure.

    ``params`` may be raw (query-string) — it is merged over the skill defaults and
    coerced, so the record is the exact effective config that produced the figure.
    Reads ``data_path``; call before the temp upload is unlinked.

    ``actions`` is optional.  When provided (AI-assisted runs), each entry carries
    ``{action_id, actor, type, target, prompt, model, approved_by, approved_at}``
    and is appended to the bundle as ``"actions"``.  When ``None`` (the default),
    the returned dict is byte-identical to the pre-AI behaviour — existing callers
    and tests are unaffected (additive, non-breaking).

    The ``params``/``input``/``environment`` blocks are unchanged — they remain the
    sole basis for reproduction, preserving the "AI compiles away" invariant: a
    re-run from recorded ``params`` with no gateway reproduces the figure exactly.
    """
    bundle: dict = {
        "skill": {
            "id": spec.id,
            "version": spec.version,
            "title": spec.title,
            "engine": spec.engine,
            # C5: the immutable param_spec for this skill_version, stamped so the figure is
            # self-describing forever. The FE seeds the Figure-data Inputs from this (no
            # describe round-trip on re-open; an offline already-run figure still shows its
            # tunable inputs — a re-run still needs the backend). Grouped with id+version,
            # which the FE keys the spec cache by. param_spec is small (a dozen knobs) and
            # already serialized in skill.json, so this adds no meaningful weight.
            "param_spec": spec.param_spec,
        },
        "params": resolved_params(spec, params),
        "input": {
            "filename": filename,
            "sha256": sha256_file(data_path),
            "n_bytes": os.path.getsize(data_path),
        },
        "environment": environment_snapshot(),
    }
    if actions is not None:
        bundle["actions"] = actions
    return bundle

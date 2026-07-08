"""Stub-vs-real engine selection, shared by the B2 skills.

Every skill ships TWO engines behind one entrypoint:

  * STUB — a dependency-free, deterministic Plotly spec, so the contract / golden
    tests and the light skeleton run end-to-end with ZERO heavy deps.
  * REAL — the genuine analysis (scanpy / pydeseq2 / pandas), lazy-imported only
    when actually selected.

Selection via ``SELOM_SKILLS_ENGINE`` (default ``auto``):
  auto  -> real iff every required module is importable, else stub
  real  -> force real (raises later if a dep is missing)
  stub  -> force stub  (what the golden tests pin, for determinism)
"""

from importlib.util import find_spec

# The union of heavy scientific modules any skill gates its real engine on (the args every
# ``use_real_engine(...)`` call passes). If ONE of these is missing under ``auto``, the skills
# that need it silently fall back to a fabricated stub figure — the fake-science landmine WS1.1
# guards (RISKS #11). ``numpy``/``pandas`` are core (always present) but listed so the drift-guard
# test (``test_engine_policy_guard``) stays a complete mirror of the skill gates.
REQUIRED_ENGINE_MODULES = (
    "scanpy",
    "pydeseq2",
    "scipy",
    "sklearn",
    "gseapy",
    "networkx",
    "numpy",
    "pandas",
)


def use_real_engine(*required_modules: str) -> bool:
    from config import settings  # lazy: avoids a config<->_engine import cycle at construction

    engine = settings.skills_engine().lower()
    if engine == "stub":
        return False
    if engine in ("real", "scanpy"):
        return True
    return all(find_spec(m) is not None for m in required_modules)


def missing_engine_modules() -> list[str]:
    """Which of ``REQUIRED_ENGINE_MODULES`` are NOT importable in this environment."""
    return [m for m in REQUIRED_ENGINE_MODULES if find_spec(m) is None]


def resolve_engine_policy(engine: str | None = None) -> str:
    """The globally-resolved engine posture — ``"real"`` or ``"stub"`` — mirroring the decision
    ``use_real_engine`` makes per skill, so a figure's provenance can honestly say whether it was
    computed or fabricated.

    ``engine`` is the raw ``SELOM_SKILLS_ENGINE`` selector; when ``None`` it is live-read via
    ``config.settings.skills_engine()`` (the single env-reader home). The config boot guard passes
    the value explicitly because the ``settings`` singleton is not yet bound during construction.

    * ``stub``  — forced ``SELOM_SKILLS_ENGINE=stub``, OR ``auto`` with a required module missing
      (so some skills fall back to a synthetic figure). Conservative: a partial install marks the
      whole process ``stub`` (over-warn, never under-warn) — the prod boot guard forbids reaching
      that state off-dev anyway.
    * ``real``  — forced ``real``/``scanpy``, OR ``auto`` with the full stack importable. (Forced
      ``real`` with a dep genuinely missing raises an honest ImportError inside the runner — an
      error, not a fabricated figure — so it is never mislabelled ``stub``.)
    """
    if engine is None:
        from config import settings  # lazy: avoids a config<->_engine import cycle at construction

        engine = settings.skills_engine()
    engine = engine.lower()
    if engine == "stub":
        return "stub"
    if engine in ("real", "scanpy"):
        return "real"
    return "stub" if missing_engine_modules() else "real"


def to_bool(value) -> bool:
    """Coerce a param to bool. Query-string params arrive as strings, so plain
    ``bool("false")`` (truthy) is wrong — interpret the usual truthy spellings."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")

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

import os
from importlib.util import find_spec


def use_real_engine(*required_modules: str) -> bool:
    engine = os.environ.get("SELOM_SKILLS_ENGINE", "auto").lower()
    if engine == "stub":
        return False
    if engine in ("real", "scanpy"):
        return True
    return all(find_spec(m) is not None for m in required_modules)

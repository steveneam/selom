"""Reproduction engine package.

Folded from the flat ``reproduction*.py`` family (repo-structure plan §3A). The engine
spine + models live in :mod:`reproduction.core`; this ``__init__`` re-exports that public
surface so the ~14 ``import reproduction as R`` / ``from reproduction import X`` consumers
keep working unchanged after the flat→package move (contract-frozen fold).

Submodules (import by their dotted path, e.g. ``from reproduction.drive import reproduce``):
  core      — models + scoring spine (was ``reproduction.py``)
  drive     — live-reproduction orchestration (was ``reproduction_drive.py``)
  runs      — run lifecycle over a drive (was ``reproduction_runs.py``)
  fixtures  — auto-drive regression snapshots (was ``reproduction_fixtures.py``)
  guards    — classification guards (was ``reproduction_guards.py``)
  diagnose  — cold-drive gap report, dev/diagnostic (was ``reproduction_diagnose.py``)
  papers/   — per-paper captured ledgers (rpgrip1 · jev · hani · dorgau)
"""

from .core import *  # noqa: F401,F403 — re-export the engine surface (`import reproduction as R`)

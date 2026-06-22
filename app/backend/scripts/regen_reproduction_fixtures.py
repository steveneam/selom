"""Regenerate the auto-drive regression fixtures (Slice 4) from the staged papers.

Cold-drives each blessed paper through ``reproduce()`` and writes its frozen
:class:`reproduction_fixtures.DriveSnapshot` to ``tests/fixtures/reproduction/<paper>.json``. This is
the **bless / refresh** step — run it on a machine where the paper PDFs + supplements are staged
(owner-only paths below), review the JSON diff, and commit. The committed snapshots are then the
regression anchors the opt-in real re-drive test asserts against (``tests/test_reproduction_fixtures``).

  uv-run-free (EDR stub) — from app/backend:
    $env:PYTHONPATH = "D:\\selom\\app\\backend\\.venv\\Lib\\site-packages;D:\\selom\\app\\backend"
    & $PY -m scripts.regen_reproduction_fixtures            # all staged papers
    & $PY -m scripts.regen_reproduction_fixtures hani jev   # a subset

A paper whose main PDF is not present is skipped (not an error) — so this runs cleanly anywhere and
only refreshes what is locally stageable. **Adding a paper = one entry in FIXTURE_PAPERS** (the
copy-paste pattern, DoD). RPGRIP1 has an entry but no PDF on this machine — it stays a documented
slot until its PDF is staged (``tests/fixtures/reproduction/README.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_DATA = r"C:\Users\seamegdool\Desktop\Claude code and website tips\Data"

# paper_id -> (main PDF, [ (supplement path, role) ... ]). Owner-machine absolute paths, mirroring
# the existing live-ledger tests. The supplements are the tabular files the matcher can see.
FIXTURE_PAPERS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "jev": (
        _DATA + r"\Adrian\JEV2-12-12393.pdf",
        [(_DATA + r"\Adrian\JEV2-12-12393-s001.xlsx", "tables")],
    ),
    "hani": (
        _DATA + r"\Hani\1-s2.0-S2213671122005914-main.pdf",
        [(_DATA + r"\Hani\1-s2.0-S2213671122005914-mmc2.csv", "tables"),
         (_DATA + r"\Hani\1-s2.0-S2213671122005914-mmc3.csv", "tables")],
    ),
    "dorgau": (
        _DATA + r"\Dorgau\Single-cell analyses reveal transient retinal progenitor cells in the "
                r"ciliary margin of developing human retina.pdf",
        [(_DATA + r"\Dorgau\Source Data.xlsx", "tables"),
         (_DATA + r"\Dorgau\Supplementary Data 2.xlsx", "tables")],
    ),
    # RPGRIP1 (Loi 2025): no PDF staged on this machine — documented slot, fill when staged.
    "rpgrip1": ("", []),
}

# tests/fixtures/reproduction/ relative to this script (scripts/ -> app/backend -> tests/...).
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "reproduction"


def regen(paper_id: str) -> Path | None:
    """Cold-drive one paper and write its snapshot; return the path, or ``None`` if not stageable."""
    from reproduction_drive import reproduce
    from reproduction_fixtures import save_snapshot, snapshot

    main, supplements = FIXTURE_PAPERS[paper_id]
    if not main or not Path(main).exists():
        print(f"  skip {paper_id}: main PDF not present ({main or '(no path)'})", flush=True)
        return None
    result = reproduce(main, supplements, paper_id=paper_id)
    snap = snapshot(result, paper_id=paper_id)
    path = save_snapshot(snap, FIXTURE_DIR / f"{paper_id}.json")
    print(f"  wrote {path.name}: {snap.summary} (driven={snap.n_driven}, "
          f"defects={snap.selom_defects})", flush=True)
    return path


def main(argv: list[str]) -> None:
    wanted = argv or list(FIXTURE_PAPERS)
    print(f"regen reproduction fixtures -> {FIXTURE_DIR}", flush=True)
    for paper_id in wanted:
        if paper_id not in FIXTURE_PAPERS:
            print(f"  ?? unknown paper {paper_id!r} (known: {', '.join(FIXTURE_PAPERS)})", flush=True)
            continue
        regen(paper_id)


if __name__ == "__main__":  # pragma: no cover — dev/bless harness, owner-machine data
    main(sys.argv[1:])

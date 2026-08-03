"""Regenerate the B2 stub golden snapshots.

    uv run --directory app/backend python tests/regen_golden.py

Writes ``tests/golden/<skill>.json`` from each skill's dependency-free stub. Run
after an INTENTIONAL change to a stub figure; review the diff before committing.
"""

import json
import os
import pathlib
import sys

os.environ["SELOM_SKILLS_ENGINE"] = "stub"
os.environ["SELOM_UMAP_ENGINE"] = "stub"   # umap_scrna has its own selector; must match the test's
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from skills.contract import run_skill  # noqa: E402

# The list lives in the TEST, which is the enforcement point, and is imported here rather than
# copied. It used to be duplicated in both files: adding a skill to one and not the other either
# writes a snapshot nothing asserts on, or asserts on a snapshot this script never regenerates.
# `test_every_installed_skill_has_a_golden` now covers this script too, for free.
from tests.test_skills_golden import SKILLS  # noqa: E402


def main() -> None:
    out = pathlib.Path(__file__).parent / "golden"
    out.mkdir(exist_ok=True)
    for skill_id in SKILLS:
        figure = run_skill(skill_id, "unused", {})
        (out / f"{skill_id}.json").write_text(json.dumps(figure, indent=2) + "\n")
        print(f"wrote golden/{skill_id}.json")


if __name__ == "__main__":
    main()

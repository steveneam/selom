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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from skills.contract import run_skill  # noqa: E402

SKILLS = [
    "cluster", "violin", "deg", "volcano", "heatmap", "enrichment", "go_graph", "pathway",
    "markers", "annotate", "trajectory", "pca", "composition", "proteomics_de", "gsea",
    "corr_heatmap", "upset", "scorecard", "normalization_qc", "sankey", "string_network",
    "cepo", "boxplot", "pvca", "regression", "integration", "pseudotime_genes",
    "diff_abundance", "ssgsea",
]


def main() -> None:
    out = pathlib.Path(__file__).parent / "golden"
    out.mkdir(exist_ok=True)
    for skill_id in SKILLS:
        figure = run_skill(skill_id, "unused", {})
        (out / f"{skill_id}.json").write_text(json.dumps(figure, indent=2) + "\n")
        print(f"wrote golden/{skill_id}.json")


if __name__ == "__main__":
    main()

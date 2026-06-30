"""Entrypoint for the mixing_metrics skill — stub vs real engine dispatch.

The real engine (``run_real.py``) reads the AnnData, resolves an embedding + batch/label
vectors, and calls the pure ``metrics.compute_all``. The stub here is a dependency-free
deterministic bar chart + Statistics table of plausible metric values, so the contract /
golden tests and the light skeleton run end-to-end with ZERO heavy deps.
"""

from skills._engine import use_real_engine
from skills._table import table


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.mixing_metrics.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


# Deterministic plausible values for a well-integrated 2-batch dataset WITH cell-type labels —
# enough to render the bar + table contract without any heavy dependency.
_STUB_ROWS = [
    ("iLISI (batch)", 1.78, "↑ mixing"),
    ("cLISI (label)", 1.06, "↓ separation"),
    ("kBET acceptance", 0.82, "↑ mixing"),
    ("ARI", 0.91, "↑ agreement"),
    ("NMI", 0.88, "↑ agreement"),
    ("ASW batch", 0.74, "↑ mixing"),
    ("ASW label", 0.69, "↑ separation"),
]


def _stub_figure() -> dict:
    labels = [r[0] for r in _STUB_ROWS]
    values = [r[1] for r in _STUB_ROWS]
    spec = {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": values,
                "y": labels,
                "name": "mixing metrics",
            }
        ],
        "layout": {
            "title": {"text": "Integration mixing metrics (stub)"},
            "xaxis": {"title": {"text": "score"}},
        },
    }
    spec["table"] = table(
        ["metric", "value", "direction", "note"],
        [[m, v, d, ""] for (m, v, d) in _STUB_ROWS],
        title="Integration mixing metrics",
    )
    return spec

"""Reproduction Engine — the threshold/contrast sweep (build-plan R3, loop stage 9).

When a *count* golden misses (e.g. RPGRIP1 Fig 5's signature = 78/181, down-in-both = 49),
the SOP sweeps the setting grid — contrast × stat(raw/adj) × threshold × direction × lfc —
to either **pin the authors' undocumented choice** that reproduces the printed number, or
**prove it irreproducible** (SOP step 9 / guard 1). This is the deterministic codification
of the manual ``fig5_sweep*.py`` scratch scripts.

Pure-Python, no heavy deps: it operates on already-loaded DE rows (``list[dict]`` with a
gene key + ``lfc`` and the stat columns), so the caller owns CSV/DataFrame loading and this
stays unit-testable on fixtures. The sweep produces a :class:`reproduction.Sweep` and, when
the *stated* method does not yield the printed number, the ``methods_vs_numbers``
:class:`reproduction.Inconsistency` (the Fig 5 headline → ``blame: paper-irreproducible``).
"""

from __future__ import annotations

from itertools import product

from reproduction import Inconsistency, Ledger, Panel, Sweep, SweepCell

# The default grid — the axes the dogfood swept (fig5_sweep2.py).
DEFAULT_STATS = ("padj", "p")
DEFAULT_THRESHOLDS = (0.01, 0.05, 0.1, 0.15, 0.2)
DEFAULT_LFC_MINS = (0.0, 0.585, 1.0)  # 0, 1.5x, 2x
DEFAULT_DIRECTIONS = ("any", "up", "down")


def _passes(row: dict, stat: str, thr: float, direction: str, lfc_min: float) -> bool:
    """Does one DE row clear the (stat, threshold, direction, |lfc|) gate?"""
    val = row.get(stat)
    lfc = row.get("lfc")
    if val is None or lfc is None:
        return False
    if not (val < thr):
        return False
    if abs(lfc) < lfc_min:
        return False
    if direction == "up":
        return lfc > 0
    if direction == "down":
        return lfc < 0
    return True


def signature_set(
    rows, universe, *, stat: str, thr: float, direction: str = "any",
    lfc_min: float = 0.0, gene_key: str = "gene",
) -> set:
    """Genes in ``universe`` that clear the gate (universe ∩ significant) — the scratch
    ``sigset`` restricted to the deterministic universe (SOP rule 3)."""
    uni = set(universe)
    return {
        r[gene_key]
        for r in rows
        if r.get(gene_key) in uni and _passes(r, stat, thr, direction, lfc_min)
    }


def signature_count(rows, universe, **kw) -> int:
    return len(signature_set(rows, universe, **kw))


def _cell_value(
    contrasts: dict[str, list], universe, *,
    contrast: str | None, intersect: tuple[str, str] | None,
    stat: str, thr: float, direction: str, lfc_min: float, gene_key: str,
) -> int:
    """The count at one grid point — a single contrast, or the intersection of two
    (the down-in-both case: RPGRIP1 Fig 5's 49 = signature down in BOTH contrasts)."""
    kw = dict(stat=stat, thr=thr, direction=direction, lfc_min=lfc_min, gene_key=gene_key)
    if intersect is not None:
        a, b = intersect
        return len(signature_set(contrasts[a], universe, **kw)
                   & signature_set(contrasts[b], universe, **kw))
    return signature_count(contrasts[contrast], universe, **kw)


def run_sweep(
    panel_key: str,
    golden_metric: str,
    golden_value: int,
    contrasts: dict[str, list],
    universe,
    *,
    contrast: str | None = None,
    intersect: tuple[str, str] | None = None,
    stated_setting: dict | None = None,
    stats=DEFAULT_STATS,
    thresholds=DEFAULT_THRESHOLDS,
    lfc_mins=DEFAULT_LFC_MINS,
    directions=DEFAULT_DIRECTIONS,
    gene_key: str = "gene",
    int_tol: int = 0,
    printed_in: str = "figure",
) -> tuple[Sweep, Inconsistency | None]:
    """Sweep the grid for one count golden → ``(Sweep, Inconsistency | None)``.

    Exactly one of ``contrast`` (a single named contrast) or ``intersect`` (two names,
    down/up-in-both) selects what each cell counts. The first grid point whose count
    equals ``golden_value`` (within ``int_tol``) is the ``reproducing_setting``; if none
    does, ``irreproducible=True``. ``stated_setting`` (the paper's documented method, e.g.
    ``{"stat": "padj", "thr": 0.05, "direction": "any", "lfc_min": 0.0}``) is evaluated
    separately: when the printed number is **not** what the stated method yields, a
    ``methods_vs_numbers`` :class:`Inconsistency` is returned (guard 1) — the engine never
    silently adopts whatever unstated threshold "works"."""
    if (contrast is None) == (intersect is None):
        raise ValueError("pass exactly one of contrast= or intersect=")

    def value_at(stat, thr, direction, lfc_min):
        return _cell_value(
            contrasts, universe, contrast=contrast, intersect=intersect,
            stat=stat, thr=thr, direction=direction, lfc_min=lfc_min, gene_key=gene_key,
        )

    grid: list[SweepCell] = []
    reproducing: dict | None = None
    base = {"contrast": contrast or f"{intersect[0]}∩{intersect[1]}"}
    for stat, thr, lfc_min, direction in product(stats, thresholds, lfc_mins, directions):
        setting = {**base, "stat": stat, "thr": thr, "direction": direction, "lfc_min": lfc_min}
        val = value_at(stat, thr, direction, lfc_min)
        grid.append(SweepCell(setting=setting, value=val))
        if reproducing is None and abs(val - golden_value) <= int_tol:
            reproducing = setting

    stated_value = None
    if stated_setting is not None:
        s = {"stat": "padj", "thr": 0.05, "direction": "any", "lfc_min": 0.0, **stated_setting}
        stated_value = value_at(s["stat"], s["thr"], s["direction"], s["lfc_min"])

    sweep = Sweep(
        panel_key=panel_key,
        golden_metric=golden_metric,
        golden_value=golden_value,
        axes=["contrast", "stat", "thr", "direction", "lfc_min"],
        grid=grid,
        stated_setting=stated_setting,
        stated_value=stated_value,
        reproducing_setting=reproducing,
        irreproducible=reproducing is None,
    )

    inconsistency = None
    stated_misses = stated_setting is not None and abs((stated_value or 0) - golden_value) > int_tol
    if stated_misses:
        if reproducing is None:
            note = (f"printed {golden_metric}={golden_value} is unreachable on the deposited "
                    f"data at any swept setting; the stated method yields {stated_value}")
        else:
            note = (f"printed {golden_metric}={golden_value} reproduces only at the unstated "
                    f"setting {reproducing}, not the stated {stated_setting} (={stated_value})")
        inconsistency = Inconsistency(
            kind="methods_vs_numbers",
            printed_in=[printed_in],
            conflicting_value=[str(golden_value), str(stated_value)],
            note=note,
        )
        sweep.note = note
    return sweep, inconsistency


def sweep_panel(
    ledger: Ledger,
    panel: Panel,
    golden_metric: str,
    contrasts: dict[str, list],
    universe,
    **kw,
) -> Sweep:
    """Run :func:`run_sweep` for a panel's golden and append the results to the ledger.

    The golden value is read from the panel; the resulting ``Sweep`` is appended to
    ``ledger.sweeps`` and any ``methods_vs_numbers`` ``Inconsistency`` to
    ``ledger.paper.inconsistencies`` (with cross-refs wired)."""
    gold = next((g for g in panel.golden if g.metric == golden_metric), None)
    if gold is None:
        raise ValueError(f"panel {panel.key} has no golden {golden_metric!r}")
    sweep, inconsistency = run_sweep(
        panel.key, golden_metric, int(gold.value), contrasts, universe, **kw
    )
    if inconsistency is not None:
        ref = len(ledger.paper.inconsistencies)
        ledger.paper.inconsistencies.append(inconsistency)
        sweep.inconsistency_ref = ref
        gold.inconsistency_ref = ref
    ledger.sweeps.append(sweep)
    return sweep

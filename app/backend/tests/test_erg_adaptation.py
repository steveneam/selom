"""The rod/cone label an ERG figure claims — in its TITLE, in its recorded meta, and in its prose.

Whether a full-field ERG is scotopic (rod-driven, dark-adapted) or photopic (cone-driven, against
a rod-suppressing background) is the first thing a reader needs, and Selom was resolving it three
different ways:

* the runners resolved it through ``_erg.resolve_flash_mode``, where an explicit ``stimulus_type``
  wins over the friendly ``adaptation`` hint and ``auto`` falls back to whichever mode the DATA
  carries;
* the figure titles hard-coded ``adapt or "scotopic"``, so on an export with no ``stimulus_type``
  column (the iWorx path) a run asked for ``adaptation="photopic"`` was titled *Scotopic*;
* ``companions.methods._erg_adaptation`` read ``adaptation`` alone, so a ``stimulus_type``-driven
  photopic figure got a paragraph about overnight dark-adapted mice.

One resolution now: the runner's own ``_erg.adaptation_mode`` fallback for the title, and the
data-resolved answer recorded on ``layout.meta.adaptation`` exactly when it differs from what the
parameters alone would say — the ``meta.significance`` pattern, so a default run writes nothing and
the figure is unchanged.
"""

import csv

from companions import methods
from skills.contract import load_skill

# Lane: the fast one, like `test_erg_units.py`'s end-to-end runner tests — the heavy lane is
# auto-marked BY FILE in `conftest._SLOW_FILES` and is deliberately corpus-free in CI. These drive
# the real runners on synthetic tmp_path CSVs, which is exactly the fast lane's shape.


def _waveforms(path, stimulus_types=()):
    """A minimal ``erg_waveforms_long``: 2 conditions × 1 intensity, optionally tagged with one or
    more ``stimulus_type`` values (the Diagnosys multi-mode shape)."""
    modes = list(stimulus_types) or [None]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        head = ["condition", "intensity_group", "time_ms", "voltage_uv", "intensity_log_cd_s_m2"]
        w.writerow(head + (["stimulus_type"] if stimulus_types else []))
        for mode in modes:
            for cond, amp in (("Control", 300.0), ("Untreated", 80.0)):
                for i in range(60):
                    t = i * 2.0
                    v = -0.2 * amp if 10 <= t <= 20 else (amp if 40 <= t <= 60 else 0.0)
                    row = [cond, "Group4", t, v, 1.0]
                    w.writerow(row + ([mode] if stimulus_types else []))


def _title(spec) -> str:
    return str(spec["layout"]["title"]["text"])


def _meta(spec):
    return (spec.get("layout") or {}).get("meta") or {}


def test_trace_title_follows_the_adaptation_hint_with_no_stimulus_column(tmp_path):
    """The iWorx path carries no ``stimulus_type`` column, so the runner's data-resolved label is
    empty and the title fell back to the literal "scotopic" — mislabelling a run the user explicitly
    asked to measure with cone windows."""
    from skills.proprietary.erg_traces.run_real import run

    p = tmp_path / "wave.csv"
    _waveforms(p)

    assert "scotopic" in _title(run(str(p), {}))
    assert "photopic" in _title(run(str(p), {"adaptation": "photopic"}))
    assert "photopic" in _title(run(str(p), {"stimulus_type": "photopic_flash"}))


def test_meta_adaptation_is_recorded_only_when_the_DATA_decided(tmp_path):
    """``auto`` on a photopic-only export resolves from the data — a fact no parameter can express,
    so it is recorded for the methods paragraph. When the parameters already say it (or agree with
    it), nothing is written and the figure is byte-identical to before."""
    from skills.proprietary.erg_traces.run_real import run

    photopic_only = tmp_path / "photopic.csv"
    _waveforms(photopic_only, ["photopic_flash"])
    both = tmp_path / "both.csv"
    _waveforms(both, ["scotopic_flash", "photopic_flash"])
    plain = tmp_path / "plain.csv"
    _waveforms(plain)

    # The data decided: `auto` + only photopic present → photopic, which "auto" alone cannot say.
    spec = run(str(photopic_only), {})
    assert _meta(spec).get("adaptation") == "photopic"
    assert "photopic" in _title(spec)

    # Params already agree → nothing recorded (default runs stay unchanged).
    assert "adaptation" not in _meta(run(str(both), {}))
    assert "adaptation" not in _meta(run(str(plain), {}))
    assert "adaptation" not in _meta(run(str(photopic_only), {"adaptation": "photopic"}))


def test_the_paragraph_follows_the_figure_it_describes(tmp_path):
    """End to end: the recorded mode reaches the prose through ``build_body``'s meta lift, so the
    paragraph and the title cannot disagree about rod versus cone."""
    from skills.proprietary.erg_traces.run_real import run

    p = tmp_path / "photopic.csv"
    _waveforms(p, ["photopic_flash"])
    spec = run(str(p), {})

    text = methods.build(load_skill("erg_traces"), {}, figure=spec)["text"]
    assert "photopic (cone-driven)" in text
    assert "dark-adapted mice" not in text
    assert "photopic" in _title(spec)

    # Without the figure (litsynth replaying from recorded params alone) the paragraph falls back to
    # the param-derived answer rather than inventing one.
    assert "scotopic" in methods.build(load_skill("erg_traces"), {})["text"]


def test_bar_and_intensity_response_share_the_resolution(tmp_path):
    """All three flash skills read the same helper; the bar and the curve record it too."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar
    from skills.proprietary.erg_intensity_response.run_real import run as run_ir

    p = tmp_path / "metrics.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "intensity_log_cd_s_m2", "b_wave_uv",
                    "stimulus_type"])
        for cond, vmax in (("Control", 300.0), ("Untreated", 90.0)):
            for gi, x in enumerate([-1.0, 0.0, 1.0, 2.0], start=1):
                for eye in (-3.0, 3.0):
                    w.writerow([cond, f"Group{gi}", x, vmax * (gi / 4.0) + eye, "photopic_flash"])

    bar = run_bar(str(p), {"intensity_group": "Group4"})
    assert "Photopic" in _title(bar)
    assert _meta(bar).get("adaptation") == "photopic"

    ir = run_ir(str(p), {})
    assert "Photopic" in _title(ir)
    assert _meta(ir).get("adaptation") == "photopic"

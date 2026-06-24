"""ERG flicker — the steady-state periodic-response figure the flash trace grid can't make.
Proprietary ERG module (docs/diagnosys-erg/spec.md, R-flicker).

Two editable views of one skill (D3 in the spec — flicker's graph + metric differ enough from a
flash trace to be its own skill):

* ``view="waveform"`` (default) — small-multiples of the steady-state flicker waveform (flicker
  frequency down the rows, conditions across the columns), via the shared ``_tracegrid`` primitive.
* ``view="summary"`` — N1→P1 amplitude versus flicker frequency, one line per condition (the
  structural sibling of ``erg_intensity_response`` but x = frequency and **no Naka-Rushton** — a
  flicker series is not an intensity-saturation curve).

The flicker metric is **N1→P1 peak-to-trough** measured on the phase-averaged steady-state cycle
(``_erg.flicker_landmarks``); no a-/b-wave language. Both views attach a per-condition N1/P1 table
(native — Pillar 1). Stub = a dependency-free synthetic grid (golden-stable); real path
(``run_real``) reads the long ERG waveform table.
"""
import math

from skills import _erg
from skills._table import table
from skills._tracegrid import grid_spec

# Synthetic stub: a 3-condition × 2-frequency flicker grid telling the 3-way story
# (Control ≫ rescue > Untreated), each frequency attenuating the response.
_STUB_CONDS = ["Control", "Untreated", "AAV8-RK-PDE6B-3UTR"]
_STUB_FREQS = [10.0, 30.0]
# N1→P1 half-amplitude (µV) per condition at 10 Hz; 30 Hz attenuates (cone temporal roll-off).
_STUB_AMP = {"Control": 12.0, "Untreated": 3.0, "AAV8-RK-PDE6B-3UTR": 7.0}
_FREQ_GAIN = {10.0: 1.0, 30.0: 0.45}


def run(data_path: str, params: dict) -> dict:
    from skills._engine import use_real_engine

    if use_real_engine("pandas", "numpy"):
        from skills.proprietary.erg_flicker.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


# ---- shared builders (stub + real) -----------------------------------------------------
def flicker_grid(panels, *, nrows, ncols, row_labels, col_labels, params,
                 unit="µV", factor=1.0, title="Flicker ERG"):
    """The steady-state waveform small-multiples (one trace per condition × frequency)."""
    return grid_spec(
        panels, nrows=nrows, ncols=ncols,
        scalebar={"x_len": float(params.get("scale_ms", 50.0)), "x_unit": "ms",
                  "y_len": float(params.get("scale_uv", 20.0)) * factor, "y_unit": unit},
        row_labels=row_labels, col_labels=col_labels, title=title,
    )


def freq_spec(cond_series, *, unit="µV", factor=1.0, title="Flicker N1→P1 vs frequency"):
    """Editable N1→P1-amplitude-versus-frequency spec (shared by stub + real).

    ``cond_series`` = ordered list of ``(condition, freqs_hz, amps_uv)``. Per condition: a
    markers+line trace of N1→P1 amplitude against flicker frequency. ``unit``/``factor`` set the
    amplitude display unit (default µV, factor 1.0). No fit — flicker is not a saturation curve."""
    data = []
    for cond, freqs, amps in cond_series:
        color = _erg.COLORS.get(cond, "#888888")
        label = _erg.COL_LABELS.get(cond, cond).replace("<br>", " ")
        data.append({
            "type": "scatter", "mode": "lines+markers",
            "x": [round(float(f), 3) for f in freqs],
            "y": [_erg.disp_round(v, factor) for v in amps],
            "marker": {"color": color, "size": 8, "line": {"color": "#ffffff", "width": 0.6}},
            "line": {"color": color, "width": 1.6},
            "name": label, "legendgroup": cond, "hoverinfo": "x+y+name",
        })
    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": "flicker frequency (Hz)"}},
        "yaxis": {"title": {"text": f"N1–P1 amplitude ({unit})"}, "rangemode": "tozero"},
        "legend": {"title": {"text": "condition"}},
        "showlegend": True, "plot_bgcolor": "white",
    }
    return {"data": data, "layout": layout}


def flicker_table(rows, unit="µV", *, source="Selom", provenance=""):
    """Per (condition × frequency) N1/P1 table. ``rows`` = ``[cond, hz, n1p1, p1_ms, n]``.
    ``source`` notes whether the metric came from the device markers or Selom's re-derivation;
    ``provenance`` (erg-manual-marks R6) optionally appends an operator-adjusted count to the
    caption (empty → byte-identical title)."""
    title = f"Flicker N1→P1 ({source}-measured{provenance})"
    return table([
        "condition", "frequency (Hz)", f"N1→P1 ({unit})", "P1 implicit (ms)", "n (eyes)",
    ], rows, title=title)


# ---- stub ------------------------------------------------------------------------------
def _stub_wave(t_ms: float, freq: float, half_amp: float) -> float:
    """A synthetic steady-state flicker cycle: a sinusoid at ``freq`` (corneal-negative first)."""
    return round(-half_amp * math.sin(2.0 * math.pi * freq * t_ms / 1000.0), 3)


def _stub_figure(params: dict) -> dict:
    view = str(params.get("view", "waveform")).strip().lower()
    times = list(range(0, 201, 2))  # one shared 200 ms window; 30 Hz simply shows more cycles
    tbl_rows = []
    # Native N1/P1 table (both views): peak-to-trough = 2 × half-amplitude; P1 at the quarter cycle.
    series = {}
    for cond in _STUB_CONDS:
        freqs, amps = [], []
        for freq in _STUB_FREQS:
            ha = _STUB_AMP[cond] * _FREQ_GAIN[freq]
            n1p1 = round(2.0 * ha, 3)
            p1_ms = round(1000.0 / freq * 0.75, 1)  # trough at quarter, peak at three-quarter cycle
            tbl_rows.append([cond, freq, n1p1, p1_ms, 4])
            freqs.append(freq)
            amps.append(n1p1)
        series[cond] = (freqs, amps)

    if view == "summary":
        cond_series = [(c, series[c][0], series[c][1]) for c in _STUB_CONDS]
        spec = freq_spec(cond_series, title="Flicker N1→P1 vs frequency (stub)")
        spec["table"] = flicker_table(tbl_rows)
        return spec

    panels = []
    for r, freq in enumerate(_STUB_FREQS):
        for c, cond in enumerate(_STUB_CONDS):
            ha = _STUB_AMP[cond] * _FREQ_GAIN[freq]
            panels.append({
                "row": r, "col": c, "x": times,
                "y": [_stub_wave(t, freq, ha) for t in times],
                "color": _erg.COLORS[cond], "name": f"{cond} {freq:g}Hz", "group": cond,
            })
    spec = flicker_grid(
        panels, nrows=len(_STUB_FREQS), ncols=len(_STUB_CONDS),
        row_labels=[f"{f:g} Hz" for f in _STUB_FREQS],
        col_labels=[_erg.COL_LABELS[c] for c in _STUB_CONDS],
        params=params, title="Flicker ERG (stub)")
    spec["table"] = flicker_table(tbl_rows)
    return spec

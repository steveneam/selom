"""Reconstruction stage (X2, Track B) — redraw an editable figure + SSIM self-QA.

The extraction front-half (X1) turns a paper into a target spec; X2 closes the loop on the
*figure itself*: take a panel's chart form + the recovered data, **redraw it as an editable Plotly
spec** (the same wire shape every Selom skill emits, so the figure editor opens it), render that to
pixels, and **self-QA by structural similarity (SSIM)** against the original panel raster. SSIM is
the confidence signal — "did we reconstruct what the authors drew?" — and the gate for the
human-confirm step (E4).

Two halves, split exactly like the engine's CI-safe core vs gated oracle:

* **SSIM core** — pure numpy (box-window SSIM, no scipy/skimage), so it is CI-safe and unit-tested.
* **render + redraw** — Plotly redraw is pure dict construction; rendering to PNG needs Kaleido
  (system Chrome, no Docker), so :func:`render_spec` degrades cleanly when it is unavailable and
  the render→SSIM-vs-original loop is the owner-machine dogfood.

Open-Q#3 (the SSIM acceptance band) is **RESOLVED by calibration** on real RPGRIP1 Fig-6 panels
(2026-06-18). The finding is not a threshold but a *correction of what SSIM measures here*: SSIM is
a **registered** (pixel-aligned) metric. On genuinely-equivalent redraw-vs-publisher-scan pairs it
scored 0.66–0.76, while *different* panels scored 0.74–0.78 — i.e. the negative controls scored
HIGHER, because a freshly-laid-out Plotly redraw is not spatially registered to the scan and the
whole-panel score is dominated by shared whitespace + gross layout, not figure identity (content-
weighting and content-bbox cropping did not separate them either). So SSIM-vs-scan is demoted to an
**advisory** signal (never a pass/fail), and the bands below are calibrated to the regime where SSIM
*is* valid: **registered** comparisons (re-render integrity / corruption detection), anchored by the
controls identity=1.00 and blur-3px=0.85. The faithfulness of a redraw to the authors' figure is
judged by the **golden-target match** (Venn counts, %, gene-set sizes — the engine's job), not pixels.
"""

from __future__ import annotations

import io

import numpy as np
from pydantic import BaseModel

from skills._plotly import jsonable
from skills.theme import apply as apply_theme

# --- SSIM bands (open-Q#3 — CALIBRATED on real RPGRIP1 Fig-6 panels 2026-06-18) ---------------
# These gate only **registered** comparisons (re-render of the same spec / corruption detection),
# the regime where SSIM is meaningful. Anchored by the calibration controls: identity = 1.00,
# Gaussian-blur-3px = 0.85 (visible-but-recognizable degradation), inverted/white-vs-black ≈ 0.
# A redraw vs an UNREGISTERED publisher scan is advisory only (see :func:`self_qa`, registered=False):
# calibration measured equivalent pairs at 0.66–0.76 vs different-panel pairs at 0.74–0.78, so no
# scan-comparison threshold can separate right from wrong — acceptance there lives in the golden match.
SSIM_EQUIVALENT = 0.95   # registered + near-identical (re-render integrity; allows antialiasing jitter)
SSIM_PLAUSIBLE = 0.80    # registered + recognizably the same, degraded (blur-3px=0.85 lands here)
SSIM_ACCEPT = SSIM_PLAUSIBLE   # accept floor for REGISTERED comparisons only


class ReconstructionQA(BaseModel):
    """The self-QA verdict for one reconstructed panel: its SSIM, the band it falls in, and whether
    it clears the accept floor. ``accepted`` is ``None`` for an **unregistered** scan comparison
    (advisory only — SSIM cannot gate a redraw against a publisher scan; see the module docstring)."""

    panel_key: str = ""
    ssim: float
    band: str                  # "equivalent" | "plausible" | "divergent"
    accepted: bool | None      # bool for a registered comparison; None when advisory (scan)
    registered: bool = True    # False = compared against an unregistered publisher scan (advisory)
    note: str = ""


# --- SSIM core (pure numpy; CI-safe) ------------------------------------------


def _to_gray(arr: np.ndarray) -> np.ndarray:
    """HxW or HxWxC uint8/float → float64 luminance HxW."""
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim == 3:
        a = a[..., :3] @ np.array([0.299, 0.587, 0.114])
    return a


def _box_sum(x: np.ndarray, win: int) -> np.ndarray:
    """Sum over every ``win``×``win`` window, via a summed-area table (O(n), exact, no deps)."""
    ii = np.pad(x, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return ii[win:, win:] - ii[:-win, win:] - ii[win:, :-win] + ii[:-win, :-win]


def ssim(a: np.ndarray, b: np.ndarray, *, win: int = 7, data_range: float = 255.0) -> float:
    """Mean structural similarity between two equal-shape images (Wang et al. 2004), box window.

    Returns a scalar in [-1, 1] (1.0 = identical). Inputs are converted to luminance; they must be
    the same shape (resize first — see :func:`self_qa`). Box-window rather than Gaussian to stay
    pure-numpy; the difference is immaterial for a coarse faithfulness signal."""
    a = _to_gray(a)
    b = _to_gray(b)
    if a.shape != b.shape:
        raise ValueError(f"SSIM needs equal shapes, got {a.shape} vs {b.shape}")
    win = max(1, min(win, *a.shape))
    n = win * win
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    mu_a = _box_sum(a, win) / n
    mu_b = _box_sum(b, win) / n
    mu_aa = _box_sum(a * a, win) / n
    mu_bb = _box_sum(b * b, win) / n
    mu_ab = _box_sum(a * b, win) / n
    va = mu_aa - mu_a ** 2
    vb = mu_bb - mu_b ** 2
    vab = mu_ab - mu_a * mu_b
    smap = ((2 * mu_a * mu_b + c1) * (2 * vab + c2)) / \
           ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2))
    return float(smap.mean())


def _band(score: float) -> str:
    if score >= SSIM_EQUIVALENT:
        return "equivalent"
    if score >= SSIM_PLAUSIBLE:
        return "plausible"
    return "divergent"


def _load_gray(png: bytes) -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype=np.float64)


def self_qa(original_png: bytes, reconstructed_png: bytes, *, panel_key: str = "",
            accept: float = SSIM_ACCEPT, registered: bool = True) -> ReconstructionQA:
    """SSIM self-QA of a reconstruction against a reference raster (both PNG bytes).

    The reconstruction is resized to the reference's dimensions, greyscaled, and scored.

    ``registered`` declares whether the two images are pixel-aligned:

    * ``True`` (default) — a **registered** comparison (a re-render of the same spec, or a synthetic
      reference). SSIM is meaningful: ``accepted`` is ``score >= accept`` and gates the human-confirm
      step (E4).
    * ``False`` — the reference is an **unregistered publisher scan**. Per the open-Q#3 calibration
      (equivalent pairs 0.66–0.76 vs different-panel pairs 0.74–0.78 — overlapping, NEG above EQ), SSIM
      cannot separate a faithful redraw from a wrong one here, so the verdict is **advisory**:
      ``accepted`` is ``None`` and faithfulness is decided by the golden-target match, not this score."""
    from PIL import Image

    orig = _load_gray(original_png)
    recon_img = Image.open(io.BytesIO(reconstructed_png)).convert("L")
    h, w = orig.shape
    recon = np.asarray(recon_img.resize((w, h)), dtype=np.float64)
    score = ssim(orig, recon)
    band = _band(score)
    if registered:
        return ReconstructionQA(
            panel_key=panel_key, ssim=round(score, 4), band=band, accepted=score >= accept,
            registered=True,
            note=f"SSIM {score:.3f} vs reference ({band}; registered accept floor {accept})")
    return ReconstructionQA(
        panel_key=panel_key, ssim=round(score, 4), band=band, accepted=None, registered=False,
        note=(f"SSIM {score:.3f} vs UNREGISTERED scan — ADVISORY only (a redraw is not pixel-"
              f"registered to a publisher scan; calibration showed this cannot gate). Decide "
              f"faithfulness by the golden-target match."))


# --- editable redraw (Track B) ------------------------------------------------


def reconstruct_panel(chart_form: str, data: dict, *, title: str = "", style: str = "selom") -> dict:
    """Redraw a panel from its recovered data into an editable Plotly spec (the wire shape every
    Selom skill emits, themed). Supports the common reconstructable forms; raises for the rest
    (chart→data recovery for bar/line scans is X4).

    ``data`` per form:
      * ``volcano``      → ``{"log2fc": [...], "neg_log10_p": [...], "category": [...]}``
      * ``bar``/``stacked_bar`` → ``{"x": [...], "series": {name: [values]}}``
      * ``heatmap``      → ``{"z": [[...]], "x": [...], "y": [...]}``
    """
    import plotly.graph_objects as go

    form = chart_form.lower()
    if form == "volcano":
        cats = data.get("category") or ["hit"] * len(data["log2fc"])
        fig = go.Figure()
        for cat in dict.fromkeys(cats):
            idx = [i for i, c in enumerate(cats) if c == cat]
            fig.add_scatter(
                x=[data["log2fc"][i] for i in idx],
                y=[data["neg_log10_p"][i] for i in idx],
                mode="markers", name=str(cat))
        fig.update_layout(xaxis_title="log2 fold change", yaxis_title="-log10 p")
        skill = "volcano"
    elif form in ("bar", "stacked_bar", "composition"):
        fig = go.Figure()
        for name, ys in data["series"].items():
            fig.add_bar(x=data["x"], y=ys, name=str(name))
        fig.update_layout(barmode="stack" if form != "bar" else "group")
        skill = "composition"
    elif form == "heatmap":
        fig = go.Figure(go.Heatmap(z=data["z"], x=data.get("x"), y=data.get("y")))
        skill = "heatmap"
    else:
        raise ValueError(
            f"reconstruct_panel does not redraw '{chart_form}' (text-recoverable forms only; "
            f"bar/line chart->data recovery is X4)")
    if title:
        fig.update_layout(title=title)
    return apply_theme(jsonable(fig.to_dict()), skill, style)


def render_spec(spec: dict, *, width: int = 700, height: int = 500, scale: float = 1.0) -> bytes:
    """Render a Plotly spec to PNG bytes (Kaleido; system Chrome, no Docker). Degrades cleanly with
    an actionable error if Kaleido isn't available — the render→SSIM-vs-original loop is the
    owner-machine dogfood, like the gated R-oracle."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("reconstruction render needs plotly (uv sync --extra omics)") from exc
    fig = go.Figure(spec)
    try:
        return fig.to_image(format="png", width=width, height=height, scale=scale)
    except Exception as exc:  # pragma: no cover - Kaleido/Chrome not available in this profile
        raise RuntimeError(
            "could not render the reconstruction to PNG — Kaleido (system Chrome) is required; "
            "the render→SSIM-vs-original self-QA is the owner-machine dogfood"
        ) from exc


def reconstruct_and_qa(chart_form: str, data: dict, original_png: bytes, *, panel_key: str = "",
                       title: str = "", style: str = "selom",
                       registered: bool = False) -> tuple[dict, ReconstructionQA]:
    """Full Track-B loop for one panel: redraw → render → SSIM self-QA against ``original_png``.
    Returns the editable spec + the QA verdict. Needs Kaleido (gated; see :func:`render_spec`).

    ``registered`` defaults to ``False`` because ``original_png`` is normally the **publisher scan**
    (unregistered → advisory SSIM, open-Q#3). Pass ``registered=True`` only when ``original_png`` is a
    re-render of the same spec (an integrity check, where SSIM gates)."""
    spec = reconstruct_panel(chart_form, data, title=title, style=style)
    recon_png = render_spec(spec)
    qa = self_qa(original_png, recon_png, panel_key=panel_key, registered=registered)
    return spec, qa

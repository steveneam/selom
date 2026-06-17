"""Chart → data recovery (X4) — recover the numeric series behind a bar/line/scatter panel raster.

For panels where the data must be **recovered from the published image** because there is no raw
input to recompute from (a scanned bar/line/scatter with no deposited table). This is the clean-room,
Selom-native build of the WebPlotDigitizer / ClawBio ``data-extractor`` model (decision E6): an
explicit **axis calibration** (two known reference points per axis → a pixel↔data map, linear or log)
plus a per-form pixel reader. Library-only — numpy + scipy.ndimage + Pillow (all BSD/HPND). The ML
route (DePlot/MatCha/LineFormer) is deliberately **not** a shipped dependency.

HONEST CEILING (sub-spec ceiling #4 + the open-Q#3 lesson — never overclaim):

* Recovery needs **calibration**: the pixel→data mapping is not guessable from pixels alone, so the
  caller supplies two reference points per axis (the axis tick positions). This is the WPD contract.
* It targets **clean** bar/line/scatter marks. It does **not** recover dense scatter point clouds
  (UMAP/tSNE — unrecoverable for anyone) or heavily occluded/overlapping series.
* Recovered values are **vision-grade** (``confidence < 1.0``), never text-layer-exact — they feed the
  golden table tagged ``source: extracted`` and are subject to the human-confirm gate (E4).
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel

RECOVER_CONFIDENCE = 0.7   # vision-grade; recovered values are never text-layer-exact (E2/E4)


class Axis(BaseModel):
    """A 1-D pixel→data map from two reference points (e.g. two labelled ticks). ``log`` for a base-10
    log axis. Pixel coords are in image space (origin top-left); for a y-axis the higher data value
    has the smaller row, which the two reference points encode directly."""

    px0: float
    val0: float
    px1: float
    val1: float
    log: bool = False

    def to_data(self, px: float) -> float:
        if self.px1 == self.px0:
            raise ValueError("axis reference points must have distinct pixel coordinates")
        t = (px - self.px0) / (self.px1 - self.px0)
        if self.log:
            if self.val0 <= 0 or self.val1 <= 0:
                raise ValueError("log axis reference values must be positive")
            return 10 ** (math.log10(self.val0) + t * (math.log10(self.val1) - math.log10(self.val0)))
        return self.val0 + t * (self.val1 - self.val0)


class Calibration(BaseModel):
    """The x + y pixel→data maps for one plot's data area."""

    x: Axis
    y: Axis


class RecoveredSeries(BaseModel):
    """Recovered data for one panel. ``values`` is populated for bars (one per bar, left→right);
    ``points`` for line/scatter (data-space ``(x, y)``). ``confidence`` is vision-grade."""

    form: str                                       # "bar" | "line" | "scatter"
    values: list[float] = []
    points: list[tuple[float, float]] = []
    confidence: float = RECOVER_CONFIDENCE
    note: str = ""


# --- masking -----------------------------------------------------------------


def _as_rgb(image) -> np.ndarray:
    """PNG bytes / path / ndarray → HxWx3 uint8."""
    if isinstance(image, np.ndarray):
        arr = image
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        return arr[..., :3].astype(np.uint8)
    from PIL import Image
    if isinstance(image, (bytes, bytearray)):
        import io
        img = Image.open(io.BytesIO(bytes(image)))
    else:
        img = Image.open(str(image))
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def mask_by_darkness(image, thresh: int = 200) -> np.ndarray:
    """Foreground = pixels darker than ``thresh`` (luminance) — ink on a light background."""
    rgb = _as_rgb(image).astype(np.float64)
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    return lum < thresh


def mask_by_color(image, color: tuple[int, int, int], tol: int = 40) -> np.ndarray:
    """Foreground = pixels within Euclidean ``tol`` of ``color`` (for a coloured series)."""
    rgb = _as_rgb(image).astype(np.float64)
    dist = np.sqrt(((rgb - np.array(color, dtype=np.float64)) ** 2).sum(axis=-1))
    return dist <= tol


def _resolve_mask(image, mask, color, tol, thresh) -> np.ndarray:
    if mask is not None:
        return np.asarray(mask, dtype=bool)
    if color is not None:
        return mask_by_color(image, color, tol)
    return mask_by_darkness(image, thresh)


# --- recovery ----------------------------------------------------------------


def recover_bars(image, calib: Calibration, *, mask=None, color=None, tol: int = 40,
                 thresh: int = 200, min_bar_width: int = 2, min_col_mass: int = 2) -> RecoveredSeries:
    """Recover one value per bar from a clean bar chart (bars rising from a common baseline).

    Columns carrying foreground are grouped into bars (split on background gaps); each bar's **top**
    row is mapped through the y-calibration to its value. Returns values left→right."""
    fg = _resolve_mask(image, mask, color, tol, thresh)
    col_mass = fg.sum(axis=0)
    active = col_mass >= min_col_mass

    # group consecutive active columns into bar segments
    bars: list[tuple[int, int]] = []
    start = None
    for c, on in enumerate(active):
        if on and start is None:
            start = c
        elif not on and start is not None:
            if c - start >= min_bar_width:
                bars.append((start, c))
            start = None
    if start is not None and len(active) - start >= min_bar_width:
        bars.append((start, len(active)))

    values: list[float] = []
    for c0, c1 in bars:
        rows = np.where(fg[:, c0:c1].any(axis=1))[0]
        top_row = int(rows.min())               # smallest row index = bar top
        values.append(float(calib.y.to_data(top_row)))
    return RecoveredSeries(
        form="bar", values=values, note=f"{len(values)} bars recovered (calibrated, vision-grade)")


def recover_line(image, calib: Calibration, *, mask=None, color=None, tol: int = 40,
                 thresh: int = 200, step: int = 1) -> RecoveredSeries:
    """Trace a line: for each x-column carrying foreground, take the mean row → one ``(x, y)`` data
    point. ``step`` subsamples columns. Returns points sorted by x (data space)."""
    fg = _resolve_mask(image, mask, color, tol, thresh)
    h, w = fg.shape
    points: list[tuple[float, float]] = []
    for c in range(0, w, step):
        rows = np.where(fg[:, c])[0]
        if rows.size == 0:
            continue
        y_px = float(rows.mean())
        points.append((float(calib.x.to_data(c)), float(calib.y.to_data(y_px))))
    points.sort(key=lambda p: p[0])
    return RecoveredSeries(
        form="line", points=points, note=f"{len(points)} points traced (calibrated, vision-grade)")


def recover_scatter(image, calib: Calibration, *, mask=None, color=None, tol: int = 40,
                    thresh: int = 200, min_size: int = 3) -> RecoveredSeries:
    """Recover scatter points: connected components of the marker mask (scipy.ndimage), filtered by
    area ``>= min_size``, one centroid per component → one ``(x, y)`` data point. NOT for dense point
    clouds (honest ceiling #4)."""
    from scipy import ndimage

    fg = _resolve_mask(image, mask, color, tol, thresh)
    labels, n = ndimage.label(fg)
    if n == 0:
        return RecoveredSeries(form="scatter", points=[], note="no markers found")
    sizes = ndimage.sum(np.ones_like(labels), labels, index=range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s >= min_size]
    centroids = ndimage.center_of_mass(fg, labels, index=keep)  # (row, col) per component
    points = [(float(calib.x.to_data(c)), float(calib.y.to_data(r))) for r, c in centroids]
    points.sort(key=lambda p: p[0])
    return RecoveredSeries(
        form="scatter", points=points,
        note=f"{len(points)} markers recovered (calibrated, vision-grade)")

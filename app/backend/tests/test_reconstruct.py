"""Reconstruction subsystem (X2, Track B) — SSIM self-QA + editable redraw.

The SSIM core is pure numpy, so it is unit-tested directly on synthetic images; the editable
redraw is pure dict construction (no Kaleido), so it is tested without rendering. The full
render→SSIM-vs-original loop needs Kaleido (system Chrome) and is the owner-machine dogfood.
"""

import io

import numpy as np
import pytest
from PIL import Image

from extract.reconstruct import (
    ReconstructionQA,
    reconstruct_panel,
    self_qa,
    ssim,
)


def _png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8")).save(buf, format="PNG")
    return buf.getvalue()


def _gradient(h=64, w=64) -> np.ndarray:
    x = np.linspace(0, 255, w)
    return np.tile(x, (h, 1))


# --- SSIM core (pure numpy) ---------------------------------------------------


def test_ssim_identity_is_one():
    a = _gradient()
    assert ssim(a, a) == pytest.approx(1.0, abs=1e-9)


def test_ssim_is_symmetric():
    a = _gradient()
    b = a + 20
    assert ssim(a, b) == pytest.approx(ssim(b, a), abs=1e-9)


def test_ssim_degrades_with_difference():
    a = _gradient()
    rng = np.random.default_rng(0)
    noisy = np.clip(a + rng.normal(0, 40, a.shape), 0, 255)
    inverted = 255 - a
    assert ssim(a, noisy) < 0.99
    assert ssim(a, inverted) < ssim(a, noisy)   # an inverted image is less similar than a noised one


def test_ssim_requires_equal_shapes():
    with pytest.raises(ValueError):
        ssim(_gradient(64, 64), _gradient(32, 32))


# --- self_qa (resize + verdict over PNG bytes) --------------------------------


def test_self_qa_identical_is_equivalent_and_accepted():
    png = _png(_gradient())
    qa = self_qa(png, png, panel_key="x")
    assert isinstance(qa, ReconstructionQA)
    assert qa.ssim == pytest.approx(1.0, abs=1e-3)
    assert qa.band == "equivalent" and qa.accepted is True


def test_self_qa_very_different_is_divergent_and_rejected():
    white = _png(np.full((64, 64), 255))
    black = _png(np.zeros((64, 64)))
    qa = self_qa(white, black)
    assert qa.band == "divergent" and qa.accepted is False


def test_self_qa_resizes_reconstruction_to_original():
    # A reconstruction rendered at a different size is resized before scoring (no shape error).
    orig = _png(_gradient(80, 120))
    recon = _png(_gradient(40, 60))
    qa = self_qa(orig, recon)
    assert qa.ssim > 0.9   # same gradient, different resolution → still structurally equivalent


# --- editable redraw (Track B) ------------------------------------------------


def test_reconstruct_volcano_is_editable_spec():
    spec = reconstruct_panel("volcano", {
        "log2fc": [-2.0, 0.1, 2.5], "neg_log10_p": [3.0, 0.2, 4.0],
        "category": ["down", "n.s.", "up"]}, title="Fig 4e")
    assert isinstance(spec, dict) and isinstance(spec["data"], list) and "layout" in spec
    assert {t["type"] for t in spec["data"]} == {"scatter"}
    assert spec["layout"]["title"]["text"] == "Fig 4e"   # themed title survives


def test_reconstruct_stacked_bar_and_heatmap():
    bar = reconstruct_panel("stacked_bar", {"x": ["s1", "s2"],
                                            "series": {"Rod": [0.6, 0.5], "Cone": [0.4, 0.5]}})
    assert bar["layout"]["barmode"] == "stack"
    assert {t["type"] for t in bar["data"]} == {"bar"}
    hm = reconstruct_panel("heatmap", {"z": [[1, 2], [3, 4]], "x": ["a", "b"], "y": ["p", "q"]})
    assert hm["data"][0]["type"] == "heatmap"


def test_reconstruct_unsupported_form_raises():
    with pytest.raises(ValueError):
        reconstruct_panel("network", {})

"""Vision stage (X1 slice-2) — the live vision layer, with Claude acting as the gateway.

Slice-1 read everything from the PDF text layer (``golden.py``); it is silent on the things
that exist only as *pixels* — a chart's form when the caption doesn't name it, and counts that
are stated only graphically (RPGRIP1's "signature" gene counts annotated on the figure, a number
printed inside a Venn region, a bar height). Those need vision.

The live AI gateway isn't built yet, so for the dev/dogfood profile **Claude acts as the
gateway** ([[selom-claude-acts-as-ai-gateway]], sub-spec open-Q#2): the operator inspects the
real panel rasters (``page_raster`` → Read the PNG) and records :class:`VisionObservation`s; the
:class:`OperatorVisionGateway` replays them deterministically. That makes the loop **CI-safe and
reproducible** — exactly the engine's ``drive_captured`` posture and the gated R-oracle posture
(ADR 0002). When the real service lands, a ``LiveVisionGateway`` implements the same
:class:`VisionGateway` Protocol and nothing else changes (it slots behind the existing
``VisionClassifier`` too).

What this module adds on top of slice-1:

* :class:`VisionObservation` — one operator/vision read of a panel (chart form + graphically-
  stated counts + labels), at ``confidence < 1.0`` (text-layer-exact ints stay 1.0).
* :class:`OperatorVisionGateway` — the replayable gateway; degrades cleanly (``VisionUnavailable``)
  for any panel without a recorded observation, so callers fall back to the rule reader.
* :func:`associate_counts` — turn vision-read counts into engine ``GoldenTarget``s.
* :func:`augment_with_vision` — enrich a slice-1 ``ExtractedSpec`` with vision: fill missing chart
  forms and ADD goldens for counts the text reader returned nothing for.
* :class:`PanelBox` + :func:`segment_panels` — manual-assist panel segmentation (open-Q#1):
  operator-confirmed boxes → typed ``PanelDraft``s, chart form/scope filled from the gateway.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

import reproduction as R

from .classify import VisionUnavailable, classify_scope
from .models import SOURCE_FIGURE, ExtractedSpec, GoldenTarget, PanelDraft


def _split_key(panel_key: str) -> tuple[str, str]:
    """``"5a"`` → ``("5", "a")``; ``"5"`` → ``("5", "")``; ``""`` → ``("", "")``."""
    m = re.match(r"(\d+)\s*([A-Za-z]*)", panel_key.strip())
    return (m.group(1), m.group(2)) if m else ("", "")


class VisionObservation(BaseModel):
    """One vision read of a single panel — what the operator (acting as the gateway) sees in the
    raster. ``confidence`` defaults below 1.0 because a vision read is not text-layer-exact; a
    count we can read as crisp printed digits *on* the figure can be marked higher."""

    panel_key: str = ""
    chart_form: str = ""
    confidence: float = 0.9
    counts: dict[str, float] = Field(default_factory=dict)   # e.g. {"signature": 181, "de_up": 78}
    labels: list[str] = Field(default_factory=list)          # gene/term labels read off the figure
    scope_hint: str = ""                                     # optional; else inferred from caption
    note: str = ""


@runtime_checkable
class VisionGateway(Protocol):
    """The vision provider boundary (sub-spec open-Q#2). Implements the narrow ``classify_chart``
    seam (so it drops in behind :class:`~extract.classify.VisionClassifier`) plus the richer
    :meth:`observe`. ``OperatorVisionGateway`` (replay) and a future ``LiveVisionGateway`` (the
    real service) both satisfy it."""

    def observe(self, panel_key: str, *, image: bytes | None = None) -> VisionObservation: ...

    def classify_chart(self, caption: str, *, image: bytes | None = None) -> tuple[str, float]: ...


class OperatorVisionGateway:
    """A :class:`VisionGateway` backed by operator-recorded observations — **Claude acting as the
    AI gateway** during dev/dogfood ([[selom-claude-acts-as-ai-gateway]]).

    The operator views the real rasters and records a :class:`VisionObservation` per panel; this
    replays them deterministically (CI-safe, like ``drive_captured``). Any panel without a recorded
    observation raises :class:`VisionUnavailable` so the caller degrades to the text/rule reader —
    the vision layer never fabricates a value it didn't see. ``classify_chart`` looks the panel up
    by key (callers pass the panel key as the caption in dogfood use) or, failing that, by the
    crispest image match — but for the PoC the key lookup is the contract."""

    def __init__(self, observations: dict[str, VisionObservation] | None = None):
        self._obs = dict(observations or {})

    def record(self, obs: VisionObservation) -> None:
        """Add/replace an observation (used while the operator works through a paper's panels)."""
        self._obs[obs.panel_key] = obs

    def observe(self, panel_key: str, *, image: bytes | None = None) -> VisionObservation:
        obs = self._obs.get(panel_key)
        if obs is None:
            raise VisionUnavailable(
                f"no operator observation recorded for panel '{panel_key}' — render the raster "
                f"(page_raster), view it, and OperatorVisionGateway.record(...) the read"
            )
        return obs

    def classify_chart(self, caption: str, *, image: bytes | None = None) -> tuple[str, float]:
        obs = self._obs.get(caption)
        if obs is None or not obs.chart_form:
            raise VisionUnavailable(f"no vision chart-form recorded for '{caption}'")
        return obs.chart_form, obs.confidence


def associate_counts(obs: VisionObservation, paper_id: str, *,
                     figure: str = "", panel: str = "") -> list[GoldenTarget]:
    """Turn a panel's vision-read counts into engine :class:`GoldenTarget`s. These are the values
    the text layer could not see (graphically-stated), so they carry the observation's vision
    ``confidence`` (< 1.0) and ``source = figure`` — and they go through the same human-confirm QA
    gate as any vision-only golden (E4)."""
    fig = figure or _split_key(obs.panel_key)[0]
    pan = panel or _split_key(obs.panel_key)[1]
    note = obs.note or "vision-read (graphically-stated count)"
    return [
        GoldenTarget(paper_id=paper_id, figure=fig, panel=pan, metric=metric, value=value,
                     source=SOURCE_FIGURE, confidence=obs.confidence, note=note)
        for metric, value in obs.counts.items()
    ]


def augment_with_vision(spec: ExtractedSpec, gateway: VisionGateway, *,
                        keys: list[str] | None = None) -> ExtractedSpec:
    """Enrich a slice-1 :class:`ExtractedSpec` with the vision gateway: fill empty chart forms and
    ADD goldens for counts stated only graphically (which the text reader returned nothing for —
    e.g. RPGRIP1's "signature" counts). Returns a NEW spec; pure given the gateway. Panels without
    a recorded observation are left exactly as slice-1 produced them (degrade-cleanly)."""
    panels = {d.key: d.model_copy() for d in spec.panels}
    goldens = list(spec.goldens)
    have = {(g.panel_key, g.metric) for g in goldens}
    for key in (keys if keys is not None else list(panels)):
        try:
            obs = gateway.observe(key)
        except VisionUnavailable:
            continue
        fig, pan = _split_key(key)
        draft = panels.get(key)
        if draft is None:
            draft = PanelDraft(paper_id=spec.paper_id, figure=fig, panel=pan)
            panels[key] = draft
        if obs.chart_form and not draft.chart_form:
            draft.chart_form = obs.chart_form
            draft.confidence = obs.confidence
        for g in associate_counts(obs, spec.paper_id, figure=fig, panel=pan):
            if (g.panel_key, g.metric) not in have:
                goldens.append(g)
                have.add((g.panel_key, g.metric))
    return ExtractedSpec(paper_id=spec.paper_id, panels=list(panels.values()),
                         goldens=goldens, methods=spec.methods,
                         inconsistencies=spec.inconsistencies)


def venn3_totals(*, a: int, b: int, c: int, ab: int, ac: int, bc: int, abc: int) -> dict[str, int]:
    """Per-set totals for a 3-set Venn from its seven region counts (``a``/``b``/``c`` unique,
    ``ab``/``ac``/``bc`` pairwise, ``abc`` all-three).

    A vision-semantic helper: papers typically print only the *unique* and *all-three* counts in
    prose, leaving the three pairwise overlaps **pixel-only**. Reading them off the Venn lets us
    reconstruct the per-set totals the text never states — e.g. RPGRIP1 Fig 6E → Rod-1/2/3 =
    102/119/74, the GO-term targets the GSEA panel is compared against ([[selom-gsea-engine-
    sensitivity]])."""
    return {"A": a + ab + ac + abc, "B": b + ab + bc + abc, "C": c + ac + bc + abc,
            "total": a + b + c + ab + ac + bc + abc}


# --- manual-assist panel segmentation (open-Q#1) ------------------------------


class PanelBox(BaseModel):
    """An operator-confirmed panel region on a figure (manual-assist; full vector-gutter/label-
    anchor automation is deferred to X2). ``bbox`` is normalized ``(x0, y0, x1, y1)``."""

    figure: str
    panel: str = ""
    page_index: int = 0
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    caption: str = ""


def segment_panels(paper_id: str, boxes: list[PanelBox],
                   gateway: VisionGateway | None = None) -> list[PanelDraft]:
    """Manual-assist segmentation: operator-confirmed :class:`PanelBox`es → typed
    :class:`PanelDraft`s. Scope comes from the caption (guard 7); chart form comes from the
    gateway's observation when one exists, else stays blank for the rule reader to fill."""
    drafts: list[PanelDraft] = []
    for box in boxes:
        key = f"{box.figure}{box.panel}"
        chart_form, conf = "", 1.0
        if gateway is not None:
            try:
                obs = gateway.observe(key)
                chart_form, conf = obs.chart_form, obs.confidence
            except VisionUnavailable:
                pass
        drafts.append(PanelDraft(
            paper_id=paper_id, figure=box.figure, panel=box.panel, chart_form=chart_form,
            scope=classify_scope(box.caption) if box.caption else R.TRANSCRIPTOMIC,
            caption=box.caption, confidence=conf))
    return drafts

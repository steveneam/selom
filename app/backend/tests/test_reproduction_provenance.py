"""Reading provenance on the reproduction ledger (DECISIONS #16, docs/provenance-stamping/spec.md).

`extract.readers` has always known how it got a number — which layer resolved it, whether it came
off a real table, the figure, or an L3-SYNTHESIZED one, and the confidence it gave itself. The
scorecard was the one consumer that never received any of it: `panel_extractor` did
`out[gold.metric] = r.value` and dropped the rest. So a metric the reader itself rated 0.45, read
off a table the skill never emitted, rendered on `/reproduction/<slug>` — a top-level sidebar
surface — as VERIFIED / 100 Selom-confidence, indistinguishable from a native read.

These guard the six invariants in §5 of the spec. The G2 pair matters most: the whole change is
worthless if it re-baselines the numbers already published for native reads.
"""

import pytest

import reproduction.core as R
from extract.readers import (
    L2,
    L3,
    SRC_SYNTH,
    SRC_TABLE,
    Reading,
    panel_extractor,
    panel_extractor_readings,
)


def _panel(**kw):
    """A one-golden panel whose computed value will match EXACTLY — the case that used to score
    100/100 whatever the provenance was."""
    return R.Panel(
        paper_id="p", figure="1", panel="A", skill_id="volcano",
        golden=[R.Golden(metric="n_up", value=42)], **kw,
    )


def _validate(panel, value=42, readings=None):
    return R.validate_panel(panel, {"n_up": value}, run_id="r1", readings=readings)


def _reading(source, confidence=1.0, layer=L2):
    return Reading(metric="n_up", value=42, layer=layer, source=source, confidence=confidence)


# --- G1 / G2: the cap fires on a synthesized read, and ONLY on one ---------------------------


def test_a_synthesized_read_caps_selom_confidence_even_when_exact():
    """G1. An EXACT verdict off a synthesized table is still a number Selom reconstructed rather
    than one the skill emitted. Reproducibility is untouched — whether the figure can be
    regenerated is the paper's property; how well we read it back is ours."""
    panel = _panel()
    score = R.score_panel(panel, _validate(panel, readings={"n_up": _reading(SRC_SYNTH, 0.45, L3)}))
    assert score.selom_confidence == R.SYNTH_CONFIDENCE_CAP == 75
    assert score.reproducibility == 100, "the paper-side axis must not move"
    assert score.reading_provenance == "synthesized"


def test_a_native_read_is_byte_identical_to_before():
    """G2. The regression that would make this change a net loss: every ledger number already
    published for a native read has to be unchanged. Asserted by EQUALITY, both with an explicit
    table reading and with no readings supplied at all (`run_panel`, replay from a persisted
    ledger) — the two paths a caller can take."""
    panel = _panel()
    explicit = R.score_panel(panel, _validate(panel, readings={"n_up": _reading(SRC_TABLE)}))
    silent = R.score_panel(panel, _validate(panel))          # no readings — the old call shape

    for score in (explicit, silent):
        assert score.selom_confidence == 100
        assert score.reproducibility == 100
        assert score.reading_provenance == "", "a native read wears no badge"
    assert explicit.model_dump() == silent.model_dump()


def test_the_cap_is_a_cap_not_a_floor():
    """G5. A read that already scores LOWER for a better reason keeps its lower number. A genuine
    Selom defect is 15 confidence; lifting it to 75 because the value happened to be synthesized
    would be the change inventing trust rather than withdrawing it."""
    panel = _panel()
    validation = _validate(panel, value=999, readings={"n_up": _reading(SRC_SYNTH, 0.45, L3)})
    # Force the Selom-defect blame the way the scorer sees it.
    validation.results[0].blame = R.SELOM_ENGINE
    score = R.score_panel(panel, validation)
    assert score.selom_confidence == 15, "the synthesis cap must never raise a worse score"


def test_the_panel_wears_the_badge_if_any_metric_earned_it():
    """The panel takes the worst of its metrics on both axes; the badge follows the same rule."""
    panel = R.Panel(
        paper_id="p", figure="1", panel="A", skill_id="volcano",
        golden=[R.Golden(metric="n_up", value=42), R.Golden(metric="n_down", value=7)],
    )
    validation = R.validate_panel(
        panel, {"n_up": 42, "n_down": 7}, run_id="r1",
        readings={
            "n_up": _reading(SRC_TABLE),                                     # native
            "n_down": Reading(metric="n_down", value=7, layer=L3,
                              source=SRC_SYNTH, confidence=0.45),            # synthesized
        },
    )
    score = R.score_panel(panel, validation)
    assert score.reading_provenance == "synthesized"
    assert score.selom_confidence == 75


# --- G3 / G4: the two extractors cannot drift -------------------------------------------------


class _Gold:
    def __init__(self, metric):
        self.metric = metric


class _P:
    skill_id = "volcano"

    def __init__(self, metrics):
        self.golden = [_Gold(m) for m in metrics]


_TABLE = {"columns": ["gene", "log2fc", "padj"],
          "rows": [["A", 2.0, 0.001], ["B", -2.0, 0.001], ["C", 0.1, 0.9]]}


def test_the_value_extractor_derives_from_the_rich_one():
    """G4. `panel_extractor` is `{k: r.value for …}` over `panel_extractor_readings`, so the two
    cannot disagree about which metrics resolved. Re-reading instead would have re-run L3 SYNTHESIS
    for every tableless panel — paying the cost twice to recover what the first pass already had,
    and letting the two passes diverge."""
    panel = _P(["n_up", "n_down"])
    readings = panel_extractor_readings(panel, None, _TABLE)
    values = panel_extractor(panel, None, _TABLE)
    assert values == {k: r.value for k, r in readings.items()}
    assert set(values) == set(readings)


def test_an_unreadable_golden_is_omitted_by_both_not_none():
    """G3. The omit-never-None rule is what lets the drive tell "read a value, validate it" from
    "no reading → needs_recipe", and the latter must never become a Selom-confidence FAIL. The rule
    now lives in the rich function, so this pins BOTH halves of it."""
    panel = _P(["n_up", "definitely_not_a_readable_metric"])
    readings = panel_extractor_readings(panel, None, _TABLE)
    values = panel_extractor(panel, None, _TABLE)
    assert "definitely_not_a_readable_metric" not in readings
    assert "definitely_not_a_readable_metric" not in values
    assert None not in values.values()


# --- the seam itself --------------------------------------------------------------------------


def test_metric_value_carries_the_reading_provenance():
    """The run's own record, not just the score: `MetricValue` gained the triple so a persisted
    ledger says how each number was read. Defaults stay None so `run_panel` — which has no
    production caller — is unchanged rather than half-migrated."""
    stamped = R.MetricValue(metric="n_up", value=42, layer=L3, source=SRC_SYNTH,
                            read_confidence=0.45)
    assert (stamped.layer, stamped.source, stamped.read_confidence) == (L3, SRC_SYNTH, 0.45)

    bare = R.MetricValue(metric="n_up", value=42)
    assert bare.layer is None and bare.source is None and bare.read_confidence is None


def test_the_whole_path_end_to_end_on_a_really_synthesized_read():
    """The case DECISIONS #16 describes, driven through every seam rather than hand-built.

    A TABLELESS panel: no Statistics table, so `read_metric` falls through to L3 synthesis, which
    reconstructs a cluster-size table off the bar trace and rates itself 0.45. That number used to
    render on `/reproduction/<slug>` as VERIFIED / **100** Selom-confidence — indistinguishable
    from a value read off the engine's own table. The unit guards above use hand-made `Reading`s;
    this one proves the readers, the validator and the scorer are actually wired to each other.
    """
    figure = {"data": [{"type": "bar", "x": ["c0", "c1", "c2"], "y": [100, 60, 40]}],
              "layout": {"title": {"text": "Leiden clusters"}}}
    panel = R.Panel(paper_id="p", figure="1", panel="A", skill_id="cluster",
                    golden=[R.Golden(metric="n_clusters", value=3)])

    readings = panel_extractor_readings(panel, figure, None)   # no table → the synthesis path
    assert readings["n_clusters"].source == SRC_SYNTH
    assert readings["n_clusters"].layer == L3
    assert readings["n_clusters"].confidence < 0.5, "the reader already doubted this value"

    validation = R.validate_panel(panel, {"n_clusters": readings["n_clusters"].value},
                                  run_id="r1", readings=readings)
    assert validation.results[0].verdict == R.EXACT, "the value itself is right — that is the trap"

    score = R.score_panel(panel, validation)
    assert score.selom_confidence == 75, "a reconstructed table must not score as a native read"
    assert score.reproducibility == 100
    assert score.reading_provenance == "synthesized"


@pytest.mark.parametrize("verdict,expected", [(R.EXACT, 75), (R.CLOSE, 75)])
def test_the_cap_applies_to_every_verdict_not_just_exact(verdict, expected):
    """A synthesized read is no more trustworthy landing CLOSE than landing EXACT, so the cap is
    not special-cased to the perfect-match branch."""
    _repro, confidence, _attr = R._metric_score(verdict, None, substituted=False, synthesized=True)
    assert confidence == expected

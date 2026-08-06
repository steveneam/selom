"""B4 auto methods-text — every skill yields cited, parameterized prose."""

from companions import legends, methods
from companions.methods import BH, SCIPY
from skills.contract import SkillSpec, load_skill
from skills.registry import list_skill_ids


def test_every_skill_has_methods_text_and_citations():
    for skill_id in list_skill_ids():
        spec = load_skill(skill_id)
        out = methods.build(spec, {})
        assert out["text"].strip()
        # Each template names the skill via the Selom attribution sentence.
        assert f"v{spec.version}" in out["text"]
        assert f"skill '{skill_id}'" in out["text"]
        assert isinstance(out["citations"], list)


def test_methods_quote_resolved_params():
    deg = methods.build(load_skill("deg"), {"top_n": "25"})
    assert "top 25 genes" in deg["text"]
    assert any("DESeq2" in c for c in deg["citations"])

    volcano = methods.build(load_skill("volcano"), {"fc_threshold": "1.5"})
    assert "1.5" in volcano["text"]
    assert any("false discovery rate" in c for c in volcano["citations"])


def test_gsea_methods_template_is_specific_not_generic():
    # Library mode (no pasted gene_set) names the GO library + permutation NES + FDR.
    lib = methods.build(load_skill("gsea"), {"n_perm": "500"})
    assert "Gene Set Enrichment Analysis" in lib["text"]
    assert "gene=" not in lib["text"] and "gene_set=" not in lib["text"]  # not the raw-param dump
    assert "500 gene-set permutations" in lib["text"]
    assert any("PNAS" in c for c in lib["citations"])      # Subramanian 2005
    assert any("GSEApy" in c for c in lib["citations"])    # Fang 2023
    assert any("Gene Ontology" in c for c in lib["citations"])

    # Single-set mode (pasted members) names the set, drops the GO-library citation.
    single = methods.build(load_skill("gsea"), {"gene_set": "RHO,PRPH2,NRL", "set_name": "Rod set"})
    assert "Rod set" in single["text"]
    assert not any("Gene Ontology" in c for c in single["citations"])


def _gsea_fig(engine, n_perm, fdr_corrected):
    """A figure carrying only what the gsea runner records about its own run."""
    return {"layout": {"meta": {"gsea": {
        "engine": engine, "n_perm": n_perm, "fdr_corrected": fdr_corrected,
    }}}}


def test_gsea_methods_names_the_engine_that_actually_ran():
    """The paragraph said "(gseapy.prerank)" and cited GSEApy on EVERY run, but `engine` defaults to
    `auto` and resolves from what is importable — so the params never knew which statistics were
    computed. blitzGSEA fits a gamma distribution and the in-house engine is Selom's own numpy
    weighted-KS; crediting a package that did not run is a citation the reader cannot check."""
    blitz = methods.build(load_skill("gsea"), {"engine": "blitzgsea"},
                          figure=_gsea_fig("blitzgsea", 1000, True))
    assert "blitzGSEA" in blitz["text"] and "gseapy.prerank" not in blitz["text"]
    assert any("blitzGSEA" in c for c in blitz["citations"])
    assert not any("GSEApy" in c for c in blitz["citations"])

    house = methods.build(load_skill("gsea"), {"engine": "inhouse", "gene_set": "RHO,NRL"},
                          figure=_gsea_fig("inhouse", 1000, False))
    assert "in-house weighted Kolmogorov-Smirnov" in house["text"]
    assert not any("GSEApy" in c for c in house["citations"])
    # Subramanian is still owed — the METHOD is GSEA whoever implements it.
    assert any("PNAS" in c for c in house["citations"])


def test_gsea_methods_quotes_the_permutation_count_the_run_used():
    """`_perm_count` floors the two library engines at 100 and reads an explicit 0 as the default,
    so the raw param is not the resolution the run had. A methods paragraph claiming "50 gene-set
    permutations" states a precision that was never computed."""
    floored = methods.build(load_skill("gsea"), {"n_perm": "50"},
                            figure=_gsea_fig("gseapy", 100, True))
    assert "100 gene-set permutations" in floored["text"]
    assert "50 gene-set permutations" not in floored["text"]

    # Zero permutations is not a small test, it is NO test: the in-house engine leaves p at 1.0 and
    # returns the score unnormalized, so the sentence has to change, not just its number.
    none_run = methods.build(load_skill("gsea"), {"engine": "inhouse", "gene_set": "RHO,NRL",
                                                  "n_perm": "0"},
                             figure=_gsea_fig("inhouse", 0, False))
    assert "no permutation test was run" in none_run["text"]
    assert "0 gene-set permutations" not in none_run["text"]
    assert "empirical p-value" not in none_run["text"].split("no permutation test")[0]


def test_gsea_methods_claims_bh_only_when_a_correction_ran():
    """Benjamini-Hochberg across sets exists only in LIBRARY mode. A pasted single set has nothing
    to correct across and the in-house engine computes no q at all — yet the paragraph claimed the
    correction and cited Benjamini & Hochberg on both. Same family as the `_boxplot` prose that
    named Welch and BH while returning no citations, inverted."""
    library = methods.build(load_skill("gsea"), {}, figure=_gsea_fig("gseapy", 1000, True))
    assert "Benjamini-Hochberg" in library["text"]
    assert any(c is BH for c in library["citations"])

    single = methods.build(load_skill("gsea"), {"gene_set": "RHO,PRPH2,NRL"},
                           figure=_gsea_fig("gseapy", 1000, False))
    assert "Benjamini-Hochberg" not in single["text"]
    assert not any(c is BH for c in single["citations"])
    assert "false-discovery" not in single["text"]


def test_ssgsea_prose_reads_a_string_false_zscore():
    """A CONTRACT pin, not a defect pin — it passes against the pre-fix prose too, and that is
    worth recording: the template used plain truthiness (where the string "false" is TRUE), and
    was saved only because `resolved_params` casts by the declared `bool` type first. This asserts
    the property the prose depends on, so the day that coercion moves, the failure lands here
    rather than in a published paragraph claiming a transform the run skipped."""
    off = methods.build(load_skill("ssgsea"), {"zscore": "false"})
    assert "z-scored" not in off["text"]
    on = methods.build(load_skill("ssgsea"), {"zscore": "true"})
    assert "z-scored" in on["text"]


def test_ssgsea_prose_states_the_count_drawn_not_the_cap():
    """`top_n` is a cap — `order[:top_n]` yields fewer rows whenever fewer sets scored — so both the
    paragraph and the caption were quoting a number the figure could contradict. The figure's own
    title has always carried the real count."""
    spec = load_skill("ssgsea")
    fig = {"layout": {"meta": {"ssgsea": {"shown": 6, "zscore": True}}}}
    # `top_n=25` is the CAP and 6 is what was drawn. Assert on the claim, not on the digits — "25"
    # also occurs in the weight exponent 0.25, and a bare substring check would read that as a bug.
    text = methods.build(spec, {"top_n": "25"}, figure=fig)["text"]
    assert "6 most variable gene sets" in text and "25 most variable" not in text

    caption = legends.build_caption(spec, {"top_n": "25"}, figure=fig)
    assert "6 gene sets" in caption and "25 gene sets" not in caption
    # The criterion is named, not just the number — "the top N" said nothing about how N was picked.
    assert "vary most across samples" in caption


def test_go_graph_methods_template_is_specific():
    out = methods.build(load_skill("go_graph"), {"top_n": "15", "namespace": "BP"})
    assert "is_a/part_of hierarchy" in out["text"]
    assert "top 15" in out["text"] and "BP namespace" in out["text"]
    assert any("Gene Ontology" in c for c in out["citations"])
    assert any("false discovery rate" in c for c in out["citations"])


def test_cepo_methods_template_is_specific():
    out = methods.build(load_skill("cepo"), {"n_genes": "12"})
    assert "differential stability" in out["text"]
    assert "top 12 differential-stability genes" in out["text"]
    assert any("Cepo" in c for c in out["citations"])


def test_pvca_methods_template_is_specific():
    out = methods.build(load_skill("pvca"), {"factors": "batch, cell_type"})
    assert "Principal Variance Component Analysis" in out["text"]
    assert "batch, cell_type" in out["text"]
    assert "factors=" not in out["text"]  # not the raw-param dump
    assert any("Sources of variation" in c for c in out["citations"])  # Boedigheimer 2008


def test_regression_methods_template_is_specific():
    out = methods.build(load_skill("regression"), {"x": "age", "y": "score"})
    assert "ordinary-least-squares" in out["text"]
    assert "score" in out["text"] and "age" in out["text"]
    assert any("SciPy" in c for c in out["citations"])


def test_unknown_skill_falls_back_to_generic():
    spec = SkillSpec(
        id="mystery",
        version="9.9.9",
        title="Mystery Skill",
        engine="python",
        omics="proteomics",
        entrypoint="x:y",
        inputs=[],
        param_spec={"alpha": {"type": "float", "default": 0.5}},
        outputs=[],
    )
    out = methods.build(spec, {"alpha": "0.9"})
    assert "Mystery Skill" in out["text"]
    assert "alpha=0.9" in out["text"]
    assert out["citations"] == []


# --- boxplot: two printed-vs-computed lies the prose↔param backlog pointed at -------------------


def _boxplot_text(params: dict) -> str:
    from skills.contract import load_skill

    return methods.build(load_skill("boxplot"), {"group": "condition", "value": "b_wave_uv",
                                                 **params})["text"]


def test_boxplot_strip_mode_claims_no_box_it_does_not_draw():
    """`style="strip"` hides the box entirely (zero width, no fill) and plots every value. The
    methods text used to describe "box-and-whisker … whiskers extending to 1.5× the IQR"
    UNCONDITIONALLY, so a strip figure shipped with prose about furniture the reader cannot see."""
    strip = _boxplot_text({"style": "strip"})
    assert "strip plot" in strip
    assert "every individual value" in strip
    assert "IQR" not in strip and "whisker" not in strip, "no box is drawn, so no box may be claimed"

    box = _boxplot_text({})
    assert "box-and-whisker" in box and "1.5× the IQR" in box, "the box branch must keep its claim"


def test_boxplot_ordering_sentence_follows_the_order_param():
    """`resolve_order` puts the categories the user NAMED first, in the order given, and only the
    remainder follow the descending-median sort. "groups are ordered by descending median" is
    therefore true exactly when the user named none — it was stated unconditionally."""
    auto = _boxplot_text({})
    assert "ordered by descending median" in auto

    named = _boxplot_text({"order": "Control, Untreated"})
    assert "Control, Untreated lead in that order" in named
    assert "remaining groups by descending median" in named


def test_boxplot_names_the_test_behind_its_stars_only_when_pairs_was_asked_for():
    """The stars are a published claim, so the test and any multiplicity correction are named. With
    no `pairs` there is no comparison, and the sentence must not appear at all."""
    none = _boxplot_text({})
    assert "compared with" not in none

    bh = _boxplot_text({"pairs": "Control~Untreated", "sig_test": "mannwhitney", "correction": "bh"})
    assert "Mann-Whitney U" in bh and "Benjamini-Hochberg" in bh

    raw = _boxplot_text({"pairs": "Control~Untreated"})
    assert "Welch" in raw
    assert "uncorrected for multiple comparisons" in raw, \
        "silence about multiplicity reads as 'corrected'; say which it is"


# --- ERG: the PROSE_SILENT triage of 2026-08-05 ------------------------------------------------
#
# The board predicted the ERG family would be a confirmed-waive pass ("pipeline-level/internal").
# Reading the four runners said otherwise: 26 of the 50 waived params changed what the figure
# CLAIMS while the paragraph said something else. Each test below pins one of those claims to the
# knob that decides it.


def _prose(skill_id: str, params: dict, figure: dict | None = None) -> str:
    return methods.build(load_skill(skill_id), params, figure=figure)["text"]


def test_erg_bar_names_the_wave_it_actually_plots():
    """`wave` selects the a- or b-wave and `value_col` overrides it outright. The paragraph said
    "b-wave" unconditionally — and describes the MEASUREMENT, which is a different construction for
    each landmark (baseline-to-trough vs trough-to-peak)."""
    b = _prose("erg_bwave_bar", {})
    assert "b-wave" in b and "trough-to-peak b-wave" in b

    a = _prose("erg_bwave_bar", {"wave": "a"})
    assert "a-wave" in a and "b-wave" not in a
    assert "from the pre-stimulus baseline to the initial cornea-negative trough" in a

    # `value_col` is the override the runner honours ahead of `wave`.
    assert "a-wave" in _prose("erg_bwave_bar", {"wave": "b", "value_col": "a_wave_uv"})


def test_erg_bar_spread_claim_follows_error_and_show_error():
    """"the standard error of the mean" was printed on every run — including `error="sd"` (a wider
    bar a reader would read as a standard error) and `show_error=False` (no bar at all)."""
    assert "with the standard error of the mean" in _prose("erg_bwave_bar", {})
    assert "with the standard deviation" in _prose("erg_bwave_bar", {"error": "sd"})
    assert "with a 95% confidence interval" in _prose("erg_bwave_bar", {"error": "ci95"})

    off = _prose("erg_bwave_bar", {"show_error": "false"})
    assert "and no error bar" in off
    assert "standard error" not in off


def test_erg_bar_points_claim_follows_the_points_knob():
    assert "every eye is overlaid" in _prose("erg_bwave_bar", {})
    assert "without the individual eyes overlaid" in _prose("erg_bwave_bar", {"points": "false"})


def test_erg_bar_names_the_test_behind_its_brackets_and_flags_overrides():
    """Brackets are a published claim. With no `comparisons` there is no test to name; with a
    `A~B:**` override the star was typed in by the operator, so neither the test nor SciPy may be
    credited with it."""
    none = methods.build(load_skill("erg_bwave_bar"), {})
    assert "compared with" not in none["text"]
    assert SCIPY not in none["citations"]

    computed = methods.build(load_skill("erg_bwave_bar"),
                             {"comparisons": "Control~Untreated", "sig_test": "mannwhitney",
                              "correction": "bh"})
    assert "Mann-Whitney U" in computed["text"]
    assert "Benjamini-Hochberg" in computed["text"]
    assert SCIPY in computed["citations"] and BH in computed["citations"]

    mixed = _prose("erg_bwave_bar", {"comparisons": "Control~Untreated, Control~CMV:**"})
    assert "1 show operator-supplied values rather than a computed test" in mixed
    assert "remaining 1 pair(s) were compared with Welch" in mixed

    # Every bracket overridden → no test ran, so no test and no SciPy citation.
    only = methods.build(load_skill("erg_bwave_bar"), {"comparisons": "Control~Untreated:**"})
    assert "no test was computed for them" in only["text"]
    assert "Welch" not in only["text"]
    assert SCIPY not in only["citations"]


def test_erg_adaptation_follows_stimulus_type_and_the_recorded_mode():
    """The first sentence of an ERG paragraph says whether the reader is looking at rod or cone
    physiology. It read `adaptation` alone, but every runner resolves the mode through
    `_erg.resolve_flash_mode`, where an explicit `stimulus_type` WINS — and under `auto` the answer
    comes from the data, which only the runner can report (`layout.meta.adaptation`)."""
    assert "scotopic" in _prose("erg_traces", {})

    override = _prose("erg_traces", {"stimulus_type": "photopic_flash"})
    assert "photopic (cone-driven)" in override
    assert "dark-adapted mice" not in override

    # `auto` on a photopic-only export: no parameter can say so, the runner records it.
    recorded = _prose("erg_traces", {}, {"layout": {"meta": {"adaptation": "photopic"}}})
    assert "photopic (cone-driven)" in recorded

    # The bar and the curve share the helper.
    assert "photopic" in _prose("erg_bwave_bar", {"stimulus_type": "photopic_flash"})
    assert "Photopic" in _prose("erg_intensity_response", {"stimulus_type": "photopic_flash"})


def test_erg_intensity_response_drops_the_fit_paragraph_when_fit_is_off():
    """`fit=False` runs the skill with no curve fitting at all. Every word of the Naka-Rushton
    paragraph — and both of its citations — described a model that never ran."""
    on = methods.build(load_skill("erg_intensity_response"), {})
    assert "Naka-Rushton" in on["text"]
    assert any("Naka" in c for c in on["citations"])
    assert any("SciPy" in c for c in on["citations"])

    off = methods.build(load_skill("erg_intensity_response"), {"fit": "false"})
    assert "Naka-Rushton" not in off["text"]
    assert "No intensity-response model was fit" in off["text"]
    assert not any("Naka" in c for c in off["citations"]), "a citation for a model that never ran"
    assert not any("SciPy" in c for c in off["citations"])


def test_erg_intensity_response_states_the_r2_threshold_and_its_spread():
    """"did not support a saturating fit" IS `min_r2` — the number that says which conditions were
    dropped. And `spread` decides whether any spread is drawn at all."""
    assert "R² ≥ 0.3" in _prose("erg_intensity_response", {})
    assert "R² ≥ 0.6" in _prose("erg_intensity_response", {"min_r2": "0.6"})

    assert "error bars spanning the standard error of the mean" in \
        _prose("erg_intensity_response", {})
    assert "a shaded band spanning the standard deviation" in \
        _prose("erg_intensity_response", {"spread": "band", "error": "sd"})
    none = _prose("erg_intensity_response", {"spread": "none"})
    assert "with no spread drawn" in none and "standard error" not in none


def test_erg_traces_central_mean_does_not_claim_a_representative_eye():
    """`central="mean"` titles the figure "Mean … ERG" while the paragraph said representatives are
    shown "rather than shown as group means" — the prose contradicted the figure's own title."""
    rep = _prose("erg_traces", {})
    assert "a single representative eye is shown" in rep

    mean = _prose("erg_traces", {"central": "mean", "error": "ci95"})
    assert "representative eye" not in mean
    assert "averaged point-by-point into a mean trace" in mean
    assert "a shaded band spanning a 95% confidence interval" in mean

    individual = _prose("erg_traces", {"central": "none"})
    assert "representative eye" not in individual
    assert "every contributing recording is drawn at equal weight" in individual


def test_erg_flicker_describes_the_view_it_actually_drew():
    """`view` picks ONE of two figures and the sentence claimed both at once: the default waveform
    grid draws no amplitude-versus-frequency plot, and the summary view draws no waveform grid."""
    wave = _prose("erg_flicker", {})
    assert "The steady-state waveform is shown per condition" in wave
    assert "plotted against frequency" not in wave

    summary = _prose("erg_flicker", {"view": "summary"})
    assert "N1–P1 amplitude is plotted against flicker frequency" in summary
    assert "The steady-state waveform is shown" not in summary


def test_erg_manual_marks_are_disclosed():
    """An operator-set landmark moves the time the amplitude is read at and the runner RE-MEASURES
    there — the numbers are not the ones the automatic window produced."""
    import json

    marks = json.dumps({"Control|1.0||": {"b_ms": 55.0}, "Untreated|1.0||": {"a_ms": 12.0}})
    for skill_id in ("erg_traces", "erg_bwave_bar", "erg_intensity_response", "erg_flicker"):
        assert "Landmark times" not in _prose(skill_id, {}), skill_id
        text = _prose(skill_id, {"manual_marks": marks})
        assert "set by the operator for 2 segment(s)" in text, skill_id

    # Where a device-metrics table outranks the marks, the sentence says so rather than claiming
    # they always applied.
    assert "device markers" in _prose("erg_bwave_bar", {"manual_marks": marks})
    assert "device markers" not in _prose("erg_traces", {"manual_marks": marks})


# --- the result-changing params the board named next -------------------------------------------


def test_proteomics_de_names_the_imputation_it_actually_ran():
    """`missing` is the knob that moves a proteomics fold-change further than the choice of test
    does: the default per-protein mean impute biases genuinely missing-not-at-random dropouts
    toward NO CHANGE, while `mindet`/`minprob` fill from the detection-limit tail and preserve
    them. The paragraph said "mean-imputed" on every run."""
    mean = _prose("proteomics_de", {})
    assert "at the protein's observed group mean" in mean
    assert "biases genuinely missing-not-at-random dropouts toward no change" in mean

    mindet = _prose("proteomics_de", {"missing": "mindet"})
    assert "1st percentile of that sample's observed intensities" in mindet
    assert "group mean" not in mindet

    minprob = _prose("proteomics_de", {"missing": "minprob"})
    assert "downshifted-normal draw" in minprob and "Perseus" in minprob


def test_proteomics_de_log_transform_claim_follows_log_input():
    """`log_input=True` means the intensities ARRIVED log-scaled and the runner transforms
    nothing — the paragraph opened by claiming a log2 transform that had not happened."""
    assert "were log2-transformed" in _prose("proteomics_de", {})
    already = _prose("proteomics_de", {"log_input": "true"})
    assert "already log-scaled" in already and "were log2-transformed" not in already


def test_proteomics_de_names_the_contrast():
    """"between the two groups" names neither, and the contrast is the whole claim."""
    assert "between the two sample groups" in _prose("proteomics_de", {})
    named = _prose("proteomics_de", {"group_a": "Tumour", "group_b": "Normal"})
    assert "matching 'Tumour' and 'Normal'" in named


def test_violin_names_the_test_behind_its_brackets_and_its_scale():
    """The violin draws brackets from the same `_stats.test_pairs` call as the box plot, and
    neither its methods paragraph nor its caption named the test. `normalize=False` skips both
    `normalize_total` and `log1p`, so "log1p-normalized" was a claim about a skipped step."""
    plain = methods.build(load_skill("violin"), {})
    assert "log1p-normalized" in plain["text"]
    assert "compared with" not in plain["text"]
    assert SCIPY not in plain["citations"]

    raw = _prose("violin", {"normalize": "false"})
    assert "log1p-normalized" not in raw
    assert "already-normalized (no further scaling applied)" in raw

    tested = methods.build(load_skill("violin"),
                           {"pairs": "cluster 0~cluster 1", "correction": "bonferroni"})
    assert "Welch's t-test" in tested["text"] and "Bonferroni" in tested["text"]
    assert SCIPY in tested["citations"]


def test_violin_reports_the_grouping_it_actually_used():
    """When the requested `groupby` column is absent the runner clusters the cells itself and groups
    by Leiden — the figure says so in its title and axis, and the paragraph went on naming the
    column the user asked for. It is also the only place `resolution` is recorded."""
    asked = _prose("violin", {"groupby": "cell_type"})
    assert "grouped by cell_type" in asked

    substituted = methods.build(
        load_skill("violin"), {"groupby": "cell_type"},
        figure={"layout": {"meta": {"clustered": {"requested": "cell_type", "groupby": "leiden",
                                                  "resolution": 1.2}}}})["text"]
    assert "grouped by Leiden clusters computed on the data at resolution 1.2" in substituted
    assert "the requested 'cell_type' was not present in the data" in substituted
    assert "grouped by cell_type" not in substituted


def test_markers_colour_claim_follows_normalize():
    """`normalize=False` skips `log1p`, so "mean log1p expression" described a transform the run
    did not perform — in the paragraph, in the caption, and on the colour-bar label."""
    assert "mean log1p expression" in _prose("markers", {"standard_scale": "false"})
    assert "mean supplied expression" in \
        _prose("markers", {"standard_scale": "false", "normalize": "false"})


def test_integration_names_the_implementation_that_actually_ran():
    """The runner has never called `harmonypy` — batch correction is Selom Melody, an independent
    implementation of the Harmony method, and the figure TITLE has said so the whole time while the
    paragraph said "integrated with Scanpy and Harmony". Naming the reference package for another
    engine's work is the defect the GSEA paragraph had (gseapy credited for blitzGSEA's runs)."""
    text = _prose("integration", {})
    assert "Selom Melody" in text
    assert "independent implementation of the Harmony algorithm" in text


def test_integration_prose_and_citations_follow_harmony2():
    """`harmony2` is a DIFFERENT diversity penalty and a DIFFERENT ridge (Patikas et al. 2026), not
    a tuning of the 2019 method — so describing the 2019 method, and citing Korsunsky for it, was
    wrong on every Harmony2 run. The citation half is the load-bearing one: a methods section is
    what a reader follows to reproduce the work."""
    spec = load_skill("integration")
    off_text, off_cites = methods.build_body(spec, {})
    on_text, on_cites = methods.build_body(spec, {"harmony2": True, "alpha": 0.35})

    assert "the 2019 method was used as published" in off_text
    assert not [c for c in off_cites if "Harmony2" in c], "Harmony2 cited on a 2019-method run"

    assert "Harmony2 mode was used" in on_text
    assert "different penalty and shrinkage from the 2019 method" in on_text
    assert "lambda = 0.35 x E" in on_text                    # the mode's own alpha, not a default
    assert [c for c in on_cites if "Harmony2" in c], "a Harmony2 run must cite the Harmony2 preprint"
    assert [c for c in on_cites if "Korsunsky" in c], "the base method stays cited"


def test_integration_caption_does_not_print_the_wrong_method_name():
    """A caption names what the reader is looking at, and the method's NAME is a claim it makes."""
    spec = load_skill("integration")
    assert "after Harmony correction" in legends.build_caption(spec, {})
    assert "after Harmony2 correction" in legends.build_caption(spec, {"harmony2": True})

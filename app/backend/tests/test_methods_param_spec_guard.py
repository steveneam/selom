"""WS1.2 — Methods/legend prose ↔ ``param_spec`` accuracy guard.

``companions/methods.py`` and ``companions/legends.py`` hand-write publication prose that
interpolates parameter values by name (``p['top_n']``, ``p.get('fc_threshold')``, …). Those
templates and the skill's ``param_spec`` (its ``skill.json``) are two copies of the same
parameter vocabulary that can silently drift: rename a param in the ``skill.json`` and the
template keeps naming the old key — ``resolved_params`` then serves the *default* (or raises
``KeyError``), so the methods text is confidently wrong about how the figure was made. That
breaks the "is THIS figure reproducible?" promise the methods layer exists to keep.

This guard statically reads every string key each per-skill template pulls off its resolved-
params dict (direct ``p[...]`` / ``p.get(...)`` **and** through same-module helpers that receive
that dict — e.g. ``_erg_adaptation(p)``, legends' ``_contrast(p)``) and asserts each one is a
declared key in that skill's live ``param_spec``. Renaming a referenced param in a ``skill.json``
makes the guard fail; reverting turns it green. It reads the templates only — it does not, and
must not, rewrite the prose.
"""

from __future__ import annotations

import ast
import enum
import pathlib

import pytest

from companions import legends, methods
from skills.contract import load_skill


def _module_funcs(mod) -> dict[str, ast.FunctionDef]:
    """Every module-level (and nested) ``def`` in a companion module, by name — the pool we
    resolve helper calls against."""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    return {n.name: n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)}


def _referenced_keys(func: ast.FunctionDef, params_arg: str,
                     funcs: dict[str, ast.FunctionDef], seen: set[str]) -> set[str]:
    """All string keys read off ``params_arg`` inside ``func`` — ``p['k']`` and ``p.get('k', …)``
    (including inside f-strings) — following calls to same-module helpers that receive
    ``params_arg`` in a positional slot, so a value formatted via a helper is still checked."""
    keys: set[str] = set()
    for node in ast.walk(func):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == params_arg and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            keys.add(node.slice.value)  # p['key']
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name)
                and node.func.value.id == params_arg and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            keys.add(node.args[0].value)  # p.get('key' [, default])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            callee = funcs.get(node.func.id)
            if callee is not None and node.func.id not in seen:
                for i, arg in enumerate(node.args):
                    if (isinstance(arg, ast.Name) and arg.id == params_arg
                            and i < len(callee.args.args)):
                        keys |= _referenced_keys(callee, callee.args.args[i].arg, funcs,
                                                 seen | {node.func.id})
    return keys


def _template_refs(mod, skill_id: str) -> set[str]:
    """The param keys the ``skill_id`` template in ``mod`` references (empty if untemplated)."""
    builder = mod._TEMPLATES.get(skill_id)
    if builder is None:
        return set()
    funcs = _module_funcs(mod)
    fdef = funcs[builder.__name__]
    return _referenced_keys(fdef, fdef.args.args[0].arg, funcs, {builder.__name__})


_CASES = (
    [("methods", sid) for sid in sorted(methods._TEMPLATES)]
    + [("legends", sid) for sid in sorted(legends._TEMPLATES)]
)
_MODULES = {"methods": methods, "legends": legends}


@pytest.mark.parametrize("module,skill_id", _CASES)
def test_template_references_only_declared_params(module, skill_id):
    """Every parameter a hand-written template names must be a live ``param_spec`` key — so a
    renamed/removed param in the ``skill.json`` can't leave the prose quoting a stale name."""
    refs = _template_refs(_MODULES[module], skill_id)
    declared = set(load_skill(skill_id).param_spec)
    # ``_``-prefixed keys are NOT user config and have no param_spec entry by design: they are facts
    # resolved at run time from the data and injected by ``build_body`` (e.g.
    # ``_significance_adjusted`` — whether the DE table carried a multiple-testing-corrected column,
    # which decides if the prose may claim Benjamini-Hochberg). They cannot go stale against a
    # skill.json rename, which is what this guard protects; the reserved prefix keeps them out of
    # ``resolved_params``' recorded config too.
    stale = sorted(r for r in refs - declared if not r.startswith("_"))
    assert not stale, (
        f"{module}.py template for {skill_id!r} references param(s) {stale} absent from its "
        f"param_spec {sorted(declared)} — the prose would quote a default/wrong value. Rename "
        f"the token in the template or restore it in skills/**/{skill_id}/skill.json."
    )


# ── the OTHER direction: a declared param the prose never mentions ─────────────────────────────
#
# The guard above is exact in ONE direction — it catches prose naming a param that no longer
# exists. It cannot catch the defect that actually shipped on 2026-08-05: prose describing a step
# the run SKIPPED. `pvca`'s methods said "Features were standardized" unconditionally while the
# runner only scales when `normalize` is set, and `cepo`'s said "genes detected in at least N cells"
# while the runner filters CELL TYPES. Both were green through nine gates, because a template that
# never reads `normalize` cannot be caught by a rule about templates that read the wrong key.
#
# So this asserts the reverse: every param a skill declares is either named by its prose or listed
# below, deliberately. The list is a RATCHET in the `API_ONLY_KNOBS` shape — exact in both
# directions, so it can only shrink and nothing new joins it silently.
#
# ⚑ EVERY WAIVER CARRIES ITS VERDICT. The list began (2026-08-05) as a RAW capture — 269 params
# across 61 templates, none of them examined — and the value of triaging it is that the two buckets
# are nothing alike. `erg_traces.band_color` is a colour; `erg_intensity_response.fit` switches the
# entire Naka-Rushton model off while the paragraph went on describing it. A flat set cannot tell
# those apart, so the split is recorded ON each entry and the guard enforces the vocabulary:
#
#   PRESENTATION — decides how the figure LOOKS. The prose asserts nothing about it, and adding a
#                  sentence would pad the paragraph without making the figure more reproducible.
#   INTERNAL     — plumbing: caps, engine seeds, advanced overrides that do not change what the
#                  figure claims. Named here so "not user-facing" is a decision, not an oversight.
#   VIA_OUTCOME  — the claim IS made, from the runner's recorded outcome (a ``_``-prefixed fact
#                  lifted by ``build_body`` / ``legends._facts``) rather than from the param name.
#                  Strictly better than quoting the param, because these params are INERT unless a
#                  data-dependent branch fired, and only the runner knows whether it did.
#   IN_METHODS   — legends only: the methods paragraph carries the claim and the caption makes none
#                  this param could falsify. A caption is one sentence about one figure, not a
#                  second copy of the recipe.
#   UNTRIAGED    — the raw capture, not yet examined. This is the DEBT, and it is a counted ratchet
#                  (`_UNTRIAGED_CEILING`) that can only shrink.
#
# There is deliberately no OWED verdict: a param whose prose is owed gets the SENTENCE and leaves
# this list. A waiver that admits it is protecting a known lie would be worse than no waiver.
#
# The immediate value never depended on the triage: a NEW param must either be described in the
# prose or be added here on purpose. Both defects of 2026-08-05 arrived exactly that way — a knob
# became reachable and its methods sentence was never re-checked.


class Silence(str, enum.Enum):
    PRESENTATION = "presentation"
    INTERNAL = "internal"
    VIA_OUTCOME = "via-outcome"
    IN_METHODS = "in-methods"
    UNTRIAGED = "untriaged"


_P, _I, _U = Silence.PRESENTATION, Silence.INTERNAL, Silence.UNTRIAGED
_OUT, _M = Silence.VIA_OUTCOME, Silence.IN_METHODS


def _untriaged(*keys: str) -> dict[str, Silence]:
    """The raw 2026-08-05 capture, verbatim — not yet examined. Shrinks as templates are triaged."""
    return {k: _U for k in keys}


PROSE_SILENT: dict[tuple[str, str], dict[str, Silence]] = {
    ("methods", "annotate"): _untriaged("embedding", "normalize"),
    # ("methods", "boxplot") is GONE — the first entry this ratchet retired. All 11 of its params
    # are described now, and two of its claims were live printed-vs-computed lies the backlog
    # pointed straight at: "box-and-whisker … 1.5× the IQR" on a `style="strip"` run that draws no
    # box at all, and "ordered by descending median" on a run where `order` puts the user's named
    # categories first. Both read green through nine gates because a template that never mentions a
    # param cannot be caught by a rule about templates that mention the wrong one.
    ("methods", "cluster"): _untriaged("normalize"),
    ("methods", "composition"): _untriaged("order", "orientation", "sort_by"),
    ("methods", "deg"): _untriaged(
        "condition_col", "covariate_col", "group_col", "group_val", "label_col", "method",
        "min_cells", "min_count", "normalization", "normalize", "time_col"
    ),
    ("methods", "diff_abundance"): _untriaged("condition_col", "label_col", "min_cells",
                                              "sample_col"),
    ("methods", "enrichment"): _untriaged("fc_threshold", "fdr_threshold", "gene_sets"),
    # ── THE ERG FAMILY, TRIAGED 2026-08-05 ──────────────────────────────────────────────────────
    # The board predicted a confirmed-waive pass ("mostly pipeline-level/internal"). It was half
    # wrong: 26 of these 50 params changed what the figure CLAIMS and the paragraph said otherwise,
    # so they got sentences and left this list. What survives is genuinely presentational — colours,
    # alphas, scale-bar lengths, legend toggles, display units the prose never quotes.
    ("methods", "erg_bwave_bar"): {
        "bar_fill": _P, "hline": _P, "hline_label": _P, "legend": _P,
        # The paragraph quotes no unit; the axis title and the Statistics table carry it.
        "display_unit": _P,
    },
    ("methods", "erg_flicker"): {
        "marks": _P, "mark_labels": _P, "scale_ms": _P, "scale_uv": _P, "display_unit": _P,
    },
    ("methods", "erg_intensity_response"): {
        "band_alpha": _P, "band_color": _P, "boundary_lines": _P, "display_unit": _P,
        # Unlike the bar, this paragraph makes no claim about individual eyes being drawn, so
        # silence stays honest whichever way the knob is set.
        "points": _P,
    },
    ("methods", "erg_traces"): {
        "band_alpha": _P, "band_color": _P, "boundary_lines": _P, "display_unit": _P,
        "error_every": _P, "marks": _P, "mark_labels": _P, "scale_ms": _P, "scale_uv": _P,
    },
    # ────────────────────────────────────────────────────────────────────────────────────────────
    ("methods", "facs_gating"): _untriaged(
        "bins", "comp_matrix", "max_events", "transform_t", "x_channel", "y_channel"
    ),
    # ("methods", "gsea") is GONE — `engine` was its last waiver, and the paragraph now names the
    # engine that actually ran (recorded by the runner, because `auto` resolves at run time) and
    # cites it, instead of crediting gseapy for blitzGSEA's and the in-house engine's work.
    ("methods", "heatmap"): _untriaged("annotations", "cut_k", "quant_track", "split_by",
                                       "split_by_cut"),
    ("methods", "integration"): _untriaged("alpha", "harmony2"),
    ("methods", "line"): _untriaged("central", "markers", "points", "x", "y"),
    # ("methods", "markers") is GONE — `normalize` skips log1p, and the dotplot's colour was
    # described as "mean log1p expression" either way.
    ("methods", "normalization_qc"): _untriaged("max_cells"),
    ("methods", "pathway"): _untriaged("fc_threshold", "fdr_threshold"),
    ("methods", "pca"): _untriaged("group_regex", "label_points"),
    # ("methods", "proteomics_de") is GONE — the second entry this ratchet retired, and the one the
    # board pointed at: `missing` chooses between a mean impute that biases MNAR dropouts toward no
    # change and two left-censored fills that preserve them, and the paragraph said "mean-imputed"
    # on every run. `log_input` was the same shape one clause earlier ("log2-transformed" on a run
    # that transforms nothing).
    ("methods", "pseudotime_genes"): _untriaged("groupby", "n_bins", "normalize"),
    ("methods", "qq"): _untriaged("max_points", "p_col", "top_n"),
    ("methods", "regression"): _untriaged("fit", "group", "label"),
    ("methods", "sankey"): _untriaged("max_links"),
    ("methods", "scorecard"): _untriaged("fill", "max_rows"),
    ("methods", "string_network"): _untriaged("fdr_threshold", "max_genes"),
    ("methods", "trajectory"): _untriaged("embedding", "groupby", "normalize"),
    ("methods", "upset"): _untriaged("sort_by"),
    ("methods", "violin"): {
        # Leiden `resolution` applies ONLY when the requested `groupby` column is absent and the
        # runner clusters the cells itself. Quoting the param would claim a clustering that usually
        # never happened; the paragraph states it from `layout.meta.clustered` instead, which is the
        # only place that resolution is recorded at all.
        "resolution": _OUT,
    },
    ("methods", "volcano"): _untriaged("highlight"),
    ("legends", "annotate"): _untriaged("embedding", "groupby", "normalize"),
    ("legends", "boxplot"): _untriaged(
        "add_count", "correction", "notched", "order", "orientation", "pairs", "points",
        "sig_test", "style"
    ),
    ("legends", "cepo"): _untriaged("exprs_pct", "min_cells", "normalize"),
    ("legends", "cluster"): _untriaged("n_neighbors", "n_pcs", "normalize"),
    ("legends", "composition"): _untriaged("order", "orientation", "sort_by"),
    ("legends", "corr_heatmap"): _untriaged("cluster"),
    ("legends", "deg"): _untriaged(
        "condition_col", "covariate_col", "group_col", "group_val", "groupby", "label",
        "label_col", "method", "min_cells", "min_count", "mode", "normalization", "normalize",
        "sample_col", "time_col"
    ),
    ("legends", "diff_abundance"): _untriaged(
        "condition_col", "label_col", "min_cells", "normalization", "sample_col"
    ),
    ("legends", "enrichment"): _untriaged("fc_threshold", "fdr_threshold", "gene_sets"),
    ("legends", "go_graph"): _untriaged("fc_threshold", "fdr_threshold", "namespace"),
    # ── GSEA + ssGSEA, TRIAGED 2026-08-05 (with NEXT#3's control pass over the same runners) ──────
    # Both captions describe the figure's GEOMETRY — the running-score curve, the sample x pathway
    # heatmap — and name no library, no engine and no statistic, so none of these can falsify one.
    # The methods paragraph states all of them. Triaged only after reading both runners' bodies,
    # which is what turned up three live printed-vs-computed lies in the METHODS half of the same
    # templates: the paragraph credited `gseapy.prerank` whatever `engine` resolved to (`auto`
    # resolves from what is importable, so the params never knew), quoted the raw `n_perm` while
    # both library engines floor it at 100 and read an explicit 0 as 1000, and claimed a
    # Benjamini-Hochberg correction — with the citation — on single-set and in-house runs that
    # correct nothing. Those left the prose, not this list.
    ("legends", "gsea"): {
        "engine": _M, "gene_set": _M, "gene_sets": _M, "n_perm": _M, "set_name": _M, "weight": _M,
    },
    ("legends", "heatmap"): _untriaged(
        "annotations", "cluster", "cut_k", "quant_track", "split_by", "split_by_cut"
    ),
    ("legends", "integration"): _untriaged(
        "alpha", "harmony2", "max_iter_harmony", "n_hvg", "n_neighbors", "n_pcs", "normalize",
        "theta"
    ),
    # ("legends", "markers") is GONE — two wrong claims on the DEFAULT path: `standard_scale` is
    # default-true, so the colour encodes [0,1]-scaled expression and the caption called it the
    # mean; and "top N marker genes" named no criterion while `rank_by` chooses between a p-value
    # ranking and a one-versus-rest effect size.
    ("legends", "normalization_qc"): _untriaged(
        "doublet_threshold", "doublets", "filter", "max_cells", "nmads"
    ),
    ("legends", "pathway"): _untriaged("fc_threshold", "fdr_threshold"),
    ("legends", "pca"): _untriaged("group_regex", "label_points", "scale"),
    ("legends", "proteomics_de"): {
        # The caption names the contrast, the thresholds, the label count and any non-default
        # imputation. It makes no claim about the input scale, the sparsity filter or which t-test
        # ran — the methods paragraph states all three, and a caption is one sentence.
        "log_input": _M, "min_valid": _M, "stats": _M,
    },
    ("legends", "pseudotime_genes"): _untriaged("groupby", "n_bins", "normalize", "root"),
    ("legends", "pvca"): _untriaged("normalize", "pct_threshold"),
    ("legends", "regression"): _untriaged("fit", "group", "label"),
    ("legends", "sankey"): _untriaged("max_links"),
    ("legends", "scorecard"): _untriaged("fill", "invert_metrics", "max_rows", "normalize"),
    # `top_n` is deliberately absent: the caption quoted it as a COUNT ("the top 25 gene sets")
    # when it is a cap, and named no criterion for "top" — the pair of defects that retired the
    # `markers` caption. It now reads the realized count and says "vary most across samples", so it
    # is described rather than waived. `zscore` stays silent honestly: the caption claims "pathway
    # activity" without asserting a scale, and the colourbar names it on the figure itself.
    ("legends", "ssgsea"): {
        "gene_set": _M, "gene_sets": _M, "max_size": _M, "min_size": _M, "weight": _M,
        "zscore": _M,
    },
    ("legends", "string_network"): _untriaged("fdr_threshold", "max_genes"),
    ("legends", "trajectory"): _untriaged("embedding", "groupby", "normalize", "root", "threshold"),
    ("legends", "umap_scrna"): _untriaged("n_hvg", "n_neighbors", "n_pcs", "normalize"),
    ("legends", "upset"): _untriaged("mode", "sort_by"),
    ("legends", "violin"): {
        # The caption names the gene, the grouping actually used and the bracket test. It claims no
        # scale, no ordering and no n= labels, so those three cannot make it wrong; `resolution` is
        # reported through the recorded clustering, exactly as in the methods paragraph.
        "normalize": _M, "order": _M, "add_count": _M, "resolution": _OUT,
    },
    ("legends", "volcano"): _untriaged("highlight"),
}

# The DEBT ratchet. Every entry still tagged UNTRIAGED is a param nobody has asked "does the prose
# owe this a sentence?" — the state the whole list started in. It can only shrink: triaging a
# template either gives a param a sentence (it leaves the list) or records a verdict (it stays with
# PRESENTATION / INTERNAL). Lower this number when you triage; a new UNTRIAGED entry pushes over it
# and fails, which is the point — nothing joins the backlog silently.
_UNTRIAGED_CEILING = 166
@pytest.mark.parametrize("module,skill_id", _CASES)
def test_every_declared_param_is_described_or_deliberately_silent(module, skill_id):
    """The reverse direction — a declared param the prose never mentions is either described or
    written down. Prevents the printed-vs-computed lie: prose asserting a step the run skipped."""
    refs = {r for r in _template_refs(_MODULES[module], skill_id) if not r.startswith("_")}
    declared = set(load_skill(skill_id).param_spec)
    waived = set(PROSE_SILENT.get((module, skill_id), {}))

    undocumented = sorted(declared - refs - waived)
    assert not undocumented, (
        f"{module}.py template for {skill_id!r} never mentions param(s) {undocumented}. Either name "
        f"them in the prose (and make any claim they control CONDITIONAL on their value), or add "
        f"them to PROSE_SILENT with a verdict. Silence is allowed; silence by accident is not."
    )

    # Stale in the other direction: a param that GAINED a sentence, or was removed from the
    # skill.json, must leave the list — or the waiver quietly protects a name that no longer needs
    # protecting and the backlog stops shrinking on paper while standing still in fact.
    stale = sorted(w for w in waived if w not in declared or w in refs)
    assert not stale, (
        f"PROSE_SILENT[({module!r}, {skill_id!r})] still waives {stale}, which the template now "
        f"describes (or the skill.json no longer declares). Remove them — the list only shrinks."
    )


def test_prose_silent_names_only_live_skills():
    """Guard the guard: an entry for a template that no longer exists is dead weight pretending to
    be a tracked debt."""
    live = set(_CASES)
    assert sorted(k for k in PROSE_SILENT if k not in live) == []


def test_every_waiver_carries_a_declared_verdict():
    """Guard the guard: a bare string (or any value outside the vocabulary) would re-create the flat
    set this list started as, where a colour and a model switch look identical."""
    bad = sorted((f"{m}.{s}.{k}", repr(v)) for (m, s), d in PROSE_SILENT.items()
                 for k, v in d.items() if not isinstance(v, Silence))
    assert bad == [], f"waivers with no declared verdict: {bad}"


def test_untriaged_backlog_only_shrinks():
    """The debt ratchet. UNTRIAGED means "nobody has asked whether the prose owes this a sentence" —
    the state every entry started in. Triaging is the work; this makes the backlog a number that can
    only go down, and stops a new param joining it silently under cover of the old ones."""
    n = sum(1 for d in PROSE_SILENT.values() for v in d.values() if v is Silence.UNTRIAGED)
    assert n <= _UNTRIAGED_CEILING, (
        f"{n} UNTRIAGED waivers, ceiling {_UNTRIAGED_CEILING}. A new param may not join the "
        f"backlog: give it a sentence, or a PRESENTATION / INTERNAL verdict."
    )
    assert n == _UNTRIAGED_CEILING, (
        f"{n} UNTRIAGED waivers but the ceiling still says {_UNTRIAGED_CEILING} — lower it to {n}, "
        f"or the backlog shrinks on paper while the ratchet stays slack."
    )


def test_extractor_is_not_vacuous():
    """Guard the guard: the AST reader must actually resolve the known params of representative
    templates (direct refs and a helper-routed one), so it can never pass by extracting nothing."""
    assert {"fc_threshold", "fdr_threshold", "top_n"} <= _template_refs(methods, "volcano")
    assert {"top_n", "groupby", "mode", "reference", "treatment"} <= _template_refs(methods, "deg")
    assert "adaptation" in _template_refs(methods, "erg_traces")  # reached via _erg_adaptation(p)
    assert {"reference", "treatment"} <= _template_refs(legends, "deg")  # reached via _contrast(p)

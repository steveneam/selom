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
# ⚑ THIS LIST IS A RAW FIRST CAPTURE, NOT A TRIAGED ONE. It is every unmentioned param as of
# 2026-08-05 (269 across 61 templates), which is the backlog the board predicted this guard would
# surface. It has NOT been split into "cosmetic, no sentence owed" (`erg_traces.band_color`,
# `scale_ms`) versus "changes the result and the prose owes it a sentence" — and the second bucket
# is real and load-bearing: `deg.method` decides WHICH TEST ran, `proteomics_de.missing` decides an
# imputation that biases fold-changes toward zero, `boxplot.sig_test`/`correction` decide the stars
# drawn on the figure. Doing that triage is the next session's work on this item.
#
# The immediate value does not depend on the triage: a NEW param must now either be described in
# the prose or be added here on purpose. Both defects of 2026-08-05 arrived exactly that way — a
# knob became reachable and its methods sentence was never re-checked.
PROSE_SILENT: dict[tuple[str, str], set[str]] = {
    ("methods", "annotate"): {"embedding", "normalize"},
    # ("methods", "boxplot") is GONE — the first entry this ratchet retired. All 11 of its params
    # are described now, and two of its claims were live printed-vs-computed lies the backlog
    # pointed straight at: "box-and-whisker … 1.5× the IQR" on a `style="strip"` run that draws no
    # box at all, and "ordered by descending median" on a run where `order` puts the user's named
    # categories first. Both read green through nine gates because a template that never mentions a
    # param cannot be caught by a rule about templates that mention the wrong one.
    ("methods", "cluster"): {"normalize"},
    ("methods", "composition"): {"order", "orientation", "sort_by"},
    ("methods", "deg"): {
        "condition_col", "covariate_col", "group_col", "group_val", "label_col", "method",
        "min_cells", "min_count", "normalization", "normalize", "time_col"
    },
    ("methods", "diff_abundance"): {"condition_col", "label_col", "min_cells", "sample_col"},
    ("methods", "enrichment"): {"fc_threshold", "fdr_threshold", "gene_sets"},
    ("methods", "erg_bwave_bar"): {
        "bar_fill", "comparisons", "correction", "display_unit", "error", "hline", "hline_label",
        "intensity_group", "legend", "manual_marks", "points", "show_error", "sig_test",
        "stimulus_type", "value_col", "wave"
    },
    ("methods", "erg_flicker"): {
        "display_unit", "manual_marks", "mark_labels", "marks", "scale_ms", "scale_uv", "view"
    },
    ("methods", "erg_intensity_response"): {
        "band_alpha", "band_color", "boundary_lines", "display_unit", "error", "fit",
        "manual_marks", "min_r2", "points", "spread", "stimulus_type", "value_col"
    },
    ("methods", "erg_traces"): {
        "band_alpha", "band_color", "boundary_lines", "central", "display_unit", "error",
        "error_every", "manual_marks", "mark_labels", "marks", "role", "scale_ms", "scale_uv",
        "spread", "stimulus_type"
    },
    ("methods", "facs_gating"): {
        "bins", "comp_matrix", "max_events", "transform_t", "x_channel", "y_channel"
    },
    ("methods", "gsea"): {"engine"},
    ("methods", "heatmap"): {"annotations", "cut_k", "quant_track", "split_by", "split_by_cut"},
    ("methods", "integration"): {"alpha", "harmony2"},
    ("methods", "line"): {"central", "markers", "points", "x", "y"},
    ("methods", "markers"): {"normalize"},
    ("methods", "normalization_qc"): {"max_cells"},
    ("methods", "pathway"): {"fc_threshold", "fdr_threshold"},
    ("methods", "pca"): {"group_regex", "label_points"},
    ("methods", "proteomics_de"): {"group_a", "group_b", "log_input", "missing", "top_n"},
    ("methods", "pseudotime_genes"): {"groupby", "n_bins", "normalize"},
    ("methods", "qq"): {"max_points", "p_col", "top_n"},
    ("methods", "regression"): {"fit", "group", "label"},
    ("methods", "sankey"): {"max_links"},
    ("methods", "scorecard"): {"fill", "max_rows"},
    ("methods", "string_network"): {"fdr_threshold", "max_genes"},
    ("methods", "trajectory"): {"embedding", "groupby", "normalize"},
    ("methods", "upset"): {"sort_by"},
    ("methods", "violin"): {
        "add_count", "correction", "normalize", "order", "pairs", "resolution", "sig_test"
    },
    ("methods", "volcano"): {"highlight"},
    ("legends", "annotate"): {"embedding", "groupby", "normalize"},
    ("legends", "boxplot"): {
        "add_count", "correction", "notched", "order", "orientation", "pairs", "points",
        "sig_test", "style"
    },
    ("legends", "cepo"): {"exprs_pct", "min_cells", "normalize"},
    ("legends", "cluster"): {"n_neighbors", "n_pcs", "normalize"},
    ("legends", "composition"): {"order", "orientation", "sort_by"},
    ("legends", "corr_heatmap"): {"cluster"},
    ("legends", "deg"): {
        "condition_col", "covariate_col", "group_col", "group_val", "groupby", "label",
        "label_col", "method", "min_cells", "min_count", "mode", "normalization", "normalize",
        "sample_col", "time_col"
    },
    ("legends", "diff_abundance"): {
        "condition_col", "label_col", "min_cells", "normalization", "sample_col"
    },
    ("legends", "enrichment"): {"fc_threshold", "fdr_threshold", "gene_sets"},
    ("legends", "go_graph"): {"fc_threshold", "fdr_threshold", "namespace"},
    ("legends", "gsea"): {"engine", "gene_set", "gene_sets", "n_perm", "set_name", "weight"},
    ("legends", "heatmap"): {
        "annotations", "cluster", "cut_k", "quant_track", "split_by", "split_by_cut"
    },
    ("legends", "integration"): {
        "alpha", "harmony2", "max_iter_harmony", "n_hvg", "n_neighbors", "n_pcs", "normalize",
        "theta"
    },
    ("legends", "markers"): {"method", "normalize", "rank_by", "standard_scale"},
    ("legends", "normalization_qc"): {
        "doublet_threshold", "doublets", "filter", "max_cells", "nmads"
    },
    ("legends", "pathway"): {"fc_threshold", "fdr_threshold"},
    ("legends", "pca"): {"group_regex", "label_points", "scale"},
    ("legends", "proteomics_de"): {
        "group_a", "group_b", "log_input", "min_valid", "missing", "stats", "top_n"
    },
    ("legends", "pseudotime_genes"): {"groupby", "n_bins", "normalize", "root"},
    ("legends", "pvca"): {"normalize", "pct_threshold"},
    ("legends", "regression"): {"fit", "group", "label"},
    ("legends", "sankey"): {"max_links"},
    ("legends", "scorecard"): {"fill", "invert_metrics", "max_rows", "normalize"},
    ("legends", "ssgsea"): {"gene_set", "gene_sets", "max_size", "min_size", "weight", "zscore"},
    ("legends", "string_network"): {"fdr_threshold", "max_genes"},
    ("legends", "trajectory"): {"embedding", "groupby", "normalize", "root", "threshold"},
    ("legends", "umap_scrna"): {"n_hvg", "n_neighbors", "n_pcs", "normalize"},
    ("legends", "upset"): {"mode", "sort_by"},
    ("legends", "violin"): {
        "add_count", "context", "correction", "normalize", "order", "pairs", "resolution",
        "sig_test"
    },
    ("legends", "volcano"): {"highlight"},
}
@pytest.mark.parametrize("module,skill_id", _CASES)
def test_every_declared_param_is_described_or_deliberately_silent(module, skill_id):
    """The reverse direction — a declared param the prose never mentions is either described or
    written down. Prevents the printed-vs-computed lie: prose asserting a step the run skipped."""
    refs = {r for r in _template_refs(_MODULES[module], skill_id) if not r.startswith("_")}
    declared = set(load_skill(skill_id).param_spec)
    waived = PROSE_SILENT.get((module, skill_id), set())

    undocumented = sorted(declared - refs - waived)
    assert not undocumented, (
        f"{module}.py template for {skill_id!r} never mentions param(s) {undocumented}. Either name "
        f"them in the prose (and make any claim they control CONDITIONAL on their value), or add "
        f"them to PROSE_SILENT with a reason. Silence is allowed; silence by accident is not."
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


def test_extractor_is_not_vacuous():
    """Guard the guard: the AST reader must actually resolve the known params of representative
    templates (direct refs and a helper-routed one), so it can never pass by extracting nothing."""
    assert {"fc_threshold", "fdr_threshold", "top_n"} <= _template_refs(methods, "volcano")
    assert {"top_n", "groupby", "mode", "reference", "treatment"} <= _template_refs(methods, "deg")
    assert "adaptation" in _template_refs(methods, "erg_traces")  # reached via _erg_adaptation(p)
    assert {"reference", "treatment"} <= _template_refs(legends, "deg")  # reached via _contrast(p)

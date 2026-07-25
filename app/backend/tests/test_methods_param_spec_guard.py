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


def test_extractor_is_not_vacuous():
    """Guard the guard: the AST reader must actually resolve the known params of representative
    templates (direct refs and a helper-routed one), so it can never pass by extracting nothing."""
    assert {"fc_threshold", "fdr_threshold", "top_n"} <= _template_refs(methods, "volcano")
    assert {"top_n", "groupby", "mode", "reference", "treatment"} <= _template_refs(methods, "deg")
    assert "adaptation" in _template_refs(methods, "erg_traces")  # reached via _erg_adaptation(p)
    assert {"reference", "treatment"} <= _template_refs(legends, "deg")  # reached via _contrast(p)

"""Drift guard for the shared column-synonym vocabulary (:mod:`engine.vocab`).

Two halves, one invariant — *the DE / metabolomics synonym vocabulary has exactly one definition*:

1. **In-lane single-sourcing (identity).** Every engine consumer that reads the vocabulary — classify
   (:mod:`engine.databundle`), the role resolver (:mod:`engine.columns`), the D1 fit/schema gate
   (:mod:`engine.compat`), the D2 usability gate (:mod:`engine.frame_schema`), and the DE-column QC
   (:mod:`engine.qc`) — must reference the *same tuple objects* the primitive exports, not an equal
   copy. Identity matters: ``columns._ROLE_BY_SYNONYMS_ID`` keys on ``id(...)`` and
   ``frame_schema._NUMERIC_SYNONYM_SETS`` holds the tuple objects, so a re-typed but ``==``-equal copy
   would silently break role resolution. If any consumer re-hardcodes the set, identity breaks here.

2. **No second copy forks (AST scan).** A scan of the product source tree flags any *new* module that
   defines its own collection-literal of these synonyms. The engine primitive (``engine/vocab.py``) is
   the one allowed definition. The six ``skills/*/run_real.py`` forks (fold-change / p-value / gene)
   were converged onto this primitive by restructure WS3.1, so the allow-list is now empty — any new
   fork anywhere fails the test with a pointer at the primitive.

3. **The six DE runners single-source the RESOLVER, not just the vocabulary (identity + AST).** WS3.1
   converged the vocabulary and left the MATCHER forked into six byte-identical ``_pick`` copies, so
   one runner could silently diverge (exact vs substring, a different tie-break, a dropped override)
   with every guard above still green — finding A19. Each runner now binds ``resolve`` to
   :func:`engine.columns.resolve` (identity), and a second AST scan fails on any ``skills/**``
   function shaped like a re-forked matcher (a membership test nested two levels deep in iteration
   over its own parameters).

Co-located in ``engine/`` (not ``tests/``) because the parallel-sprint ENG lane owns
``app/backend/engine/**`` and must not touch ``tests/``; the backend has no ``testpaths`` restriction,
so pytest collects it in the same ``-m "not slow"`` gate. The backend root is found by walking up to
the dir holding ``pyproject.toml``, so the file keeps working if it is later relocated to ``tests/``.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

from engine import columns, compat, databundle, frame_schema, qc, vocab

# Historically the six ``skills/*/run_real.py`` runners each carried their own ``_FC_COLS`` /
# ``_P_COLS`` / ``_METRIC_COLS`` copy of the fold-change / p-value vocabulary; restructure WS3.1
# converged them onto :mod:`engine.vocab`, so the allow-list is now empty. Adding a NEW fork anywhere
# fails :func:`test_no_unexpected_synonym_set_fork` — the whole point of an empty allow-list.
KNOWN_OUT_OF_LANE_FORKS: frozenset[str] = frozenset()

# The one allowed engine-side definition.
PRIMITIVE_REL = "engine/vocab.py"

# The six DE runners that read the shared column vocabulary — converged by WS3.1 (vocabulary) and by
# A19 (the resolver). Each binds a module-level ``resolve`` to :func:`engine.columns.resolve`; the
# identity test below locks that.
DE_RUNNER_MODULES = (
    "skills.volcano.run_real",
    "skills.enrichment.run_real",
    "skills.go_graph.run_real",
    "skills.pathway.run_real",
    "skills.string_network.run_real",
    "skills.gsea.run_real",
)

# How many members must overlap for a collection-literal to count as "a copy of the set" (not an
# incidental list that happens to mention one column name, e.g. deg's ``["log2FoldChange", "padj"]``).
_FORK_THRESHOLD = 3

# Dirs never worth scanning (deps, caches, build/VCS metadata) and ``tests/`` (test fixtures build
# DataFrames from these column names as dict keys — not a spine fork; out of this guard's scope).
_SKIP_DIRS = frozenset({
    ".venv", "venv", "__pycache__", ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "node_modules", "tests", "scripts", "oracle_templates", ".idea", ".vscode",
})


def _backend_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (parent / "engine").is_dir():
            return parent
    raise RuntimeError("backend root (dir with pyproject.toml + engine/) not found")


def _literal_strings(node: ast.AST) -> set[str]:
    """Lower-cased string constants of a list/tuple/set literal (``set()`` for anything else)."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {
            e.value.lower()
            for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
    return set()


def _defines_a_synonym_set(path: Path) -> bool:
    """True if the module assigns a collection-literal that overlaps the fold-change or the p-value
    vocabulary by at least ``_FORK_THRESHOLD`` members — i.e. carries its own copy of a synonym set."""
    logfc = set(vocab.DE_LOGFC_SYNONYMS)
    pval = set(vocab.DE_PVAL_SYNONYMS)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        strs = _literal_strings(getattr(node, "value", None))
        if len(strs & logfc) >= _FORK_THRESHOLD or len(strs & pval) >= _FORK_THRESHOLD:
            return True
    return False


def _scan_for_forks(root: Path) -> set[str]:
    # os.walk with in-place dir pruning so heavy trees (``.venv`` — thousands of dep files) are never
    # descended into; ``Path.rglob`` would traverse them before any filter and make the scan crawl.
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                path = Path(dirpath) / name
                if _defines_a_synonym_set(path):
                    found.add(path.relative_to(root).as_posix())
    return found


# --- 1. in-lane single-sourcing (identity) ------------------------------------------------

def test_engine_consumers_share_the_primitive_by_identity():
    lf, pv, mt = vocab.DE_LOGFC_SYNONYMS, vocab.DE_PVAL_SYNONYMS, vocab.METABOLOMICS_TOKENS
    # databundle re-exports the SAME objects under its historical private names.
    assert databundle._LOGFC is lf
    assert databundle._PVAL is pv
    assert databundle._METAB_TOKENS is mt
    # the role resolver, the D1 gate, the D2 gate, and QC all hold the primitive's objects.
    assert columns._LOGFC is lf and columns._PVAL is pv
    assert columns.ROLE_SYNONYMS["logFC"] is lf and columns.ROLE_SYNONYMS["pval"] is pv
    assert compat._FC[1] is lf and compat._SIG[1] is pv
    assert frame_schema._NUMERIC_SYNONYM_SETS == (lf, pv)
    assert frame_schema._NUMERIC_SYNONYM_SETS[0] is lf
    assert frame_schema._NUMERIC_SYNONYM_SETS[1] is pv
    assert qc._PVAL is pv
    # identity-based role reverse-map still resolves (the reason identity, not equality, is required).
    assert columns.role_of_synonyms(lf) == "logFC"
    assert columns.role_of_synonyms(pv) == "pval"


def test_vocabulary_values_are_stable():
    # Locks the exact substring vocabulary a header must contain to resolve to a role. Editing these
    # sets is a deliberate act (a header variant added/removed), not an accidental drift.
    assert vocab.DE_LOGFC_SYNONYMS == (
        "log2foldchange", "logfoldchange", "logfc", "log2fc", "avg_log2fc", "log fold change",
    )
    # Significance is TIERED: adjusted-for-multiple-testing first, raw p second, and the union is a
    # presence set only. WS3.1 (7440f56) pointed runner SELECTION at the union and the raw token won
    # for every non-DESeq2 convention — a raw p plotted on an axis labelled "adjusted". The tiers,
    # their order, and the union's derivation are all pinned so that cannot recur silently.
    assert vocab.DE_PADJ_SYNONYMS == (
        "padj", "p_val_adj", "pvals_adj", "adj.p.val", "adj.pval", "fdr", "qvalue", "q.value",
    )
    assert vocab.DE_PVAL_RAW_SYNONYMS == ("pvalue", "p_val", "p.value", "pval")
    assert vocab.DE_PVAL_SYNONYMS == vocab.DE_PADJ_SYNONYMS + vocab.DE_PVAL_RAW_SYNONYMS


def test_significance_selection_prefers_the_adjusted_tier():
    """The behavioural half of the pin: no ordering of the presence union may be used for selection.

    A guard on the tuples alone would still pass if a runner scanned the union in order, so assert
    the resolver's OUTCOME on the header that exposed the regression (limma: both P.Value and FDR).
    """
    cols = {"logfc": "logFC", "p.value": "P.Value", "fdr": "FDR"}
    assert columns.pick_significance(cols) == ("FDR", True)
    assert columns.pick_significance({"logfc": "logFC", "p.value": "P.Value"}) == ("P.Value", False)
    assert vocab.METABOLOMICS_TOKENS == ("m/z", "hmdb", "metabolite", "kegg c")


# --- 1b. the six DE runners single-source the RESOLVER (identity) --------------------------

def test_de_runners_share_the_column_resolver_by_identity():
    """Every converged DE runner resolves columns through the SAME function the engine exports.

    The vocabulary halves above cannot see a forked *matcher*: six byte-identical ``_pick`` copies
    consumed the one shared vocabulary and every guard stayed green while any one of them could
    diverge (A19). A runner that reintroduces its own picker rebinds or drops this name and fails
    here, with a pointer at the one home.
    """
    import importlib

    for mod_name in DE_RUNNER_MODULES:
        mod = importlib.import_module(mod_name)
        assert getattr(mod, "resolve", None) is columns.resolve, (
            f"{mod_name} must resolve columns through the shared resolver — bind `resolve` to "
            f"engine.columns.resolve (`from engine.columns import resolve`), never a local picker."
        )


# --- 1c. no runner re-forks the MATCHER (AST scan of skills/**) ----------------------------
# The deleted fork's shape, and the shape any re-fork wears whether written as nested ``for`` loops,
# a ``for`` around a comprehension, or one comprehension with two ``for`` clauses::
#
#     for syn in synonyms:                 # iterates a PARAMETER
#         for low, orig in cols.items():   # iterates a PARAMETER
#             if syn in low:               # both operands are ITERATION TARGETS
#                 return orig
#
# All three conditions are required, which is what keeps the scan quiet on ordinary skill code:
# nesting depth >= 2, both operands of the membership test bound as iteration targets, and at least
# one of those iterations reading a parameter of the function. Ordinary lookups (``m in pos``,
# ``sym in adata.var_names``, ``c in _erg.CONDITION_ORDER``) fail one of them and are not flagged, and
# neither is the single-level exact lookup in ``skills/sankey/run_real.py::_pick`` — resolving a
# fixed source/target/value literal is a different question from DE role resolution.

SKILLS_REL = "skills"


def _iter_root(node: ast.AST) -> str | None:
    """The name an iterable expression reads: ``cols`` for ``cols``, ``cols.items()``, ``cols.keys()``."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _forks_the_matcher(fn: ast.AST, params: set[str]) -> bool:
    """True if ``fn`` contains a ``_pick``-shaped column match (see the note above)."""
    hit = False

    def walk(node: ast.AST, depth: int, bound: dict[str, str | None]) -> None:
        nonlocal hit
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Compare) and any(
                isinstance(op, (ast.In, ast.NotIn)) for op in child.ops
            ):
                operands = [child.left, *child.comparators]
                names = [o.id for o in operands if isinstance(o, ast.Name)]
                if (depth >= 2 and len(names) == len(operands) >= 2
                        and all(n in bound for n in names)
                        and any(bound[n] in params for n in names)):
                    hit = True
            if isinstance(child, ast.For):
                walk(child, depth + 1,
                     {**bound, **dict.fromkeys(_target_names(child.target), _iter_root(child.iter))})
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                inner = dict(bound)
                for gen in child.generators:
                    inner.update(dict.fromkeys(_target_names(gen.target), _iter_root(gen.iter)))
                walk(child, depth + len(child.generators), inner)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # a nested def is scored on its own
            else:
                walk(child, depth, bound)

    walk(fn, 0, {})
    return hit


def _forked_matchers(path: Path) -> list[str]:
    """Names of ``_pick``-shaped column matchers defined in ``path`` (see the note above)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
        if len(params) >= 2 and _forks_the_matcher(node, params):
            out.append(node.name)
    return out


# The three spellings of the deleted fork, verbatim + the two rewrites a re-fork would most plausibly
# reach for. A guard that has never been shown to go red is not a ratchet, so the detector is proven
# against them here rather than by a one-off manual check.
_REFORK_SPELLINGS = (
    "nested for",
    """
def _pick(cols, synonyms):
    for syn in synonyms:
        for low, orig in cols.items():
            if syn in low:
                return orig
    return None
""",
    "for + genexp",
    """
def _pick(cols, synonyms):
    for syn in synonyms:
        hit = next((orig for low, orig in cols.items() if syn in low), None)
        if hit is not None:
            return hit
    return None
""",
    "one comprehension, two for clauses",
    """
def _pick(cols, synonyms):
    return next((orig for syn in synonyms for low, orig in cols.items() if syn in low), None)
""",
)


def test_the_refork_detector_actually_fires():
    for label, src in zip(_REFORK_SPELLINGS[::2], _REFORK_SPELLINGS[1::2]):
        fn = ast.parse(src).body[0]
        params = {a.arg for a in fn.args.args}
        assert _forks_the_matcher(fn, params), f"the detector no longer catches a re-fork ({label})"


def test_the_refork_detector_leaves_ordinary_skill_code_alone():
    # The shapes that made a naive "nested iteration + membership test" scan unusable: one operand is
    # not an iteration target, or neither iteration reads a parameter.
    quiet = """
def upset_spec(intersections, sets):
    pos = {s: i for i, s in enumerate(sets)}
    for cid, it in zip(sets, intersections):
        for m in it["members"]:
            if m in pos:
                yield cid, m

def _two_group_columns(columns, design):
    for col in columns:
        for s in [str(c) for c in columns]:
            if s in design.index:
                return col
    return None
"""
    tree = ast.parse(quiet)
    for fn in tree.body:
        params = {a.arg for a in fn.args.args}
        assert not _forks_the_matcher(fn, params), f"{fn.name} must not be flagged"


def test_no_runner_re_forks_the_column_matcher():
    root = _backend_root()
    offenders: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root / SKILLS_REL):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            offenders += [f"{rel}::{fn}" for fn in _forked_matchers(path)]

    assert not offenders, (
        "A column matcher has re-forked under skills/** — the failure mode A19 named (one shared "
        "vocabulary, six forked matchers, every vocabulary guard still green):\n  "
        + "\n  ".join(sorted(offenders))
        + "\n\nResolve through the one resolver instead:\n"
        "  from engine.columns import normalize, resolve\n"
        "  col = resolve('gene' | 'logFC' | 'pval', df.columns, params.get('_column_override'))\n"
    )


# --- 2. no second copy forks (AST scan) ---------------------------------------------------

def test_no_unexpected_synonym_set_fork():
    root = _backend_root()
    found = _scan_for_forks(root)

    # the primitive is the one engine-side definition and must be detected (sanity: the scan works).
    assert PRIMITIVE_REL in found, (
        f"{PRIMITIVE_REL} should hold the synonym vocabulary; the scan found: {sorted(found)}"
    )

    allowed = KNOWN_OUT_OF_LANE_FORKS | {PRIMITIVE_REL}
    unexpected = found - allowed
    assert not unexpected, (
        "A second copy of the DE/metabolomics column vocabulary has forked in:\n  "
        + "\n  ".join(sorted(unexpected))
        + "\n\nImport the shared primitive instead:\n"
        "  from engine.vocab import DE_LOGFC_SYNONYMS, DE_PVAL_SYNONYMS, METABOLOMICS_TOKENS\n"
        "(If this is an intentional, coordinated out-of-lane fork, add it to "
        "KNOWN_OUT_OF_LANE_FORKS with a note.)"
    )


def test_known_forks_are_still_forks_not_stale():
    # Keep the allow-list honest: an entry that no longer forks (already converged) should be pruned
    # so the list documents *real* debt. A converged fork failing here is a welcome signal to update
    # this guard — not a spine regression.
    root = _backend_root()
    stale = sorted(
        rel for rel in KNOWN_OUT_OF_LANE_FORKS
        if not (root / rel).exists() or not _defines_a_synonym_set(root / rel)
    )
    assert not stale, (
        "These allow-listed forks no longer carry a synonym-set copy (converged or moved) — "
        "remove them from KNOWN_OUT_OF_LANE_FORKS:\n  " + "\n  ".join(stale)
    )

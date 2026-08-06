"""The RUNNER ↔ ``skill.json`` param-declaration guard — the ninth layer of shipped-≠-reachable.

``test_methods_param_spec_guard.py`` compares a skill's declared ``param_spec`` against the *prose*
that describes it. This one compares it against the **runner that executes it**, in both directions:

* a param the runner READS but the ``skill.json`` never declares, and
* a param the ``skill.json`` declares but no runner ever reads.

The first is invisible to every other guard **by construction**, which is why it needed its own.
``skills.contract._execute`` merges unknown caller keys straight through (``contract.py:78,90``),
``validate_param_ranges`` skips any key absent from ``param_spec`` (``:164-166``), and
``resolved_params`` passes them into the **recorded provenance bundle** (``:210-212``). So an
undeclared param works, changes the figure, and is written into the reproducibility record — while
``API_ONLY_KNOBS``, the prose↔param guard and ``paramFieldsFromSpec`` all START from the declaration
and therefore cannot see it. It is not range-checked, not type-cast, not controllable, not
describable, and a reader of the recorded bundle has no spec to interpret it against.

The second direction is the mirror defect: a declared knob renders a control, is offered to the
user, and is read by nothing — the user turns it and the figure does not move.

⚑ **The dict is resolved by BINDING, never by the variable being spelled ``params``.** A first probe
that matched on the name reported 13 hits and 3 were false positives — it caught ``pathway``'s
Reactome loop variable (``p["stId"]``), which is a REST response, not config. So the walk seeds at
the skill's declared entrypoint, binds the dict to that function's own argument name, and re-binds at
every hop (positional slot or keyword) into the callee's own name for it.

**There is deliberately no waiver list.** The first red run was four params across two skills
(``confusion.x``/``.y`` — undocumented aliases, deleted; ``erg_bwave_bar.vline``/``.vline_label`` —
a live styling knob, declared), and both directions were cleared to zero in the same change. A
waiver would be a place for the fifth to hide. If one is ever genuinely owed, that is a decision to
argue for in review, not an entry to add.
"""

from __future__ import annotations

import ast
import functools
import pathlib

import pytest

from skills.contract import PROPRIETARY_DIR, SKILLS_DIR, load_skill
from skills.registry import list_skill_ids

# `skills` is a namespace package (no __init__.py), so its `__file__` is None — the loader's own
# resolved paths are the honest source for both roots.
_SKILLS_DIR = SKILLS_DIR


def _module_funcs(path: pathlib.Path) -> tuple[dict[str, ast.FunctionDef],
                                               dict[str, tuple[str, str]]]:
    """One module → (its functions by name, its ``from skills.… import x as y`` aliases).

    The aliases are what make ``from skills.confusion.run_real import run as run_real`` resolvable:
    every skill's entrypoint dispatches stub-vs-real through exactly that shape, so without them the
    walk would stop at the front door of every real engine."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    funcs = {n.name: n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "skills" and len(parts) >= 2:
                for a in node.names:
                    aliases[a.asname or a.name] = (parts[-1], a.name)
    return funcs, aliases


@functools.lru_cache(maxsize=None)
def _shared_modules() -> dict[str, tuple[dict, dict]]:
    """The leaf modules every skill shares (``_charts`` · ``_stats`` · ``_design`` · …). Included in
    the pool because a runner that hands its params dict to one of them (``_design.load_design``)
    would otherwise be a hole the guard cannot see through — and a hole is indistinguishable from a
    clean bill of health."""
    return {p.stem: _module_funcs(p) for p in sorted(_SKILLS_DIR.glob("*.py"))}


class _Pool:
    """Every function reachable from one skill's runner, by (module stem, name)."""

    def __init__(self, skill_dir: pathlib.Path):
        self._mods = dict(_shared_modules())
        for path in sorted(skill_dir.glob("*.py")):   # the skill's own modules win on a clash
            self._mods[path.stem] = _module_funcs(path)

    def func(self, mod: str, name: str) -> ast.FunctionDef | None:
        return self._mods.get(mod, ({}, {}))[0].get(name)

    def resolve(self, mod: str, name: str) -> tuple[str, ast.FunctionDef] | None:
        """A called name, from inside ``mod`` → the function it runs. Import alias first (the
        stub/real dispatch renames), then the calling module's own defs."""
        target = self._mods.get(mod, ({}, {}))[1].get(name)
        if target is not None:
            fn = self.func(*target)
            if fn is not None:
                return target[0], fn
        fn = self.func(mod, name)
        return (mod, fn) if fn is not None else None


def _is_params(node: ast.AST, name: str) -> bool:
    """Is this expression the params dict? The bound name, or the ``(params or {})`` idiom three
    runners use (``composition``/``enrichment``/``scorecard``) — which a Name-only reader misses,
    and would then report the key it guards as an undeclared read's opposite: a declared-but-dead
    knob that is in fact live."""
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        return any(_is_params(v, name) for v in node.values)
    return False


def _rebind(callee: ast.FunctionDef, call: ast.Call, name: str) -> str | None:
    """The callee's OWN name for the params dict, if this call passes it — positionally or by
    keyword. ``None`` = this call does not hand the dict on."""
    positional = [a.arg for a in callee.args.posonlyargs] + [a.arg for a in callee.args.args]
    for i, arg in enumerate(call.args):
        if _is_params(arg, name) and i < len(positional):
            return positional[i]
    accepted = set(positional) | {a.arg for a in callee.args.kwonlyargs}
    for kw in call.keywords:
        if kw.arg and kw.arg in accepted and _is_params(kw.value, name):
            return kw.arg
    return None


def _walk(pool: _Pool, mod: str, func: ast.FunctionDef, name: str,
          seen: frozenset, unresolved: list[str]) -> set[str]:
    """Every string key read off the params dict inside ``func`` — and, transitively, inside every
    function ``func`` hands the dict to. Anything it hands the dict to and CANNOT follow is recorded
    in ``unresolved`` rather than dropped, because a silent miss reads as 'nothing undeclared'."""
    keys: set[str] = set()
    for node in ast.walk(func):
        if (isinstance(node, ast.Subscript) and _is_params(node.value, name)
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
            keys.add(node.slice.value)                                   # params['k']
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get", "pop", "setdefault"}
                and _is_params(node.func.value, name) and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            keys.add(node.args[0].value)                                 # params.get('k', …)
        elif (isinstance(node, ast.Compare) and len(node.ops) == 1
                and isinstance(node.ops[0], (ast.In, ast.NotIn))
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
                and _is_params(node.comparators[0], name)):
            keys.add(node.left.value)                                    # 'k' in params

        if not isinstance(node, ast.Call):
            continue
        hands_it_on = (any(_is_params(a, name) for a in node.args)
                       or any(_is_params(kw.value, name) for kw in node.keywords))
        if not hands_it_on:
            continue
        where = f"{mod}.{func.name}:{node.lineno}"
        if not isinstance(node.func, ast.Name):
            unresolved.append(f"{where} -> {ast.unparse(node.func)}()")
            continue
        hit = pool.resolve(mod, node.func.id)
        if hit is None:
            unresolved.append(f"{where} -> {node.func.id}()")
            continue
        callee_mod, callee = hit
        if (callee_mod, callee.name) in seen:
            continue
        bound = _rebind(callee, node, name)
        if bound is None:                       # **splat, or a slot the signature has no name for
            unresolved.append(f"{where} -> {node.func.id}(**…)")
            continue
        keys |= _walk(pool, callee_mod, callee, bound,
                      seen | {(callee_mod, callee.name)}, unresolved)
    return keys


def _skill_dir(skill_id: str) -> pathlib.Path:
    flat = _SKILLS_DIR / skill_id
    return flat if (flat / "skill.json").exists() else PROPRIETARY_DIR / skill_id


@functools.lru_cache(maxsize=None)
def _refs(skill_id: str) -> tuple[frozenset[str], tuple[str, ...]]:
    """(keys the runner reads, calls that hand the dict somewhere unfollowable) for one skill."""
    spec = load_skill(skill_id)
    module, entry = spec.entrypoint.split(":")
    mod = module.split(".")[-1]
    pool = _Pool(_skill_dir(skill_id))
    func = pool.func(mod, entry)
    assert func is not None, f"{skill_id}: entrypoint {spec.entrypoint!r} resolves to no function"
    names = [a.arg for a in func.args.args]
    assert "params" in names, (
        f"{skill_id}: entrypoint {spec.entrypoint!r} takes {names} — the contract calls every "
        f"runner as run(data_path=…, params=…), so a runner without a `params` argument means the "
        f"contract changed and this guard is now binding to the wrong thing."
    )
    unresolved: list[str] = []
    keys = _walk(pool, mod, func, "params", frozenset({(mod, entry)}), unresolved)
    return frozenset(keys), tuple(sorted(set(unresolved)))


def runner_param_refs(skill_id: str) -> set[str]:
    return set(_refs(skill_id)[0])


_SKILL_IDS = sorted(list_skill_ids())


@pytest.mark.parametrize("skill_id", _SKILL_IDS)
def test_runner_reads_only_declared_params(skill_id):
    """A param the runner reads must be declared. An undeclared one changes the figure, reaches the
    provenance bundle, and is invisible to every declaration-driven surface — so it is a knob that
    exists for whoever read the source and for nobody else."""
    declared = set(load_skill(skill_id).param_spec)
    # `_`-prefixed keys are reserved runtime injections (`_design_path`, `_column_override`), not
    # user config: `resolved_params` strips them from the recorded bundle by design, and they have no
    # param_spec entry on purpose — the same carve-out the prose guard makes.
    undeclared = sorted(k for k in runner_param_refs(skill_id)
                        if k not in declared and not k.startswith("_"))
    assert not undeclared, (
        f"{skill_id}'s runner reads param(s) {undeclared} that its skill.json never declares. "
        f"Either DECLARE them (they change the figure — give them a param_spec entry, a control and "
        f"a methods sentence) or DELETE the read (an undocumented alias for a declared key). "
        f"Declared: {sorted(declared)}."
    )


@pytest.mark.parametrize("skill_id", _SKILL_IDS)
def test_every_declared_param_is_read_by_the_runner(skill_id):
    """The mirror: a declared param no runner reads renders a control that does nothing. The user
    turns it, the figure does not move, and the recorded bundle claims it was configuration."""
    declared = set(load_skill(skill_id).param_spec)
    dead = sorted(declared - runner_param_refs(skill_id))
    assert not dead, (
        f"{skill_id} declares param(s) {dead} that no runner reads — a control the user can set "
        f"that changes nothing. Wire them, or remove them from skills/**/{skill_id}/skill.json. "
        f"(If the read is real but routed somewhere this walk cannot follow, the blind-spot guard "
        f"below should have failed first — fix that instead of waiving this.)"
    )


@pytest.mark.parametrize("skill_id", _SKILL_IDS)
def test_no_runner_hands_its_params_somewhere_unfollowable(skill_id):
    """Guard the guard, and the load-bearing one. Both assertions above are only as strong as the
    walk: move a ``params.get`` into a helper this cannot resolve and the undeclared key vanishes
    from the first test while the declared one turns up 'dead' in the second. So a params dict handed
    to something unresolvable is a FAILURE, not a quiet gap."""
    _refs_, unresolved = _refs(skill_id)
    assert not unresolved, (
        f"{skill_id} hands its params dict to something this guard cannot follow: {list(unresolved)}. "
        f"Every key read behind that call is unchecked. Keep the helper in the skill's own package or "
        f"in skills/*.py (both are in the pool), pass the dict by name rather than **splatting it, or "
        f"teach the walk that shape — do not leave it unresolved."
    )


def test_the_walk_is_not_vacuous():
    """A reader that extracted nothing would pass every assertion above. These four pin the hops
    that make the walk non-trivial — each one was a real miss in an earlier draft."""
    # keyword dispatch across modules: run.py -> `run_real(data_path=…, params=params)`, then a
    # positional hop into `_confusion(frame, params, source)`.
    assert {"true", "predicted", "normalize"} <= runner_param_refs("confusion")
    # the `(params or {}).get("order")` idiom, reached by a 6th-positional hop from run_real.
    assert "order" in runner_param_refs("composition")
    # out of the skill's own package into a SHARED leaf module (skills/_design.py::load_design).
    assert "_design_path" in runner_param_refs("deg")
    # the proprietary namespace, and a styling knob two hops deep (run_real -> bar_spec).
    assert {"wave", "hline", "vline"} <= runner_param_refs("erg_bwave_bar")


def test_every_shipped_skill_is_checked():
    """The parametrization reads the live registry; if that ever narrows, this guard would go quiet
    on the skills it stopped naming while still reporting green for the ones it kept."""
    assert len(_SKILL_IDS) >= 44, f"only {len(_SKILL_IDS)} skills enumerated — the registry shrank?"
    assert len(_SKILL_IDS) == len(set(_SKILL_IDS))

"""Enforce backend structure conventions (repo-structure plan §1.4) in the fast gate.

Chat memory and docs rot; a convention only holds if a check fails when it drifts. These
guards backstop the rules in CLAUDE.md / docs/repo-structure/plan.md so re-introducing a
flat handler or a flat domain module fails CI/local before it lands.
"""

import os
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# App-config env is read through config.Settings ONLY (single-env-reader ratchet, M-002). These
# files may read os.environ/os.getenv directly because they are genuinely environmental (runtime
# execution-env probes) or write a per-run override — not app config:
_ENV_READER_ALLOWLIST = frozenset({
    "config.py",                       # THE single typed home (Settings + the live accessors)
    "db/engine.py",                    # AWS_LAMBDA_FUNCTION_NAME — runtime execution-env probe
    "oracle.py",                       # LOCALAPPDATA — Windows environment probe
    "reproduction/papers/hani.py",     # WRITES SELOM_UMAP_ENGINE as a per-reproduction override
    "reproduction/papers/dorgau.py",   # WRITES SELOM_UMAP_ENGINE as a per-reproduction override
})
# Dirs the env scan prunes (third-party / generated code reads os.environ freely and is not ours).
_ENV_SCAN_SKIP_DIRS = frozenset({
    ".venv", "venv", "__pycache__", "node_modules", "data", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "graphify-out", ".git", "build", "dist",
})
# Routers stay thin over the engine facade: a router may import only these engine.* submodules
# (import boundary, M-002). Reaching into any other engine internal fails the guard.
_ROUTER_ENGINE_ALLOWLIST = frozenset({"compat", "match", "recommend"})


def test_main_has_no_app_route_decorators():
    """Route handlers must live in routers/ (plan §1.1), not main.py."""
    import re

    main_src = (BACKEND / "main.py").read_text(encoding="utf-8")
    matches = re.compile(r"@app\.(get|post|put|patch|delete)\b").findall(main_src)
    assert not matches, (
        f"main.py contains {len(matches)} @app.<method> decorator(s): {matches}. "
        "Route handlers must live in routers/, not main.py."
    )


def test_no_flat_reproduction_modules():
    """The reproduction engine is a package (plan §3A) — no flat reproduction_*.py at root.

    New engine modules go in reproduction/ (per-paper ledgers in reproduction/papers/).
    repro_assets.py and skill_gaps.py stay flat by design and don't match this glob.
    """
    strays = sorted(p.name for p in BACKEND.glob("reproduction_*.py"))
    assert not strays, (
        f"flat reproduction_*.py at the backend root: {strays}. The reproduction engine is "
        "a package — add new modules under reproduction/ (reproduction/papers/ for per-paper "
        "ledgers) and import via the dotted path. See docs/repo-structure/plan.md §3A."
    )


def test_companion_builders_live_in_package():
    """The figure-companion builders live in companions/ (plan §3B), not flat at root."""
    strays = sorted(
        name
        for name in ("methods.py", "legends.py", "provenance.py", "guardrails.py")
        if (BACKEND / name).is_file()
    )
    assert not strays, (
        f"companion builder(s) flat at the backend root: {strays}. methods/legends/provenance/"
        "guardrails belong in companions/ (import via `from companions import X`). "
        "See docs/repo-structure/plan.md §3B."
    )


def test_ai_reuses_core_validation():
    """ai/ must import validate_param_ranges from skills.contract — no parallel validation path.

    The AI action gateway must validate through the exact same function that the HTTP layer
    uses (``routers/_run.py``).  A duplicate implementation in ai/ would allow AI-proposed
    params to pass checks that human-submitted params would fail, violating Requirement 3.
    If this guard fails, ai/registry.py or ai/execute.py has reimplemented validation
    instead of delegating to skills.contract.validate_param_ranges.
    """
    found = False
    for src_file in ("ai/registry.py", "ai/execute.py"):
        src = (BACKEND / src_file).read_text(encoding="utf-8")
        if "validate_param_ranges" in src:
            found = True
            break
    assert found, (
        "Neither ai/registry.py nor ai/execute.py references validate_param_ranges. "
        "AI validation must reuse skills.contract.validate_param_ranges — no parallel path. "
        "See spec.md Invariant 'Validation reuse'."
    )


def test_ai_live_package_structure():
    """ai/live/ must exist and contain pydantic_gateway.py without re-implementing validation.

    The live gateway is a structured-output *translator* only — it maps NL goal +
    context into an ActionPlan.  Validation lives exclusively in ai/execute.py and
    ai/registry.py (the existing structure guard already asserts this for those files).
    The live gateway must not add a third path.
    """
    live_dir = BACKEND / "ai" / "live"
    assert live_dir.is_dir(), (
        "ai/live/ directory must exist (Slice 2). "
        "Create it with ai/live/__init__.py + ai/live/pydantic_gateway.py."
    )
    assert (live_dir / "pydantic_gateway.py").is_file(), (
        "ai/live/pydantic_gateway.py must exist (PydanticAIGateway, Slice 2)."
    )
    gw_src = (live_dir / "pydantic_gateway.py").read_text(encoding="utf-8")
    assert "validate_param_ranges" not in gw_src, (
        "ai/live/pydantic_gateway.py must not reimplement validation. "
        "The live gateway is a structured-output translator only; "
        "validate_param_ranges is called by ai/registry.py via ai/execute.py."
    )


def test_ai_apply_router_uses_execute_skill_run():
    """POST /ai/apply must route through _execute_skill_run — no second gated path.

    Inspection: routers/ai.py must import and call _execute_skill_run (the shared
    human run body) so AI-assisted runs go through the exact same QC / D1 / D2
    gates as human runs.  A separate AI execution path would violate the
    'same gateway as humans' invariant (spec invariant 3).
    """
    ai_router_src = (BACKEND / "routers" / "ai.py").read_text(encoding="utf-8")
    assert "_execute_skill_run" in ai_router_src, (
        "routers/ai.py must call _execute_skill_run for POST /ai/apply. "
        "AI-assisted runs must use the same gated body as human runs."
    )


def test_ai_apply_stamps_provenance_through_the_chokepoint():
    """POST /ai/apply must stamp AI attribution through the ONE server chokepoint — no parallel path.

    The figure's provenance.actions[] is the integrity boundary of the AI write-path: a forgeable
    actor/model/approved_by tag silently lies about who authored a figure. So /ai/apply must route the
    posted delta through provenance.stamp_ai_actions (which re-derives actor/model/approved_by/approved_at
    server-side) and hand the run path ONLY the stamped list — never the raw client actions. A future
    edit that feeds _execute_skill_run the unstamped list would re-open the forgery hole; this fails it.
    See docs/provenance-chokepoint/spec.md, [[selom-provenance-stamping-chokepoint]].
    """
    ai_router_src = (BACKEND / "routers" / "ai.py").read_text(encoding="utf-8")
    assert "provenance.stamp_ai_actions(" in ai_router_src, (
        "routers/ai.py must derive provenance attribution via provenance.stamp_ai_actions "
        "(the one server-controlled chokepoint), not trust caller-supplied stamps."
    )
    assert "ai_actions=trusted_actions" in ai_router_src, (
        "routers/ai.py must pass the STAMPED list (trusted_actions) to _execute_skill_run."
    )
    assert "ai_actions=actions_list" not in ai_router_src, (
        "routers/ai.py must NOT hand the raw client actions_list to _execute_skill_run — that bypasses "
        "the stamping chokepoint and re-opens the attribution-forgery hole."
    )
    # No parallel path: routers/ai.py is the ONLY router that feeds _execute_skill_run an ai_actions list.
    for path in (BACKEND / "routers").glob("*.py"):
        if path.name == "ai.py":
            continue
        assert "ai_actions=" not in path.read_text(encoding="utf-8"), (
            f"routers/{path.name} passes ai_actions to the run path — AI provenance must be stamped "
            "only via routers/ai.py → provenance.stamp_ai_actions (no parallel write path)."
        )
    # The in-process variant (ai/execute.py commit_recompute, used by the AI-compiles-away tests) must
    # stamp through the SAME chokepoint — not merge approved_by into a raw actions dict (gauntlet
    # spine-consistency, 2026-06-30).
    exec_src = (BACKEND / "ai" / "execute.py").read_text(encoding="utf-8")
    assert "stamp_ai_actions" in exec_src, (
        "ai/execute.py (commit_recompute) must stamp attribution via provenance.stamp_ai_actions, "
        "not build a parallel actions record."
    )


def test_ai_action_registry_matches_action_types():
    """ACTION_REGISTRY keys, ACTION_TYPES tuple, and ActionType Literal must be identical.

    All three declarations live in different files but describe the same closed set.
    This guard catches the common mistake of adding a new action type to only one of the
    three places — which would let the Literal parse it, but the registry never execute it
    (or vice-versa).  Completeness + disjointness both checked, mirroring the
    skill-table-contract guard pattern.
    """
    from typing import get_args

    from ai import models, registry

    registry_keys = set(registry.ACTION_REGISTRY)
    types_tuple = set(models.ACTION_TYPES)
    literal_members = set(get_args(models.ActionType))

    assert registry_keys == types_tuple, (
        f"ACTION_REGISTRY keys {sorted(registry_keys)} don't match ACTION_TYPES tuple "
        f"{sorted(types_tuple)}.  Add/remove from both in the same commit."
    )
    assert types_tuple == literal_members, (
        f"ACTION_TYPES tuple {sorted(types_tuple)} doesn't match ActionType Literal members "
        f"{sorted(literal_members)}.  Keep models.ACTION_TYPES and models.ActionType in sync."
    )


def _iter_backend_py():
    """Every backend .py, pruning third-party/generated trees (so the scan is our code only)."""
    for dirpath, dirnames, filenames in os.walk(BACKEND):
        dirnames[:] = [d for d in dirnames if d not in _ENV_SCAN_SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield pathlib.Path(dirpath) / fn


def test_single_env_reader():
    """App-config env is read through config.Settings, not scattered os.environ/os.getenv reads.

    A renamed or duplicated env key silently diverges when reads are scattered across modules;
    routing them through the ONE typed home (config.Settings' fields + its live accessors) makes the
    selector set a single reviewable surface — the seam parallel lanes depend on. tests/ (setup /
    monkeypatch) and the explicit allowlist (genuine runtime env probes + the per-run
    SELOM_UMAP_ENGINE writers) are exempt. See docs/eng-practices-port/plan.md M-002 +
    docs/hardening-port/gate-ledger.md.
    """
    import re

    pat = re.compile(r"\bos\.(?:environ|getenv)\b")
    offenders = []
    for p in _iter_backend_py():
        rel = p.relative_to(BACKEND).as_posix()
        if rel in _ENV_READER_ALLOWLIST or rel.startswith("tests/"):
            continue
        if pat.search(p.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert not offenders, (
        f"os.environ/os.getenv read outside config.Settings: {sorted(offenders)}. Route app-config "
        "env through config.Settings (add a typed field or a live accessor in config.py); only a "
        "genuine runtime env probe / per-run override belongs in _ENV_READER_ALLOWLIST (add it on "
        "purpose). See docs/eng-practices-port/plan.md M-002."
    )


def test_routers_import_only_allowlisted_engine_facade():
    """routers/ import only an explicit set of engine.* facade modules (import boundary, M-002).

    Routers are the thin HTTP layer; reaching directly into a new engine internal couples the API to
    engine implementation and is exactly the seam a frozen contract must protect. A new
    engine.<module> import in a router fails here until _ROUTER_ENGINE_ALLOWLIST is extended on
    purpose. See docs/eng-practices-port/plan.md M-002.
    """
    import re

    # Anchored to line-start so a prose mention of "engine.x" never counts — only real imports.
    pat = re.compile(r"^\s*(?:from|import)\s+engine\.([A-Za-z_]\w*)", re.MULTILINE)
    offenders: dict[str, set[str]] = {}
    for p in sorted((BACKEND / "routers").glob("*.py")):
        for mod in pat.findall(p.read_text(encoding="utf-8")):
            if mod not in _ROUTER_ENGINE_ALLOWLIST:
                offenders.setdefault(p.name, set()).add(mod)
    assert not offenders, (
        f"router(s) import non-allowlisted engine internals: "
        f"{ {k: sorted(v) for k, v in offenders.items()} }. Routers are the thin HTTP layer — route "
        "through the service/facade layer, or extend _ROUTER_ENGINE_ALLOWLIST deliberately. "
        "See docs/eng-practices-port/plan.md M-002."
    )

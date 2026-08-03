"""The skill-coverage ratchet — "are all the skills working?" stays answered.

Two tiers, deliberately:

**Fast (runs in CI, no corpus needed).** The structural guarantees that make the published matrix
trustworthy — every registered skill has a declared case, every skip carries a reason, the committed
matrix covers exactly the live roster, and every real engine still IMPORTS. These are what catch the
silent-drop failure mode: a new skill added with no case, or a case quietly downgraded to a skip, is
a red test rather than a matrix that just gets smaller.

**Slow (`pytest -m slow`, needs SELOM_DATASETS_DIR).** The live matrix: every skill through its real
engine on real data, asserting nothing that the committed matrix records as passing has regressed.
This is the same check `scripts/skill-smoke.sh` gates on; CI's fast gate does not run it (CI is
`pytest -m "not slow"` with no corpus), so the shell script is the enforcement point at a milestone
and this is the enforcement point for anyone running the full suite.

Regenerate the matrix after an intentional change: `scripts/skill-smoke.sh --write`.
"""

import importlib

import pytest

from skills import smoke

# --------------------------------------------------------------- fast: structural guarantees


def test_every_registered_skill_has_a_case():
    """No silent drops. The roster comes from the registry, so a new skill dir fails here until
    it is either smoked or explicitly skipped with a reason."""
    missing = [sid for sid in smoke.skill_ids() if sid not in smoke.CASES]
    assert not missing, (
        f"skills with no smoke case: {missing}. Add a smoke.Case (preferred) or a smoke.Skip with "
        f"a reason to skills/smoke.py — a skill with no row reads as covered when it is not."
    )


def test_no_case_for_a_skill_that_no_longer_exists():
    roster = set(smoke.skill_ids())
    stale = [sid for sid in smoke.CASES if sid not in roster]
    assert not stale, f"smoke cases for unregistered skills: {stale}"


def test_every_skip_carries_a_reason():
    """A silent skip reads as a pass. A skip must say what is missing and what would unblock it."""
    for sid, entry in smoke.CASES.items():
        if isinstance(entry, smoke.Skip):
            assert len(entry.reason.strip()) > 40, f"{sid}: skip reason is too thin to act on"


def test_every_case_names_a_dataset_and_explains_itself():
    for sid, entry in smoke.CASES.items():
        if isinstance(entry, smoke.Case):
            assert entry.dataset.strip(), f"{sid}: case has no dataset"
            assert entry.note.strip(), f"{sid}: case has no note saying why this input is honest"


def test_committed_matrix_matches_the_live_roster():
    """The published matrix is the artefact people read. It must cover the roster exactly — a stale
    row (deleted skill) or a missing row (new skill) both mean the doc is lying."""
    matrix = smoke.load_matrix()
    assert matrix, "docs/skill-coverage/matrix.json is missing — run scripts/skill-smoke.sh --write"
    assert set(matrix) == set(smoke.skill_ids()), (
        "committed matrix is out of sync with the registry; regenerate with "
        "`scripts/skill-smoke.sh --write`"
    )


def test_a_committed_pass_is_not_silently_downgraded_to_a_skip():
    """Deleting a case for a skill the matrix records as PASSING would make the gate green while
    coverage fell. Recording it as a Skip instead is the same move by another name."""
    for sid, row in smoke.load_matrix().items():
        if row["status"] == smoke.PASS:
            assert isinstance(smoke.CASES.get(sid), smoke.Case), (
                f"{sid} passes in the committed matrix but no longer has a runnable case"
            )


def test_every_real_engine_imports():
    """Import every skill's real-engine module. The golden tests pin the STUBS (they run with
    `SELOM_SKILLS_ENGINE=stub`), so nothing in the fast gate otherwise touches a `run_real` at all —
    a syntax or import error in one would ship green. Heavy scientific imports are lazy inside
    `run()`, so this stays cheap."""
    broken = []
    for sid in smoke.skill_ids():
        spec = importlib.import_module("skills.contract").load_skill(sid)
        base = spec.entrypoint.split(":")[0].rsplit(".", 1)[0]   # skills.<ns>.<id>
        for engine_mod in (f"{base}.run_real", f"{base}.run_scanpy"):
            try:
                importlib.import_module(engine_mod)
                break
            except ModuleNotFoundError as exc:
                if exc.name != engine_mod:
                    broken.append(f"{sid}: {engine_mod} -> {exc}")   # a real missing dependency
                    break
            except Exception as exc:  # noqa: BLE001 — any import-time error is the finding
                broken.append(f"{sid}: {engine_mod} -> {type(exc).__name__}: {exc}")
                break
        else:
            broken.append(f"{sid}: no real-engine module (run_real.py / run_scanpy.py) found")
    assert not broken, "real engines that do not import: " + "; ".join(broken)


def test_stub_output_is_treated_as_a_failure():
    """The honesty check itself, checked. A figure that is really a stub must never score a pass —
    this is the fake-science landmine (RISKS #11) the matrix exists to keep shut."""
    stub = {"data": [{"x": [1], "y": [2]}], "layout": {"title": {"text": "Volcano (stub)"}}}
    assert "STUB" in smoke.check_figure(stub)
    real = {"data": [{"x": [1], "y": [2]}], "layout": {"title": {"text": "Volcano"}}}
    assert smoke.check_figure(real) == ""
    assert "empty" in smoke.check_figure({"data": [], "layout": {}})


def test_a_removed_plotly_key_is_a_failure():
    """The no-op-encoding check, checked — the sibling of the numeric-string-axis invariant.

    A trace carrying a key Plotly has REMOVED is valid JSON and renders without error; it just
    silently ignores the instruction. `regression` shipped `transforms: [{type: groupby}]` for
    exactly this reason and drew every point in one colour while advertising a `group` knob.
    plotly.py 6 refuses the key, but the skills return raw dicts, so nothing was checking.
    """
    bad = {"data": [{"x": [1], "y": [2],
                     "transforms": [{"type": "groupby", "groups": ["a"]}]}],
           "layout": {"title": {"text": "Scatter"}}}
    problem = smoke.check_figure(bad)
    assert "transforms" in problem and "trace[0]" in problem
    # and the fixed shape — one trace per group — passes
    ok = {"data": [{"x": [1], "y": [2], "name": "a"}, {"x": [3], "y": [4], "name": "b"}],
          "layout": {"title": {"text": "Scatter"}}}
    assert smoke.check_figure(ok) == ""


# --------------------------------------------------------------- slow: the live matrix


@pytest.mark.slow
def test_live_matrix_has_not_regressed(monkeypatch):
    """Run every skill's real engine on real data and compare against the committed matrix.

    Skipped without the corpus rather than passed: a matrix whose rows all say "not run" is not
    evidence, and reporting it as green is precisely the lie this file exists to prevent.
    """
    if smoke._corpus() is None:
        pytest.skip("SELOM_DATASETS_DIR unset — the live matrix needs the real corpus")
    for key, value in smoke.REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    problems = smoke.regressions(smoke.run_matrix())
    assert not problems, "skill smoke regressions:\n  " + "\n  ".join(problems)


def test_pin_process_refuses_an_unpinned_run(monkeypatch):
    """The refusal itself, checked. Without the real-engine pin, `auto` can silently serve stub
    figures — so an unpinned smoke run must be a loud error, not a green matrix."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    with pytest.raises(RuntimeError, match="refuses to run unpinned"):
        smoke.pin_process()
